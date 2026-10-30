"""Core CivicLens persistence models.

The schema deliberately separates a citizen submission (Report) from the
underlying real-world problem (Issue). Multiple reports can be linked to one
issue during the deduplication quest.
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
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trust_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    reports: Mapped[list["Report"]] = relationship(back_populates="reporter")
    status_changes: Mapped[list["StatusLog"]] = relationship(back_populates="changed_by")


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
    category: Mapped[str] = mapped_column(String(80), index=True)
    description: Mapped[str] = mapped_column(Text)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    verification_status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    reporter: Mapped[User] = relationship(back_populates="reports")
    issue: Mapped[Issue | None] = relationship(back_populates="reports")


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
