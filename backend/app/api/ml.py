from fastapi import APIRouter, Depends

from app.api.dependencies import require_user
from app.models.user import User

router = APIRouter()


@router.get("/health")
async def ml_health(_: User = Depends(require_user)) -> dict[str, str]:
    return {"status": "ok", "surface": "ml"}
