"""Verify Supabase Auth access tokens and expose a minimal user identity."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError

from ..settings import settings

bearer = HTTPBearer(auto_error=False)
ALLOWED_ALGORITHMS = ["ES256", "RS256", "EdDSA"]


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    if not settings.supabase_url:
        raise RuntimeError("RADAR_SUPABASE_URL must be configured for the hosted app")
    project_url = settings.supabase_url.rstrip("/")
    if not project_url.startswith("https://"):
        raise RuntimeError("RADAR_SUPABASE_URL must use HTTPS")
    return PyJWKClient(f"{project_url}/auth/v1/.well-known/jwks.json")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401, detail="Bearer access token required", headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        jwks = _jwks_client()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Authentication is not configured") from exc

    if not settings.supabase_url:
        raise HTTPException(status_code=503, detail="Authentication is not configured")
    project_url = settings.supabase_url.rstrip("/")
    try:
        signing_key = jwks.get_signing_key_from_jwt(credentials.credentials)
        claims = jwt.decode(
            credentials.credentials,
            signing_key.key,
            algorithms=ALLOWED_ALGORITHMS,
            audience="authenticated",
            issuer=f"{project_url}/auth/v1",
            options={"require": ["exp", "sub", "iss", "aud"]},
        )
    except PyJWKClientConnectionError as exc:
        raise HTTPException(status_code=503, detail="Authentication provider is unavailable") from exc
    except (jwt.PyJWTError, PyJWKClientError, OSError) as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise HTTPException(status_code=401, detail="Access token has no user subject")
    return AuthenticatedUser(id=subject)
