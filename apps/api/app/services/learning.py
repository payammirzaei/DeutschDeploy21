from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.learning import (
    ActivityInstance,
    Attempt,
    Course,
    CourseDay,
    CourseRelease,
    Enrollment,
    Evaluation,
    ReleaseActivity,
)
from app.models.user import User
from app.schemas.learning import (
    ActivityInstanceView,
    ActivitySummary,
    AttemptIn,
    AttemptResult,
    ChoiceView,
    DayView,
    LearningHome,
    NextActivityResponse,
    StartLearningResult,
    UpgradeLearningResult,
)
from app.services.curriculum import (
    COURSE_SLUG,
    LATEST_RELEASE_VERSION,
    ensure_curriculum_releases,
)
from app.services.exercise_registry import (
    evaluate_registered_exercise,
    materialize_registered_exercise,
)
from app.services.interview_drills import (
    load_interview_drills,
    materialize_interview_drill,
)


async def ensure_starter_learning(
    session: AsyncSession,
    user: User,
) -> StartLearningResult:
    _, _, latest = await ensure_curriculum_releases(session, user)
    enrollment = await get_active_enrollment(session, user.id)
    created_enrollment = enrollment is None

    if enrollment is None:
        enrollment = Enrollment(
            user_id=user.id,
            course_release_id=latest.id,
            status="active",
            current_day=1,
        )
        session.add(enrollment)
        await session.flush()

    release = await session.get(CourseRelease, enrollment.course_release_id)
    if release is None:
        raise RuntimeError("Enrollment references a missing course release")

    return StartLearningResult(
        enrollment_id=enrollment.id,
        course_release_id=release.id,
        release_version=release.version_number,
        created_enrollment=created_enrollment,
        pinned_activity_count=await _release_activity_count(
            session,
            release.id,
        ),
    )


async def upgrade_to_latest_release(
    session: AsyncSession,
    user: User,
) -> UpgradeLearningResult:
    _, _, latest = await ensure_curriculum_releases(session, user)
    active = await get_active_enrollment(session, user.id)

    if active is None:
        active = Enrollment(
            user_id=user.id,
            course_release_id=latest.id,
            status="active",
            current_day=1,
        )
        session.add(active)
        await session.flush()
        return UpgradeLearningResult(
            enrollment_id=active.id,
            from_release_version=None,
            to_release_version=LATEST_RELEASE_VERSION,
            created_enrollment=True,
            carried_completed_days=0,
            current_day=1,
            pinned_activity_count=await _release_activity_count(
                session,
                latest.id,
            ),
        )

    active_release = await session.get(
        CourseRelease,
        active.course_release_id,
    )
    if active_release is None:
        raise RuntimeError("Active enrollment references a missing release")

    if active_release.version_number == LATEST_RELEASE_VERSION:
        days = await _day_views(session, active)
        return UpgradeLearningResult(
            enrollment_id=active.id,
            from_release_version=active_release.version_number,
            to_release_version=active_release.version_number,
            created_enrollment=False,
            carried_completed_days=sum(day.completed for day in days),
            current_day=active.current_day,
            pinned_activity_count=await _release_activity_count(
                session,
                active_release.id,
            ),
        )

    existing_latest = await session.scalar(
        select(Enrollment).where(
            Enrollment.user_id == user.id,
            Enrollment.course_release_id == latest.id,
        )
    )
    created_enrollment = existing_latest is None
    if existing_latest is None:
        existing_latest = Enrollment(
            user_id=user.id,
            course_release_id=latest.id,
            status="active",
            current_day=1,
        )
        session.add(existing_latest)
        await session.flush()
    else:
        existing_latest.status = "active"

    active.status = "superseded"
    days = await _day_views(session, existing_latest)
    current_day = _first_incomplete_from_views(days)
    existing_latest.current_day = current_day
    await session.flush()

    return UpgradeLearningResult(
        enrollment_id=existing_latest.id,
        from_release_version=active_release.version_number,
        to_release_version=LATEST_RELEASE_VERSION,
        created_enrollment=created_enrollment,
        carried_completed_days=sum(day.completed for day in days),
        current_day=current_day,
        pinned_activity_count=await _release_activity_count(
            session,
            latest.id,
        ),
    )


