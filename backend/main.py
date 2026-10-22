"""
main.py
─────────────────────────────────────────────────────────────────────────────
ProbeQA FastAPI backend entry point.

HOW TO RUN (from the backend/ directory)
  pip install -r requirements.txt
  playwright install chromium
  uvicorn main:app --host 127.0.0.1 --port 8000 --reload

  --host 127.0.0.1  → bind to loopback only; NOT accessible from the internet
  --port 8000       → default FastAPI development port
  --reload          → auto-restart when you save a .py file (dev only)

INTERVIEW NOTE
  "FastAPI uses Python's asyncio event loop, so the server can handle multiple
   requests concurrently without threads.  When a Playwright test is running
   (which does I/O — network, disk), other requests can be served in parallel."
"""

import os
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from starlette.routing import Match

from runner import run_smoke_test, run_saucedemo_login_test
from validator import ValidationError, validate_url
from scenarios import TestPlan, REGISTERED_SCENARIOS
from llm_planner import generate_test_plan, GeminiPlannerError
from agent_loop import run_agent_loop, AgentExecutionResult
from database import (
    init_db,
    save_test_run,
    query_test_runs,
    get_test_run_by_id,
    calculate_reports_summary,
)
from metrics import (
    record_http_request,
    record_agent_run,
    get_metrics_payload,
)

# ── Initialize SQLite Database Tables ────────────────────────────────────────
init_db()

# ── Load environment variables from .env (if it exists) ──────────────────────
# python-dotenv reads key=value lines from a .env file and injects them into
# os.environ.  Explicitly point to backend/.env regardless of working directory.
_dotenv_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_dotenv_path)

# ── Application metadata ──────────────────────────────────────────────────────
# These strings appear in the auto-generated OpenAPI docs at /docs
APP_VERSION = "0.1.0"

app = FastAPI(
    title="ProbeQA API",
    description=(
        "AI-powered web testing backend. "
        "Stage 1: smoke tests via Playwright. "
        "Natural-language instruction interpretation coming in a future stage."
    ),
    version=APP_VERSION,
)

