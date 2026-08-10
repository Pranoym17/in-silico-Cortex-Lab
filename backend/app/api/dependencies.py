from fastapi import Depends, HTTPException, Request, status

from app.core.config import get_settings
from app.models.user import User


def require_user(request: Request) -> User:
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    allowed = {email.strip().lower() for email in get_settings().admin_email_addresses.split(",") if email.strip()}
    if not user.email or user.email.strip().lower() not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required")
    return user

