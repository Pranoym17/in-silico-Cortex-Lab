from typing import Any

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


def verify_supabase_jwt(token: str) -> dict[str, Any]:
    settings = get_settings()

    try:
        claims = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
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
