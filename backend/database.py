"""
database.py
─────────────────────────────────────────────────────────────────────────────
Persistent SQLite / SQLAlchemy storage for ProbeQA test runs and reports.

RESPONSIBILITIES:
  1. Manages connection to SQLite (or PostgreSQL via DATABASE_URL).
  2. Defines the TestRunRecord table schema.
  3. Provides transaction-safe persistence for:
     - Direct Playwright smoke tests
     - Registered scenario workflows (SauceDemo valid/invalid/lockout)
     - Stage 5 Observe–Act–Evaluate autonomous agent loops
  4. Keeps credentials, secrets, and raw binaries (screenshots) OUT of the database.
     Screenshots remain as files on disk in backend/evidence/, referenced by path.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    case,
    create_engine,
    desc,
    func,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Load backend/.env reliably
_dotenv_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_dotenv_path)

# Default to local SQLite database in backend/ directory
DEFAULT_DB_PATH = Path(__file__).resolve().parent / "probeqa.db"
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip() or f"sqlite:///{DEFAULT_DB_PATH}"

# For SQLite, check_same_thread=False allows FastAPI background tasks to query the same file
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,  # Set True for SQL debug logs if needed
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── SQLAlchemy Models ─────────────────────────────────────────────────────────

class TestRunRecord(Base):
    """
    Persistent record of an executed test run.
    Stores metadata, assertion results, durations, screenshot path, and full action traces.
    """
    __tablename__ = "test_runs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    run_id = Column(String(64), unique=True, index=True, nullable=False)
    goal = Column(String(500), nullable=False)
    scenario = Column(String(100), index=True, nullable=False)
    target_origin = Column(String(255), nullable=False)
    status = Column(String(20), index=True, nullable=False)  # 'passed', 'failed', 'error'
    mode = Column(String(50), nullable=False, default="direct")  # 'direct', 'planned', 'agent_loop'
    provider = Column(String(50), nullable=True)  # 'groq', 'gemini', 'heuristic_fallback', etc.
    model = Column(String(100), nullable=True)    # e.g. 'qwen/qwen3.8-27b'

    # Timings & Telemetry
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    duration_ms = Column(Integer, nullable=False, default=0)

    # DOM & HTTP Assertions
    http_status = Column(Integer, nullable=True)
    page_title = Column(String(255), nullable=True)
    has_body_content = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    deterministic_verdict = Column(Text, nullable=True)

    # Evidence Reference (Path on disk, not binary blob)
    screenshot_path = Column(String(255), nullable=True)

    # Audit & Trace
    total_iterations = Column(Integer, default=1)
    action_trace = Column(Text, nullable=True)  # Serialized JSON string of StepRecords
    limitation_note = Column(Text, nullable=True)
    is_real = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Stage 6B Reliability & Evaluation Telemetry
    recovery_attempts = Column(Integer, default=0, nullable=False)
    llm_errors_count = Column(Integer, default=0, nullable=False)
    action_failures_count = Column(Integer, default=0, nullable=False)
    error_category = Column(String(50), nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        """Converts model instance to JSON-serializable dictionary."""
        trace_data = None
        if self.action_trace:
            try:
                trace_data = json.loads(self.action_trace)
            except Exception:
                trace_data = self.action_trace

        return {
            "id": self.id,
            "run_id": self.run_id,
            "goal": self.goal,
            "scenario": self.scenario,
            "target_origin": self.target_origin,
            "status": self.status,
            "mode": self.mode,
            "provider": self.provider,
            "model": self.model,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "duration_ms": self.duration_ms,
            "http_status": self.http_status,
            "page_title": self.page_title,
            "has_body_content": self.has_body_content,
            "error_message": self.error_message,
            "deterministic_verdict": self.deterministic_verdict,
            "screenshot_path": self.screenshot_path,
            "total_iterations": self.total_iterations,
            "action_trace": trace_data,
            "limitation_note": self.limitation_note,
            "is_real": self.is_real,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "recovery_attempts": self.recovery_attempts or 0,
            "llm_errors_count": self.llm_errors_count or 0,
            "action_failures_count": self.action_failures_count or 0,
            "error_category": self.error_category,
        }


# ── Database Initialization & Helper Functions ────────────────────────────────

def init_db():
    """Initializes tables in probeqa.db if they do not exist and applies migrations."""
    Base.metadata.create_all(bind=engine)
    # Automatic backward-compatible column addition for SQLite
    if DATABASE_URL.startswith("sqlite"):
        try:
            with engine.connect() as conn:
                from sqlalchemy import text
                result = conn.execute(text("PRAGMA table_info(test_runs)"))
                existing_cols = {row[1] for row in result.fetchall()}
                new_cols = [
                    ("recovery_attempts", "INTEGER DEFAULT 0"),
                    ("llm_errors_count", "INTEGER DEFAULT 0"),
                    ("action_failures_count", "INTEGER DEFAULT 0"),
                    ("error_category", "VARCHAR(50)"),
                ]
                for col_name, col_def in new_cols:
                    if col_name not in existing_cols:
                        conn.execute(text(f"ALTER TABLE test_runs ADD COLUMN {col_name} {col_def}"))
                conn.commit()
        except Exception:
            pass


def get_db():
    """FastAPI Dependency for database session management with automatic cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def save_test_run(
    run_id: str,
    goal: str,
    scenario: str,
    target_origin: str,
    status: str,
    duration_ms: int,
    started_at: Optional[datetime] = None,
    mode: str = "direct",
    provider: Optional[str] = None,
    model: Optional[str] = None,
    http_status: Optional[int] = None,
    page_title: Optional[str] = None,
    has_body_content: bool = True,
    error_message: Optional[str] = None,
    deterministic_verdict: Optional[str] = None,
    screenshot_path: Optional[str] = None,
    total_iterations: int = 1,
    action_trace: Optional[Any] = None,
    limitation_note: Optional[str] = None,
    recovery_attempts: int = 0,
    llm_errors_count: int = 0,
    action_failures_count: int = 0,
    error_category: Optional[str] = None,
) -> TestRunRecord:
    """
    Persists a test run record to SQLite, preventing duplicates and ensuring
    clean rollback on unexpected database errors.
    """
    init_db()
    db: Session = SessionLocal()
    try:
        # Check for existing record to prevent duplicates
        existing = db.query(TestRunRecord).filter(TestRunRecord.run_id == run_id).first()
        if existing:
            return existing

        serialized_trace = None
        if action_trace is not None:
            if isinstance(action_trace, (dict, list)):
                serialized_trace = json.dumps(action_trace)
            else:
                serialized_trace = str(action_trace)

        record = TestRunRecord(
            run_id=run_id,
            goal=goal,
            scenario=scenario,
            target_origin=target_origin,
            status=status,
            mode=mode,
            provider=provider,
            model=model,
            started_at=started_at or datetime.now(timezone.utc),
            duration_ms=duration_ms,
            http_status=http_status,
            page_title=page_title,
            has_body_content=has_body_content,
            error_message=error_message,
            deterministic_verdict=deterministic_verdict,
            screenshot_path=screenshot_path,
            total_iterations=total_iterations,
            action_trace=serialized_trace,
            limitation_note=limitation_note,
            is_real=True,
            recovery_attempts=recovery_attempts,
            llm_errors_count=llm_errors_count,
            action_failures_count=action_failures_count,
            error_category=error_category,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def query_test_runs(
    limit: int = 50,
    offset: int = 0,
    status_filter: Optional[str] = None,
) -> tuple[List[Dict[str, Any]], int]:
    """Retrieves paginated test runs from SQLite sorted by creation time descending."""
    init_db()
    db: Session = SessionLocal()
    try:
        query = db.query(TestRunRecord)
        if status_filter:
            query = query.filter(TestRunRecord.status == status_filter.lower())

        total = query.count()
        records = query.order_by(desc(TestRunRecord.created_at)).offset(offset).limit(limit).all()
        return [r.to_dict() for r in records], total
    finally:
        db.close()


def get_test_run_by_id(run_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single run record by its unique run_id."""
    init_db()
    db: Session = SessionLocal()
    try:
        record = db.query(TestRunRecord).filter(TestRunRecord.run_id == run_id).first()
        return record.to_dict() if record else None
    finally:
        db.close()


def calculate_reports_summary() -> Dict[str, Any]:
    """
    Computes real aggregate metrics and reporting breakdowns directly from persisted SQLite runs.
    """
    init_db()
    db: Session = SessionLocal()
    try:
        total_runs = db.query(TestRunRecord).count()
        if total_runs == 0:
            return {
                "total_runs": 0,
                "passed_runs": 0,
                "failed_runs": 0,
                "error_runs": 0,
                "pass_rate": 0.0,
                "avg_duration_ms": 0,
                "scenario_reports": [],
                "recent_runs": [],
                "is_empty": True,
            }

        passed_runs = db.query(TestRunRecord).filter(TestRunRecord.status == "passed").count()
        failed_runs = db.query(TestRunRecord).filter(TestRunRecord.status == "failed").count()
        error_runs = db.query(TestRunRecord).filter(TestRunRecord.status == "error").count()
        pass_rate = round((passed_runs / total_runs) * 100, 1)

        # Average duration
        avg_dur_result = db.query(func.avg(TestRunRecord.duration_ms)).scalar()
        avg_duration_ms = int(avg_dur_result) if avg_dur_result else 0

        # Breakdown by scenario
        scenario_rows = (
            db.query(
                TestRunRecord.scenario,
                func.count(TestRunRecord.id).label("total"),
                func.sum(case((TestRunRecord.status == "passed", 1), else_=0)).label("passed"),
                func.sum(case((TestRunRecord.status != "passed", 1), else_=0)).label("failed"),
                func.avg(TestRunRecord.duration_ms).label("avg_dur"),
            )
            .group_by(TestRunRecord.scenario)
            .all()
        )

        scenario_reports = []
        for row in scenario_rows:
            sc_total = row.total or 0
            sc_passed = row.passed or 0
            sc_failed = row.failed or 0
            sc_pct = round((sc_passed / sc_total) * 100, 1) if sc_total > 0 else 0.0
            scenario_reports.append({
                "scenario": row.scenario,
                "total": sc_total,
                "passed": sc_passed,
                "failed": sc_failed,
                "pass_rate": sc_pct,
                "avg_duration_ms": int(row.avg_dur or 0),
            })

        # Recent 10 runs
        recent_records = (
            db.query(TestRunRecord)
            .order_by(desc(TestRunRecord.created_at))
            .limit(10)
            .all()
        )

        return {
            "total_runs": total_runs,
            "passed_runs": passed_runs,
            "failed_runs": failed_runs,
            "error_runs": error_runs,
            "pass_rate": pass_rate,
            "avg_duration_ms": avg_duration_ms,
            "scenario_reports": scenario_reports,
            "recent_runs": [r.to_dict() for r in recent_records],
            "is_empty": False,
        }
    finally:
        db.close()
