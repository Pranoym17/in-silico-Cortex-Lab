import base64
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.core.config import get_settings
from app.main import app
from app.services.auth import AuthError, verify_supabase_jwt


def base64url_uint(value: int) -> str:
    return base64.urlsafe_b64encode(value.to_bytes(32, "big")).rstrip(b"=").decode()


def make_token(**overrides):
    settings = get_settings()
    now = datetime.now(UTC)
    claims = {
        "sub": "supabase-user-123",
        "email": "researcher@example.com",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
        "user_metadata": {
            "full_name": "Demo Researcher",
            "avatar_url": "https://example.com/avatar.png",
        },
    }
    claims.update(overrides)
    return jwt.encode(claims, settings.supabase_jwt_secret, algorithm="HS256")


def make_user():
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=uuid4(),
        supabase_user_id="supabase-user-123",
        email="researcher@example.com",
        display_name="Demo Researcher",
        avatar_url="https://example.com/avatar.png",
        created_at=now,
        updated_at=now,
        last_seen_at=now,
    )


def test_verify_supabase_jwt_accepts_valid_token():
    claims = verify_supabase_jwt(make_token())

    assert claims["sub"] == "supabase-user-123"
    assert claims["email"] == "researcher@example.com"


def test_verify_supabase_jwt_accepts_asymmetric_supabase_token(monkeypatch):
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_pem = private_key.private_bytes(
        Encoding.PEM,
        PrivateFormat.PKCS8,
        NoEncryption(),
    )
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "supabase-user-123",
            "email": "researcher@example.com",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=10)).timestamp()),
        },
        private_pem,
        algorithm="ES256",
        headers={"kid": "test-key"},
    )
    public_jwk = jwt.get_unverified_header(token)
    public_numbers = private_key.public_key().public_numbers()
    public_jwk.update(
        {
            "kty": "EC",
            "crv": "P-256",
            "use": "sig",
            "x": base64url_uint(public_numbers.x),
            "y": base64url_uint(public_numbers.y),
        }
    )

    monkeypatch.setattr("app.services.auth._fetch_supabase_jwks", lambda: {"keys": [public_jwk]})

    claims = verify_supabase_jwt(token)

    assert claims["sub"] == "supabase-user-123"


def test_verify_supabase_jwt_rejects_missing_subject():
    with pytest.raises(AuthError):
        verify_supabase_jwt(make_token(sub=None))


@pytest.mark.asyncio
async def test_me_requires_authentication():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


@pytest.mark.asyncio
async def test_invalid_bearer_token_is_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/me", headers={"Authorization": "Bearer not-a-jwt"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid authentication token"}


@pytest.mark.asyncio
async def test_me_returns_synced_user(monkeypatch):
    user = make_user()

    async def fake_get_or_create_user_from_claims(session, claims):
        assert claims["sub"] == "supabase-user-123"
        return user

    monkeypatch.setattr("app.services.auth.get_or_create_user_from_claims", fake_get_or_create_user_from_claims)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/me", headers={"Authorization": f"Bearer {make_token()}"})

    assert response.status_code == 200
    assert response.json()["supabase_user_id"] == "supabase-user-123"
    assert response.json()["email"] == "researcher@example.com"
