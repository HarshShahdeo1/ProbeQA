"""
test_metrics.py
─────────────────────────────────────────────────────────────────────────────
Comprehensive Test Suite for ProbeQA Stage 7A Prometheus Instrumentation.

Validates:
  1. /metrics exposition format and HTTP 200 response.
  2. Recursive scrape exclusion (calls to /metrics do not self-increment HTTP counter).
  3. HTTP request counter and latency histogram updating on real API endpoints.
  4. Label normalization against route templates (preventing cardinality explosion on IDs).
  5. Agent run counters (passed vs. failed runs) and duration/iteration distributions.
  6. Recovery attempt counters labeled by error category.
  7. LLM inference request counters and latency histograms.
  8. Active agent runs gauge lifecycle (increment on start, decrement on completion).
"""

import os
import sys
import time
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent))

from starlette.testclient import TestClient
from main import app
from metrics import (
    record_agent_run,
    record_recovery_attempt,
    record_llm_request,
    track_active_agent_run,
    AGENT_ACTIVE_RUNS,
)


def test_metrics_endpoint_exposition():
    print("\n--- TEST 1: /metrics Endpoint Exposition & Self-Scrape Exclusion ---")
    client = TestClient(app)

    # Scrape metrics
    resp = client.get("/metrics")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    assert "text/plain" in resp.headers["content-type"]
    text = resp.text

    # Verify standard metric definitions are present
    assert "# TYPE probeqa_http_requests_total counter" in text
    assert "# TYPE probeqa_http_request_duration_seconds histogram" in text
    assert "# TYPE probeqa_agent_runs_total counter" in text
    assert "# TYPE probeqa_agent_run_duration_seconds histogram" in text
    assert "# TYPE probeqa_agent_iterations histogram" in text
    assert "# TYPE probeqa_agent_recovery_attempts_total counter" in text
    assert "# TYPE probeqa_agent_active_runs gauge" in text
    assert "# TYPE probeqa_llm_requests_total counter" in text
    assert "# TYPE probeqa_llm_request_duration_seconds histogram" in text

    # Verify self-scrape exclusion: /metrics itself must NOT be in probeqa_http_requests_total
    for line in text.splitlines():
        if "probeqa_http_requests_total" in line and not line.startswith("#"):
            assert 'endpoint="/metrics"' not in line, "Self-scraping /metrics was erroneously recorded in HTTP counter"

    print("  [PASS] /metrics returned valid Prometheus text format.")
    print("  [PASS] Self-scrape exclusion verified: /metrics excluded from HTTP counter.")


def test_http_requests_and_latency_metric():
    print("\n--- TEST 2: HTTP Request Counter and Latency Histogram Tracking ---")
    client = TestClient(app)

    # Call /health 3 times
    client.get("/health")
    client.get("/health")
    client.get("/health")

    # Scrape metrics
    resp = client.get("/metrics")
    text = resp.text

    # Check that GET /health status 200 is recorded with value >= 3.0
    found_health = False
    for line in text.splitlines():
        if 'probeqa_http_requests_total{endpoint="/health",method="GET",status_code="200"}' in line:
            val = float(line.split()[-1])
            assert val >= 3.0, f"Expected >= 3.0, got {val}"
            found_health = True
            break
    assert found_health, "Could not find HTTP request counter for /health"

    # Check duration histogram presence
    assert 'probeqa_http_request_duration_seconds_count{endpoint="/health",method="GET"}' in text
    print("  [PASS] probeqa_http_requests_total correctly incremented for /health.")
    print("  [PASS] probeqa_http_request_duration_seconds histogram observed request latency.")


def test_route_normalization_cardinality_safety():
    print("\n--- TEST 3: Route Path Normalization (Cardinality Protection) ---")
    client = TestClient(app)

    # Call /api/runs with dynamic non-existent IDs
    client.get("/api/runs/dynamic_run_id_001")
    client.get("/api/runs/dynamic_run_id_002")

    resp = client.get("/metrics")
    text = resp.text

    # Ensure dynamic IDs do NOT appear as raw label values
    assert "dynamic_run_id_001" not in text, "Dynamic run ID leaked into Prometheus label!"
    assert "dynamic_run_id_002" not in text, "Dynamic run ID leaked into Prometheus label!"

    # Ensure normalized template /api/runs/{run_id} is used
    found_normalized = any(
        'probeqa_http_requests_total{endpoint="/api/runs/{run_id}",method="GET",status_code="404"}' in line
        for line in text.splitlines()
    )
    assert found_normalized, "Route template /api/runs/{run_id} was not used as metric label"
    print("  [PASS] Dynamic run IDs normalized to '/api/runs/{run_id}' preventing cardinality explosion.")


