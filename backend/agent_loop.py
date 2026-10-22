"""
agent_loop.py
─────────────────────────────────────────────────────────────────────────────
Bounded Observe–Act–Evaluate (OAE) Agent Loop for ProbeQA.

WHY THIS EXISTS (Stage 5 Architecture):
  In Stage 4, the planner acted in an "open-loop": it generated an entire sequence
  of steps upfront before touching the browser, and then executed a hardcoded script.

  Stage 5 implements true closed-loop agentic behavior:
    1. OBSERVE: Extract a structured, sanitized snapshot of the live DOM state
       (URL, page title, visible text summary, approved element presence).
    2. DECIDE (ACT): The LLM analyzes the goal, the latest observation, and previous
       actions to select EXACTLY ONE next bounded action (or decides to STOP).
    3. VALIDATE: The action is validated against strict Pydantic schemas and our
       restricted tool registry. Unsafe actions, code injections, and external
       navigations are strictly blocked.
    4. EXECUTE: Playwright performs the single validated action.
    5. EVALUATE: Playwright captures a new observation and runs deterministic
       assertions to verify ground truth (the LLM never decides pass/fail alone).
    6. REPEAT: Iterates until the goal is satisfied, an unrecoverable failure occurs,
       or the safety iteration limit (default: 8) is reached.
"""

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urlparse

from dotenv import load_dotenv
import httpx
from playwright.async_api import (
    Page,
    async_playwright,
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError,
)
from pydantic import BaseModel, Field, model_validator, ValidationError as PydanticValidationError

from runner import (
    EVIDENCE_DIR,
    SAUCEDEMO_TARGET_URL,
    SAUCEDEMO_EXPECTED_HOST,
    SAUCEDEMO_EXPECTED_SCHEME,
    SAUCEDEMO_EXPECTED_PORTS,
    validate_saucedemo_origin,
)
from scenarios import APPROVED_ELEMENT_ALIASES
from metrics import (
    record_agent_run,
    record_recovery_attempt,
    record_llm_request,
    track_active_agent_run,
)

# Load backend/.env reliably
_dotenv_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_dotenv_path)

MAX_AGENT_ITERATIONS = 8
MAX_OBSERVATION_TEXT_LEN = 400
ACTION_TIMEOUT_MS = 10_000
MAX_RECOVERY_ATTEMPTS = 2
LLM_RETRY_LIMIT = 2
LLM_RETRY_BACKOFF_SECONDS = [1.0, 2.0]

# ── Structured Error Categories ───────────────────────────────────────────────

class ErrorCategory:
    """Standardized error categories for agent diagnosis and evaluation telemetry."""
    LLM_TRANSIENT_ERROR = "LLM_TRANSIENT_ERROR"          # 429 rate limit, 503 unavailable, network timeout
    LLM_FATAL_ERROR = "LLM_FATAL_ERROR"                  # 401/403 auth failure, unrecoverable schema error
    BROWSER_TIMEOUT = "BROWSER_TIMEOUT"                  # PlaywrightTimeoutError on navigation or locator
    MISSING_ELEMENT = "MISSING_ELEMENT"                  # Target selector alias not present in DOM
    REPETITION_DETECTED = "REPETITION_DETECTED"          # Unproductive repeated identical action
    SECURITY_VIOLATION = "SECURITY_VIOLATION"            # Target origin breach, selector injection, overflow
    ASSERTION_FAILURE = "ASSERTION_FAILURE"              # Ground-truth DOM assertion failed
    ITERATION_LIMIT_EXCEEDED = "ITERATION_LIMIT_EXCEEDED"# Reached max iterations without goal completion
    UNSUPPORTED_ACTION = "UNSUPPORTED_ACTION"            # Action type or target outside approved registry


# Approved credential presets for bounded testing (no arbitrary credential generation)
APPROVED_CREDENTIALS = {
    "standard_user": "standard_user",
    "locked_out_user": "locked_out_user",
    "invalid_user": "invalid_user_probeqa",
    "secret_sauce": "secret_sauce",
    "wrong_password": "wrong_password_123",
}

# ── Pydantic Schemas for Observe-Act-Evaluate Loop ─────────────────────────────

class BrowserObservation(BaseModel):
    """Structured perception of the browser state captured after each action."""
    current_url: str = Field(..., description="Current browser URL")
    page_title: str = Field(..., description="HTML document title")
    is_approved_origin: bool = Field(..., description="Whether current URL strictly matches SauceDemo origin")
    available_elements: Dict[str, bool] = Field(
        default_factory=dict,
        description="Map of approved element aliases and whether they currently exist in the DOM"
    )
    visible_text_summary: str = Field(..., description="Sanitized, truncated text content visible on the page")
    error_banner_text: Optional[str] = Field(default=None, description="Text inside error element if present")
    inventory_items_count: int = Field(default=0, description="Number of inventory items visible on page")


