"""
Clerk session token verification.

WHY verify JWTs against Clerk's JWKS instead of trusting a header:
Never trust a `user_id` or `org_id` passed in a request body/header from
the client — that's trivially spoofable with curl. The ONLY trustworthy
identity is what you extract from a cryptographically verified JWT.

We cache the JWKS (JSON Web Key Set) in memory with a short TTL instead
of fetching it from Clerk on every single request — that would add a
network round-trip to every authenticated call and is unnecessary since
Clerk's signing keys rotate infrequently.
"""

import time

import httpx
from fastapi import Depends, Header
from jose import jwt
from jose.exceptions import JWTError

from app.config import get_settings
from app.core.exceptions import UnauthorizedError
from app.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

_jwks_cache: dict = {"keys": None, "fetched_at": 0.0}
_JWKS_TTL_SECONDS = 3600


def _get_jwks() -> dict:
    now = time.time()
    if _jwks_cache["keys"] is not None and (now - _jwks_cache["fetched_at"]) < _JWKS_TTL_SECONDS:
        return _jwks_cache["keys"]

    try:
        resp = httpx.get(settings.CLERK_JWKS_URL, timeout=5.0)
        resp.raise_for_status()
        jwks = resp.json()
    except httpx.HTTPError as exc:
        logger.error("clerk_jwks_fetch_failed", error=str(exc))
        # If we have a stale cache, prefer serving on stale keys over hard-failing
        # every authenticated request in the app because Clerk had a blip.
        if _jwks_cache["keys"] is not None:
            return _jwks_cache["keys"]
        raise UnauthorizedError("Unable to verify authentication at this time")

    _jwks_cache["keys"] = jwks
    _jwks_cache["fetched_at"] = now
    return jwks


class AuthenticatedUser:
    __slots__ = ("user_id", "org_id", "claims")

    def __init__(self, user_id: str, org_id: str | None, claims: dict):
        self.user_id = user_id
        self.org_id = org_id
        self.claims = claims


def get_current_user(authorization: str | None = Header(default=None)) -> AuthenticatedUser:
    """
    FastAPI dependency: verifies the Clerk session JWT and returns the
    authenticated identity. Raise UnauthorizedError on ANY failure mode —
    expired token, bad signature, missing header — never fall through to
    treating an unverifiable request as anonymous-but-allowed.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError("Missing or malformed Authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    jwks = _get_jwks()

    try:
        header = jwt.get_unverified_header(token)
        key = next((k for k in jwks.get("keys", []) if k.get("kid") == header.get("kid")), None)
        if key is None:
            raise UnauthorizedError("Unable to find matching signing key")

        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=settings.CLERK_ISSUER,
            options={"verify_aud": False},
        )
    except JWTError as exc:
        logger.warning("jwt_verification_failed", error=str(exc))
        raise UnauthorizedError("Invalid or expired session token")

    user_id = claims.get("sub")
    if not user_id:
        raise UnauthorizedError("Token missing subject claim")

    org_claim = claims.get("o") or {}
    org_id = org_claim.get("id") if isinstance(org_claim, dict) else None
    return AuthenticatedUser(user_id=user_id, org_id=org_id, claims=claims)


def require_org_membership(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    """Use on recruiter-facing routes that must be scoped to an org (multi-tenant safety)."""
    if not user.org_id:
        raise UnauthorizedError("This action requires an active organization context")
    return user