# ── CORS middleware ───────────────────────────────────────────────────────────
# CORS = Cross-Origin Resource Sharing.
#
# WHY WE NEED THIS:
#   The React dev server runs on http://localhost:5173.
#   The FastAPI server runs on http://localhost:8000.
#   These are different "origins" (different ports).
#   Without CORS headers the browser blocks the fetch() call in NewTestForm.jsx.
#
# allow_origins: which frontends are allowed to call this API.
#   In development we allow both the Vite dev server and a hypothetical
#   production build.  In production you would replace "*" with your
#   actual domain.
#
# allow_methods: which HTTP verbs are allowed.
# allow_headers: which request headers are allowed.
ALLOWED_ORIGINS = [
    "http://localhost:5173",   # Vite dev server
    "http://localhost:4173",   # Vite preview server
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,    # We have no cookies or auth yet
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# ── Prometheus HTTP Request Monitoring Middleware ────────────────────────────
# Intercepts all incoming HTTP calls to track probeqa_http_requests_total and
# probeqa_http_request_duration_seconds.
# Prevents cardinality explosion by matching scope against route path templates.

@app.middleware("http")
async def prometheus_http_middleware(request: Request, call_next):
    # Exclude /metrics endpoint to avoid noisy recursive scraping loops
    if request.url.path == "/metrics":
        return await call_next(request)

    start_mono = time.monotonic()
    method = request.method
    endpoint = "unmatched"

    # Match request against route templates (e.g. /api/runs/{run_id} instead of /api/runs/a1b2c3)
    for route in request.app.routes:
        match, _ = route.matches(request.scope)
        if match == Match.FULL:
            endpoint = getattr(route, "path", request.url.path)
            break

    # If static file under /evidence, normalize endpoint
    if endpoint == "unmatched" and request.url.path.startswith("/evidence"):
        endpoint = "/evidence/{file_path}"

    try:
        response = await call_next(request)
        status_code = str(response.status_code)
    except Exception as exc:
        status_code = "500"
        record_http_request(
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            duration_seconds=time.monotonic() - start_mono,
        )
        raise exc from None

    record_http_request(
        method=method,
        endpoint=endpoint,
        status_code=status_code,
        duration_seconds=time.monotonic() - start_mono,
    )
    return response

# ── Serve screenshots as static files ─────────────────────────────────────────
# After a test runs, the screenshot is saved in backend/evidence/.
# We mount that directory at the /evidence URL path so the frontend can
# display it with:  <img src="http://localhost:8000/evidence/run_abc123.png" />
EVIDENCE_DIR = Path(__file__).parent / "evidence"
EVIDENCE_DIR.mkdir(exist_ok=True)  # create the directory if it doesn't exist

app.mount(
    "/evidence",                    # URL prefix
    StaticFiles(directory=str(EVIDENCE_DIR)),  # local directory to serve
    name="evidence",
)


# ── Request / Response models ─────────────────────────────────────────────────
# Pydantic BaseModel does three things for us automatically:
#   1. Parses the incoming JSON body into typed Python attributes.
#   2. Validates the types (e.g. url must be a string).
#   3. Generates the JSON schema shown in /docs.

class TestRunRequest(BaseModel):
    """Body of POST /api/tests/run"""

    url: str
    instruction: str = ""    # optional for now; will be used with LLM later
    mode: str = "smoke"      # "smoke" | "ai-assisted" | "manual"
    scenario: str = "smoke"  # "smoke" | "saucedemo_login"

    @field_validator("url")
    @classmethod
    def url_must_not_be_empty(cls, v: str) -> str:
        """Pydantic validator: run before our URL safety check."""
        if not v or not v.strip():
            raise ValueError("url must not be empty.")
        return v.strip()


class PlanRequest(BaseModel):
    """Body of POST /api/agent/plan"""
    goal: str
    target_url: str | None = None


class ExecutePlanRequest(BaseModel):
    """Body of POST /api/agent/execute"""
    plan_id: str
    scenario_id: str
    target_origin: str


class AgentLoopRequest(BaseModel):
    """Body of POST /api/agent/loop/run (Stage 5 Bounded OAE Agent Loop)"""
    goal: str
    max_iterations: int = 8


class HealthResponse(BaseModel):
    """Body of GET /health"""
    status: str
    version: str


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns 200 OK when the backend server is running.",
)
async def health_check():
    """
    A simple liveness probe.

    The React frontend calls this first to verify the backend is reachable
    before enabling the real Run Agent button.
    """
    return HealthResponse(status="ok", version=APP_VERSION)


@app.get(
    "/metrics",
    summary="Prometheus Metrics Exposition",
    description=(
        "Exposes live ProbeQA telemetry in standard Prometheus text exposition format. "
        "Excludes recursive self-scraping calls. "
        "NOTE FOR PRODUCTION DEPLOYMENT: This endpoint exposes internal operational metrics "
        "and should be protected by firewall, private network isolation, or reverse proxy basic auth."
    ),
    include_in_schema=False,
)
def prometheus_metrics():
    """Returns official Prometheus exposition text format for scraping."""
    payload, content_type = get_metrics_payload()
    return Response(content=payload, media_type=content_type)


@app.post(
    "/api/agent/plan",
    response_model=TestPlan,
    summary="Generate AI Test Plan",
    description="Analyzes natural-language testing intent and synthesizes a structured, bounded TestPlan."
)
async def create_plan(request: PlanRequest):
    """
    AI planning endpoint:
    Converts unstructured testing goals into an inspectable, bounded TestPlan.
    """
    if not request.goal.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Testing goal cannot be empty."
        )
    try:
        plan = await generate_test_plan(request.goal, request.target_url)
        return plan
    except GeminiPlannerError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=f"{exc.message} (Category: {exc.error_category})"
        ) from exc


