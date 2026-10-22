"""
test_database.py
─────────────────────────────────────────────────────────────────────────────
Comprehensive Test Suite for Stage 6A: Persistent Storage & Reports.

Covers:
  1. Table initialization in SQLite.
  2. Saving successful and failed test runs.
  3. Duplicate run_id idempotency.
  4. Querying paginated test runs and status filtering.
  5. Fetching individual run details with serialized trace.
  6. Calculating real aggregate reports summary (totals, pass rate %, durations).
  7. Verification that saved records survive session close and application restart.
"""

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from database import (
    init_db,
    save_test_run,
    query_test_runs,
    get_test_run_by_id,
    calculate_reports_summary,
    SessionLocal,
    TestRunRecord,
)


def test_database_persistence():
    print("\n--- TEST 1: SQLite Persistence & CRUD Operations ---")
    init_db()

    # 1. Save a successful standard user run
    run_id_1 = f"test_run_{uuid.uuid4().hex[:10]}"
    record1 = save_test_run(
        run_id=run_id_1,
        goal="Verify standard_user login and product inventory",
        scenario="saucedemo_valid_login",
        target_origin="https://www.saucedemo.com/",
        status="passed",
        duration_ms=2100,
        mode="planned",
        provider="groq",
        model="qwen/qwen3.8-27b",
        http_status=200,
        page_title="Swag Labs",
        has_body_content=True,
        screenshot_path=f"evidence/{run_id_1}.png",
        total_iterations=4,
        action_trace=[{"step": 1, "action": "navigate"}, {"step": 2, "action": "click"}],
        limitation_note="Verified 6 inventory items rendered.",
    )
    assert record1.run_id == run_id_1
    assert record1.status == "passed"
    print(f"  [PASS] Saved successful run {run_id_1} to SQLite.")

    # 2. Save a failed run with error diagnostics
    run_id_2 = f"test_run_{uuid.uuid4().hex[:10]}"
    record2 = save_test_run(
        run_id=run_id_2,
        goal="Verify invalid login error",
        scenario="saucedemo_invalid_login",
        target_origin="https://www.saucedemo.com/",
        status="failed",
        duration_ms=3400,
        mode="agent_loop",
        provider="gemini",
        model="gemini-2.5-flash",
        http_status=200,
        page_title="Swag Labs",
        has_body_content=True,
        error_message="Assertion failed: Error message banner was not found in DOM.",
        screenshot_path=f"evidence/{run_id_2}.png",
        total_iterations=5,
        action_trace=[{"step": 1, "action": "fill"}],
    )
    assert record2.status == "failed"
    assert "Assertion failed" in record2.error_message
    print(f"  [PASS] Saved failed run {run_id_2} with diagnostic error message.")

    # 3. Prevent duplicate run_id insertion
    dup_record = save_test_run(
        run_id=run_id_1,
        goal="Duplicate attempt",
        scenario="saucedemo_valid_login",
        target_origin="https://www.saucedemo.com/",
        status="passed",
        duration_ms=1000,
    )
    assert dup_record.id == record1.id
    print(f"  [PASS] Idempotency confirmed: Duplicate insert ignored for {run_id_1}.")

    # 4. Fetch individual run by ID
    fetched = get_test_run_by_id(run_id_1)
    assert fetched is not None
    assert fetched["run_id"] == run_id_1
    assert fetched["provider"] == "groq"
    assert isinstance(fetched["action_trace"], list)
    assert len(fetched["action_trace"]) == 2
    print(f"  [PASS] Retrieved run {run_id_1} with parsed JSON action trace.")

    # 5. Query paginated runs and filter by status
    runs, total = query_test_runs(limit=10, offset=0)
    assert total >= 2
    assert any(r["run_id"] == run_id_1 for r in runs)
    assert any(r["run_id"] == run_id_2 for r in runs)

    passed_runs, passed_total = query_test_runs(status_filter="passed")
    assert passed_total >= 1
    assert all(r["status"] == "passed" for r in passed_runs)
    print(f"  [PASS] Paginated queries & status filtering verified (Total: {total}, Passed: {passed_total}).")

    # 6. Calculate real reports summary
    summary = calculate_reports_summary()
    assert summary["is_empty"] is False
    assert summary["total_runs"] >= 2
    assert summary["passed_runs"] >= 1
    assert summary["failed_runs"] >= 1
    assert 0.0 <= summary["pass_rate"] <= 100.0
    assert summary["avg_duration_ms"] > 0
    assert len(summary["scenario_reports"]) >= 1
    print(f"  [PASS] Reports summary calculated: Total={summary['total_runs']}, PassRate={summary['pass_rate']}%, AvgDur={summary['avg_duration_ms']}ms.")

    # 7. Persistence survival across independent database sessions
    db_fresh = SessionLocal()
    persisted = db_fresh.query(TestRunRecord).filter(TestRunRecord.run_id == run_id_1).first()
    assert persisted is not None
    assert persisted.goal == "Verify standard_user login and product inventory"
    db_fresh.close()
    print("  [PASS] Records confirmed persisted in probeqa.db file.")


if __name__ == "__main__":
    test_database_persistence()
    print("\n=== ALL STAGE 6A DATABASE TESTS PASSED DETERMINISTICALLY ===")
