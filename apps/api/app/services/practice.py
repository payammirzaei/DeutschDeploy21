import hashlib
from collections import defaultdict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.learning import (
    ActivityInstance,
    Attempt,
    CourseDay,
    ReleaseActivity,
)
from app.models.mastery import LearnerMastery, LearningTarget
from app.models.user import User
from app.schemas.practice import PracticeActivityView, PracticeNextResponse
from app.services.exercise_registry import (
    ALL_SILENT_EXERCISE_TYPES,
    UnsupportedExerciseError,
    learning_target_for_registered,
    materialize_registered_exercise,
)
from app.services.learning import (
    ensure_starter_learning,
    get_active_enrollment,
)

TAP_FIRST_EXERCISE_TYPES = {
    "meaning_multiple_choice",
    "perfect_participle_choice",
    "auxiliary_choice",
    "sentence_order",
    "meaning_matching",
    "usage_error_spotting",
    "phrase_builder",
}

_STATE_RANK = {
    "review": 0,
    "learning": 1,
    "new": 2,
    "stable": 3,
    "mastered": 4,
}


async def get_next_silent_practice(
    session: AsyncSession,
    user: User,
) -> PracticeNextResponse:
    await ensure_starter_learning(session, user)
    enrollment = await get_active_enrollment(session, user.id)
    if enrollment is None:
        raise RuntimeError(
            "Silent practice requires an active learning enrollment"
        )

    activities = list(
        (
            await session.execute(
                select(ReleaseActivity)
                .join(CourseDay, CourseDay.id == ReleaseActivity.day_id)
                .where(
                    CourseDay.release_id == enrollment.course_release_id,
                    ReleaseActivity.source_kind == "content",
                    ReleaseActivity.content_version_id.is_not(None),
                )
                .order_by(
                    CourseDay.day_number,
                    ReleaseActivity.position,
                )
            )
        ).scalars()
    )
    if not activities:
        raise RuntimeError(
            "No published content activities are available for silent practice"
        )

    instance_rows = (
        await session.execute(
            select(
                ActivityInstance,
                func.count(Attempt.id),
            )
            .outerjoin(
                Attempt,
                Attempt.activity_instance_id == ActivityInstance.id,
            )
            .where(
                ActivityInstance.enrollment_id == enrollment.id,
                ActivityInstance.instance_key.like("silent:%"),
                ActivityInstance.release_activity_id.is_not(None),
            )
            .group_by(ActivityInstance.id)
        )
    ).all()
    counts: dict[tuple[UUID, str], int] = {
        (instance.release_activity_id, instance.exercise_type): int(
            attempt_count or 0
        )
        for instance, attempt_count in instance_rows
        if instance.release_activity_id is not None
    }
    type_attempts: dict[str, int] = defaultdict(int)
    for (_, exercise_type), attempt_count in counts.items():
        type_attempts[exercise_type] += attempt_count

    mastery_rows = (
        await session.execute(
            select(LearningTarget, LearnerMastery)
            .join(
                LearnerMastery,
                LearnerMastery.target_id == LearningTarget.id,
            )
            .where(
                LearnerMastery.user_id == user.id,
                LearningTarget.content_version_id.is_not(None),
            )
        )
    ).all()
    mastery_by_identity = {
        (
            target.content_version_id,
            target.skill_dimension,
            target.production_mode,
        ): mastery
        for target, mastery in mastery_rows
    }

    missing_types = [
        exercise_type
        for exercise_type in ALL_SILENT_EXERCISE_TYPES
        if type_attempts.get(exercise_type, 0) == 0
    ]
    if missing_types:
        return await _materialize_exploration_candidate(
            session,
            user,
            enrollment,
            activities,
            counts,
            missing_types,
        )

    candidates: list[
        tuple[
            tuple[int, int, float, int, int, str],
            ReleaseActivity,
            str,
            LearnerMastery | None,
        ]
    ] = []
    for exercise_type in ALL_SILENT_EXERCISE_TYPES:
        skill_dimension, production_mode = learning_target_for_registered(
            exercise_type
        )
        for activity in activities:
            if activity.content_version_id is None:
                continue
            mastery = mastery_by_identity.get(
                (
                    activity.content_version_id,
                    skill_dimension,
                    production_mode,
                )
            )
            attempts = counts.get((activity.id, exercise_type), 0)
            candidates.append(
                (
                    _adaptive_key(
                        user.id,
                        activity.id,
                        exercise_type,
                        attempts,
                        mastery,
                    ),
                    activity,
                    exercise_type,
                    mastery,
                )
            )

    for _, activity, exercise_type, mastery in sorted(
        candidates,
        key=lambda item: item[0],
    ):
        try:
            instance = await materialize_registered_exercise(
                session,
                enrollment,
                activity,
                exercise_type,
                f"silent:{exercise_type}",
            )
        except UnsupportedExerciseError:
            continue
        return _response(
            instance,
            counts.get((activity.id, exercise_type), 0),
            strategy="adaptive_weakness",
            mastery=mastery,
        )

    raise RuntimeError(
        "No compatible silent exercise could be materialized"
    )