class AgentActionDecision(BaseModel):
    """Single-step action chosen by the LLM."""
    thought: str = Field(..., description="Chain-of-thought reasoning explaining why this action was chosen")
    action_type: Literal["navigate", "fill", "click", "assert", "stop"] = Field(
        ...,
        description="One of: navigate, fill, click, assert, stop"
    )
    target: Optional[str] = Field(
        default=None,
        description="Approved element alias, route, or target URL (must be SauceDemo), or null when action_type is stop"
    )
    value: Optional[str] = Field(
        default=None,
        description="Approved credential key or input text (e.g. 'locked_out_user', 'secret_sauce')"
    )
    stop_reason: Optional[str] = Field(
        default=None,
        description="Reason for stopping when action_type is 'stop'"
    )

    @model_validator(mode="after")
    def validate_target_for_non_stop(self):
        if self.action_type != "stop" and not self.target:
            raise ValueError(f"Target is required when action_type is '{self.action_type}'.")
        return self


class StepRecord(BaseModel):
    """Complete audit log for a single iteration in the agent loop."""
    iteration: int
    observation_before: BrowserObservation
    decision: AgentActionDecision
    action_result: str
    is_success: bool
    duration_ms: int


class AgentExecutionResult(BaseModel):
    """Final output of the bounded Observe-Act-Evaluate agent run."""
    run_id: str
    goal: str
    status: Literal["passed", "failed", "error"]
    task_success: bool = Field(default=False, description="Deterministic outcome: True if status == 'passed'")
    total_iterations: int
    steps: List[StepRecord]
    assertions_evaluated: List[str]
    deterministic_verdict: str
    screenshot_path: Optional[str] = None
    duration_ms: int
    provider: str
    model: str
    timestamp: str

    # Stage 6B Reliability & Evaluation Metrics
    recovery_attempts: int = Field(default=0, description="Count of recovery actions triggered")
    llm_errors_count: int = Field(default=0, description="Count of transient or non-transient LLM errors encountered")
    action_failures_count: int = Field(default=0, description="Count of browser action failures or missing elements")
    error_category: Optional[str] = Field(default=None, description="Classified error category if run failed or had errors")
    expected_assertion_passed: bool = Field(default=False, description="Whether deterministic assertion suite verified pass")


# ── System Prompt for Single-Step Decision Making ─────────────────────────────

AGENT_SYSTEM_PROMPT = """You are ProbeQA's Autonomous Browser QA Agent.
You operate inside a bounded Observe-Act-Evaluate control loop.
Your task is to achieve the user's browser testing goal by selecting EXACTLY ONE next action at a time.

ENVIRONMENT CONSTRAINTS:
- You are testing the public practice application at https://www.saucedemo.com/
- You may ONLY interact with approved element aliases:
    - 'username_input' (#user-name)
    - 'password_input' (#password)
    - 'login_button' (#login-button)
    - 'login_error' ([data-test="error"])
    - 'inventory_items' (.inventory_item)
- Approved action_types:
    - 'navigate': target must be 'https://www.saucedemo.com/'
    - 'fill': target must be 'username_input' or 'password_input'. Value must be a valid credential (e.g. 'standard_user', 'locked_out_user', 'invalid_user', 'secret_sauce', 'wrong_password')
    - 'click': target must be 'login_button'
    - 'assert': target must be 'login_error' or 'inventory_items'
    - 'stop': choose this when the goal has been achieved or cannot proceed.

RULES:
1. Always analyze the LATEST observation before deciding.
2. If the page is not yet loaded, navigate to 'https://www.saucedemo.com/'.
3. Once the goal is satisfied (e.g. error banner is visible for locked_out_user, or inventory is displayed for standard_user), choose action_type 'stop' with a clear stop_reason.
4. Output STRICT JSON conforming to the schema. Do not output markdown code blocks.
"""


# ── Browser Observation Extractor ─────────────────────────────────────────────

