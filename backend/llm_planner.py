"""
llm_planner.py
─────────────────────────────────────────────────────────────────────────────
Multi-Provider AI Test Planner for ProbeQA supporting Groq & Google Gemini.

RESPONSIBILITIES
  1. Accepts natural-language testing instructions from the user.
  2. Synthesizes a structured, bounded TestPlan conforming to Pydantic schemas.
  3. Maps intent to one of the 4 approved scenarios in the Tool Registry:
     - smoke_test
     - saucedemo_valid_login
     - saucedemo_locked_out_login
     - saucedemo_invalid_login
  4. Provides high-speed inference via Groq or Google Gemini.
  5. Includes clear diagnostics and fallback for offline evaluation.

SECURITY PRINCIPLES
  - Never logs, returns, or leaks API keys to frontend or console.
  - Passes authentication via standard request headers (never in URLs).
  - The LLM does NOT execute code; it produces structured JSON for human review.
  - LLM plans are untrusted inputs re-validated against registered constraints before execution.
"""

import json
import os
import time
import uuid
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
import httpx
from pydantic import ValidationError as PydanticValidationError

from scenarios import (
    TestPlan,
    PlanAction,
    REGISTERED_SCENARIOS,
    ALLOWED_ACTION_TYPES,
    APPROVED_ELEMENT_ALIASES,
)
from metrics import record_llm_request

# ── Load environment variables reliably ──────────────────────────────────────
_dotenv_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_dotenv_path)

DEFAULT_GROQ_MODEL = "qwen/qwen3.8-27b"
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"


