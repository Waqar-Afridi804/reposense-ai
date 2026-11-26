from fastapi import APIRouter, Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.auth import (
    AuthenticatedUser,
    get_current_user,
    invalidate_token_cache,
    sync_user_profile,
)
from app.db.models import UserProfile
from app.db.session import get_db
from app.schemas.auth import AiQuotaResponse, UserProfileResponse
from app.services.quota_service import get_ai_quota_status

router = APIRouter(prefix="/auth", tags=["Authentication"])
_bearer_scheme = HTTPBearer(auto_error=False)


@router.get("/me", response_model=UserProfileResponse)
def get_me(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserProfileResponse:
    """Return the authenticated user's persisted profile."""
    profile = db.get(UserProfile, current_user.id)
    if profile is None:
        profile = sync_user_profile(db, current_user, force=True)
    return profile


@router.get("/ai-quota", response_model=AiQuotaResponse)
def get_my_ai_quota(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AiQuotaResponse:
    """Return the authenticated user's 7-day AI assistant chat and word quota."""
    return AiQuotaResponse(**get_ai_quota_status(db, current_user.id))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> None:
    """Evict the current access token from the backend verification cache."""
    if credentials and credentials.credentials:
        invalidate_token_cache(credentials.credentials)
