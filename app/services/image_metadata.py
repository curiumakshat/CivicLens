"""Image validation and EXIF GPS extraction."""

from io import BytesIO
import math
from typing import BinaryIO

from PIL import ExifTags, Image, UnidentifiedImageError


class ImageMetadataError(ValueError):
    """Raised when an image is unsupported or has no usable GPS metadata."""


# Keep uploads below common serverless request-body limits so the request can
# reach FastAPI on hosted deployments such as Vercel.
MAX_IMAGE_BYTES = 4 * 1024 * 1024
ALLOWED_FORMATS = {"JPEG": ".jpg", "PNG": ".png"}
GPS_TAG = 34853


def _ratio_to_float(value: object) -> float:
    """Convert Pillow EXIF rationals or numeric values to a finite float."""

    try:
        result = float(value)
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        if isinstance(value, (tuple, list)) and len(value) == 2 and float(value[1]) != 0:
            result = float(value[0]) / float(value[1])
        else:
            raise ImageMetadataError("Image GPS metadata contains an invalid coordinate.") from exc
    if not math.isfinite(result):
        raise ImageMetadataError("Image GPS metadata contains an invalid coordinate.")
    return result


def _dms_to_decimal(values: object, reference: object, label: str) -> float:
    if not isinstance(values, (tuple, list)) or len(values) != 3:
        raise ImageMetadataError(f"Image GPS {label} metadata is incomplete.")
    degrees, minutes, seconds = (_ratio_to_float(value) for value in values)
    if degrees < 0 or minutes < 0 or seconds < 0 or minutes >= 60 or seconds >= 60:
        raise ImageMetadataError(f"Image GPS {label} metadata is invalid.")
    decimal = degrees + minutes / 60 + seconds / 3600
    reference_text = str(reference).upper()
    if reference_text in {"S", "W"}:
        decimal = -decimal
    elif reference_text not in {"N", "E"}:
        raise ImageMetadataError(f"Image GPS {label} reference is invalid.")
    return decimal


def extract_exif_gps(image_bytes: bytes) -> tuple[float, float, str]:
    """Validate an image and return normalized (latitude, longitude, suffix)."""

    if not image_bytes:
        raise ImageMetadataError("Upload an image file.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ImageMetadataError("Image must be 4 MB or smaller.")

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image.verify()
        with Image.open(BytesIO(image_bytes)) as image:
            image_format = image.format
            exif = image.getexif()
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageMetadataError("Upload a valid JPEG or PNG image.") from exc

    if image_format not in ALLOWED_FORMATS:
        raise ImageMetadataError("Only JPEG and PNG images are accepted.")

    try:
        gps_info = exif.get_ifd(GPS_TAG)
    except (AttributeError, KeyError, ValueError):
        gps_info = exif.get(GPS_TAG)
    if not gps_info:
        raise ImageMetadataError("Image must contain EXIF GPS coordinates.")

    # Pillow exposes GPS IFD keys as numeric tags on some versions and as
    # GPSInfo enum keys on others, so normalize both forms.
    gps = {}
    for key, value in gps_info.items():
        gps[ExifTags.GPSTAGS.get(key, key)] = value

    latitude = _dms_to_decimal(gps.get("GPSLatitude"), gps.get("GPSLatitudeRef"), "latitude")
    longitude = _dms_to_decimal(gps.get("GPSLongitude"), gps.get("GPSLongitudeRef"), "longitude")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ImageMetadataError("Image GPS coordinates are outside valid ranges.")

    return round(latitude, 6), round(longitude, 6), ALLOWED_FORMATS[image_format]


def read_upload(upload: BinaryIO) -> bytes:
    """Read an upload without allowing a caller to bypass the size limit."""

    return upload.read(MAX_IMAGE_BYTES + 1)
