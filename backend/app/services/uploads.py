from pathlib import PurePath
from uuid import uuid4

import boto3

from app.core.config import get_settings
from app.models.user import User
from app.schemas.upload import UploadIntentRequest, UploadIntentResponse


def _safe_filename(filename: str) -> str:
    name = PurePath(filename).name.strip().replace(" ", "_")
    return name or "stimulus"


def _s3_client():
    settings = get_settings()
    client_kwargs = {
        "region_name": settings.aws_region,
        "endpoint_url": f"https://s3.{settings.aws_region}.amazonaws.com",
    }

    if settings.aws_access_key_id and settings.aws_secret_access_key:
        client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
        client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key

    return boto3.client("s3", **client_kwargs)


def create_upload_intent(owner: User, data: UploadIntentRequest) -> UploadIntentResponse:
    settings = get_settings()
    filename = _safe_filename(data.filename)
    block_part = str(data.block_id) if data.block_id else uuid4().hex
    object_key = f"uploads/{owner.id}/experiments/{data.experiment_id}/{block_part}/{filename}"
    max_size = 10 * 1024 * 1024 if data.kind == "image" else 100 * 1024 * 1024

    s3_client = _s3_client()
    upload = s3_client.generate_presigned_post(
        Bucket=settings.s3_bucket_name,
        Key=object_key,
        Fields={
            "Content-Type": data.mime_type,
        },
        Conditions=[
            ["content-length-range", 1, max_size],
            {"Content-Type": data.mime_type},
        ],
        ExpiresIn=settings.s3_upload_expires_seconds,
    )

    return UploadIntentResponse(
        upload_url=upload["url"],
        object_key=object_key,
        headers={},
        fields={key: str(value) for key, value in upload["fields"].items()},
        expires_in_seconds=settings.s3_upload_expires_seconds,
    )
