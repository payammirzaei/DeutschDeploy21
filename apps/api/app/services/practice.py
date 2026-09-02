import hashlib
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.learning import ActivityInstance, Attempt, CourseDay, ReleaseActivity
from app.models.user import User
from app.schemas.practice import PracticeActivityView, PracticeNextResponse
from app.services.exercises import (
    SILENT_EXERCISE_TYPES,
    UnsupportedExerciseError,
    materialize_exercise,
)
from app.services.learning import ensure_starter_learning, get_active_enrollment


async def get_next_silent_practice(
    session: AsyncSession,
    user: User,
) -> PracticeNextResponse:
    await ensure_starter_learning(session, user)
    enrollment = await get_active_enrollment(session, user.id)
    if enrollment is None:
        raise RuntimeError("Silent practice requires an active learning enrollment")

    activities = list(
        (
            await session.execute(
                select(ReleaseActivity)
                .join(CourseDay, CourseDay.id == ReleaseActivity.day_id)
                .where(CourseDay.release_id == enrollment.course_release_id)
                .order_by(CourseDay.day_number, ReleaseActivity.position)
            )
        ).scalars()
    )
    if not activities:
        raise RuntimeError("No published activities are available for silent practice")

    instance_rows = (
        await session.execute(
            select(ActivityInstance, func.count(Attempt.id))
            .outerjoin(Attempt, Attempt.activity_instance_id == ActivityInstance.id)
            .where(
                ActivityInstance.enrollment_id == enrollment.id,
                ActivityInstance.instance_key.like("silent:%"),
            )
            .group_by(ActivityInstance.id)
        )
    ).all()
    counts: dict[tuple[UUID, str], int] = {
        (instance.release_activity_id, instance.exercise_type): int(attempt_count or 0)
        for instance, attempt_count in instance_rows
    }
    total_attempts = sum(counts.values())
    start_index = total_attempts % len(SILENT_EXERCISE_TYPES)
    type_order = (
        SILENT_EXERCISE_TYPES[start_index:]
        + SILENT_EXERCISE_TYPES[:start_index]
    )

    for exercise_type in type_order:
        ordered_activities = sorted(
            activities,
            key=lambda activity: (
                counts.get((activity.id, exercise_type), 0),
                _digest(f"{user.id}:{exercise_type}:{activity.id}"),
            ),
        )
        for activity in ordered_activities:
            attempt_count = counts.get((activity.id, exercise_type), 0)
            try:
                instance = await materialize_exercise(
                    session,
                    enrollment,
                    activity,
                    exercise_type,
                    f"silent:{exercise_type}",
                )
            except UnsupportedExerciseError:
                continue
            return PracticeNextResponse(
                activity=PracticeActivityView(
                    id=instance.id,
                    content_version_id=instance.content_version_id,
                    exercise_type=instance.exercise_type,
                    contract_version=instance.contract_version,
                    prompt_checksum=instance.prompt_checksum,
                    prompt=instance.prompt,
                    attempt_count=attempt_count,
                ),
                available_types=list(SILENT_EXERCISE_TYPES),
            )

    raise RuntimeError("No compatible silent exercise could be materialized")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
