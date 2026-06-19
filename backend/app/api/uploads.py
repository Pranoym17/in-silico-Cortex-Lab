import logging
import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.upload import UploadIntentRequest, UploadIntentResponse
from app.services.experiments import get_owned_experiment
from app.services.uploads import create_upload_intent

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/presign", response_model=UploadIntentResponse, status_code=status.HTTP_201_CREATED)
async def create_upload_intent_route(
    body: UploadIntentRequest,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_db),
) -> UploadIntentResponse:
    await get_owned_experiment(session, user, body.experiment_id)
    try:
        return await asyncio.to_thread(create_upload_intent, user, body)
    except Exception as exc:
        logger.exception(
            "upload_presign_failed",
            extra={
                "user_id": str(user.id),
                "experiment_id": str(body.experiment_id),
                "error_code": "upload_failed",
            },
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "upload_failed",
                "message": "Upload setup failed. Check S3 configuration and retry.",
            },
        ) from exc
