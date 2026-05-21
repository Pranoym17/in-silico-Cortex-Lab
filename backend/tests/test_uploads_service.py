from types import SimpleNamespace
from uuid import uuid4

from app.schemas.upload import UploadIntentRequest
from app.services import uploads


def test_create_upload_intent_uses_settings_credentials(monkeypatch):
    captured_client_kwargs = {}

    def fake_client(service_name, **kwargs):
        captured_client_kwargs.update(kwargs)
        assert service_name == "s3"

        return SimpleNamespace(generate_presigned_url=lambda **_: "https://s3.example/presigned")

    monkeypatch.setattr("app.services.uploads.boto3.client", fake_client)
    uploads.get_settings.cache_clear()
    monkeypatch.setenv("AWS_REGION", "us-east-2")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "access-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret-key")
    monkeypatch.setenv("S3_BUCKET_NAME", "cortexlab-pranoy-dev")

    owner = SimpleNamespace(id=uuid4())
    response = uploads.create_upload_intent(
        owner,
        UploadIntentRequest(
            experiment_id=uuid4(),
            block_id=uuid4(),
            kind="image",
            filename="face.png",
            mime_type="image/png",
            size_bytes=1024,
        ),
    )

    assert response.upload_url == "https://s3.example/presigned"
    assert captured_client_kwargs == {
        "region_name": "us-east-2",
        "endpoint_url": "https://s3.us-east-2.amazonaws.com",
        "aws_access_key_id": "access-key",
        "aws_secret_access_key": "secret-key",
    }
    uploads.get_settings.cache_clear()
