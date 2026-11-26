from datetime import datetime, timedelta, timezone
from uuid import UUID
from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import AiChatLog

MAX_CHATS_PER_WINDOW = 6
MAX_WORDS_PER_WINDOW = 400
QUOTA_WINDOW_DAYS = 7


def get_ai_quota_status(db: Session, user_id: UUID) -> dict:
    """Compute a user's AI assistant chat & word usage within the rolling 7-day window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=QUOTA_WINDOW_DAYS)
    row = db.execute(
        select(
            func.count(AiChatLog.id),
            func.coalesce(func.sum(AiChatLog.word_count), 0),
            func.min(AiChatLog.created_at),
        ).where(
            AiChatLog.user_id == user_id,
            AiChatLog.created_at >= cutoff,
        )
    ).one()

    chats_used = int(row[0] or 0)
    words_used = int(row[1] or 0)
    oldest_at: datetime | None = row[2]

    is_limited = chats_used >= MAX_CHATS_PER_WINDOW or words_used >= MAX_WORDS_PER_WINDOW
    reset_at: datetime | None = None
    if is_limited and oldest_at is not None:
        if oldest_at.tzinfo is None:
            oldest_at = oldest_at.replace(tzinfo=timezone.utc)
        reset_at = oldest_at + timedelta(days=QUOTA_WINDOW_DAYS)

    return {
        "chats_used": chats_used,
        "chats_limit": MAX_CHATS_PER_WINDOW,
        "words_used": words_used,
        "words_limit": MAX_WORDS_PER_WINDOW,
        "window_days": QUOTA_WINDOW_DAYS,
        "is_limited": is_limited,
        "reset_at": reset_at,
    }


def enforce_ai_quota(db: Session, user_id: UUID) -> dict:
    """Raise HTTP 429 if the user has reached 6 chats or 400 words in the last 7 days."""
    quota = get_ai_quota_status(db, user_id)
    if quota["is_limited"]:
        reset_str = (
            quota["reset_at"].strftime("%Y-%m-%d %H:%M UTC")
            if quota["reset_at"] is not None
            else f"{QUOTA_WINDOW_DAYS} days"
        )
        raise AppError(
            message=(
                f"AI assistant quota reached ({quota['chats_used']}/{MAX_CHATS_PER_WINDOW} chats, "
                f"{quota['words_used']}/{MAX_WORDS_PER_WINDOW} words). "
                f"Please wait until {reset_str} for your 7-day window to reset."
            ),
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="ai_quota_exceeded",
        )
    return quota


def record_ai_chat_usage(
    db: Session,
    user_id: UUID,
    repository_id: UUID,
    question: str,
    answer: str,
) -> None:
    """Persist a completed AI assistant chat and word count to PostgreSQL."""
    word_count = len(question.split()) + len(answer.split())
    db.add(
        AiChatLog(
            user_id=user_id,
            repository_id=repository_id,
            word_count=word_count,
        )
    )
    db.commit()