class LLMPlannerError(Exception):
    """Raised when an LLM API call fails, preventing silent fallback masking."""
    def __init__(self, message: str, status_code: int = 502, error_category: str = "upstream_error"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_category = error_category


# Alias for backward-compatibility with main.py
GeminiPlannerError = LLMPlannerError


PLANNER_SYSTEM_PROMPT = """You are ProbeQA's AI Test Planner.
Your role is to analyze a user's natural-language browser testing goal and convert it into a strictly structured, bounded test plan.

You have access to exactly 4 permitted scenarios:
1. 'smoke_test': General web smoke test. Checks if a target URL loads, returns healthy HTTP status, and renders visible content. Allowed on any safe public URL.
2. 'saucedemo_valid_login': Navigates to https://www.saucedemo.com/, fills standard_user / secret_sauce, clicks login, asserts transition to /inventory.html, and asserts 6 items render.
3. 'saucedemo_locked_out_login': Navigates to https://www.saucedemo.com/, fills locked_out_user / secret_sauce, clicks login, and asserts the user lockout error banner is displayed.
4. 'saucedemo_invalid_login': Navigates to https://www.saucedemo.com/, fills invalid credentials, clicks login, and asserts the credential mismatch error banner is displayed.

Rules:
- If the user goal does not match any of these 4 scenarios (e.g. 'order pizza', 'hack database', 'transfer money'), set is_supported=false, scenario_id=null, and explain in unsupported_reason.
- Do NOT generate arbitrary code, shell commands, or arbitrary CSS selectors. Use only approved element aliases: username_input, password_input, login_button, inventory_items, login_error.
- Return output strictly conforming to the requested JSON schema.
"""


def _build_deterministic_plan(goal: str, target_url: Optional[str] = None) -> TestPlan:
    """Fallback intent classifier when no LLM API key is configured."""
    plan_id = f"plan_{uuid.uuid4().hex[:10]}"
    lower_goal = goal.lower().strip()
    target = (target_url or "").strip()

    unsupported_keywords = ["pizza", "bank", "transfer", "hack", "bitcoin", "weather", "music", "flight"]
    if any(k in lower_goal for k in unsupported_keywords):
        return TestPlan(
            plan_id=plan_id,
            goal=goal,
            interpreted_goal="Unsupported test request",
            scenario_id=None,
            target_origin=target or "https://example.com",
            actions=[],
            expected_outcomes=[],
            explanation="The requested goal is outside ProbeQA's registered testing domain.",
            is_supported=False,
            unsupported_reason=f"Goal '{goal}' cannot be mapped to any permitted browser testing scenario.",
            provider="deterministic_fallback",
            model=None,
        )

    if "locked" in lower_goal or "lockout" in lower_goal:
        return TestPlan(
            plan_id=plan_id,
            goal=goal,
            interpreted_goal="Verify locked-out user receives lockout error banner",
            scenario_id="saucedemo_locked_out_login",
            target_origin="https://www.saucedemo.com/",
            actions=[
                PlanAction(step=1, action_type="navigate", target="https://www.saucedemo.com/", description="Navigate to SauceDemo login portal"),
                PlanAction(step=2, action_type="locate_and_fill", target="username_input", description="Fill locked_out_user credentials"),
                PlanAction(step=3, action_type="locate_and_fill", target="password_input", description="Fill secret_sauce password"),
                PlanAction(step=4, action_type="click", target="login_button", description="Click login button"),
                PlanAction(step=5, action_type="assert_error_message", target="login_error", description="Verify 'Sorry, this user has been locked out' error banner is visible"),
                PlanAction(step=6, action_type="capture_screenshot", target="viewport", description="Capture screenshot of error state"),
            ],
            expected_outcomes=[
                "URL remains on https://www.saucedemo.com/",
                "Error container [data-test='error'] is visible",
                "Error message contains lockout notice"
            ],
            explanation="Goal specifies testing user lockout behavior on login. Mapped to registered locked_out_login workflow.",
            is_supported=True,
            provider="deterministic_fallback",
            model=None,
        )

    if "invalid" in lower_goal or "wrong" in lower_goal or "reject" in lower_goal or "bad password" in lower_goal:
        return TestPlan(
            plan_id=plan_id,
            goal=goal,
            interpreted_goal="Verify invalid credentials produce mismatch error banner",
            scenario_id="saucedemo_invalid_login",
            target_origin="https://www.saucedemo.com/",
            actions=[
                PlanAction(step=1, action_type="navigate", target="https://www.saucedemo.com/", description="Navigate to SauceDemo login portal"),
                PlanAction(step=2, action_type="locate_and_fill", target="username_input", description="Fill invalid username credentials"),
                PlanAction(step=3, action_type="locate_and_fill", target="password_input", description="Fill test password"),
                PlanAction(step=4, action_type="click", target="login_button", description="Click login button"),
                PlanAction(step=5, action_type="assert_error_message", target="login_error", description="Verify 'Username and password do not match' error is visible"),
                PlanAction(step=6, action_type="capture_screenshot", target="viewport", description="Capture screenshot of rejection state"),
            ],
            expected_outcomes=[
                "URL remains on https://www.saucedemo.com/",
                "Error container [data-test='error'] is visible",
                "Error text confirms credential rejection"
            ],
            explanation="Goal specifies verifying credential validation and error messaging.",
            is_supported=True,
            provider="deterministic_fallback",
            model=None,
        )

    if "login" in lower_goal or "inventory" in lower_goal or "standard" in lower_goal or "sauce" in lower_goal:
        return TestPlan(
            plan_id=plan_id,
            goal=goal,
            interpreted_goal="Verify successful login and product inventory display for standard_user",
            scenario_id="saucedemo_valid_login",
            target_origin="https://www.saucedemo.com/",
            actions=[
                PlanAction(step=1, action_type="navigate", target="https://www.saucedemo.com/", description="Navigate to SauceDemo login portal"),
                PlanAction(step=2, action_type="locate_and_fill", target="username_input", description="Fill standard_user credentials"),
                PlanAction(step=3, action_type="locate_and_fill", target="password_input", description="Fill secret_sauce password"),
                PlanAction(step=4, action_type="click", target="login_button", description="Click login button"),
                PlanAction(step=5, action_type="wait_for_route", target="/inventory.html", description="Wait for page transition to /inventory.html"),
                PlanAction(step=6, action_type="assert_element_count", target="inventory_items:6", description="Assert exactly 6 product cards (.inventory_item) render"),
                PlanAction(step=7, action_type="capture_screenshot", target="viewport", description="Capture screenshot of product inventory"),
            ],
            expected_outcomes=[
                "Page transitions to https://www.saucedemo.com/inventory.html",
                "Product catalog loads with exactly 6 products",
                "No authentication error banner is visible"
            ],
            explanation="Goal indicates standard authentication workflow. Mapped to registered valid login scenario.",
            is_supported=True,
            provider="deterministic_fallback",
            model=None,
        )

    resolved_url = target if (target and target.startswith("http")) else "https://example.com"
    return TestPlan(
        plan_id=plan_id,
        goal=goal,
        interpreted_goal=f"Verify reachability, HTTP response, and visible DOM content for {resolved_url}",
        scenario_id="smoke_test",
        target_origin=resolved_url,
        actions=[
            PlanAction(step=1, action_type="navigate", target=resolved_url, description=f"Navigate to {resolved_url}"),
            PlanAction(step=2, action_type="assert_element_count", target="body_text_length>=20", description="Assert page returns HTTP < 400 and has visible content"),
            PlanAction(step=3, action_type="capture_screenshot", target="viewport", description="Capture full-page smoke test screenshot"),
        ],
        expected_outcomes=[
            "Server responds with HTTP status 200 (or < 400)",
            "DOM contains non-empty body text",
            "Page title is retrieved successfully"
        ],
        explanation="General web reachability and content verification for arbitrary public targets.",
        is_supported=True,
        provider="deterministic_fallback",
        model=None,
    )


def _clean_json_text(text: str) -> str:
    clean = text.strip()
    if clean.startswith("```json"):
        clean = clean[7:]
    elif clean.startswith("```"):
        clean = clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    return clean.strip()


async def _generate_groq_plan(goal: str, target_url: Optional[str] = None) -> TestPlan:
    """Generates structured test plan using high-speed Groq API."""
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    model = os.environ.get("GROQ_MODEL", "").strip() or DEFAULT_GROQ_MODEL

    if not api_key:
        raise LLMPlannerError("GROQ_API_KEY is not configured.", status_code=401, error_category="auth_error")

    endpoint = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    user_prompt = f"""User natural-language testing goal:
"{goal}"

User provided target URL: "{target_url or 'None'}"

Synthesize a structured TestPlan JSON matching the schema:
{{
  "plan_id": "plan_{uuid.uuid4().hex[:10]}",
  "goal": "{goal}",
  "interpreted_goal": "<concise summary>",
  "scenario_id": "<one of: smoke_test, saucedemo_valid_login, saucedemo_locked_out_login, saucedemo_invalid_login, or null if unsupported>",
  "target_origin": "<https://...>",
  "actions": [
    {{"step": 1, "action_type": "<action_type>", "target": "<target>", "description": "<description>"}}
  ],
  "expected_outcomes": ["<outcome 1>", "<outcome 2>"],
  "explanation": "<why this plan matches the goal>",
  "is_supported": true,
  "unsupported_reason": null
}}
"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
    }

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(endpoint, headers=headers, json=payload)
    except httpx.TimeoutException as exc:
        record_llm_request(provider="groq", outcome="timeout", duration_seconds=time.monotonic() - t0)
        raise LLMPlannerError(f"Groq API request timed out after 15s for model '{model}'.", status_code=504, error_category="timeout") from exc
    except httpx.RequestError as exc:
        record_llm_request(provider="groq", outcome="network_error", duration_seconds=time.monotonic() - t0)
        raise LLMPlannerError(f"Network error contacting Groq API: {type(exc).__name__}", status_code=502, error_category="network_error") from exc

    dur = time.monotonic() - t0
    if resp.status_code != 200:
        record_llm_request(provider="groq", outcome="http_error", duration_seconds=dur)
        if resp.status_code in (401, 403):
            raise LLMPlannerError("Groq authentication failed: Invalid or expired GROQ_API_KEY.", status_code=401, error_category="auth_error")
        elif resp.status_code == 429:
            raise LLMPlannerError("Groq API rate limit or quota exceeded (HTTP 429).", status_code=429, error_category="quota_exceeded")
        elif resp.status_code == 404:
            raise LLMPlannerError(f"Groq model '{model}' not found or inaccessible.", status_code=404, error_category="model_not_found")
        else:
            raise LLMPlannerError(f"Groq API returned HTTP {resp.status_code}.", status_code=resp.status_code, error_category="upstream_error")

    record_llm_request(provider="groq", outcome="success", duration_seconds=dur)

    try:
        data = resp.json()
        raw_text = data["choices"][0]["message"]["content"]
        parsed = json.loads(_clean_json_text(raw_text))
        test_plan = TestPlan(**parsed)
    except (json.JSONDecodeError, PydanticValidationError, KeyError, IndexError) as exc:
        raise LLMPlannerError(f"Failed to validate Groq response against TestPlan schema: {exc}", status_code=502, error_category="schema_validation_error") from exc

    test_plan.provider = "groq"
    test_plan.model = model
    test_plan.explanation += f" (Generated live via Groq API model: {model})"
    return test_plan


async def _generate_gemini_plan(goal: str, target_url: Optional[str] = None) -> TestPlan:
    """Generates structured test plan using Google Gemini API."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    model = os.environ.get("GEMINI_MODEL", "").strip() or DEFAULT_GEMINI_MODEL

    if not api_key:
        raise LLMPlannerError("GEMINI_API_KEY is not configured.", status_code=401, error_category="auth_error")

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }

    prompt_content = f"""User natural-language testing goal:
"{goal}"

User provided target URL: "{target_url or 'None'}"

Synthesize a structured TestPlan JSON matching the Pydantic schema:
{{
  "plan_id": "plan_{uuid.uuid4().hex[:10]}",
  "goal": "{goal}",
  "interpreted_goal": "<concise summary>",
  "scenario_id": "<one of: smoke_test, saucedemo_valid_login, saucedemo_locked_out_login, saucedemo_invalid_login, or null if unsupported>",
  "target_origin": "<https://...>",
  "actions": [
    {{"step": 1, "action_type": "<action>", "target": "<target>", "description": "<description>"}}
  ],
  "expected_outcomes": ["<outcome 1>", "<outcome 2>"],
  "explanation": "<why this plan matches the goal>",
  "is_supported": true,
  "unsupported_reason": null
}}
"""

    payload = {
        "system_instruction": {"parts": [{"text": PLANNER_SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": prompt_content}]}],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.1,
        }
    }

    active_model = model
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(endpoint, headers=headers, json=payload)

            if resp.status_code == 503 and model != "gemini-2.5-flash":
                backup_endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
                backup_resp = await client.post(backup_endpoint, headers=headers, json=payload)
                if backup_resp.status_code == 200:
                    resp = backup_resp
                    active_model = "gemini-2.5-flash"
    except httpx.TimeoutException as exc:
        record_llm_request(provider="gemini", outcome="timeout", duration_seconds=time.monotonic() - t0)
        raise LLMPlannerError(f"Gemini API request timed out after 25s for model '{model}'.", status_code=504, error_category="timeout") from exc
    except httpx.RequestError as exc:
        record_llm_request(provider="gemini", outcome="network_error", duration_seconds=time.monotonic() - t0)
        raise LLMPlannerError(f"Network error contacting Gemini API: {type(exc).__name__}", status_code=502, error_category="network_error") from exc

    dur = time.monotonic() - t0
    if resp.status_code != 200:
        record_llm_request(provider="gemini", outcome="http_error", duration_seconds=dur)
        err_body_text = resp.text
        if "API_KEY_INVALID" in err_body_text or resp.status_code in (401, 403):
            raise LLMPlannerError("Gemini API authentication failed: Invalid or expired GEMINI_API_KEY.", status_code=401, error_category="auth_error")
        elif resp.status_code == 404:
            raise LLMPlannerError(f"Gemini model '{active_model}' was not found or is unavailable (HTTP 404).", status_code=404, error_category="model_not_found")
        elif resp.status_code == 429:
            raise LLMPlannerError("Gemini API quota or rate limit exceeded (HTTP 429).", status_code=429, error_category="quota_exceeded")
        elif resp.status_code == 400:
            raise LLMPlannerError("Gemini API bad request (HTTP 400). Please check model parameters.", status_code=400, error_category="bad_request")
        elif resp.status_code >= 500:
            raise LLMPlannerError(f"Google Gemini service error (HTTP {resp.status_code}). Upstream model temporarily unavailable.", status_code=502, error_category="upstream_service_error")
        else:
            raise LLMPlannerError(f"Gemini API responded with unexpected HTTP {resp.status_code}.", status_code=resp.status_code, error_category="unexpected_http_error")

    try:
        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise LLMPlannerError("Gemini API returned response without candidates.", status_code=502, error_category="empty_candidates")
        raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        parsed = json.loads(_clean_json_text(raw_text))
        test_plan = TestPlan(**parsed)
    except (json.JSONDecodeError, PydanticValidationError, KeyError, IndexError) as exc:
        raise LLMPlannerError(f"Gemini plan does not conform to TestPlan schema: {exc}", status_code=502, error_category="schema_validation_error") from exc

    test_plan.provider = "gemini"
    test_plan.model = active_model
    test_plan.explanation += f" (Generated live via Google Gemini API model: {active_model})"
    record_llm_request(provider="gemini", outcome="success", duration_seconds=dur)
    return test_plan


async def generate_test_plan(goal: str, target_url: Optional[str] = None) -> TestPlan:
    """
    Main entry point for AI test planning.

    Supports Groq, Google Gemini, or clean deterministic fallback.
    Priority:
      1. If GROQ_API_KEY is present and LLM_PROVIDER is 'groq' (or default when configured), routes to Groq.
      2. If GEMINI_API_KEY is present, routes to Gemini.
      3. If neither key is configured, provides deterministic fallback.
    """
    provider_pref = os.environ.get("LLM_PROVIDER", "").strip().lower()
    has_groq = bool(os.environ.get("GROQ_API_KEY", "").strip())
    has_gemini = bool(os.environ.get("GEMINI_API_KEY", "").strip())

    if (provider_pref == "groq" and has_groq) or (has_groq and not has_gemini) or (has_groq and provider_pref != "gemini"):
        return await _generate_groq_plan(goal, target_url)
    elif has_gemini:
        return await _generate_gemini_plan(goal, target_url)
    else:
        plan = _build_deterministic_plan(goal, target_url)
        plan.explanation += " (Note: Generated using ProbeQA Deterministic Rule Planner because no LLM API key is configured in backend/.env.)"
        return plan
