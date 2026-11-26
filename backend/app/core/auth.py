from dataclasses import dataclass
import hashlib
from uuid import UUID
import httpx
from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.cache import auth_token_cache, profile_sync_cache
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.models import UserProfile
from app.db.session import get_db

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    """Verified Supabase Auth user identity."""

    id: UUID
    email: str
    display_name: str | None
    avatar_url: str | None


def _token_cache_key(token: str) -> str:
    return "tok:" + hashlib.sha256(token.encode("utf-8")).hexdigest()


def invalidate_token_cache(token: str | None) -> None:
    if token:
        auth_token_cache.delete(_token_cache_key(token))


def _extract_jwt_exp(token: str) -> float | None:
    import base64
    import json

    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64).decode("utf-8"))
        exp = payload.get("exp")
        return float(exp) if exp is not None else None
    except Exception:
        return None


def verify_supabase_token(token: str, settings: Settings) -> AuthenticatedUser:
    """Verify a Supabase Auth access token against Supabase /auth/v1/user."""
    import time

    exp = _extract_jwt_exp(token)
    now = time.time()
    if exp is not None and exp <= now:
        raise AppError(
            message="Session has expired. Please sign in again.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="unauthorized",
        )

    cache_key = _token_cache_key(token)
    cached = auth_token_cache.get(cache_key)
    if cached is not None:
        return cached

    supabase_url = settings.SUPABASE_URL.strip().rstrip("/")
    api_key = settings.SUPABASE_PUBLISHABLE_KEY.strip() or settings.SUPABASE_SECRET_KEY.strip()
    if not supabase_url or not api_key or "YOUR_SUPABASE" in supabase_url:
        raise AppError(
            message="Supabase Auth is not configured on the backend.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="auth_not_configured",
        )

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{supabase_url}/auth/v1/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": api_key,
                },
            )
    except httpx.TimeoutException as exc:
        raise AppError(
            message="Authentication service timed out.",
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            code="auth_timeout",
        ) from exc
    except httpx.RequestError as exc:
        raise AppError(
            message="Unable to reach authentication service.",
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="auth_network_error",
        ) from exc

    if resp.status_code in (401, 403):
        raise AppError(
            message="Invalid or expired session. Please sign in again.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="unauthorized",
        )
    if resp.status_code >= 400:
        raise AppError(
            message="Authentication verification failed.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="unauthorized",
        )

    data = resp.json()
    raw_id = data.get("id")
    email = data.get("email")
    if not raw_id or not email:
        raise AppError(
            message="Invalid user identity returned by authentication provider.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="unauthorized",
        )

    meta = data.get("user_metadata") or {}
    display_name = meta.get("full_name") or meta.get("name") or email.split("@", 1)[0]
    avatar_url = meta.get("avatar_url") or meta.get("picture")

    user = AuthenticatedUser(
        id=UUID(str(raw_id)),
        email=str(email),
        display_name=str(display_name) if display_name else None,
        avatar_url=str(avatar_url) if avatar_url else None,
    )
    ttl = min(60.0, max(1.0, exp - time.time())) if exp is not None else 60.0
    auth_token_cache.set(cache_key, user, ttl=ttl)
    return user


def sync_user_profile(db: Session, auth_user: AuthenticatedUser, force: bool = False) -> UserProfile | None:
    """Ensure the authenticated user has an up-to-date UserProfile row in PostgreSQL."""
    sync_key = f"prof:{auth_user.id}"
    if not force and profile_sync_cache.get(sync_key) is True:
        return None

    profile = db.get(UserProfile, auth_user.id)
    if profile is None:
        profile = UserProfile(
            id=auth_user.id,
            email=auth_user.email,
            display_name=auth_user.display_name,
            avatar_url=auth_user.avatar_url,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    else:
        changed = False
        if profile.email != auth_user.email:
            profile.email = auth_user.email
            changed = True
        if auth_user.display_name and profile.display_name != auth_user.display_name:
            profile.display_name = auth_user.display_name
            changed = True
        if auth_user.avatar_url and profile.avatar_url != auth_user.avatar_url:
            profile.avatar_url = auth_user.avatar_url
            changed = True
        if changed:
            db.commit()
            db.refresh(profile)

    profile_sync_cache.set(sync_key, True, ttl=300.0)
    return profile


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    """FastAPI dependency that enforces a valid Supabase Auth Bearer token."""
    if not credentials or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise AppError(
            message="Authentication required. Please sign in with Google.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="unauthorized",
        )

    auth_user = verify_supabase_token(credentials.credentials, settings)
    sync_user_profile(db, auth_user, force=False)
    return auth_user
