import hashlib
import json
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import ContentVersion, VerbVersion
from app.models.learning import ActivityInstance, CourseDay, Enrollment, ReleaseActivity
from app.services.advanced_exercises import (
    ADVANCED_EXERCISE_TYPES,
    ADVANCED_TARGETS,
    UnsupportedAdvancedExerciseError,
    evaluate_advanced,
    materialize_advanced,
)
from app.services.exercises import (
    CONTRACT_VERSION,
    SILENT_EXERCISE_TYPES,
    TARGET_BY_EXERCISE,
    UnsupportedExerciseError,
    evaluate_exercise,
    learning_target_for,
    materialize_exercise,
)

ALL_SILENT_EXERCISE_TYPES = (*SILENT_EXERCISE_TYPES, *ADVANCED_EXERCISE_TYPES)
TARGET_BY_EXERCISE.update(ADVANCED_TARGETS)


async def materialize_registered_exercise(
    session: AsyncSession,
    enrollment: Enrollment,
    activity: ReleaseActivity,
    exercise_type: str,
    instance_key: str,
) -> ActivityInstance:
    if exercise_type not in ADVANCED_EXERCISE_TYPES:
        return await materialize_exercise(
            session,
            enrollment,
            activity,
            exercise_type,
            instance_key,
        )

    existing = await session.scalar(
        select(ActivityInstance).where(
            ActivityInstance.enrollment_id == enrollment.id,
            ActivityInstance.release_activity_id == activity.id,
            ActivityInstance.instance_key == instance_key,
        )
    )
    if existing is not None:
        return existing

    version = await session.get(ContentVersion, activity.content_version_id)
    verb = await session.get(VerbVersion, activity.content_version_id)
    day = await session.get(CourseDay, activity.day_id)
    if version is None or verb is None or day is None:
        raise RuntimeError("Pinned content version cannot be materialized")

    try:
        prompt, answer_key = await materialize_advanced(
            session,
            activity,
            version,
            verb,
            day,
            exercise_type,
        )
    except UnsupportedAdvancedExerciseError as exc:
        raise UnsupportedExerciseError(str(exc)) from exc

    checksum = hashlib.sha256(
        json.dumps(prompt, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    instance = ActivityInstance(
        enrollment_id=enrollment.id,
        release_activity_id=activity.id,
        instance_key=instance_key,
        content_version_id=version.id,
        exercise_type=exercise_type,
        contract_version=CONTRACT_VERSION,
        prompt=prompt,
        answer_key=answer_key,
        prompt_checksum=checksum,
    )
    session.add(instance)
    await session.flush()
    return instance


def evaluate_registered_exercise(
    instance: ActivityInstance,
    *,
    choice_id: str | None,
    text: str | None,
    token_ids: Sequence[str] | None,
    pair_ids: Sequence[str] | None,
) -> tuple[dict, dict, bool, int, str]:
    if instance.exercise_type not in ADVANCED_EXERCISE_TYPES:
        return evaluate_exercise(
            instance,
            choice_id=choice_id,
            text=text,
            token_ids=token_ids,
        )

    try:
        raw, normalized, correct = evaluate_advanced(
            instance,
            choice_id=choice_id,
            text=text,
            token_ids=token_ids,
            pair_ids=pair_ids,
        )
    except UnsupportedAdvancedExerciseError as exc:
        raise UnsupportedExerciseError(str(exc)) from exc
    return (
        raw,
        normalized,
        correct,
        100 if correct else 0,
        "correct" if correct else "review_needed",
    )


def learning_target_for_registered(exercise_type: str) -> tuple[str, str]:
    return ADVANCED_TARGETS.get(exercise_type, learning_target_for(exercise_type))