@app.post(
    "/api/agent/execute",
    summary="Execute Approved AI Test Plan",
    description="Validates that an approved plan conforms to registered constraints and runs real Playwright assertions."
)
async def execute_plan(request: ExecutePlanRequest):
    """
    Approved plan execution endpoint:
    Treats plan as untrusted input; re-validates scenario and origin constraints before running.
    """
    # 1. Re-validate scenario exists in restricted registry
    if request.scenario_id not in REGISTERED_SCENARIOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Scenario '{request.scenario_id}' is not in the approved tool registry."
        )

    # 2. Re-validate origin and execute corresponding bounded workflow
    if request.scenario_id.startswith("saucedemo"):
        try:
            validate_url("https://www.saucedemo.com/")
        except ValidationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        result = await run_saucedemo_login_test(workflow_type=request.scenario_id)
        save_test_run(
            run_id=result["run_id"],
            goal=f"Approved Plan: {request.scenario_id}",
            scenario=request.scenario_id,
            target_origin=request.target_origin,
            status=result["status"],
            duration_ms=result["duration_ms"],
            mode="planned",
            http_status=result.get("http_status"),
            page_title=result.get("page_title"),
            has_body_content=result.get("has_body_content", True),
            error_message=result.get("error_message"),
            screenshot_path=result.get("screenshot_path"),
            limitation_note=result.get("limitation_note"),
        )
        record_agent_run(
            scenario=request.scenario_id,
            status=result["status"],
            duration_seconds=result["duration_ms"] / 1000.0,
            iterations=1,
        )
        return result

    if request.scenario_id == "smoke_test":
        try:
            safe_url = validate_url(request.target_origin)
        except ValidationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        result = await run_smoke_test(safe_url)
        save_test_run(
            run_id=result["run_id"],
            goal=f"Approved Smoke Plan on {safe_url}",
            scenario="smoke_test",
            target_origin=safe_url,
            status=result["status"],
            duration_ms=result["duration_ms"],
            mode="planned",
            http_status=result.get("http_status"),
            page_title=result.get("page_title"),
            has_body_content=result.get("has_body_content", True),
            error_message=result.get("error_message"),
            screenshot_path=result.get("screenshot_path"),
            limitation_note=result.get("limitation_note"),
        )
        record_agent_run(
            scenario="smoke_test",
            status=result["status"],
            duration_seconds=result["duration_ms"] / 1000.0,
            iterations=1,
        )
        return result

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported scenario execution requested: '{request.scenario_id}'."
    )


@app.post(
    "/api/agent/loop/run",
    response_model=AgentExecutionResult,
    summary="Run Bounded Observe-Act-Evaluate Agent Loop",
    description="Executes a live closed-loop agent: observes DOM, queries LLM for single next action, executes via Playwright, and evaluates deterministic assertions."
)
async def run_loop(request: AgentLoopRequest):
    """
    Stage 5 dynamic agent loop execution endpoint.
    Performs closed-loop browser testing step by step with strict tool bounding.
    """
    if not request.goal.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Testing goal cannot be empty."
        )
    result = await run_agent_loop(goal=request.goal, max_iterations=request.max_iterations)
    save_test_run(
        run_id=result.run_id,
        goal=result.goal,
        scenario="observe_act_evaluate_loop",
        target_origin="https://www.saucedemo.com/",
        status=result.status,
        duration_ms=result.duration_ms,
        mode="agent_loop",
        provider=result.provider,
        model=result.model,
        http_status=200,
        page_title="Swag Labs",
        has_body_content=True,
        error_message=None if result.status == "passed" else result.deterministic_verdict,
        deterministic_verdict=result.deterministic_verdict,
        screenshot_path=result.screenshot_path,
        total_iterations=result.total_iterations,
        action_trace=[s.model_dump() for s in result.steps],
        limitation_note=f"Autonomous Agent Loop via {result.provider} ({result.model})",
        recovery_attempts=result.recovery_attempts,
        llm_errors_count=result.llm_errors_count,
        action_failures_count=result.action_failures_count,
        error_category=result.error_category,
    )
    return result


