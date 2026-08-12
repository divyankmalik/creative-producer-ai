"""Verifies Supabase-issued session JWTs sent by the frontend.

Real session tokens (from an actual sign-in) turned out to be signed with
ES256 -- an asymmetric key, verified via a public key + key ID (kid) fetched
from Supabase's JWKS endpoint -- not the HS256 shared-secret scheme the
static anon/service_role keys use (see SUPABASE_JWT_SECRET). Found live: an
implementation that only checked HS256 silently rejected every real session
token while passing every hand-crafted HS256 test token, since a synthetic
test token built the same way as the (wrong) assumption can't catch an
assumption being wrong. JWKS verification is tried first; the HS256 secret
is kept as a fallback in case older tokens or a future project
reconfiguration ever issue that format again.
"""

from __future__ import annotations

from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException

from app.config import get_settings

_jwks_client: jwt.PyJWKClient | None = None


def _get_jwks_client() -> jwt.PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        settings = get_settings()
        # PyJWKClient caches fetched keys itself -- this doesn't hit the
        # network on every request, only when a kid it hasn't seen shows up.
        _jwks_client = jwt.PyJWKClient(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json")
    return _jwks_client


def _decode(token: str) -> dict:
    settings = get_settings()

    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        return jwt.decode(token, signing_key.key, algorithms=["ES256", "RS256"], audience="authenticated")
    except jwt.InvalidTokenError:
        return {}
    except Exception:
        # JWKS fetch/network failure, unknown kid, etc. -- fall through to
        # the HS256 path below rather than treating this as "invalid token."
        pass

    try:
        # audience="authenticated" matches the claim Supabase stamps on
        # every real session token -- rejecting anything else is a cheap
        # extra check beyond just "signature verifies."
        return jwt.decode(token, settings.supabase_jwt_secret, algorithms=["HS256"], audience="authenticated")
    except jwt.InvalidTokenError:
        return {}


async def get_current_user_id(authorization: str | None = Header(default=None)) -> UUID | None:
    """Optional auth -- returns None (not a 401) for anonymous requests.

    Used by routes that work both signed-in and signed-out (e.g. project
    creation, which has always allowed anonymous use and still does). A
    missing, malformed, or expired token is treated identically to no
    token at all, never an error, since these routes never required auth
    to begin with.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    payload = _decode(authorization.removeprefix("Bearer "))
    sub = payload.get("sub")
    return UUID(sub) if sub else None


async def require_user_id(user_id: UUID | None = Depends(get_current_user_id)) -> UUID:
    """Hard auth requirement -- for routes that only make sense signed in,
    e.g. listing "my projects". 401s instead of silently treating a missing/
    invalid token as anonymous.
    """
    if user_id is None:
        raise HTTPException(status_code=401, detail="sign-in required")
    return user_id
