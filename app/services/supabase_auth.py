"""Supabase Auth JWT verification for FastAPI."""

from functools import lru_cache

import jwt
from fastapi import HTTPException, Request, status
from jwt import PyJWKClient

from app.config import settings


@lru_cache(maxsize=1)
def jwks_client() -> PyJWKClient:
    if not settings.supabase_jwks_url:
        raise RuntimeError("SUPABASE_JWKS_URL is not configured.")
    return PyJWKClient(settings.supabase_jwks_url)


def verify_supabase_request(request: Request) -> dict:
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Supabase session token required.")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        signing_key = jwks_client().get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, signing_key, algorithms=["ES256", "RS256"], audience="authenticated", issuer=f"{settings.supabase_url}/auth/v1")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Supabase session.") from exc
    if not claims.get("sub") or not claims.get("email"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Supabase session has no verified email.")
    return claims
