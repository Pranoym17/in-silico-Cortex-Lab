from fastapi import APIRouter, Depends, status

from app.api.dependencies import require_user
from app.models.user import User
from app.schemas.upload import UploadIntentRequest, UploadIntentResponse
from app.services.uploads import create_upload_intent

router = APIRouter()


@router.post("/presign", response_model=UploadIntentResponse, status_code=status.HTTP_201_CREATED)
async def create_upload_intent_route(
    body: UploadIntentRequest,
    user: User = Depends(require_user),
) -> UploadIntentResponse:
    return create_upload_intent(user, body)
