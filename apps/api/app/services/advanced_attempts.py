from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.learning import ActivityInstance, Attempt, Enrollment, Evaluation
from app.models.user import User
from app.schemas.learning import AttemptIn, AttemptResult
from app.services.exercise_registry import evaluate_registered_exercise


async def submit_advanced_attempt(
    session: AsyncSession,
    user: User,
    instance_id: UUID,
    idempotency_key: str,
    payload: AttemptIn,
) -> AttemptResult:
    existing = await session.scalar(
        select(Attempt).where(Attempt.idempotency_key == idempotency_key)
    )
    if existing is not None:
        if existing.user_id != user.id:
            raise PermissionError("Idempotency key belongs to another user")
        evaluation = await session.scalar(
            select(Evaluation).where(Evaluation.attempt_id == existing.id)
        )
        if evaluation is None:
            raise RuntimeError("Attempt exists without evaluation")
        enrollment = await session.get(Enrollment, existing.enrollment_id)
        if enrollment is None:
            raise RuntimeError("Attempt references a missing enrollment")
        return _result(existing, evaluation, enrollment.current_day)

    instance = await session.get(ActivityInstance, instance_id)
    if instance is None:
        raise LookupError("Activity instance not found")
    enrollment = await session.get(Enrollment, instance.enrollment_id)
    if enrollment is None or enrollment.user_id != user.id:
        raise PermissionError("Activity instance does not belong to this user")
    if instance.instance_key == "course":
        raise RuntimeError("Advanced optional exercises cannot replace course activities")

    raw_answer, normalized_answer, correct, score, feedback_code = (
        evaluate_registered_exercise(
            instance,
            choice_id=payload.choice_id,
            text=payload.text,
            token_ids=payload.token_ids,
            pair_ids=payload.pair_ids,
        )
    )
    attempt = Attempt(
        user_id=user.id,
        enrollment_id=enrollment.id,
        activity_instance_id=instance.id,
        idempotency_key=idempotency_key,
        raw_answer=raw_answer,
        normalized_answer=normalized_answer,
        client_duration_ms=payload.duration_ms,
    )
    session.add(attempt)
    await session.flush()

    evaluation = Evaluation(
        attempt_id=attempt.id,
        evaluator_type="deterministic",
        evaluator_version=1,
        correct=correct,
        score=score,
        feedback_code=feedback_code,
    )
    session.add(evaluation)
    await session.flush()
    return _result(attempt, evaluation, enrollment.current_day)


def _result(
    attempt: Attempt,
    evaluation: Evaluation,
    current_day: int,
) -> AttemptResult:
    return AttemptResult(
        attempt_id=attempt.id,
        evaluation_id=evaluation.id,
        correct=evaluation.correct,
        score=evaluation.score,
        feedback_code=evaluation.feedback_code,
        day_complete=False,
        next_day=current_day,
    )
