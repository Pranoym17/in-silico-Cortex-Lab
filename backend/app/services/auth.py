import json
from typing import Any
from urllib.request import urlopen

from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.services.users import get_or_create_user_from_claims


class AuthError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message


def _get_jwks_url() -> str:
    settings = get_settings()
    if not settings.supabase_url:
        raise AuthError("Supabase URL is required for asymmetric JWT verification")

    return f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"


def _fetch_supabase_jwks() -> dict[str, Any]:
    with urlopen(_get_jwks_url(), timeout=5) as response:
        return json.loads(response.read())


def _get_jwks_key(token: str) -> dict[str, Any]:
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise AuthError("Invalid authentication token") from exc
    key_id = header.get("kid")
    if not key_id:
        raise AuthError("Authentication token is missing key ID")

    jwks = _fetch_supabase_jwks()
    for key in jwks.get("keys", []):
        if key.get("kid") == key_id:
            return key

    raise AuthError("Authentication token key was not found")


def verify_supabase_jwt(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise AuthError("Invalid authentication token") from exc
    algorithm = header.get("alg")

    if algorithm == "HS256":
        key: str | dict[str, Any] = settings.supabase_jwt_secret
        algorithms = ["HS256"]
    elif algorithm in {"ES256", "RS256"}:
        key = _get_jwks_key(token)
        algorithms = [algorithm]
    else:
        raise AuthError("Unsupported authentication token algorithm")

    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=algorithms,
            options={"verify_aud": False},
        )
    except JWTError as exc:
        raise AuthError("Invalid authentication token") from exc

    if not claims.get("sub"):
        raise AuthError("Authentication token is missing subject")

    return claims


class SupabaseAuthMiddleware(BaseHTTPMiddleware):
    """Verify Supabase JWTs and attach the local app user when a bearer token is present."""

    async def dispatch(self, request: Request, call_next):
        authorization = request.headers.get("authorization", "")
        request.state.user = None

        if authorization:
            if not authorization.lower().startswith("bearer "):
                return JSONResponse({"detail": "Invalid authorization header"}, status_code=401)

            token = authorization.split(" ", 1)[1].strip()
            if not token:
                return JSONResponse({"detail": "Missing bearer token"}, status_code=401)

            try:
                claims = verify_supabase_jwt(token)
                async with AsyncSessionLocal() as session:
                    request.state.user = await get_or_create_user_from_claims(session, claims)
            except AuthError as exc:
                return JSONResponse({"detail": exc.message}, status_code=401)

        return await call_next(request)
