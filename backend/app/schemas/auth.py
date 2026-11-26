from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class UserProfileResponse(BaseModel):
    """Authenticated user profile returned to the frontend."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: str | None = None
    avatar_url: str | None = None
    created_at: datetime


class AiQuotaResponse(BaseModel):
    """Rolling 7-day AI assistant chat and word quota status."""

    chats_used: int
    chats_limit: int
    words_used: int
    words_limit: int
    window_days: int
    is_limited: bool
    reset_at: datetime | None = None
