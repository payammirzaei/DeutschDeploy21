from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import VerbVersion
from app.models.learning import ActivityInstance, Attempt, Evaluation
from app.models.mastery import LearnerMastery, LearningTarget, MasteryEvent, ReviewQueueEntry
from app.models.user import User
from app.schemas.mastery import (
    MasteryTargetView,
    RebuildMasteryResult,
    ReviewActivityView,
    ReviewHome,
    ReviewNextResponse,
    ReviewQueueItem,
)
from app.services.exercise_registry import learning_target_descriptor

SCHEDULER_VERSION = 1


def utcnow() -> datetime:
    return datetime.now(UTC)


def _schedule(
    correct: bool,
    streak: int,
    lapses: int,
) -> tuple[str, timedelta, float, float, str]:
    if not correct:
        return (
            "review",
            timedelta(minutes=10),
            0.35,
            min(1.0, 0.6 + lapses * 0.05),
            "recent_failure",
        )
    if streak <= 1:
        return "learning", timedelta(days=1), 1.0, 0.5, "first_success"
    if streak == 2:
        return "review", timedelta(days=3), 2.0, 0.45, "building_recall"
    if streak <= 4:
        return "stable", timedelta(days=7), 5.0, 0.4, "stable_recall"
    return "mastered", timedelta(days=21), 12.0, 0.35, "mastery_maintenance"


async def record_attempt_evidence(
    session: AsyncSession,
    user: User,
    attempt: Attempt,
    evaluation: Evaluation,
    instance: ActivityInstance,
) -> None:
    existing = await session.scalar(
        select(MasteryEvent).where(MasteryEvent.attempt_id == attempt.id)
    )
    if existing is not None:
        return

    descriptor = learning_target_descriptor(instance)
    target = await session.scalar(
        select(LearningTarget).where(
            LearningTarget.target_key == descriptor["target_key"]
        )
    )
    if target is None:
        content_version_value = descriptor["content_version_id"]
        content_version_id = (
            UUID(str(content_version_value)) if content_version_value is not None else None
        )
        target = LearningTarget(
            target_key=str(descriptor["target_key"]),
            target_label=descriptor["target_label"],
            target_kind=str(descriptor["target_kind"]),
            content_version_id=content_version_id,
            skill_dimension=str(descriptor["skill_dimension"]),
            production_mode=str(descriptor["production_mode"]),
            policy_version=SCHEDULER_VERSION,
        )
        session.add(target)
        await session.flush()

    mastery = await session.scalar(
        select(LearnerMastery).where(
            LearnerMastery.user_id == user.id,
            LearnerMastery.target_id == target.id,
        )
    )
    previous_streak = mastery.success_streak if mastery else 0
    previous_lapses = mastery.lapses if mastery else 0
    streak = previous_streak + 1 if evaluation.correct else 0
    lapses = previous_lapses + (0 if evaluation.correct else 1)
    state, interval, stability, difficulty, explanation = _schedule(
        evaluation.correct,
        streak,
        lapses,
    )
    now = attempt.submitted_at
    due_at = now + interval
    sequence = int(
        await session.scalar(
            select(func.coalesce(func.max(MasteryEvent.event_sequence), 0)).where(
                MasteryEvent.user_id == user.id
            )
        )
        or 0
    ) + 1
    grade = 4 if evaluation.correct else 1
    event = MasteryEvent(
        user_id=user.id,
        target_id=target.id,
        attempt_id=attempt.id,
        event_sequence=sequence,
        grade=grade,
        correct=evaluation.correct,
        score=evaluation.score,
        evidence_weight=1.0,
        policy_version=SCHEDULER_VERSION,
        occurred_at=now,
    )
    session.add(event)

    confidence = min(1.0, ((mastery.evidence_count if mastery else 0) + 1) / 5)
    if mastery is None:
        mastery = LearnerMastery(user_id=user.id, target_id=target.id)
        session.add(mastery)
    mastery.state = state
    mastery.stability = stability
    mastery.difficulty = difficulty
    mastery.confidence = confidence
    mastery.success_streak = streak
    mastery.lapses = lapses
    mastery.evidence_count = (mastery.evidence_count or 0) + 1
    mastery.last_attempt_at = now
    mastery.last_success_at = now if evaluation.correct else mastery.last_success_at
    mastery.next_review_at = due_at
    mastery.last_event_sequence = sequence
    mastery.scheduler_version = SCHEDULER_VERSION
    mastery.explanation_code = explanation

    queue = await session.scalar(
        select(ReviewQueueEntry).where(
            ReviewQueueEntry.user_id == user.id,
            ReviewQueueEntry.target_id == target.id,
        )
    )
    priority = 100 if not evaluation.correct else max(20, 70 - streak * 10)
    if queue is None:
        queue = ReviewQueueEntry(
            user_id=user.id,
            target_id=target.id,
            activity_instance_id=instance.id,
            due_at=due_at,
            priority=priority,
            reason_code=explanation,
            scheduler_version=SCHEDULER_VERSION,
        )
        session.add(queue)
    else:
        queue.activity_instance_id = instance.id
        queue.due_at = due_at
        queue.priority = priority
        queue.reason_code = explanation
        queue.scheduler_version = SCHEDULER_VERSION
        queue.updated_at = utcnow()
    await session.flush()


