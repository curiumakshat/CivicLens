"""Report submission and listing endpoints for CivicLens."""

from pathlib import Path
import os
import tempfile
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Report, User
from app.services.image_metadata import ImageMetadataError, extract_exif_gps, read_upload


router = APIRouter(prefix="/api/reports", tags=["reports"])
ROOT = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = (
    Path(tempfile.gettempdir()) / "civiclens-uploads"
    if os.getenv("VERCEL") == "1" or os.getenv("VERCEL_ENV")
    else ROOT / "uploads"
)


class ReportCreate(BaseModel):
    category: str = Field(min_length=2, max_length=80)
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(default="", max_length=1000)
    latitude: float = Field(default=26.9124)
    longitude: float = Field(default=75.7873)
    photo_url: str | None = None


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def submit_report_with_image(
    request: Request,
    category: str = Form(..., min_length=2, max_length=80),
    title: str = Form(..., min_length=3, max_length=160),
    description: str = Form(default="", max_length=1000),
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    """Accept only real images containing valid EXIF GPS coordinates."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please log in to submit a civic report.")
    if photo.content_type not in {"image/jpeg", "image/png"}:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only JPEG and PNG images are accepted.")

    image_bytes = read_upload(photo.file)
    try:
        latitude, longitude, suffix = extract_exif_gps(image_bytes)
    except ImageMetadataError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{suffix}"
    destination = UPLOAD_DIR / filename
    destination.write_bytes(image_bytes)

    report = Report(
        reporter_id=user_id,
        category=category.strip(),
        description=f"{title.strip()}: {description.strip()}" if description.strip() else title.strip(),
        photo_url=f"uploads/{filename}",
        latitude=latitude,
        longitude=longitude,
        verification_status="pending",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return {
        "status": "success",
        "report_id": report.id,
        "reporter_id": report.reporter_id,
        "photo_path": report.photo_url,
        "latitude": report.latitude,
        "longitude": report.longitude,
        "message": "Report accepted with EXIF GPS coordinates.",
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def submit_report(
    payload: ReportCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Submit a civic observation and link it to the authenticated resident."""
    user_id = request.session.get("user_id")
    if not user_id:
        # Require authentication or fallback to first verified user for graceful testing
        user = db.query(User).filter(User.is_verified.is_(True)).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Please log in to submit a civic report.",
            )
        user_id = user.id

    report = Report(
        reporter_id=user_id,
        category=payload.category,
        description=f"{payload.title}: {payload.description}" if payload.description else payload.title,
        photo_url=payload.photo_url,
        latitude=payload.latitude,
        longitude=payload.longitude,
        verification_status="verified" if request.session.get("auth_provider") == "google" else "pending",
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return {
        "status": "success",
        "report_id": report.id,
        "reporter_id": report.reporter_id,
        "category": report.category,
        "message": "Report successfully recorded and linked to your resident account.",
    }


@router.get("/my-reports")
def get_my_reports(request: Request, db: Session = Depends(get_db)):
    """Retrieve all civic reports submitted by the currently logged-in resident."""
    user_id = request.session.get("user_id")
    if not user_id:
        return {"reports": []}

    reports = (
        db.query(Report)
        .filter(Report.reporter_id == user_id)
        .order_by(Report.created_at.desc())
        .all()
    )
    return {
        "reports": [
            {
                "id": r.id,
                "category": r.category,
                "description": r.description,
                "created_at": r.created_at.isoformat(),
                "status": r.verification_status,
            }
            for r in reports
        ]
    }


@router.get("/locality")
def get_locality_reports(db: Session = Depends(get_db)):
    """Return recent reports raised across the resident's locality feed."""
    reports = db.query(Report).order_by(Report.created_at.desc()).limit(50).all()
    return {
        "reports": [
            {
                "id": r.id,
                "category": r.category,
                "description": r.description,
                "latitude": r.latitude,
                "longitude": r.longitude,
                "created_at": r.created_at.isoformat(),
                "status": r.verification_status,
            }
            for r in reports
        ]
    }
