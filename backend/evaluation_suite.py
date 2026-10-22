"""
evaluation_suite.py
─────────────────────────────────────────────────────────────────────────────
ProbeQA Repeatable Agent Evaluation Suite (Stage 6B).

Evaluates the autonomous agent across 4 core test scenarios:
  1. Standard User Login & Inventory Verification (SauceDemo)
  2. Locked-Out User Error Banner Verification (SauceDemo)
  3. Invalid Credentials Error Banner Verification (SauceDemo)
  4. Direct Origin Reachability & Smoke Verification (SauceDemo)

CAPABILITIES:
  - Deterministic Mock Mode: Fast, cost-free regression testing without network
    or API token dependency.
  - Live Execution Mode: Runs full Playwright browser automation with real LLM
    providers (Groq / Gemini) and live assertions.
  - Telemetry & Reliability Metrics: Computes Task Success Rate (%), average
    duration, recovery attempts, error category breakdown, and assertion audits.
"""

import argparse
import asyncio
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent))

from agent_loop import (
    AgentActionDecision,
    AgentExecutionResult,
    BrowserObservation,
    ErrorCategory,
    StepRecord,
    evaluate_deterministic_outcome,
    run_agent_loop,
)
from database import init_db, save_test_run
from runner import run_saucedemo_login_test, run_smoke_test


EVAL_SCENARIOS = [
    {
        "id": "standard_login",
        "name": "Standard User Login & Inventory Check",
        "type": "agent_loop",
        "goal": "Verify that standard_user logs in successfully and sees 6 inventory products",
        "expected_status": "passed",
    },
    {
        "id": "locked_out_user",
        "name": "Locked-Out User Error Banner Check",
        "type": "agent_loop",
        "goal": "Verify that locked_out_user receives a user lockout error message",
        "expected_status": "passed",
    },
    {
        "id": "invalid_credentials",
        "name": "Invalid Credentials Error Banner Check",
        "type": "agent_loop",
        "goal": "Verify that invalid_user receives a credentials mismatch error",
        "expected_status": "passed",
    },
    {
        "id": "smoke_test",
        "name": "Direct Origin Reachability & Title Smoke Test",
        "type": "smoke",
        "goal": "Verify reachability, HTTP 200, and Swag Labs title on https://www.saucedemo.com/",
        "expected_status": "passed",
    },
]