async def get_review_home(session: AsyncSession, user: User) -> ReviewHome:
    now = utcnow()
    rows = (
        await session.execute(
            select(ReviewQueueEntry, LearningTarget, LearnerMastery, VerbVersion)
            .join(LearningTarget, LearningTarget.id == ReviewQueueEntry.target_id)
            .join(
                LearnerMastery,
                (LearnerMastery.target_id == LearningTarget.id)
                & (LearnerMastery.user_id == ReviewQueueEntry.user_id),
            )
            .outerjoin(VerbVersion, VerbVersion.version_id == LearningTarget.content_version_id)
            .where(ReviewQueueEntry.user_id == user.id)
            .order_by(ReviewQueueEntry.due_at, ReviewQueueEntry.priority.desc())
        )
    ).all()
    due: list[ReviewQueueItem] = []
    mastery_views: list[MasteryTargetView] = []
    weak_count = 0
    mastered_count = 0
    for queue, target, mastery, verb in rows:
        label = _target_label(target, verb)
        if mastery.state in {"review", "learning"}:
            weak_count += 1
        if mastery.state == "mastered":
            mastered_count += 1
        mastery_views.append(
            MasteryTargetView(
                target_id=target.id,
                target_kind=target.target_kind,
                target_label=label,
                content_version_id=target.content_version_id,
                lemma=label,
                skill_dimension=target.skill_dimension,
                state=mastery.state,
                stability=mastery.stability,
                difficulty=mastery.difficulty,
                confidence=mastery.confidence,
                success_streak=mastery.success_streak,
                lapses=mastery.lapses,
                evidence_count=mastery.evidence_count,
                next_review_at=mastery.next_review_at,
                explanation_code=mastery.explanation_code,
            )
        )
        if queue.due_at <= now:
            due.append(
                ReviewQueueItem(
                    target_id=target.id,
                    target_kind=target.target_kind,
                    activity_instance_id=queue.activity_instance_id,
                    content_version_id=target.content_version_id,
                    lemma=label,
                    due_at=queue.due_at,
                    overdue=queue.due_at < now,
                    priority=queue.priority,
                    reason_code=queue.reason_code,
                    state=mastery.state,
                )
            )
    next_due = rows[0][0].due_at if rows else None
    return ReviewHome(
        due_count=len(due),
        scheduled_count=len(rows),
        weak_count=weak_count,
        mastered_count=mastered_count,
        next_due_at=next_due,
        due=due,
        mastery=mastery_views,
    )


async def get_next_review(session: AsyncSession, user: User) -> ReviewNextResponse:
    now = utcnow()
    row = (
        await session.execute(
            select(
                ReviewQueueEntry,
                LearningTarget,
                LearnerMastery,
                ActivityInstance,
                VerbVersion,
            )
            .join(LearningTarget, LearningTarget.id == ReviewQueueEntry.target_id)
            .join(
                LearnerMastery,
                (LearnerMastery.target_id == LearningTarget.id)
                & (LearnerMastery.user_id == ReviewQueueEntry.user_id),
            )
            .join(ActivityInstance, ActivityInstance.id == ReviewQueueEntry.activity_instance_id)
            .outerjoin(VerbVersion, VerbVersion.version_id == LearningTarget.content_version_id)
            .where(
                ReviewQueueEntry.user_id == user.id,
                ReviewQueueEntry.due_at <= now,
            )
            .order_by(ReviewQueueEntry.priority.desc(), ReviewQueueEntry.due_at)
            .limit(1)
        )
    ).first()
    if row is None:
        return ReviewNextResponse(completed=True)
    queue, target, mastery, instance, verb = row
    label = _target_label(target, verb)
    return ReviewNextResponse(
        completed=False,
        activity=ReviewActivityView(
            target_id=target.id,
            target_kind=target.target_kind,
            activity_instance_id=instance.id,
            content_version_id=target.content_version_id,
            exercise_type=instance.exercise_type,
            contract_version=instance.contract_version,
            prompt_checksum=instance.prompt_checksum,
            prompt=instance.prompt,
            lemma=label,
            question=str(instance.prompt["question"]),
            choices=list(instance.prompt.get("choices", [])),
            reason_code=queue.reason_code,
            due_at=queue.due_at,
            state=mastery.state,
        ),
    )


async def rebuild_mastery(session: AsyncSession, user: User) -> RebuildMasteryResult:
    attempts = (
        await session.execute(
            select(Attempt, Evaluation, ActivityInstance)
            .join(Evaluation, Evaluation.attempt_id == Attempt.id)
            .join(ActivityInstance, ActivityInstance.id == Attempt.activity_instance_id)
            .where(Attempt.user_id == user.id)
            .order_by(Attempt.submitted_at, Attempt.id)
        )
    ).all()
    await session.execute(
        delete(ReviewQueueEntry).where(ReviewQueueEntry.user_id == user.id)
    )
    await session.execute(delete(LearnerMastery).where(LearnerMastery.user_id == user.id))
    await session.execute(delete(MasteryEvent).where(MasteryEvent.user_id == user.id))
    await session.flush()
    for attempt, evaluation, instance in attempts:
        await record_attempt_evidence(session, user, attempt, evaluation, instance)
    target_count = int(
        await session.scalar(
            select(func.count(LearnerMastery.id)).where(LearnerMastery.user_id == user.id)
        )
        or 0
    )
    queue_count = int(
        await session.scalar(
            select(func.count(ReviewQueueEntry.id)).where(ReviewQueueEntry.user_id == user.id)
        )
        or 0
    )
    return RebuildMasteryResult(
        event_count=len(attempts),
        target_count=target_count,
        queue_count=queue_count,
    )


def _target_label(target: LearningTarget, verb: VerbVersion | None) -> str:
    if target.target_label:
        return target.target_label
    if verb is not None:
        return verb.infinitive
    return target.target_key
