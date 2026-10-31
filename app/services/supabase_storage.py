"""Server-side Supabase Storage integration for report images."""

from urllib.parse import quote

import httpx

from app.config import settings


class SupabaseStorageError(RuntimeError):
    """Raised when Supabase Storage rejects an image operation."""


def _object_url(storage_path: str) -> str:
    if not settings.supabase_url or not settings.supabase_secret_key:
        raise SupabaseStorageError("Supabase Storage is not configured on the server.")
    bucket = quote(settings.supabase_reports_bucket, safe="")
    path = quote(storage_path, safe="/")
    return f"{settings.supabase_url}/storage/v1/object/{bucket}/{path}"


def _headers(content_type: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {settings.supabase_secret_key}",
        "apikey": settings.supabase_secret_key,
        "x-upsert": "false",
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def upload_report_image(storage_path: str, image_bytes: bytes, content_type: str) -> str:
    """Upload bytes to the configured private reports bucket and return its path."""
    try:
        response = httpx.post(
            _object_url(storage_path),
            headers=_headers(content_type),
            content=image_bytes,
            timeout=30.0,
        )
    except httpx.HTTPError as exc:
        raise SupabaseStorageError("Unable to reach Supabase Storage.") from exc
    if response.status_code >= 400:
        detail = response.text[:300].strip() or "Supabase Storage rejected the upload."
        raise SupabaseStorageError(f"{detail} (HTTP {response.status_code})")
    return f"{settings.supabase_reports_bucket}/{storage_path}"


def delete_report_image(storage_path: str) -> None:
    """Best-effort cleanup when report persistence fails after upload."""
    try:
        response = httpx.delete(
            _object_url(storage_path),
            headers=_headers(),
            timeout=15.0,
        )
        response.raise_for_status()
    except (httpx.HTTPError, SupabaseStorageError):
        # Cleanup must not hide the original database error.
        return