async def run_mock_agent_scenario(scenario: Dict[str, Any]) -> AgentExecutionResult:
    """
    Executes a deterministic mock evaluation for unit testing and CI.
    Simulates observation steps, recovery handling, and deterministic outcome evaluation.
    """
    start_mono = time.monotonic()
    goal = scenario["goal"]
    lower_goal = goal.lower()
    run_id = f"mock_{int(time.time() * 1000) % 1000000}"

    steps: List[StepRecord] = []
    recovery_attempts = 0
    action_failures_count = 0
    llm_errors_count = 0
    error_category = None

    # Step 1: Simulated Navigation
    obs1 = BrowserObservation(
        current_url="about:blank",
        page_title="",
        is_approved_origin=False,
        available_elements={},
        visible_text_summary="",
    )
    dec1 = AgentActionDecision(
        thought="Browser is blank. Navigating to SauceDemo origin.",
        action_type="navigate",
        target="https://www.saucedemo.com/",
    )
    steps.append(
        StepRecord(
            iteration=1,
            observation_before=obs1,
            decision=dec1,
            action_result="Navigated to https://www.saucedemo.com/ (status: 200)",
            is_success=True,
            duration_ms=45,
        )
    )

    # Step 2: Simulated Form Filling
    obs2 = BrowserObservation(
        current_url="https://www.saucedemo.com/",
        page_title="Swag Labs",
        is_approved_origin=True,
        available_elements={"username_input": True, "password_input": True, "login_button": True},
        visible_text_summary="Accepted usernames are: standard_user, locked_out_user",
    )

    if "locked" in lower_goal:
        user = "locked_out_user"
    elif "invalid" in lower_goal:
        user = "invalid_user"
    else:
        user = "standard_user"

    dec2 = AgentActionDecision(
        thought=f"Filling username with {user}",
        action_type="fill",
        target="username_input",
        value=user,
    )
    steps.append(
        StepRecord(
            iteration=2,
            observation_before=obs2,
            decision=dec2,
            action_result=f"Filled element 'username_input' with preset value.",
            is_success=True,
            duration_ms=25,
        )
    )

    # Step 3: Simulated Password Filling
    dec3 = AgentActionDecision(
        thought="Filling password with secret_sauce",
        action_type="fill",
        target="password_input",
        value="secret_sauce",
    )
    steps.append(
        StepRecord(
            iteration=3,
            observation_before=obs2,
            decision=dec3,
            action_result="Filled element 'password_input' with preset value.",
            is_success=True,
            duration_ms=20,
        )
    )

    # Step 4: Simulated Click
    dec4 = AgentActionDecision(
        thought="Clicking login button",
        action_type="click",
        target="login_button",
    )
    steps.append(
        StepRecord(
            iteration=4,
            observation_before=obs2,
            decision=dec4,
            action_result="Clicked element 'login_button'.",
            is_success=True,
            duration_ms=30,
        )
    )

    # Final observation simulation based on scenario
    if "locked" in lower_goal:
        final_obs = BrowserObservation(
            current_url="https://www.saucedemo.com/",
            page_title="Swag Labs",
            is_approved_origin=True,
            available_elements={"login_error": True},
            visible_text_summary="Epic sadface: Sorry, this user has been locked out.",
            error_banner_text="Epic sadface: Sorry, this user has been locked out.",
            inventory_items_count=0,
        )
        assertions = [
            "URL must remain on https://www.saucedemo.com/",
            "Error container [data-test='error'] must be visible in DOM",
            "Error message text must contain 'locked out'",
        ]
        status = "passed"
        verdict = "Ground-truth verified: Error banner 'Epic sadface: Sorry, this user has been locked out.' is displayed."
    elif "invalid" in lower_goal:
        final_obs = BrowserObservation(
            current_url="https://www.saucedemo.com/",
            page_title="Swag Labs",
            is_approved_origin=True,
            available_elements={"login_error": True},
            visible_text_summary="Epic sadface: Username and password do not match any user in this service",
            error_banner_text="Epic sadface: Username and password do not match any user in this service",
            inventory_items_count=0,
        )
        assertions = [
            "URL must remain on https://www.saucedemo.com/",
            "Error container [data-test='error'] must be visible in DOM",
            "Error message text must indicate credentials do not match",
        ]
        status = "passed"
        verdict = "Ground-truth verified: Error banner 'Epic sadface: Username and password do not match' is displayed."
    else:
        final_obs = BrowserObservation(
            current_url="https://www.saucedemo.com/inventory.html",
            page_title="Swag Labs",
            is_approved_origin=True,
            available_elements={"inventory_items": True},
            visible_text_summary="Products: Sauce Labs Backpack, Bike Light, Bolt T-Shirt...",
            inventory_items_count=6,
        )
        assertions = [
            "URL must transition to https://www.saucedemo.com/inventory.html",
            "Inventory items (.inventory_item) count must equal exactly 6",
            "No error banner must be visible",
        ]
        status = "passed"
        verdict = "Ground-truth verified: Reached /inventory.html with exactly 6 products."

    elapsed_ms = int((time.monotonic() - start_mono) * 1000)

    return AgentExecutionResult(
        run_id=run_id,
        goal=goal,
        status=status,
        task_success=True,
        total_iterations=len(steps),
        steps=steps,
        assertions_evaluated=assertions,
        deterministic_verdict=verdict,
        screenshot_path=f"evidence/mock_{run_id}.png",
        duration_ms=elapsed_ms,
        provider="mock_evaluator",
        model="deterministic-mock",
        timestamp=datetime.now(timezone.utc).isoformat(),
        recovery_attempts=recovery_attempts,
        llm_errors_count=llm_errors_count,
        action_failures_count=action_failures_count,
        error_category=error_category,
        expected_assertion_passed=True,
    )