def test_agent_runs_metrics_success_and_failure():
    print("\n--- TEST 4: Agent Run Metrics (Passed vs Failed & Durations) ---")
    scenario_name = "test_eval_scenario"

    # Record 1 passed run and 1 failed run
    record_agent_run(scenario=scenario_name, status="passed", duration_seconds=2.45, iterations=5)
    record_agent_run(scenario=scenario_name, status="failed", duration_seconds=1.10, iterations=3)

    client = TestClient(app)
    resp = client.get("/metrics")
    text = resp.text

    # Verify passed and failed counter series
    passed_line = any(
        f'probeqa_agent_runs_total{{scenario="{scenario_name}",status="passed"}}' in line
        for line in text.splitlines()
    )
    failed_line = any(
        f'probeqa_agent_runs_total{{scenario="{scenario_name}",status="failed"}}' in line
        for line in text.splitlines()
    )
    assert passed_line, f"Passed run counter for {scenario_name} not found"
    assert failed_line, f"Failed run counter for {scenario_name} not found"

    # Verify duration and iteration histograms
    assert f'probeqa_agent_run_duration_seconds_count{{scenario="{scenario_name}"}}' in text
    assert f'probeqa_agent_iterations_count{{scenario="{scenario_name}"}}' in text

    print(f"  [PASS] Recorded passed and failed agent runs for scenario '{scenario_name}'.")
    print(f"  [PASS] Agent duration and iterations histograms accurately updated.")


def test_recovery_and_llm_metrics():
    print("\n--- TEST 5: Recovery Attempts and LLM Request Metrics ---")

    # Record recovery attempts
    record_recovery_attempt("MISSING_ELEMENT")
    record_recovery_attempt("BROWSER_TIMEOUT")

    # Record LLM requests across providers
    record_llm_request(provider="groq", outcome="success", duration_seconds=0.35)
    record_llm_request(provider="groq", outcome="transient_error", duration_seconds=0.12)
    record_llm_request(provider="gemini", outcome="success", duration_seconds=0.78)

    client = TestClient(app)
    resp = client.get("/metrics")
    text = resp.text

    # Verify recovery attempts
    assert 'probeqa_agent_recovery_attempts_total{error_category="MISSING_ELEMENT"}' in text
    assert 'probeqa_agent_recovery_attempts_total{error_category="BROWSER_TIMEOUT"}' in text

    # Verify LLM request counters & histograms
    assert 'probeqa_llm_requests_total{outcome="success",provider="groq"}' in text
    assert 'probeqa_llm_requests_total{outcome="transient_error",provider="groq"}' in text
    assert 'probeqa_llm_requests_total{outcome="success",provider="gemini"}' in text
    assert 'probeqa_llm_request_duration_seconds_count{provider="groq"}' in text
    assert 'probeqa_llm_request_duration_seconds_count{provider="gemini"}' in text

    print("  [PASS] Safe recovery counters accurately recorded error categories.")
    print("  [PASS] LLM inference counters and latency histograms recorded across providers.")


def test_active_agent_runs_gauge():
    print("\n--- TEST 6: Active Agent Runs Gauge Lifecycle ---")
    scenario = "gauge_test_scenario"

    # Gauge starts at 0 before execution
    val_before = AGENT_ACTIVE_RUNS.labels(scenario=scenario)._value.get()
    assert val_before == 0.0

    # Inside context manager, gauge should be 1
    with track_active_agent_run(scenario):
        val_during = AGENT_ACTIVE_RUNS.labels(scenario=scenario)._value.get()
        assert val_during == 1.0, f"Expected 1.0 active runs, got {val_during}"

    # After exit, gauge should return cleanly to 0
    val_after = AGENT_ACTIVE_RUNS.labels(scenario=scenario)._value.get()
    assert val_after == 0.0, f"Expected gauge to reset to 0.0, got {val_after}"

    print(f"  [PASS] probeqa_agent_active_runs gauge incremented to 1.0 during execution and reset to 0.0 on completion.")


def main():
    test_metrics_endpoint_exposition()
    test_http_requests_and_latency_metric()
    test_route_normalization_cardinality_safety()
    test_agent_runs_metrics_success_and_failure()
    test_recovery_and_llm_metrics()
    test_active_agent_runs_gauge()
    print("\n=== ALL PROMETHEUS INSTRUMENTATION TESTS PASSED ===")


if __name__ == "__main__":
    main()
