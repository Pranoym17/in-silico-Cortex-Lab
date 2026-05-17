from fastapi import APIRouter, Depends

from app.api.dependencies import require_user
from app.models.user import User
from app.schemas.user import UserResponse

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(require_user)) -> User:
    return user