async def capture_observation(page: Page) -> BrowserObservation:
    """Extracts a structured, sanitized snapshot of the current page state."""
    current_url = page.url or ""
    page_title = await page.title() if current_url else ""

    # Origin check
    is_approved_origin = False
    try:
        validate_saucedemo_origin(current_url)
        is_approved_origin = True
    except Exception:
        is_approved_origin = False

    # Check presence of approved element aliases
    available_elements: Dict[str, bool] = {}
    for alias, selector in APPROVED_ELEMENT_ALIASES.items():
        try:
            count = await page.locator(selector).count()
            available_elements[alias] = (count > 0)
        except Exception:
            available_elements[alias] = False

    # Check error banner text if present
    error_banner_text: Optional[str] = None
    if available_elements.get("login_error", False):
        try:
            txt = await page.locator(APPROVED_ELEMENT_ALIASES["login_error"]).first.text_content(timeout=1000)
            if txt:
                error_banner_text = txt.strip()
        except Exception:
            pass

    # Count inventory items
    inventory_items_count = 0
    if available_elements.get("inventory_items", False):
        try:
            inventory_items_count = await page.locator(APPROVED_ELEMENT_ALIASES["inventory_items"]).count()
        except Exception:
            inventory_items_count = 0

    # Extract truncated visible body text
    visible_text = ""
    try:
        raw_body = await page.evaluate("() => document.body ? document.body.innerText : ''")
        lines = [line.strip() for line in raw_body.splitlines() if line.strip()]
        compact_text = " | ".join(lines)
        visible_text = compact_text[:MAX_OBSERVATION_TEXT_LEN]
    except Exception:
        visible_text = "(DOM inaccessible)"

    return BrowserObservation(
        current_url=current_url,
        page_title=page_title,
        is_approved_origin=is_approved_origin,
        available_elements=available_elements,
        visible_text_summary=visible_text,
        error_banner_text=error_banner_text,
        inventory_items_count=inventory_items_count,
    )


# ── Single-Step Action Decision (LLM Cognition) ───────────────────────────────