@app.post(
    "/api/tests/run",
    summary="Run a test scenario (direct execution)",
    description=(
        "Accepts a test target and scenario type. Executes Playwright browser automation "
        "for generic smoke testing or predefined deterministic workflows like SauceDemo login. "
        "Returns genuine pass/fail based on real DOM and navigation assertions."
    ),
)
async def run_test(request: TestRunRequest):
    """
    Main test execution endpoint.

    Scenarios:
      - 'saucedemo_login': Executes multi-step login workflow on https://www.saucedemo.com/
      - 'smoke' (default): Generic smoke test verifying HTTP status, title, and body content.
    """
    # ── Branch 1: SauceDemo Deterministic Login Scenario ──────────────────────
    if request.scenario == "saucedemo_login":
        # Ensure the fixed practice target passes standard URL safety validation
        try:
            validate_url("https://www.saucedemo.com/")
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        # Execute deterministic login workflow
        result = await run_saucedemo_login_test()
        save_test_run(
            run_id=result["run_id"],
            goal=request.instruction or "Direct SauceDemo Login Workflow",
            scenario="saucedemo_login",
            target_origin="https://www.saucedemo.com/",
            status=result["status"],
            duration_ms=result["duration_ms"],
            mode="direct",
            http_status=result.get("http_status"),
            page_title=result.get("page_title"),
            has_body_content=result.get("has_body_content", True),
            error_message=result.get("error_message"),
            screenshot_path=result.get("screenshot_path"),
            limitation_note=result.get("limitation_note"),
        )
        record_agent_run(
            scenario="saucedemo_login",
            status=result["status"],
            duration_seconds=result["duration_ms"] / 1000.0,
            iterations=1,
        )
        return result

    # ── Branch 2: Standard Smoke Test ─────────────────────────────────────────
    try:
        safe_url = validate_url(request.url)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    result = await run_smoke_test(safe_url)
    save_test_run(
        run_id=result["run_id"],
        goal=request.instruction or f"Direct Smoke Test on {safe_url}",
        scenario="smoke_test",
        target_origin=safe_url,
        status=result["status"],
        duration_ms=result["duration_ms"],
        mode="direct",
        http_status=result.get("http_status"),
        page_title=result.get("page_title"),
        has_body_content=result.get("has_body_content", True),
        error_message=result.get("error_message"),
        screenshot_path=result.get("screenshot_path"),
        limitation_note=result.get("limitation_note"),
    )
    record_agent_run(
        scenario="smoke_test",
        status=result["status"],
        duration_seconds=result["duration_ms"] / 1000.0,
        iterations=1,
    )
    return result


# ── History & Reports Endpoints (Stage 6A Persistence) ─────────────────────────

@app.get(
    "/api/runs",
    summary="Get paginated real test runs history",
    description="Fetches persistent test execution records from SQLite database.",
)
async def get_runs(limit: int = 50, offset: int = 0, status: str | None = None):
    runs, total = query_test_runs(limit=limit, offset=offset, status_filter=status)
    return {"items": runs, "total": total, "limit": limit, "offset": offset}


@app.get(
    "/api/runs/{run_id}",
    summary="Get detailed test run record by ID",
    description="Returns single persistent run with action trace and assertion diagnostics.",
)
async def get_run(run_id: str):
    record = get_test_run_by_id(run_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test run '{run_id}' not found.",
        )
    return record


@app.get(
    "/api/reports/summary",
    summary="Get real aggregate test reports",
    description="Computes aggregate metrics, pass rate, failure counts, and scenario breakdowns directly from SQLite records.",
)
async def get_reports_summary():
    return calculate_reports_summary()
