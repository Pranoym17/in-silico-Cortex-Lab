from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.ml import RsaRequest, RsaResponse
from app.services.ml_rsa import run_rsa

router = APIRouter()


@router.get("/health")
async def ml_health(_: User = Depends(require_user)) -> dict[str, str]:
    return {"status": "ok", "surface": "ml"}


@router.post("/rsa", response_model=RsaResponse)
async def run_rsa_route(
    body: RsaRequest,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_db),
) -> RsaResponse:
    return await run_rsa(session, user, body)
