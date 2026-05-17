from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    id: UUID
    supabase_user_id: str
    email: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

