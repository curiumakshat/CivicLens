"""Core CivicLens persistence models.

The schema deliberately separates a citizen submission (Report) from the
underlying real-world problem (Issue). Multiple reports can be linked to one
issue during deduplication.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for new records."""
    return datetime.now(timezone.utc)


class User(Base):
    """A citizen or officer who interacts with CivicLens."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contact: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    auth_provider: Mapped[str] = mapped_column(String(40), default="otp", nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trust_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    reports: Mapped[list["Report"]] = relationship(back_populates="reporter")
    status_changes: Mapped[list["StatusLog"]] = relationship(back_populates="changed_by")


class OtpCode(Base):
    """A hashed, short-lived one-time verification code."""

    __tablename__ = "otp_codes"
    __table_args__ = (Index("ix_otp_codes_contact_created", "contact", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contact: Mapped[str] = mapped_column(String(255), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Issue(Base):
    """The real-world civic problem represented by one or more reports."""

    __tablename__ = "issues"
    __table_args__ = (
        Index("ix_issues_status_priority", "status", "priority_score"),
        Index("ix_issues_location", "latitude", "longitude"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="Reported", index=True, nullable=False)
    priority_score: Mapped[float] = mapped_column(Float, default=0.0, index=True, nullable=False)
    priority_band: Mapped[str] = mapped_column(String(20), default="Low", nullable=False)
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    reports: Mapped[list["Report"]] = relationship(back_populates="issue")
    status_logs: Mapped[list["StatusLog"]] = relationship(
        back_populates="issue", cascade="all, delete-orphan"
    )


class Report(Base):
    """One citizen-submitted observation of a civic problem."""

    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_reports_category_location", "category", "latitude", "longitude"),
        Index("ix_reports_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    issue_id: Mapped[int | None] = mapped_column(ForeignKey("issues.id"), index=True, nullable=True)
    ward_id: Mapped[int | None] = mapped_column(ForeignKey("wards.id"), index=True, nullable=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    description: Mapped[str] = mapped_column(Text)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    verification_status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False, index=True)
    severity: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    reporter: Mapped[User] = relationship(back_populates="reports")
    issue: Mapped[Issue | None] = relationship(back_populates="reports")
    ward: Mapped["Ward | None"] = relationship(back_populates="reports")
    status_logs: Mapped[list["ReportStatusLog"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )


class Ward(Base):
    """Verified locality metadata used by the priority engine."""

    __tablename__ = "wards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    population: Mapped[int | None] = mapped_column(Integer, nullable=True)
    population_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    boundary_geojson: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    reports: Mapped[list[Report]] = relationship(back_populates="ward")


class ReportStatusLog(Base):
    """Immutable audit record for citizen-report lifecycle changes."""

    __tablename__ = "report_status_log"
    __table_args__ = (Index("ix_report_status_log_report_created", "report_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    changed_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    report: Mapped[Report] = relationship(back_populates="status_logs")
    changed_by: Mapped[User] = relationship()


class StatusLog(Base):
    """An auditable transition in an issue's public lifecycle."""

    __tablename__ = "status_log"
    __table_args__ = (Index("ix_status_log_issue_created", "issue_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id"), index=True)
    changed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    from_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_status: Mapped[str] = mapped_column(String(40))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    issue: Mapped[Issue] = relationship(back_populates="status_logs")
    changed_by: Mapped[User | None] = relationship(back_populates="status_changes")
