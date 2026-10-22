"""
metrics.py
─────────────────────────────────────────────────────────────────────────────
Prometheus Instrumentation & Observability Registry for ProbeQA (Stage 7A).

METRIC TYPES & DEV-OPS PRINCIPLES:
  1. Counter: A monotonically increasing cumulative value (e.g., total requests,
     total runs, recovery attempts). Used with rate() or increase() in PromQL.
  2. Gauge: A numerical value that can go up or down, reflecting current live state
     (e.g., currently executing agent runs, memory, concurrent tasks).
  3. Histogram: Samples observations (usually request durations or step counts)
     and counts them in configurable buckets. Essential for percentile latencies
     (p50, p90, p99) using histogram_quantile().

CARDINALITY & PRIVACY SAFEGUARDS:
  - Bounded labels only: Labels must never contain dynamic user IDs, passwords,
    full URLs, user prompts, arbitrary query params, or stack traces.
  - Strict route templating: HTTP endpoints are normalized (e.g. /api/runs/{run_id}
    instead of /api/runs/f3a8c1) to prevent memory exhaustion in Prometheus TSDB.
"""

import time
from contextlib import contextmanager
from typing import Generator

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    REGISTRY,
    generate_latest,
)

# ── 1. HTTP Request Metrics ───────────────────────────────────────────────────

HTTP_REQUESTS_TOTAL = Counter(
    "probeqa_http_requests_total",
    "Total count of HTTP requests processed by ProbeQA.",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "probeqa_http_request_duration_seconds",
    "Histogram of HTTP request processing duration in seconds.",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

# ── 2. Agent Execution Metrics ────────────────────────────────────────────────

AGENT_RUNS_TOTAL = Counter(
    "probeqa_agent_runs_total",
    "Total count of completed browser test runs and agent loop executions.",
    ["scenario", "status"],
)

AGENT_RUN_DURATION_SECONDS = Histogram(
    "probeqa_agent_run_duration_seconds",
    "Histogram of total agent execution duration in seconds.",
    ["scenario"],
    buckets=(0.5, 1.0, 2.0, 3.5, 5.0, 7.5, 10.0, 15.0, 20.0, 30.0, 60.0),
)

AGENT_ITERATIONS = Histogram(
    "probeqa_agent_iterations",
    "Distribution of iteration counts taken by agent runs.",
    ["scenario"],
    buckets=(1, 2, 3, 4, 5, 6, 7, 8, 10, 12),
)

AGENT_RECOVERY_ATTEMPTS_TOTAL = Counter(
    "probeqa_agent_recovery_attempts_total",
    "Total count of safe recovery actions triggered during agent loops.",
    ["error_category"],
)

AGENT_ACTIVE_RUNS = Gauge(
    "probeqa_agent_active_runs",
    "Gauge of currently executing agent runs in progress.",
    ["scenario"],
)

# ── 3. LLM API Telemetry Metrics ──────────────────────────────────────────────

LLM_REQUESTS_TOTAL = Counter(
    "probeqa_llm_requests_total",
    "Total count of LLM API requests made for planning and single-step decisions.",
    ["provider", "outcome"],
)

LLM_REQUEST_DURATION_SECONDS = Histogram(
    "probeqa_llm_request_duration_seconds",
    "Histogram of latency for LLM inference requests in seconds.",
    ["provider"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 15.0, 20.0),
)


# ── Helper Recording Functions (Fail-Safe) ────────────────────────────────────

def record_http_request(method: str, endpoint: str, status_code: str, duration_seconds: float) -> None:
    """Safely increments HTTP request counter and records duration in histogram."""
    try:
        HTTP_REQUESTS_TOTAL.labels(
            method=method.upper(),
            endpoint=endpoint,
            status_code=str(status_code),
        ).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(
            method=method.upper(),
            endpoint=endpoint,
        ).observe(max(0.0, duration_seconds))
    except Exception:
        pass


def record_agent_run(scenario: str, status: str, duration_seconds: float, iterations: int = 1) -> None:
    """Safely records a completed agent or scenario execution."""
    try:
        norm_scenario = scenario or "unknown"
        norm_status = status or "error"
        AGENT_RUNS_TOTAL.labels(scenario=norm_scenario, status=norm_status).inc()
        AGENT_RUN_DURATION_SECONDS.labels(scenario=norm_scenario).observe(max(0.0, duration_seconds))
        AGENT_ITERATIONS.labels(scenario=norm_scenario).observe(max(1, iterations))
    except Exception:
        pass


def record_recovery_attempt(error_category: str) -> None:
    """Safely increments recovery attempt counter labeled by error category."""
    try:
        norm_category = error_category or "UNKNOWN_ERROR"
        AGENT_RECOVERY_ATTEMPTS_TOTAL.labels(error_category=norm_category).inc()
    except Exception:
        pass


def record_llm_request(provider: str, outcome: str, duration_seconds: float) -> None:
    """Safely records an LLM inference API call, outcome, and duration."""
    try:
        norm_provider = provider or "unknown"
        norm_outcome = outcome or "unknown"
        LLM_REQUESTS_TOTAL.labels(provider=norm_provider, outcome=norm_outcome).inc()
        LLM_REQUEST_DURATION_SECONDS.labels(provider=norm_provider).observe(max(0.0, duration_seconds))
    except Exception:
        pass


@contextmanager
def track_active_agent_run(scenario: str) -> Generator[None, None, None]:
    """
    Context manager that increments probeqa_agent_active_runs upon entry
    and decrements it upon exit, ensuring clean Gauge tracking even if exceptions occur.
    """
    norm_scenario = scenario or "unknown"
    try:
        AGENT_ACTIVE_RUNS.labels(scenario=norm_scenario).inc()
    except Exception:
        pass

    try:
        yield
    finally:
        try:
            AGENT_ACTIVE_RUNS.labels(scenario=norm_scenario).dec()
        except Exception:
            pass


def get_metrics_payload() -> tuple[bytes, str]:
    """Returns the formatted Prometheus metrics text exposition and Content-Type header."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
