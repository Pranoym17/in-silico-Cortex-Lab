from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "local"
    database_url: str = "postgresql+asyncpg://cortex:cortex@localhost:5432/cortexlab"
    redis_url: str = "redis://localhost:6379/0"
    aws_region: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    s3_bucket_name: str = "cortexlab-local"
    s3_upload_expires_seconds: int = 900
    sqs_queue_url: str = "http://localhost:4566/000000000000/cortexlab-jobs"
    supabase_jwt_secret: str = "replace-me"
    frontend_origin: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