async def decide_next_action(
    goal: str,
    latest_observation: BrowserObservation,
    step_history: List[StepRecord],
    execution_context: Optional[Dict[str, Any]] = None,
) -> AgentActionDecision:
    """
    Asks the LLM to select exactly one next action given the goal, the latest
    observation, and the sequence of previously executed actions.

    Stage 6B Reliability:
      - Bounded exponential backoff retries for transient LLM errors (429, 502, 503, 504, timeouts).
      - Immediate non-retry / fail-fast for fatal errors (401/403 unauthorized, 400 bad request, schema errors).
      - Tracks LLM error counts and diagnostic error categories in execution_context.
    """
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()

    # Build concise history summary for prompt
    history_summary = []
    for s in step_history:
        history_summary.append(
            f"Step {s.iteration}: Action={s.decision.action_type}({s.decision.target}, val={s.decision.value}) -> Result={s.action_result}"
        )
    history_str = "\n".join(history_summary) if history_summary else "(No previous actions taken yet)"

    user_prompt = f"""TESTING GOAL:
"{goal}"

LATEST BROWSER OBSERVATION:
- Current URL: {latest_observation.current_url}
- Title: {latest_observation.page_title}
- Approved Origin: {latest_observation.is_approved_origin}
- Available Elements in DOM: {json.dumps(latest_observation.available_elements)}
- Error Banner: {latest_observation.error_banner_text or 'None'}
- Inventory Item Count: {latest_observation.inventory_items_count}
- Visible Text Summary: "{latest_observation.visible_text_summary}"

ACTION HISTORY SO FAR:
{history_str}

Select EXACTLY ONE next action. Return strict JSON matching:
{{
  "thought": "<concise explanation of why this action is chosen>",
  "action_type": "<navigate | fill | click | assert | stop>",
  "target": "<approved element alias or https://www.saucedemo.com/>",
  "value": "<credential or null>",
  "stop_reason": "<explanation if action_type is stop, otherwise null>"
}}
"""

    def record_llm_error(category: str):
        if execution_context is not None:
            execution_context["llm_errors_count"] = execution_context.get("llm_errors_count", 0) + 1
            execution_context["last_error_category"] = category

    # 1. Use Groq if available
    if groq_key:
        model = os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b").strip()
        url = "https://api.groq.com/openai/v1/chat/com/completions" if "/openai" in os.environ.get("GROQ_URL", "") else "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": AGENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

        # Bounded transient retry loop with backoff
        for attempt in range(LLM_RETRY_LIMIT + 1):
            t_llm_start = asyncio.get_event_loop().time()
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                    llm_dur = asyncio.get_event_loop().time() - t_llm_start

                    if resp.status_code == 200:
                        raw_json = resp.json()["choices"][0]["message"]["content"]
                        parsed = json.loads(raw_json)
                        record_llm_request(provider="groq", outcome="success", duration_seconds=llm_dur)
                        return AgentActionDecision(**parsed)

                    # Fatal non-transient status codes: fail fast without retrying
                    if resp.status_code in (400, 401, 403):
                        record_llm_error(ErrorCategory.LLM_FATAL_ERROR)
                        record_llm_request(provider="groq", outcome="fatal_error", duration_seconds=llm_dur)
                        break

                    # Transient status codes: retry with backoff
                    if resp.status_code in (429, 502, 503, 504):
                        record_llm_error(ErrorCategory.LLM_TRANSIENT_ERROR)
                        record_llm_request(provider="groq", outcome="transient_error", duration_seconds=llm_dur)
                        if attempt < LLM_RETRY_LIMIT:
                            backoff = LLM_RETRY_BACKOFF_SECONDS[attempt]
                            await asyncio.sleep(backoff)
                            continue
                        break

                    # Other unhandled HTTP errors
                    record_llm_error(ErrorCategory.LLM_TRANSIENT_ERROR)
                    record_llm_request(provider="groq", outcome="transient_error", duration_seconds=llm_dur)
                    break

            except (httpx.TimeoutException, httpx.NetworkError) as net_err:
                llm_dur = asyncio.get_event_loop().time() - t_llm_start
                record_llm_error(ErrorCategory.LLM_TRANSIENT_ERROR)
                outcome_type = "timeout" if isinstance(net_err, httpx.TimeoutException) else "network_error"
                record_llm_request(provider="groq", outcome=outcome_type, duration_seconds=llm_dur)
                if attempt < LLM_RETRY_LIMIT:
                    backoff = LLM_RETRY_BACKOFF_SECONDS[attempt]
                    await asyncio.sleep(backoff)
                    continue
                break
            except (json.JSONDecodeError, PydanticValidationError, KeyError):
                llm_dur = asyncio.get_event_loop().time() - t_llm_start
                record_llm_error(ErrorCategory.LLM_FATAL_ERROR)
                record_llm_request(provider="groq", outcome="schema_error", duration_seconds=llm_dur)
                break
            except Exception:
                llm_dur = asyncio.get_event_loop().time() - t_llm_start
                record_llm_error(ErrorCategory.LLM_FATAL_ERROR)
                record_llm_request(provider="groq", outcome="fatal_error", duration_seconds=llm_dur)
                break

    # 2. Use Gemini if Groq is unavailable or failed
    if gemini_key:
        model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {"x-goog-api-key": gemini_key, "Content-Type": "application/json"}
        payload = {
            "system_instruction": {"parts": [{"text": AGENT_SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {"response_mime_type": "application/json", "temperature": 0.1},
        }

        for attempt in range(LLM_RETRY_LIMIT + 1):
            t_llm_start = asyncio.get_event_loop().time()
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                    llm_dur = asyncio.get_event_loop().time() - t_llm_start

                    if resp.status_code == 200:
                        raw_json = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                        parsed = json.loads(raw_json)
                        record_llm_request(provider="gemini", outcome="success", duration_seconds=llm_dur)
                        return AgentActionDecision(**parsed)

                    if resp.status_code in (400, 401, 403):
                        record_llm_error(ErrorCategory.LLM_FATAL_ERROR)
                        record_llm_request(provider="gemini", outcome="fatal_error", duration_seconds=llm_dur)
                        break

                    if resp.status_code in (429, 502, 503, 504):
                        record_llm_error(ErrorCategory.LLM_TRANSIENT_ERROR)
                        record_llm_request(provider="gemini", outcome="transient_error", duration_seconds=llm_dur)
                        if attempt < LLM_RETRY_LIMIT:
                            backoff = LLM_RETRY_BACKOFF_SECONDS[attempt]
                            await asyncio.sleep(backoff)
                            continue
                        break

                    record_llm_error(ErrorCategory.LLM_TRANSIENT_ERROR)
                    record_llm_request(provider="gemini", outcome="transient_error", duration_seconds=llm_dur)
                    break

            except (httpx.TimeoutException, httpx.NetworkError) as net_err:
                llm_dur = asyncio.get_event_loop().time() - t_llm_start
                record_llm_error(ErrorCategory.LLM_TRANSIENT_ERROR)
                outcome_type = "timeout" if isinstance(net_err, httpx.TimeoutException) else "network_error"
                record_llm_request(provider="gemini", outcome=outcome_type, duration_seconds=llm_dur)
                if attempt < LLM_RETRY_LIMIT:
                    backoff = LLM_RETRY_BACKOFF_SECONDS[attempt]
                    await asyncio.sleep(backoff)
                    continue
                break
            except (json.JSONDecodeError, PydanticValidationError, KeyError):
                llm_dur = asyncio.get_event_loop().time() - t_llm_start
                record_llm_error(ErrorCategory.LLM_FATAL_ERROR)
                record_llm_request(provider="gemini", outcome="schema_error", duration_seconds=llm_dur)
                break
            except Exception:
                llm_dur = asyncio.get_event_loop().time() - t_llm_start
                record_llm_error(ErrorCategory.LLM_FATAL_ERROR)
                record_llm_request(provider="gemini", outcome="fatal_error", duration_seconds=llm_dur)
                break

    # 3. Deterministic heuristic fallback (offline mode or when LLM unavailable)
    return _heuristic_action_fallback(goal, latest_observation, step_history)


def _heuristic_action_fallback(
    goal: str,
    obs: BrowserObservation,
    step_history: List[StepRecord],
) -> AgentActionDecision:
    """Deterministic fallback for unit testing and offline evaluation."""
    lower_goal = goal.lower()
    is_lockout = "locked" in lower_goal or "lockout" in lower_goal
    is_invalid = "invalid" in lower_goal or "wrong" in lower_goal

    if is_lockout:
        user_cred = "locked_out_user"
    elif is_invalid:
        user_cred = "invalid_user"
    else:
        user_cred = "standard_user"

    # Step 1: Navigate if not on SauceDemo
    if not obs.is_approved_origin or not obs.current_url.startswith("https://www.saucedemo.com"):
        return AgentActionDecision(
            thought="Browser is not on SauceDemo origin. Navigating to start URL.",
            action_type="navigate",
            target="https://www.saucedemo.com/",
            value=None,
        )

    # If lockout error is already visible, stop
    if is_lockout and obs.error_banner_text and "locked out" in obs.error_banner_text.lower():
        return AgentActionDecision(
            thought="Lockout error banner is confirmed in DOM. Goal achieved.",
            action_type="stop",
            target="login_error",
            stop_reason="Lockout error banner is visible and verified.",
        )

    # If invalid credentials error is visible, stop
    if is_invalid and obs.error_banner_text and ("do not match" in obs.error_banner_text.lower() or "epic sadface" in obs.error_banner_text.lower()):
        return AgentActionDecision(
            thought="Invalid credentials error banner is confirmed in DOM. Goal achieved.",
            action_type="stop",
            target="login_error",
            stop_reason="Invalid credentials error banner is visible and verified.",
        )

    # If standard user inventory is visible, stop
    if not is_lockout and not is_invalid and obs.inventory_items_count == 6:
        return AgentActionDecision(
            thought="Inventory page contains 6 items. Goal achieved.",
            action_type="stop",
            target="inventory_items",
            stop_reason="6 inventory items rendered successfully on /inventory.html.",
        )

    # Actions based on history
    filled_user = any(s.decision.action_type == "fill" and s.decision.target == "username_input" for s in step_history)
    filled_pass = any(s.decision.action_type == "fill" and s.decision.target == "password_input" for s in step_history)
    clicked_btn = any(s.decision.action_type == "click" and s.decision.target == "login_button" for s in step_history)

    if not filled_user and obs.available_elements.get("username_input", False):
        return AgentActionDecision(
            thought=f"Filling username field with {user_cred}.",
            action_type="fill",
            target="username_input",
            value=user_cred,
        )

    if not filled_pass and obs.available_elements.get("password_input", False):
        return AgentActionDecision(
            thought="Filling password field with secret_sauce.",
            action_type="fill",
            target="password_input",
            value="secret_sauce",
        )

    if not clicked_btn and obs.available_elements.get("login_button", False):
        return AgentActionDecision(
            thought="Submitting login form by clicking login button.",
            action_type="click",
            target="login_button",
        )

    return AgentActionDecision(
        thought="All planned interactions executed. Stopping agent.",
        action_type="stop",
        target="login_error" if (is_lockout or is_invalid) else "inventory_items",
        stop_reason="Interactions completed; awaiting deterministic assertion evaluation.",
    )


# ── Action Execution Sandbox (Playwright Tool Registry) ───────────────────────

async def execute_agent_action(page: Page, decision: AgentActionDecision) -> tuple[str, bool]:
    """
    Safely executes a single validated agent action on the live Playwright page.
    Enforces strict security guardrails:
      - Validates origin before and after every action.
      - Rejects arbitrary selectors or scripts.
      - Enforces timeouts.
    """
    if decision.action_type == "stop":
        return f"Agent requested stop: {decision.stop_reason}", True

    if not decision.target:
        return f"Invalid action: Target element or URL is required for action_type '{decision.action_type}'.", False

    if decision.action_type == "navigate":
        # Strict origin validation
        if decision.target != "https://www.saucedemo.com/":
            return f"Security violation: Navigate target '{decision.target}' is not permitted.", False

        try:
            resp = await page.goto(decision.target, timeout=ACTION_TIMEOUT_MS, wait_until="domcontentloaded")
            validate_saucedemo_origin(page.url)
            status_code = resp.status if resp else "loaded"
            return f"Navigated to {decision.target} (status: {status_code})", True
        except Exception as exc:
            return f"Browser timeout: Navigation failed: {exc}", False

    # All non-navigate actions require being on approved origin
    try:
        validate_saucedemo_origin(page.url)
    except Exception as exc:
        return f"Pre-action security failure: {exc}", False

    # Check target alias in approved registry
    if decision.target not in APPROVED_ELEMENT_ALIASES:
        return f"Security violation: Selector alias '{decision.target}' is not approved.", False

    selector = APPROVED_ELEMENT_ALIASES[decision.target]

    if decision.action_type == "fill":
        # Check approved credential value
        raw_val = decision.value or ""
        resolved_val = APPROVED_CREDENTIALS.get(raw_val, raw_val)

        # Basic sanitation: disallow long injections
        if len(resolved_val) > 100:
            return "Security violation: Input value exceeds length limit.", False

        try:
            await page.fill(selector, resolved_val, timeout=ACTION_TIMEOUT_MS)
            return f"Filled element '{decision.target}' with preset value.", True
        except PlaywrightTimeoutError:
            return f"Missing element: Element '{decision.target}' not found or not interactable within timeout.", False
        except Exception as exc:
            return f"Fill action failed on '{decision.target}': {exc}", False

    if decision.action_type == "click":
        try:
            await page.click(selector, timeout=ACTION_TIMEOUT_MS)
            await page.wait_for_timeout(500)  # Brief DOM settling time
            # Re-validate origin after click to detect unauthorized redirects
            validate_saucedemo_origin(page.url)
            return f"Clicked element '{decision.target}'.", True
        except PlaywrightTimeoutError:
            return f"Missing element: Element '{decision.target}' was not clickable within timeout.", False
        except Exception as exc:
            return f"Click action failed on '{decision.target}': {exc}", False

    if decision.action_type == "assert":
        try:
            visible = await page.locator(selector).first.is_visible(timeout=ACTION_TIMEOUT_MS)
            return f"Asserted '{decision.target}' visibility: {visible}", visible
        except Exception as exc:
            return f"Assertion failed on '{decision.target}': {exc}", False

    return f"Unsupported action type: {decision.action_type}", False


# ── Deterministic Outcome Evaluation ──────────────────────────────────────────

async def evaluate_deterministic_outcome(
    goal: str,
    final_obs: BrowserObservation,
    page: Page,
) -> tuple[Literal["passed", "failed"], List[str], str]:
    """
    CRITICAL AGENT PRINCIPLE:
    The LLM never determines test pass/fail on its own.
    This function runs strict, deterministic Playwright ground-truth assertions.
    """
    lower_goal = goal.lower()
    assertions_evaluated = []

    # Scenario A: Locked-Out User Verification
    if "locked" in lower_goal or "lockout" in lower_goal:
        assertions_evaluated.append("URL must remain on https://www.saucedemo.com/")
        assertions_evaluated.append("Error container [data-test='error'] must be visible in DOM")
        assertions_evaluated.append("Error message text must contain 'locked out'")

        url_ok = final_obs.current_url.startswith("https://www.saucedemo.com")
        error_locator = page.locator(APPROVED_ELEMENT_ALIASES["login_error"])
        is_error_visible = False
        error_text = ""

        try:
            is_error_visible = await error_locator.first.is_visible()
            if is_error_visible:
                error_text = (await error_locator.first.text_content() or "").strip()
        except Exception:
            pass

        has_lockout_text = "locked out" in error_text.lower()

        if url_ok and is_error_visible and has_lockout_text:
            return "passed", assertions_evaluated, f"Ground-truth verified: Error banner '{error_text}' is displayed."
        else:
            return "failed", assertions_evaluated, f"Assertion failed: is_error_visible={is_error_visible}, text='{error_text}'"

    # Scenario B: Invalid Credentials Error Verification
    if "invalid" in lower_goal or "wrong" in lower_goal:
        assertions_evaluated.append("URL must remain on https://www.saucedemo.com/")
        assertions_evaluated.append("Error container [data-test='error'] must be visible in DOM")
        assertions_evaluated.append("Error message text must indicate credentials do not match")

        url_ok = final_obs.current_url.startswith("https://www.saucedemo.com")
        error_locator = page.locator(APPROVED_ELEMENT_ALIASES["login_error"])
        is_error_visible = False
        error_text = ""

        try:
            is_error_visible = await error_locator.first.is_visible()
            if is_error_visible:
                error_text = (await error_locator.first.text_content() or "").strip()
        except Exception:
            pass

        has_mismatch_text = "do not match" in error_text.lower() or "epic sadface" in error_text.lower()

        if url_ok and is_error_visible and has_mismatch_text:
            return "passed", assertions_evaluated, f"Ground-truth verified: Error banner '{error_text}' is displayed."
        else:
            return "failed", assertions_evaluated, f"Assertion failed: is_error_visible={is_error_visible}, text='{error_text}'"

    # Scenario C: Standard User Login & Inventory Verification
    if "standard" in lower_goal or "login" in lower_goal or "inventory" in lower_goal:
        assertions_evaluated.append("URL must transition to https://www.saucedemo.com/inventory.html")
        assertions_evaluated.append("Inventory items (.inventory_item) count must equal exactly 6")
        assertions_evaluated.append("No error banner must be visible")

        url_ok = final_obs.current_url == "https://www.saucedemo.com/inventory.html"
        items_count = final_obs.inventory_items_count
        no_error = not final_obs.available_elements.get("login_error", False)

        if url_ok and items_count == 6 and no_error:
            return "passed", assertions_evaluated, "Ground-truth verified: Reached /inventory.html with exactly 6 products."
        else:
            return "failed", assertions_evaluated, f"Assertion failed: url_ok={url_ok}, items_count={items_count}, no_error={no_error}"

    # Default: Reachability check
    assertions_evaluated.append("Target origin is reached and DOM contains content")
    if final_obs.is_approved_origin and len(final_obs.visible_text_summary) > 20:
        return "passed", assertions_evaluated, "Ground-truth verified: Page rendered visible content."
    return "failed", assertions_evaluated, "Assertion failed: Page did not render sufficient visible content."


# ── The Master Observe-Act-Evaluate Loop ──────────────────────────────────────

async def run_agent_loop(
    goal: str,
    max_iterations: int = MAX_AGENT_ITERATIONS,
    scenario: Optional[str] = None,
) -> AgentExecutionResult:
    """
    Executes the full Observe-Act-Evaluate agent loop on SauceDemo.
    Bounded by max_iterations (default: 8).
    Incorporates Stage 6B reliability, bounded recovery, and Stage 7A Prometheus telemetry.
    """
    if not scenario:
        lower_goal = goal.lower()
        if "locked" in lower_goal or "lockout" in lower_goal:
            scenario = "saucedemo_locked_out_login"
        elif "invalid" in lower_goal or "wrong" in lower_goal:
            scenario = "saucedemo_invalid_login"
        elif "smoke" in lower_goal:
            scenario = "smoke_test"
        else:
            scenario = "saucedemo_valid_login"

    with track_active_agent_run(scenario):
        start_time = datetime.now(timezone.utc)
        start_mono = asyncio.get_event_loop().time()
        run_id = uuid.uuid4().hex[:12]
        screenshot_filename = f"run_{run_id}.png"
        screenshot_path = EVIDENCE_DIR / screenshot_filename

        step_records: List[StepRecord] = []
        final_status: Literal["passed", "failed", "error"] = "failed"
        deterministic_verdict = "Execution did not complete."
        assertions_evaluated: List[str] = []

        # Telemetry and reliability tracking
        recovery_attempts = 0
        action_failures_count = 0
        error_category: Optional[str] = None
        exec_context: Dict[str, Any] = {"llm_errors_count": 0, "last_error_category": None}

        provider = "groq" if os.environ.get("GROQ_API_KEY") else ("gemini" if os.environ.get("GEMINI_API_KEY") else "heuristic_fallback")
        model = os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b") if provider == "groq" else (os.environ.get("GEMINI_MODEL", "gemini-2.5-flash") if provider == "gemini" else "none")

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
            )
            context = await browser.new_context(viewport={"width": 1280, "height": 720})
            page = await context.new_page()

            try:
                last_failed_action: Optional[tuple] = None
                repetition_count = 0

                for iteration in range(1, max_iterations + 1):
                    iter_start = asyncio.get_event_loop().time()

                    # 1. OBSERVE
                    obs_before = await capture_observation(page)

                    # 2. DECIDE
                    decision = await decide_next_action(
                        goal=goal,
                        latest_observation=obs_before,
                        step_history=step_records,
                        execution_context=exec_context,
                    )

                    # If model chooses to STOP, break loop and evaluate
                    if decision.action_type == "stop":
                        iter_duration = int((asyncio.get_event_loop().time() - iter_start) * 1000)
                        step_records.append(
                            StepRecord(
                                iteration=iteration,
                                observation_before=obs_before,
                                decision=decision,
                                action_result=f"Agent completed loop: {decision.stop_reason}",
                                is_success=True,
                                duration_ms=iter_duration,
                            )
                        )
                        break

                    # ── Safeguard: Prevent Blind Repetition of Failed Actions ──
                    current_action_sig = (decision.action_type, decision.target, decision.value)
                    if last_failed_action is not None and current_action_sig == last_failed_action:
                        repetition_count += 1
                        action_failures_count += 1
                        iter_duration = int((asyncio.get_event_loop().time() - iter_start) * 1000)

                        if recovery_attempts < MAX_RECOVERY_ATTEMPTS:
                            recovery_attempts += 1
                            record_recovery_attempt(ErrorCategory.REPETITION_DETECTED)
                            rep_msg = f"Repetition blocked: Agent repeated failed action {decision.action_type}({decision.target}). Re-planning triggered."
                            step_records.append(
                                StepRecord(
                                    iteration=iteration,
                                    observation_before=obs_before,
                                    decision=decision,
                                    action_result=rep_msg,
                                    is_success=False,
                                    duration_ms=iter_duration,
                                )
                            )
                            await page.wait_for_timeout(500)
                            continue
                        else:
                            error_category = ErrorCategory.REPETITION_DETECTED
                            rep_msg = f"Repetition limit exceeded: Repeated failed action {decision.action_type}({decision.target}) with no effect. Halting."
                            step_records.append(
                                StepRecord(
                                    iteration=iteration,
                                    observation_before=obs_before,
                                    decision=decision,
                                    action_result=rep_msg,
                                    is_success=False,
                                    duration_ms=iter_duration,
                                )
                            )
                            break

                    # 3. ACT (EXECUTE TOOL)
                    result_msg, is_success = await execute_agent_action(page, decision)
                    iter_duration = int((asyncio.get_event_loop().time() - iter_start) * 1000)

                    step_records.append(
                        StepRecord(
                            iteration=iteration,
                            observation_before=obs_before,
                            decision=decision,
                            action_result=result_msg,
                            is_success=is_success,
                            duration_ms=iter_duration,
                        )
                    )

                    if not is_success:
                        action_failures_count += 1
                        last_failed_action = current_action_sig

                        if "Security violation" in result_msg or "Pre-action security failure" in result_msg:
                            error_category = ErrorCategory.SECURITY_VIOLATION
                            break

                        # ── Safe Recovery for Missing Elements or Timeouts ──
                        if "Missing element" in result_msg or "timeout" in result_msg.lower():
                            if recovery_attempts < MAX_RECOVERY_ATTEMPTS:
                                recovery_attempts += 1
                                rec_cat = ErrorCategory.BROWSER_TIMEOUT if "timeout" in result_msg.lower() else ErrorCategory.MISSING_ELEMENT
                                record_recovery_attempt(rec_cat)
                                await page.wait_for_timeout(500)  # Settling wait for DOM transitions
                                continue
                            else:
                                error_category = ErrorCategory.MISSING_ELEMENT
                                break
                    else:
                        # Successful action resets repetition tracking
                        last_failed_action = None
                        repetition_count = 0

                # If maximum iterations reached without natural stop
                if len(step_records) >= max_iterations and not any(s.decision.action_type == "stop" for s in step_records):
                    if not error_category:
                        error_category = ErrorCategory.ITERATION_LIMIT_EXCEEDED

                # 4. EVALUATE FINAL OUTCOME (DETERMINISTIC GROUND TRUTH)
                final_observation = await capture_observation(page)
                final_status, assertions_evaluated, deterministic_verdict = await evaluate_deterministic_outcome(
                    goal, final_observation, page
                )

                # Reconcile status with ground-truth verification
                if final_status == "passed":
                    error_category = None  # Clear error if deterministic assertions passed
                elif not error_category:
                    error_category = ErrorCategory.ASSERTION_FAILURE

            except Exception as exc:
                final_status = "error"
                error_category = ErrorCategory.UNSUPPORTED_ACTION if "unsupported" in str(exc).lower() else "UNEXPECTED_ERROR"
                deterministic_verdict = f"Agent loop failed with unexpected error: {exc}"
            finally:
                # Capture evidence screenshot safely without masking failures
                saved_screenshot = None
                try:
                    await page.screenshot(path=str(screenshot_path), full_page=False)
                    saved_screenshot = f"evidence/{screenshot_filename}"
                except Exception:
                    # Crucial reliability rule: Screenshot failure must NEVER convert a test failure to a pass
                    saved_screenshot = None

                await page.close()
                await context.close()
                await browser.close()

        elapsed = int((asyncio.get_event_loop().time() - start_mono) * 1000)
        task_success = (final_status == "passed")

        # Record completed agent run metrics in Prometheus
        record_agent_run(
            scenario=scenario,
            status=final_status,
            duration_seconds=elapsed / 1000.0,
            iterations=len(step_records),
        )

        return AgentExecutionResult(
            run_id=run_id,
            goal=goal,
            status=final_status,
            task_success=task_success,
            total_iterations=len(step_records),
            steps=step_records,
            assertions_evaluated=assertions_evaluated,
            deterministic_verdict=deterministic_verdict,
            screenshot_path=saved_screenshot,
            duration_ms=elapsed,
            provider=provider,
            model=model,
            timestamp=start_time.isoformat(),
            recovery_attempts=recovery_attempts,
            llm_errors_count=exec_context.get("llm_errors_count", 0),
            action_failures_count=action_failures_count,
            error_category=error_category,
            expected_assertion_passed=task_success,
        )
