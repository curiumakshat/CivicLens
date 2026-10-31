"""Admin-only report moderation and alert queue."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Report, ReportStatusLog, User, Ward
from app.services.priority import build_alerts, ward_for_coordinates


router = APIRouter(prefix="/api/admin", tags=["admin"])
ALLOWED_STATUSES = {"pending", "in_progress", "resolved"}


def require_admin(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    user = db.query(User).filter(User.id == user_id).first() if user_id else None
    if not user or (user.email or "").strip().lower() != settings.admin_email:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access is restricted.")
    return user


class StatusUpdate(BaseModel):
    status: str = Field(pattern="^(pending|in_progress|resolved)$")
    note: str | None = Field(default=None, max_length=500)


@router.get("/overview")
def admin_overview(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    window_days = settings.priority_window_days
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    reports = db.query(Report).filter(Report.created_at >= cutoff).order_by(Report.created_at.desc()).all()
    wards = {ward.name: ward for ward in db.query(Ward).all()}
    return {
        "alerts": build_alerts(reports, wards=wards, window_days=window_days),
        "reports": [
            {
                "id": report.id,
                "title": report.description.split(":", 1)[0],
                "category": report.category,
                "ward": ward_for_coordinates(report.latitude, report.longitude),
                "status": report.status,
                "verification_status": report.verification_status,
                "severity": report.severity,
                "created_at": report.created_at.isoformat(),
                "latitude": report.latitude,
                "longitude": report.longitude,
            }
            for report in reports
        ],
    }


@router.patch("/reports/{report_id}/status")
def update_report_status(
    report_id: int,
    payload: StatusUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    previous_status = report.status
    report.status = payload.status
    if previous_status != payload.status:
        if db.bind.dialect.name == "postgresql":
            db.execute(text("SELECT set_config('civiclens.changed_by_id', :changed_by_id, true)"), {"changed_by_id": str(_.id)})
            db.execute(text("SELECT set_config('civiclens.status_note', :status_note, true)"), {"status_note": payload.note or ""})
        else:
            db.add(ReportStatusLog(
                report_id=report.id,
                changed_by_id=_.id,
                from_status=previous_status,
                to_status=payload.status,
                note=payload.note,
            ))
    db.commit()
    return {"status": "success", "report_id": report.id, "report_status": report.status}
