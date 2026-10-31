"""Google OAuth2 (OpenID Connect via Authlib) & OTP Authentication for CivicLens."""

from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from hashlib import sha256
import base64
import hashlib
import hmac
import re
import secrets
import smtplib
from typing import Any
import urllib.parse

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import OtpCode, User


router = APIRouter(prefix="/auth", tags=["authentication"])

# Register Google OAuth with OpenID Connect discovery
oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile",
        "prompt": "select_account",
    },
)

PHONE_PATTERN = re.compile(r"^\+91\d{10}$")
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
OTP_LENGTH = 6
OTP_TTL_MINUTES = 5
MAX_ATTEMPTS = 5
MAX_REQUESTS_PER_WINDOW = 5
REQUEST_WINDOW_MINUTES = 10



class OtpRequest(BaseModel):
    contact: str = Field(min_length=5, max_length=120)


class OtpVerification(BaseModel):
    contact: str = Field(min_length=5, max_length=120)
    otp: str = Field(min_length=OTP_LENGTH, max_length=OTP_LENGTH)


class PasswordLogin(BaseModel):
    username: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=8, max_length=128)


def normalize_contact(contact: str) -> str:
    contact = contact.strip()
    if "@" in contact:
        return contact.lower()
    digits = re.sub(r"\D", "", contact)
    if len(digits) == 10:
        digits = f"91{digits}"
    return f"+{digits}"


