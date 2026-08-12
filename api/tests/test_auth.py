"""Tests for app/auth.py's JWT verification.

Tests below the ES256 section build HS256 tokens with jwt.encode directly
against the real shared secret and exercise the real cryptographic
verification path for that (fallback) branch. The ES256 tests further down
cover the branch that's actually primary in production -- Supabase's real
session tokens turned out to be ES256/JWKS-signed, not HS256 (found live:
an HS256-only implementation silently rejected every real session token
while passing every hand-crafted HS256 test token, since a synthetic test
built on the same wrong assumption can't catch the assumption being wrong).
Those use a locally-generated EC keypair with _get_jwks_client patched, so
they run offline instead of depending on Supabase's live JWKS endpoint.
"""

from __future__ import annotations

import time
from unittest.mock import patch
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException

from app.auth import get_current_user_id, require_user_id
from app.config import get_settings

SECRET = get_settings().supabase_jwt_secret


def make_token(*, secret: str = SECRET, sub: str | None = None, aud: str = "authenticated", expired: bool = False) -> str:
    payload = {
        "sub": sub or str(uuid4()),
        "aud": aud,
        "role": "authenticated",
        "exp": int(time.time()) + (-3600 if expired else 3600),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.mark.asyncio
async def test_valid_token_resolves_to_its_user_id() -> None:
    user_id = str(uuid4())
    token = make_token(sub=user_id)

    result = await get_current_user_id(f"Bearer {token}")

    assert str(result) == user_id


@pytest.mark.asyncio
async def test_wrong_secret_is_rejected_not_raised() -> None:
    token = make_token(secret="not-the-real-secret")

    result = await get_current_user_id(f"Bearer {token}")

    assert result is None


@pytest.mark.asyncio
async def test_expired_token_is_rejected() -> None:
    token = make_token(expired=True)

    result = await get_current_user_id(f"Bearer {token}")

    assert result is None


@pytest.mark.asyncio
async def test_wrong_audience_is_rejected() -> None:
    token = make_token(aud="some-other-service")

    result = await get_current_user_id(f"Bearer {token}")

    assert result is None


@pytest.mark.asyncio
async def test_missing_header_is_none_not_an_error() -> None:
    assert await get_current_user_id(None) is None


@pytest.mark.asyncio
async def test_non_bearer_header_is_ignored() -> None:
    assert await get_current_user_id("Basic dXNlcjpwYXNz") is None


@pytest.mark.asyncio
async def test_require_user_id_passes_through_a_real_user() -> None:
    user_id = str(uuid4())
    result = await require_user_id(await get_current_user_id(f"Bearer {make_token(sub=user_id)}"))
    assert str(result) == user_id


@pytest.mark.asyncio
async def test_require_user_id_raises_401_when_signed_out() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await require_user_id(None)
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# ES256 / JWKS -- the branch real Supabase session tokens actually use
# ---------------------------------------------------------------------------


def make_es256_token(private_key, *, sub: str | None = None, aud: str = "authenticated", expired: bool = False) -> str:
    payload = {
        "sub": sub or str(uuid4()),
        "aud": aud,
        "role": "authenticated",
        "exp": int(time.time()) + (-3600 if expired else 3600),
    }
    return jwt.encode(payload, private_key, algorithm="ES256", headers={"kid": "test-kid"})


@pytest.mark.asyncio
async def test_es256_token_verified_via_jwks_path() -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    user_id = str(uuid4())
    token = make_es256_token(private_key, sub=user_id)

    fake_signing_key = type("FakeSigningKey", (), {"key": private_key.public_key()})()
    with patch("app.auth._get_jwks_client") as mock_get_client:
        mock_get_client.return_value.get_signing_key_from_jwt.return_value = fake_signing_key
        result = await get_current_user_id(f"Bearer {token}")

    assert str(result) == user_id


@pytest.mark.asyncio
async def test_es256_token_signed_by_a_different_key_is_rejected() -> None:
    """The exact failure mode that matters -- a token claiming to be valid
    but not actually signed by the key JWKS says it should be.
    """
    real_key = ec.generate_private_key(ec.SECP256R1())
    attacker_key = ec.generate_private_key(ec.SECP256R1())
    token = make_es256_token(attacker_key)

    fake_signing_key = type("FakeSigningKey", (), {"key": real_key.public_key()})()
    with patch("app.auth._get_jwks_client") as mock_get_client:
        mock_get_client.return_value.get_signing_key_from_jwt.return_value = fake_signing_key
        result = await get_current_user_id(f"Bearer {token}")

    assert result is None


@pytest.mark.asyncio
async def test_jwks_lookup_failure_falls_back_to_hs256() -> None:
    """A JWKS fetch failure (network blip, unknown kid, ...) must fall
    through to the HS256 path, not be treated as an outright rejection --
    otherwise a transient JWKS outage would lock out every signed-in user
    even with a perfectly valid legacy-format token.
    """
    user_id = str(uuid4())
    token = make_token(sub=user_id)  # HS256, real secret

    with patch("app.auth._get_jwks_client") as mock_get_client:
        mock_get_client.return_value.get_signing_key_from_jwt.side_effect = Exception("jwks fetch failed")
        result = await get_current_user_id(f"Bearer {token}")

    assert str(result) == user_id