async def get_learning_home(
    session: AsyncSession,
    user: User,
) -> LearningHome:
    enrollment = await get_active_enrollment(session, user.id)
    if enrollment is None:
        return LearningHome(
            enrolled=False,
            latest_release_version=LATEST_RELEASE_VERSION,
        )

    release = await session.get(CourseRelease, enrollment.course_release_id)
    if release is None:
        raise RuntimeError("Enrollment references a missing course release")
    course = await session.get(Course, release.course_id)
    if course is None:
        raise RuntimeError("Course release references a missing course")

    days = await _day_views(session, enrollment)
    return LearningHome(
        enrolled=True,
        enrollment_id=enrollment.id,
        course_title=course.title,
        release_version=release.version_number,
        latest_release_version=LATEST_RELEASE_VERSION,
        upgrade_available=release.version_number < LATEST_RELEASE_VERSION,
        current_day=enrollment.current_day,
        available_through_day=max(
            (day.day_number for day in days),
            default=0,
        ),
        course_complete=bool(days) and all(day.completed for day in days),
        days=days,
    )


async def get_day_view(
    session: AsyncSession,
    user: User,
    day_number: int,
) -> DayView:
    enrollment = await _require_user_enrollment(session, user.id)
    days = await _day_views(session, enrollment)
    for day in days:
        if day.day_number == day_number:
            return day
    raise LookupError("Learning day not found")


async def get_next_activity(
    session: AsyncSession,
    user: User,
    day_number: int,
) -> NextActivityResponse:
    enrollment = await _require_user_enrollment(session, user.id)
    day = await session.scalar(
        select(CourseDay).where(
            CourseDay.release_id == enrollment.course_release_id,
            CourseDay.day_number == day_number,
        )
    )
    if day is None:
        raise LookupError("Learning day not found")

    activities = list(
        (
            await session.execute(
                select(ReleaseActivity)
                .where(ReleaseActivity.day_id == day.id)
                .order_by(ReleaseActivity.position)
            )
        ).scalars()
    )
    for activity in activities:
        if await _activity_submitted(
            session,
            enrollment,
            activity,
        ):
            continue
        instance = await _get_or_create_instance(
            session,
            enrollment,
            activity,
        )
        return NextActivityResponse(
            completed=False,
            activity=_instance_view(
                day.day_number,
                activity.position,
                instance,
            ),
        )

    return NextActivityResponse(completed=True)


