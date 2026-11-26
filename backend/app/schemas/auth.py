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