async def _materialize_exploration_candidate(
    session: AsyncSession,
    user: User,
    enrollment,
    activities: list[ReleaseActivity],
    counts: dict[tuple[UUID, str], int],
    missing_types: list[str],
) -> PracticeNextResponse:
    for exercise_type in missing_types:
        ordered_activities = sorted(
            activities,
            key=lambda activity: (
                counts.get((activity.id, exercise_type), 0),
                _digest(
                    f"{user.id}:{exercise_type}:{activity.id}"
                ),
            ),
        )
        for activity in ordered_activities:
            try:
                instance = await materialize_registered_exercise(
                    session,
                    enrollment,
                    activity,
                    exercise_type,
                    f"silent:{exercise_type}",
                )
            except UnsupportedExerciseError:
                continue
            return _response(
                instance,
                counts.get((activity.id, exercise_type), 0),
                strategy="explore_mix",
                mastery=None,
            )
    raise RuntimeError(
        "No compatible silent exercise could be materialized"
    )


def _adaptive_key(
    user_id: UUID,
    activity_id: UUID,
    exercise_type: str,
    attempt_count: int,
    mastery: LearnerMastery | None,
) -> tuple[int, int, float, int, int, str]:
    state = mastery.state if mastery is not None else "new"
    state_rank = _STATE_RANK.get(state, 2)
    lapse_rank = -(mastery.lapses if mastery is not None else 0)
    confidence = mastery.confidence if mastery is not None else 0.0
    interaction_rank = 0 if exercise_type in TAP_FIRST_EXERCISE_TYPES else 1
    return (
        state_rank,
        lapse_rank,
        confidence,
        interaction_rank,
        attempt_count,
        _digest(f"{user_id}:{exercise_type}:{activity_id}"),
    )


def _selection_reason(
    mastery: LearnerMastery | None,
) -> tuple[str, str]:
    if mastery is None:
        return (
            "build_evidence",
            "Fresh angle: this skill needs more evidence before the app can judge it confidently.",
        )
    if mastery.state == "review" or mastery.lapses > 0:
        return (
            "recent_miss",
            "Weak spot first: this pattern has a recent miss, so it gets another short retrieval attempt.",
        )
    if mastery.state == "learning":
        return (
            "weak_skill",
            "Still forming: this skill has limited evidence, so the mix is strengthening it now.",
        )
    if mastery.state == "stable":
        return (
            "maintain_strength",
            "Maintenance rep: this looks stable, but a quick retrieval keeps it usable.",
        )
    return (
        "mastery_refresh",
        "Long-term refresh: this skill is strong, so it only needs a light maintenance rep.",
    )


def _response(
    instance: ActivityInstance,
    attempt_count: int,
    *,
    strategy: str,
    mastery: LearnerMastery | None,
) -> PracticeNextResponse:
    if instance.content_version_id is None:
        raise RuntimeError(
            "Silent practice materialized without content identity"
        )
    if strategy == "explore_mix":
        reason_code = "fresh_family"
        reason = (
            "Exploration round: try every silent mini-game once before the mix starts targeting weaknesses."
        )
    else:
        reason_code, reason = _selection_reason(mastery)
    return PracticeNextResponse(
        strategy=strategy,
        selection_reason_code=reason_code,
        selection_reason=reason,
        interaction_mode=(
            "tap"
            if instance.exercise_type in TAP_FIRST_EXERCISE_TYPES
            else "keyboard"
        ),
        mastery_state=mastery.state if mastery is not None else "new",
        confidence=mastery.confidence if mastery is not None else 0.0,
        lapses=mastery.lapses if mastery is not None else 0,
        activity=PracticeActivityView(
            id=instance.id,
            content_version_id=instance.content_version_id,
            exercise_type=instance.exercise_type,
            contract_version=instance.contract_version,
            prompt_checksum=instance.prompt_checksum,
            prompt=instance.prompt,
            attempt_count=attempt_count,
        ),
        available_types=list(ALL_SILENT_EXERCISE_TYPES),
    )


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