async def execute_evaluation_suite(
    mode: str = "mock",
    persist: bool = True,
) -> Dict[str, Any]:
    """
    Runs the complete evaluation suite across all 4 scenarios.
    Returns structured metrics summary.
    """
    print(f"\n=======================================================")
    print(f"  PROBEQA AGENT EVALUATION SUITE (Mode: {mode.upper()})")
    print(f"=======================================================")

    results: List[Dict[str, Any]] = []
    total_start = time.monotonic()

    for idx, sc in enumerate(EVAL_SCENARIOS, 1):
        print(f"\n[{idx}/4] Evaluating: {sc['name']}...")
        run_start = time.monotonic()

        if sc["type"] == "smoke":
            # Direct smoke test evaluation
            smoke_res = await run_smoke_test("https://www.saucedemo.com/")
            is_pass = (smoke_res["status"] == "passed")
            duration_ms = smoke_res["duration_ms"]
            status = smoke_res["status"]
            verdict = smoke_res.get("error_message") or "Ground-truth verified: HTTP 200, title Swag Labs, body present."

            res_entry = {
                "scenario_id": sc["id"],
                "name": sc["name"],
                "type": "smoke",
                "status": status,
                "task_success": is_pass,
                "duration_ms": duration_ms,
                "iterations": 1,
                "recovery_attempts": 0,
                "llm_errors_count": 0,
                "action_failures_count": 0,
                "error_category": None if is_pass else "SMOKE_FAILURE",
                "verdict": verdict,
            }

            if persist:
                save_test_run(
                    run_id=smoke_res["run_id"],
                    goal=sc["goal"],
                    scenario="smoke_test",
                    target_origin="https://www.saucedemo.com/",
                    status=status,
                    duration_ms=duration_ms,
                    mode="planned",
                    http_status=smoke_res.get("http_status", 200),
                    page_title=smoke_res.get("page_title"),
                    has_body_content=smoke_res.get("has_body_content", True),
                    deterministic_verdict=verdict,
                    screenshot_path=smoke_res.get("screenshot_path"),
                    limitation_note="Evaluation Suite: Smoke Scenario",
                )

        else:
            # Agent loop evaluation (Mock or Live)
            if mode == "mock":
                agent_res = await run_mock_agent_scenario(sc)
            else:
                agent_res = await run_agent_loop(goal=sc["goal"], max_iterations=8)

            is_pass = (agent_res.status == "passed")
            res_entry = {
                "scenario_id": sc["id"],
                "name": sc["name"],
                "type": "agent_loop",
                "status": agent_res.status,
                "task_success": agent_res.task_success,
                "duration_ms": agent_res.duration_ms,
                "iterations": agent_res.total_iterations,
                "recovery_attempts": agent_res.recovery_attempts,
                "llm_errors_count": agent_res.llm_errors_count,
                "action_failures_count": agent_res.action_failures_count,
                "error_category": agent_res.error_category,
                "verdict": agent_res.deterministic_verdict,
            }

            if persist:
                save_test_run(
                    run_id=agent_res.run_id,
                    goal=agent_res.goal,
                    scenario=sc["id"],
                    target_origin="https://www.saucedemo.com/",
                    status=agent_res.status,
                    duration_ms=agent_res.duration_ms,
                    mode="agent_loop",
                    provider=agent_res.provider,
                    model=agent_res.model,
                    http_status=200,
                    page_title="Swag Labs",
                    has_body_content=True,
                    error_message=None if is_pass else agent_res.deterministic_verdict,
                    deterministic_verdict=agent_res.deterministic_verdict,
                    screenshot_path=agent_res.screenshot_path,
                    total_iterations=agent_res.total_iterations,
                    action_trace=[s.model_dump() for s in agent_res.steps],
                    limitation_note=f"Evaluation Suite ({mode.upper()} mode)",
                    recovery_attempts=agent_res.recovery_attempts,
                    llm_errors_count=agent_res.llm_errors_count,
                    action_failures_count=agent_res.action_failures_count,
                    error_category=agent_res.error_category,
                )

        status_flag = "[PASS]" if res_entry["task_success"] else "[FAIL]"
        print(f"  {status_flag} {res_entry['name']}: {res_entry['status']} ({res_entry['duration_ms']}ms, {res_entry['iterations']} iters)")
        print(f"         Verdict: {res_entry['verdict']}")
        results.append(res_entry)

    # ── Summary Calculations ──
    total_runs = len(results)
    passed_runs = sum(1 for r in results if r["task_success"])
    failed_runs = total_runs - passed_runs
    task_success_rate = (passed_runs / total_runs * 100.0) if total_runs > 0 else 0.0
    avg_duration_ms = sum(r["duration_ms"] for r in results) / total_runs if total_runs > 0 else 0.0
    total_recoveries = sum(r["recovery_attempts"] for r in results)
    total_llm_errors = sum(r["llm_errors_count"] for r in results)
    total_action_failures = sum(r["action_failures_count"] for r in results)

    error_breakdown: Dict[str, int] = {}
    for r in results:
        cat = r["error_category"]
        if cat:
            error_breakdown[cat] = error_breakdown.get(cat, 0) + 1

    summary = {
        "mode": mode,
        "total_runs": total_runs,
        "passed_runs": passed_runs,
        "failed_runs": failed_runs,
        "task_success_rate_percent": round(task_success_rate, 2),
        "avg_duration_ms": int(avg_duration_ms),
        "total_recovery_attempts": total_recoveries,
        "total_llm_errors": total_llm_errors,
        "total_action_failures": total_action_failures,
        "error_breakdown": error_breakdown,
        "results": results,
    }

    # Print Summary Table
    print("\n" + "=" * 55)
    print("           EVALUATION SUITE SUMMARY REPORT")
    print("=" * 55)
    print(f"  Execution Mode       : {mode.upper()}")
    print(f"  Total Scenarios      : {total_runs}")
    print(f"  Passed Scenarios     : {passed_runs}")
    print(f"  Failed Scenarios     : {failed_runs}")
    print(f"  Task Success Rate    : {summary['task_success_rate_percent']}%")
    print(f"  Average Duration     : {summary['avg_duration_ms']} ms")
    print(f"  Total Recoveries     : {total_recoveries}")
    print(f"  Total LLM API Errors : {total_llm_errors}")
    print(f"  Total Action Failures: {total_action_failures}")
    if error_breakdown:
        print(f"  Error Breakdown      : {error_breakdown}")
    else:
        print(f"  Error Breakdown      : None (Clean Run)")
    print("=" * 55 + "\n")

    return summary


def main():
    parser = argparse.ArgumentParser(description="ProbeQA Agent Evaluation Suite")
    parser.add_argument(
        "--mode",
        choices=["mock", "live"],
        default="mock",
        help="Evaluation mode: 'mock' (deterministic offline) or 'live' (real Playwright + LLM)",
    )
    parser.add_argument(
        "--persist",
        action="store_true",
        default=True,
        help="Persist evaluation runs to SQLite database probeqa.db",
    )
    args = parser.parse_args()

    asyncio.run(execute_evaluation_suite(mode=args.mode, persist=args.persist))


if __name__ == "__main__":
    main()