async def submit_attempt(
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
            raise PermissionError(
                "Idempotency key belongs to another user"
            )
        evaluation = await session.scalar(
            select(Evaluation).where(Evaluation.attempt_id == existing.id)
        )
        if evaluation is None:
            raise RuntimeError("Attempt exists without evaluation")
        instance = await session.get(
            ActivityInstance,
            existing.activity_instance_id,
        )
        if instance is None:
            raise RuntimeError(
                "Attempt references a missing activity instance"
            )
        enrollment = await session.get(
            Enrollment,
            existing.enrollment_id,
        )
        if enrollment is None:
            raise RuntimeError(
                "Attempt references a missing enrollment"
            )
        day_complete, next_day = await _progress_after_attempt(
            session,
            enrollment,
            instance,
            mutate=False,
        )
        return _attempt_result(
            existing,
            evaluation,
            day_complete,
            next_day,
        )

    instance = await session.get(ActivityInstance, instance_id)
    if instance is None:
        raise LookupError("Activity instance not found")
    enrollment = await session.get(Enrollment, instance.enrollment_id)
    if enrollment is None or enrollment.user_id != user.id:
        raise PermissionError(
            "Activity instance does not belong to this user"
        )

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

    day_complete, next_day = await _progress_after_attempt(
        session,
        enrollment,
        instance,
        mutate=True,
    )
    return _attempt_result(
        attempt,
        evaluation,
        day_complete,
        next_day,
    )


async def get_active_enrollment(
    session: AsyncSession,
    user_id: UUID,
) -> Enrollment | None:
    return await session.scalar(
        select(Enrollment)
        .join(
            CourseRelease,
            CourseRelease.id == Enrollment.course_release_id,
        )
        .join(Course, Course.id == CourseRelease.course_id)
        .where(
            Enrollment.user_id == user_id,
            Enrollment.status == "active",
            Course.slug == COURSE_SLUG,
        )
        .order_by(CourseRelease.version_number.desc())
        .limit(1)
    )


async def _require_user_enrollment(
    session: AsyncSession,
    user_id: UUID,
) -> Enrollment:
    enrollment = await get_active_enrollment(session, user_id)
    if enrollment is None:
        raise LookupError("Learning course has not been started")
    return enrollment


async def _day_views(
    session: AsyncSession,
    enrollment: Enrollment,
) -> list[DayView]:
    days = list(
        (
            await session.execute(
                select(CourseDay)
                .where(
                    CourseDay.release_id == enrollment.course_release_id
                )
                .order_by(CourseDay.day_number)
            )
        ).scalars()
    )
    result: list[DayView] = []
    for day in days:
        activities = list(
            (
                await session.execute(
                    select(ReleaseActivity)
                    .where(ReleaseActivity.day_id == day.id)
                    .order_by(ReleaseActivity.position)
                )
            ).scalars()
        )
        activity_views: list[ActivitySummary] = []
        submitted_count = 0
        for activity in activities:
            submitted = await _activity_submitted(
                session,
                enrollment,
                activity,
            )
            if submitted:
                submitted_count += 1
            activity_views.append(
                ActivitySummary(
                    activity_id=activity.id,
                    position=activity.position,
                    source_kind=activity.source_kind,
                    source_key=activity.source_key,
                    content_version_id=activity.content_version_id,
                    exercise_type=activity.exercise_type,
                    submitted=submitted,
                )
            )
        result.append(
            DayView(
                day_number=day.day_number,
                title=day.title,
                objective=day.objective,
                completed=(
                    bool(activity_views)
                    and submitted_count == len(activity_views)
                ),
                submitted_count=submitted_count,
                total_count=len(activity_views),
                activities=activity_views,
            )
        )
    return result


async def _activity_submitted(
    session: AsyncSession,
    enrollment: Enrollment,
    activity: ReleaseActivity,
) -> bool:
    current_attempt = await session.scalar(
        select(Attempt.id)
        .join(
            ActivityInstance,
            ActivityInstance.id == Attempt.activity_instance_id,
        )
        .where(
            Attempt.enrollment_id == enrollment.id,
            ActivityInstance.release_activity_id == activity.id,
            ActivityInstance.instance_key == "course",
        )
        .limit(1)
    )
    if current_attempt is not None:
        return True

    if (
        activity.source_kind != "content"
        or activity.content_version_id is None
    ):
        return False

    current_release = await session.get(
        CourseRelease,
        enrollment.course_release_id,
    )
    if current_release is None:
        raise RuntimeError("Enrollment references a missing release")

    carried_attempt = await session.scalar(
        select(Attempt.id)
        .join(
            ActivityInstance,
            ActivityInstance.id == Attempt.activity_instance_id,
        )
        .join(
            Enrollment,
            Enrollment.id == Attempt.enrollment_id,
        )
        .join(
            CourseRelease,
            CourseRelease.id == Enrollment.course_release_id,
        )
        .where(
            Attempt.user_id == enrollment.user_id,
            Attempt.enrollment_id != enrollment.id,
            ActivityInstance.instance_key == "course",
            ActivityInstance.content_version_id
            == activity.content_version_id,
            ActivityInstance.exercise_type == activity.exercise_type,
            CourseRelease.course_id == current_release.course_id,
            CourseRelease.version_number
            < current_release.version_number,
        )
        .limit(1)
    )
    return carried_attempt is not None


async def _get_or_create_instance(
    session: AsyncSession,
    enrollment: Enrollment,
    activity: ReleaseActivity,
) -> ActivityInstance:
    if activity.source_kind == "interview_drill":
        drills = {
            str(drill["external_id"]): drill
            for drill in load_interview_drills()
        }
        drill = drills.get(activity.source_key)
        if drill is None:
            raise RuntimeError(
                f"Interview drill missing: {activity.source_key}"
            )
        return await materialize_interview_drill(
            session,
            enrollment,
            drill,
            instance_key="course",
            release_activity_id=activity.id,
            runtime_source_key=f"{activity.source_key}:{activity.id}",
        )

    if activity.source_kind != "content":
        raise RuntimeError(
            f"Unsupported release source: {activity.source_kind}"
        )
    if activity.content_version_id is None:
        raise RuntimeError(
            "Content release activity is missing a pinned version"
        )
    return await materialize_registered_exercise(
        session,
        enrollment,
        activity,
        activity.exercise_type,
        "course",
    )


async def _progress_after_attempt(
    session: AsyncSession,
    enrollment: Enrollment,
    instance: ActivityInstance,
    *,
    mutate: bool,
) -> tuple[bool, int]:
    if instance.instance_key != "course":
        return False, enrollment.current_day
    if instance.release_activity_id is None:
        raise RuntimeError(
            "Course instance is missing its release activity"
        )

    activity = await session.get(
        ReleaseActivity,
        instance.release_activity_id,
    )
    if activity is None:
        raise RuntimeError(
            "Activity instance references a missing release activity"
        )
    day = await session.get(CourseDay, activity.day_id)
    if day is None:
        raise RuntimeError("Release activity references a missing day")

    day_complete = await _is_day_complete(
        session,
        enrollment,
        day,
    )
    if mutate:
        views = await _day_views(session, enrollment)
        enrollment.current_day = _first_incomplete_from_views(views)
        await session.flush()
    return day_complete, enrollment.current_day


async def _is_day_complete(
    session: AsyncSession,
    enrollment: Enrollment,
    day: CourseDay,
) -> bool:
    activities = list(
        (
            await session.execute(
                select(ReleaseActivity)
                .where(
                    ReleaseActivity.day_id == day.id,
                    ReleaseActivity.required.is_(True),
                )
                .order_by(ReleaseActivity.position)
            )
        ).scalars()
    )
    if not activities:
        return False
    for activity in activities:
        if not await _activity_submitted(
            session,
            enrollment,
            activity,
        ):
            return False
    return True


async def _release_activity_count(
    session: AsyncSession,
    release_id: UUID,
) -> int:
    rows = await session.execute(
        select(ReleaseActivity.id)
        .join(CourseDay, CourseDay.id == ReleaseActivity.day_id)
        .where(CourseDay.release_id == release_id)
    )
    return len(rows.scalars().all())


def _first_incomplete_from_views(days: list[DayView]) -> int:
    for day in days:
        if not day.completed:
            return day.day_number
    return max((day.day_number for day in days), default=0) + 1


def _instance_view(
    day_number: int,
    position: int,
    instance: ActivityInstance,
) -> ActivityInstanceView:
    choices = instance.prompt.get("choices", [])
    label = (
        instance.prompt.get("lemma")
        or instance.prompt.get("target_label")
        or instance.prompt.get("category")
        or "Interview"
    )
    return ActivityInstanceView(
        id=instance.id,
        day_number=day_number,
        position=position,
        source_kind=instance.source_kind,
        source_key=instance.source_key,
        content_version_id=instance.content_version_id,
        exercise_type=instance.exercise_type,
        contract_version=instance.contract_version,
        prompt_checksum=instance.prompt_checksum,
        lemma=str(label),
        question=str(instance.prompt["question"]),
        choices=[
            ChoiceView.model_validate(choice)
            for choice in choices
        ],
        prompt=instance.prompt,
    )


def _attempt_result(
    attempt: Attempt,
    evaluation: Evaluation,
    day_complete: bool,
    next_day: int,
) -> AttemptResult:
    return AttemptResult(
        attempt_id=attempt.id,
        evaluation_id=evaluation.id,
        correct=evaluation.correct,
        score=evaluation.score,
        feedback_code=evaluation.feedback_code,
        day_complete=day_complete,
        next_day=next_day,
    )
