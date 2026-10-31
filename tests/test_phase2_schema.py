"""SQLite-only safety tests for the Phase 2 model contract.

These tests never use the configured Neon engine and do not execute Alembic.
"""

from datetime import datetime, timezone

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Report, ReportStatusLog, User, Ward
from app.services.priority import build_alerts


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_phase2_tables_and_report_columns_are_present_without_touching_neon():
    db = make_session()
    tables = set(inspect(db.bind).get_table_names())
    assert {"reports", "users", "wards", "report_status_log"}.issubset(tables)
    columns = {column["name"] for column in inspect(db.bind).get_columns("reports")}
    assert {"verification_status", "status", "severity", "ward_id"}.issubset(columns)


def test_verification_status_is_preserved_and_new_status_starts_pending():
    db = make_session()
    user = User(contact="resident@example.com", email="resident@example.com", is_verified=True)
    db.add(user)
    db.flush()
    report = Report(
        reporter_id=user.id,
        category="Roads & potholes",
        description="Legacy verification remains separate",
        latitude=26.9,
        longitude=75.8,
        verification_status="verified",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    assert report.verification_status == "verified"
    assert report.status == "pending"


def test_priority_uses_ward_population_and_real_report_attributes():
    db = make_session()
    ward = Ward(name="Ward 7", population=50_000, population_source="approved census")
    db.add(ward)
    db.flush()
    user = User(contact="priority@example.com", is_verified=True)
    db.add(user)
    db.flush()
    report = Report(
        reporter_id=user.id,
        ward_id=ward.id,
        category="Roads & potholes",
        description="Priority test",
        latitude=26.9,
        longitude=75.8,
        severity=5,
        created_at=datetime.now(timezone.utc),
    )
    db.add(report)
    db.commit()
    alerts = build_alerts([report], {ward.name: ward}, window_days=30)
    assert alerts[0]["population"] == 50_000
    assert alerts[0]["severity_source"] == "configured_category_formula"
    assert alerts[0]["score_breakdown"]["population_score"] == 100.0


def test_status_history_model_keeps_report_and_actor_links():
    db = make_session()
    user = User(contact="admin@example.com", is_verified=True)
    db.add(user)
    db.flush()
    report = Report(
        reporter_id=user.id,
        category="Streetlights",
        description="Status history test",
        latitude=26.9,
        longitude=75.8,
    )
    db.add(report)
    db.flush()
    db.add(ReportStatusLog(
        report_id=report.id,
        changed_by_id=user.id,
        from_status="pending",
        to_status="in_progress",
        note="Assigned to field team",
    ))
    db.commit()
    assert db.query(ReportStatusLog).one().to_status == "in_progress"
