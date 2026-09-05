from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mastery import LearnerMastery, MasteryEvent
from app.models.user import User
from app.schemas.engagement import EngagementBadge, EngagementSummary

XP_PER_LEVEL = 250
LEARNER_TIMEZONE = "Europe/Berlin"


def _event_xp(score: int) -> int:
    bounded_score = max(0, min(100, score))
    return 10 + round(bounded_score / 20)


def _streak_metrics(
    timestamps: Sequence[datetime],
    *,
    now: datetime | None = None,
    timezone_name: str = LEARNER_TIMEZONE,
) -> tuple[int, int]:
    if not timestamps:
        return 0, 0

    timezone = ZoneInfo(timezone_name)
    today = (now or datetime.now(UTC)).astimezone(timezone).date()
    active_days = sorted({timestamp.astimezone(timezone).date() for timestamp in timestamps})

    longest = 1
    running = 1
    for previous, current in zip(active_days, active_days[1:], strict=False):
        if current - previous == timedelta(days=1):
            running += 1
            longest = max(longest, running)
        else:
            running = 1

    latest = active_days[-1]
    if latest not in {today, today - timedelta(days=1)}:
        return 0, longest

    current_streak = 1
    cursor: date = latest
    active_set = set(active_days)
    while cursor - timedelta(days=1) in active_set:
        cursor -= timedelta(days=1)
        current_streak += 1

    return current_streak, longest


def _badge(
    key: str,
    title: str,
    description: str,
    current: int,
    target: int,
) -> EngagementBadge:
    return EngagementBadge(
        key=key,
        title=title,
        description=description,
        earned=current >= target,
        progress_current=min(current, target),
        progress_target=target,
    )


def _badges(total_reps: int, longest_streak: int, mastered_targets: int) -> list[EngagementBadge]:
    return [
        _badge(
            "first_rep",
            "First rep",
            "Submit your first graded practice attempt.",
            total_reps,
            1,
        ),
        _badge("reps_25", "Momentum", "Complete 25 graded reps.", total_reps, 25),
        _badge("reps_100", "Century", "Complete 100 graded reps.", total_reps, 100),
        _badge(
            "streak_3",
            "Three in a row",
            "Practice on three consecutive days.",
            longest_streak,
            3,
        ),
        _badge("streak_7", "Week streak", "Practice on seven consecutive days.", longest_streak, 7),
        _badge(
            "mastery_10",
            "Ten mastered",
            "Reach mastered state on ten learning targets.",
            mastered_targets,
            10,
        ),
    ]


async def get_engagement_summary(session: AsyncSession, user: User) -> EngagementSummary:
    events = list(
        (
            await session.scalars(
                select(MasteryEvent)
                .where(MasteryEvent.user_id == user.id)
                .order_by(MasteryEvent.occurred_at.asc())
            )
        ).all()
    )
    mastered_targets = int(
        await session.scalar(
            select(func.count(LearnerMastery.id)).where(
                LearnerMastery.user_id == user.id,
                LearnerMastery.state == "mastered",
            )
        )
        or 0
    )

    total_reps = len(events)
    correct_reps = sum(1 for event in events if event.correct)
    xp = sum(_event_xp(event.score) for event in events)
    level = xp // XP_PER_LEVEL + 1
    level_progress = xp % XP_PER_LEVEL
    current_streak, longest_streak = _streak_metrics([event.occurred_at for event in events])
    accuracy = round((correct_reps / total_reps) * 100) if total_reps else 0

    return EngagementSummary(
        xp=xp,
        level=level,
        level_progress_percent=round((level_progress / XP_PER_LEVEL) * 100),
        next_level_xp=level * XP_PER_LEVEL,
        current_streak_days=current_streak,
        longest_streak_days=longest_streak,
        total_reps=total_reps,
        correct_reps=correct_reps,
        accuracy_percent=accuracy,
        mastered_targets=mastered_targets,
        timezone=LEARNER_TIMEZONE,
        badges=_badges(total_reps, longest_streak, mastered_targets),
    )