def hash_otp(code: str) -> str:
    return sha256(f"{settings.otp_pepper}:{code}".encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    """Hash a password with salted scrypt; plaintext is never persisted."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded or not encoded.startswith("scrypt$"):
        return False
    try:
        _, salt_text, digest_text = encoded.split("$", 2)
        salt = base64.urlsafe_b64decode(salt_text.encode())
        expected = base64.urlsafe_b64decode(digest_text.encode())
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def set_user_session(request: Request, user: User) -> str:
    request.session["user_id"] = user.id
    request.session["contact"] = user.contact
    request.session["email"] = user.email or user.contact
    request.session["name"] = user.display_name or (user.email or user.username or "Resident").split("@")[0].title()
    request.session["auth_provider"] = user.auth_provider
    return "/admin" if (user.email or "").strip().lower() == settings.admin_email else "/report"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


# ========================================================
# 1. GOOGLE OAUTH2 (AUTHLIB + OPENID CONNECT)
# ========================================================

@router.get("/google/login", summary="Initiate Google OAuth2 authentication")
async def google_login(request: Request):
    """Initiate Google OAuth authentication, generate state, and redirect to Google."""
    if not settings.has_google_oauth:
        return RedirectResponse(
            url="/login?error=" + urllib.parse.quote("Google OAuth credentials are not configured in .env.")
        )

    redirect_uri = settings.google_redirect_uri
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback", summary="Handle Google OAuth2 callback")
async def google_callback(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Handle Google authentication callback, exchange authorization code, and validate ID token."""
    # Handle user denying consent or Google-side error
    google_err = request.query_params.get("error")
    if google_err:
        return RedirectResponse(
            url=f"/login?error={urllib.parse.quote('Google sign-in was cancelled or encountered an error: ' + google_err)}"
        )

    if not settings.has_google_oauth:
        return RedirectResponse(
            url="/login?error=" + urllib.parse.quote("Google OAuth credentials are not configured.")
        )

    try:
        # Authlib exchanges code for token and automatically validates OAuth state
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as err:
        return RedirectResponse(
            url=f"/login?error={urllib.parse.quote(err.description or err.error or 'OAuth state validation failed.')}"
        )
    except Exception as exc:
        return RedirectResponse(
            url=f"/login?error={urllib.parse.quote('Authentication exchange error: ' + str(exc))}"
        )

    # Validate ID token claims
    userinfo = token.get("userinfo")
    if not userinfo:
        try:
            userinfo = await oauth.google.userinfo(token=token)
        except Exception:
            userinfo = {}

    google_sub = userinfo.get("sub")
    email = userinfo.get("email")
    email_verified = userinfo.get("email_verified")
    name = userinfo.get("name")
    picture = userinfo.get("picture")

    if not google_sub:
        return RedirectResponse(
            url="/login?error=" + urllib.parse.quote("Google authentication did not provide a valid subject identifier.")
        )

    # Security requirement: Never establish ownership with unverified email
    if not email_verified:
        return RedirectResponse(
            url="/login?error=" + urllib.parse.quote("Google account email is not verified. Unverified accounts cannot sign in.")
        )

    email = email.strip().lower() if email else None

    # Database account retrieval & safe linking
    user = db.scalar(select(User).where(User.google_sub == google_sub))

    if user is not None:
        # Existing account with matching Google sub
        if name and not user.display_name:
            user.display_name = name
        if picture and not user.avatar_url:
            user.avatar_url = picture
        if email and not user.email:
            user.email = email
        user.is_verified = True
    else:
        # Check if an account already exists with this email
        existing_user = db.scalar(select(User).where(User.email == email)) if email else None

        if existing_user is not None:
            # Safe linking check: prevent account collision if existing user has a different Google sub
            if existing_user.google_sub and existing_user.google_sub != google_sub:
                return RedirectResponse(
                    url="/login?error=" + urllib.parse.quote("This email is already associated with a different Google account.")
                )

            # Safely link verified OTP user who hasn't linked a Google sub yet
            if existing_user.is_verified and existing_user.google_sub is None:
                existing_user.google_sub = google_sub
                existing_user.auth_provider = "google"
                if picture and not existing_user.avatar_url:
                    existing_user.avatar_url = picture
                if name and not existing_user.display_name:
                    existing_user.display_name = name
                user = existing_user
            else:
                # Do not hijack unverified existing accounts
                user = User(
                    contact=f"google:{google_sub}",
                    google_sub=google_sub,
                    email=email,
                    display_name=name,
                    avatar_url=picture,
                    auth_provider="google",
                    is_verified=True,
                    trust_score=1.0,
                )
                db.add(user)
        else:
            # Create a new resident account
            contact_val = email if email else f"google:{google_sub}"
            user = User(
                contact=contact_val,
                google_sub=google_sub,
                email=email,
                display_name=name,
                avatar_url=picture,
                auth_provider="google",
                is_verified=True,
                trust_score=1.0,
            )
            db.add(user)

    db.commit()
    db.refresh(user)

    # Establish application session
    request.session["user_id"] = user.id
    request.session["contact"] = user.contact
    request.session["email"] = user.email or user.contact
    request.session["name"] = user.display_name or (user.email or "Resident").split("@")[0].title()
    request.session["avatar_url"] = user.avatar_url
    request.session["auth_provider"] = "google"
    request.session["google_sub"] = user.google_sub

    # Set secure HTTP-only cookie
    landing_page = "/admin" if (user.email or "").strip().lower() == settings.admin_email else "/report"
    redirect_target = RedirectResponse(url=landing_page, status_code=status.HTTP_303_SEE_OTHER)
    is_https = request.url.scheme == "https"
    redirect_target.set_cookie(
        "civiclens_verified",
        "1",
        httponly=True,
        samesite="lax",
        secure=is_https,
        max_age=60 * 60 * 24,
    )
    return redirect_target


# ========================================================
# 2. LOGOUT ROUTE
# ========================================================

@router.post("/password/login", summary="Sign in with a database-backed password")
def password_login(payload: PasswordLogin, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    username = payload.username.strip().lower()
    user = db.scalar(select(User).where(User.username == username))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")

    landing_page = set_user_session(request, user)
    return {
        "authenticated": True,
        "redirect_url": landing_page,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "name": user.display_name or user.username,
            "provider": "password",
        },
    }

@router.get("/logout", summary="Clear session and log out")
@router.post("/logout", summary="Clear session and log out")
def logout(request: Request, response: Response):
    """Clear the CivicLens session and redirect to the login page."""
    request.session.clear()
    res = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    res.delete_cookie("civiclens_verified")
    return res


# ========================================================
# 3. EXISTING OTP AUTHENTICATION
# ========================================================

@router.post("/request-otp")
def request_otp(payload: OtpRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Request a 6-digit OTP code dispatched via SMS/Email."""
    contact = normalize_contact(payload.contact)
    now = utc_now()
    window_start = now - timedelta(minutes=REQUEST_WINDOW_MINUTES)
    request_count = (
        db.scalar(
            select(func.count(OtpCode.id)).where(
                OtpCode.contact == contact,
                OtpCode.created_at >= window_start,
            )
        )
        or 0
    )
    if request_count >= MAX_REQUESTS_PER_WINDOW:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many OTP requests. Please wait a few minutes before trying again.",
        )

    user = db.scalar(select(User).where(or_(User.contact == contact, User.email == contact)))
    if user is None:
        user = User(
            contact=contact,
            email=contact if "@" in contact else None,
            auth_provider="otp",
            trust_score=1.0,
        )
        db.add(user)

    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(
        OtpCode(
            contact=contact,
            code_hash=hash_otp(code),
            expires_at=now + timedelta(minutes=OTP_TTL_MINUTES),
        )
    )
    db.commit()

    # Attempt real email dispatch if an email was entered and SMTP credentials exist
    sent_real = False
    if "@" in contact and settings.smtp_email and settings.smtp_password:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"CivicLens Verification Code: {code}"
            msg["From"] = f"CivicLens <{settings.smtp_email}>"
            msg["To"] = contact
            msg.attach(MIMEText(f"Your verification code is: {code}\nValid for 5 minutes.", "plain"))
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as s:
                s.ehlo()
                s.starttls()
                s.login(settings.smtp_email, settings.smtp_password)
                s.sendmail(settings.smtp_email, [contact], msg.as_string())
            sent_real = True
        except Exception:
            sent_real = False

    return {
        "message": f"Verification code dispatched to {contact}." if sent_real else "OTP generated.",
        "expires_in_seconds": OTP_TTL_MINUTES * 60,
        "demo_code": code if (settings.demo_mode and not sent_real) else None,
    }


@router.post("/verify-otp")
def verify_otp(
    payload: OtpVerification,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Verify 6-digit OTP code and establish application session."""
    contact = normalize_contact(payload.contact)
    now = utc_now()
    otp = db.scalar(
        select(OtpCode)
        .where(OtpCode.contact == contact, OtpCode.used_at.is_(None))
        .order_by(OtpCode.created_at.desc())
    )
    if otp is None or aware(otp.expires_at) <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This verification code is expired or invalid. Please request a new code.",
        )
    if otp.attempts >= MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many incorrect attempts. Please request a new code.",
        )

    otp.attempts += 1
    if not hmac.compare_digest(otp.code_hash, hash_otp(payload.otp.strip())):
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect verification code.")

    otp.used_at = now
    user = db.scalar(select(User).where(or_(User.contact == contact, User.email == contact)))
    if user is None:
        user = User(contact=contact, auth_provider="otp", trust_score=1.0)
        db.add(user)
    user.is_verified = True
    db.commit()
    db.refresh(user)

    request.session["user_id"] = user.id
    request.session["contact"] = contact
    request.session["email"] = user.email or (contact if "@" in contact else None)
    request.session["name"] = user.display_name or f"Resident {contact[-4:]}"
    request.session["auth_provider"] = "otp"

    is_https = request.url.scheme == "https"
    response.set_cookie(
        "civiclens_verified",
        "1",
        httponly=True,
        samesite="lax",
        secure=is_https,
        max_age=60 * 60 * 24,
    )

    return {
        "verified": True,
        "redirect_url": "/report",
        "user": {
            "id": user.id,
            "contact": user.contact,
            "name": user.display_name,
            "provider": "otp",
        },
    }


# ========================================================
# 4. CURRENT SESSION INFO
# ========================================================

@router.get("/me")
def current_user(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return currently authenticated resident profile."""
    user_id = request.session.get("user_id")
    if not user_id:
        return {"authenticated": False, "user": None}

    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        return {"authenticated": False, "user": None}

    return {
        "authenticated": True,
        "user": {
            "id": user.id,
            "contact": user.contact,
            "username": user.username,
            "email": user.email,
            "name": user.display_name or (user.email or user.contact).split("@")[0].title(),
            "avatar_url": user.avatar_url,
            "provider": user.auth_provider,
            "is_verified": user.is_verified,
            "trust_score": user.trust_score,
            "is_admin": (user.email or "").strip().lower() == settings.admin_email,
        },
    }
