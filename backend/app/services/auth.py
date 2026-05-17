from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class SupabaseAuthMiddleware(BaseHTTPMiddleware):
    """Development auth boundary matching the production Supabase JWT contract."""

    async def dispatch(self, request: Request, call_next):
        authorization = request.headers.get("authorization", "")
        request.state.user = None

        if authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1]
            # Full python-jose verification is added with the database user service.
            request.state.user = {"id": "local-user", "supabase_user_id": token[:16]}

        return await call_next(request)

