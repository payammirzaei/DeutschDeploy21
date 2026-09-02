from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import ContentItem, ContentVersion
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
)
from app.services.content import apply_verb_import, dry_run_verbs, load_starter_verbs, publish_item
from app.services.exercises import evaluate_exercise, materialize_exercise

COURSE_SLUG = "software-interview-21d"
STARTER_DAYS = [
    {
        "day": 1,
        "title": "Introduce yourself",
        "objective": "Build the vocabulary for a clear 60-second professional introduction.",
        "verbs": [
            "verb.vorstellen",
            "verb.arbeiten",
            "verb.lernen",
            "verb.sprechen",
            "verb.erklaeren",
            "verb.beschreiben",
            "verb.fragen",
        ],
    },
    {
        "day": 2,
        "title": "Explain what you build",
        "objective": "Describe software work, tools and implementation responsibilities.",
        "verbs": [
            "verb.entwickeln",
            "verb.programmieren",
            "verb.implementieren",
            "verb.bauen",
            "verb.erstellen",
            "verb.verwenden",
            "verb.nutzen",
        ],
    },
    {
        "day": 3,
        "title": "Problems and delivery",
        "objective": "Explain testing, debugging, problem solving and improvement work.",
        "verbs": [
            "verb.testen",
            "verb.pruefen",
            "verb.analysieren",
            "verb.loesen",
            "verb.finden",
            "verb.beheben",
            "verb.verbessern",
        ],
    },
]


async def ensure_starter_learning(
    session: AsyncSession,
    user: User,
) -> StartLearningResult:
    await _ensure_required_content(session, user)
    course = await session.scalar(select(Course).where(Course.slug == COURSE_SLUG))
    if course is None:
        course = Course(
            slug=COURSE_SLUG,
            title="21-Day German Software Interview Sprint",
            target_language="de",
            target_cefr="A2-B1",
            duration_days=21,
        )
        session.add(course)
        await session.flush()

    release = await session.scalar(
        select(CourseRelease)
        .where(CourseRelease.course_id == course.id, CourseRelease.version_number == 1)
        .limit(1)
    )
    if release is None:
        release = CourseRelease(course_id=course.id, version_number=1, status="published")
        session.add(release)
        await session.flush()
        await _build_release(session, release)

    enrollment = await session.scalar(
        select(Enrollment).where(
            Enrollment.user_id == user.id,
            Enrollment.course_release_id == release.id,
        )
    )
    created_enrollment = enrollment is None
    if enrollment is None:
        enrollment = Enrollment(
            user_id=user.id,
            course_release_id=release.id,
            status="active",
            current_day=1,
        )
        session.add(enrollment)
        await session.flush()

    pinned_activity_count = await session.scalar(
        select(func.count(ReleaseActivity.id))
        .join(CourseDay, CourseDay.id == ReleaseActivity.day_id)
        .where(CourseDay.release_id == release.id)
    )
    return StartLearningResult(
        enrollment_id=enrollment.id,
        course_release_id=release.id,
        created_enrollment=created_enrollment,
        pinned_activity_count=int(pinned_activity_count or 0),
    )


async def get_learning_home(session: AsyncSession, user: User) -> LearningHome:
    enrollment = await get_active_enrollment(session, user.id)
    if enrollment is None:
        return LearningHome(enrolled=False)

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
        current_day=enrollment.current_day,
        available_through_day=max((day.day_number for day in days), default=0),
        days=days,
    )


async def get_day_view(session: AsyncSession, user: User, day_number: int) -> DayView:
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

    activities = (
        await session.execute(
            select(ReleaseActivity)
            .where(ReleaseActivity.day_id == day.id)
            .order_by(ReleaseActivity.position)
        )
    ).scalars()
    for activity in activities:
        instance = await _get_or_create_instance(session, enrollment, day, activity)
        submitted = await session.scalar(
            select(Attempt.id).where(Attempt.activity_instance_id == instance.id).limit(1)
        )
        if submitted is None:
            return NextActivityResponse(
                completed=False,
                activity=_instance_view(day.day_number, activity.position, instance),
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
            raise PermissionError("Idempotency key belongs to another user")
        evaluation = await session.scalar(
            select(Evaluation).where(Evaluation.attempt_id == existing.id)
        )
        if evaluation is None:
            raise RuntimeError("Attempt exists without evaluation")
        instance = await session.get(ActivityInstance, existing.activity_instance_id)
        if instance is None:
            raise RuntimeError("Attempt references a missing activity instance")
        enrollment = await session.get(Enrollment, existing.enrollment_id)
        if enrollment is None:
            raise RuntimeError("Attempt references a missing enrollment")
        day_complete, next_day = await _progress_after_attempt(
            session,
            enrollment,
            instance,
            mutate=False,
        )
        return _attempt_result(existing, evaluation, day_complete, next_day)

    instance = await session.get(ActivityInstance, instance_id)
    if instance is None:
        raise LookupError("Activity instance not found")
    enrollment = await session.get(Enrollment, instance.enrollment_id)
    if enrollment is None or enrollment.user_id != user.id:
        raise PermissionError("Activity instance does not belong to this user")

    raw_answer, normalized_answer, correct, score, feedback_code = evaluate_exercise(
        instance,
        choice_id=payload.choice_id,
        text=payload.text,
        token_ids=payload.token_ids,
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
    return _attempt_result(attempt, evaluation, day_complete, next_day)


async def _ensure_required_content(session: AsyncSession, user: User) -> None:
    payloads = load_starter_verbs()
    required_ids = {external_id for day in STARTER_DAYS for external_id in day["verbs"]}
    required_payloads = [payload for payload in payloads if payload.external_id in required_ids]
    report = await dry_run_verbs(session, required_payloads)
    actions = {row.external_id: row.action for row in report.rows}
    missing = [
        payload
        for payload in required_payloads
        if actions[payload.external_id] == "create"
    ]
    if missing:
        await apply_verb_import(session, user, missing)

    for external_id in required_ids:
        item = await session.scalar(
            select(ContentItem).where(ContentItem.external_id == external_id)
        )
        if item is None:
            raise RuntimeError(f"Required content item missing: {external_id}")
        latest = await _latest_version(session, item.id)
        if latest is None:
            await publish_item(session, user, item.id)


async def _build_release(session: AsyncSession, release: CourseRelease) -> None:
    for day_spec in STARTER_DAYS:
        day = CourseDay(
            release_id=release.id,
            day_number=int(day_spec["day"]),
            title=str(day_spec["title"]),
            objective=str(day_spec["objective"]),
        )
        session.add(day)
        await session.flush()

        for position, external_id in enumerate(day_spec["verbs"], start=1):
            item = await session.scalar(
                select(ContentItem).where(ContentItem.external_id == external_id)
            )
            if item is None:
                raise RuntimeError(f"Cannot build release; content missing: {external_id}")
            version = await _latest_version(session, item.id)
            if version is None:
                raise RuntimeError(
                    f"Cannot build release; published version missing: {external_id}"
                )
            session.add(
                ReleaseActivity(
                    day_id=day.id,
                    position=position,
                    exercise_type="meaning_multiple_choice",
                    contract_version=1,
                    content_version_id=version.id,
                    required=True,
                )
            )
    await session.flush()


async def get_active_enrollment(
    session: AsyncSession,
    user_id: UUID,
) -> Enrollment | None:
    return await session.scalar(
        select(Enrollment)
        .join(CourseRelease, CourseRelease.id == Enrollment.course_release_id)
        .join(Course, Course.id == CourseRelease.course_id)
        .where(
            Enrollment.user_id == user_id,
            Enrollment.status == "active",
            Course.slug == COURSE_SLUG,
        )
        .order_by(CourseRelease.version_number.desc())
        .limit(1)
    )


async def _require_user_enrollment(session: AsyncSession, user_id: UUID) -> Enrollment:
    enrollment = await get_active_enrollment(session, user_id)
    if enrollment is None:
        raise LookupError("Learning course has not been started")
    return enrollment


async def _day_views(session: AsyncSession, enrollment: Enrollment) -> list[DayView]:
    days = (
        await session.execute(
            select(CourseDay)
            .where(CourseDay.release_id == enrollment.course_release_id)
            .order_by(CourseDay.day_number)
        )
    ).scalars()
    result: list[DayView] = []
    for day in days:
        activities = (
            await session.execute(
                select(ReleaseActivity)
                .where(ReleaseActivity.day_id == day.id)
                .order_by(ReleaseActivity.position)
            )
        ).scalars()
        activity_views: list[ActivitySummary] = []
        submitted_count = 0
        for activity in activities:
            instance = await session.scalar(
                select(ActivityInstance).where(
                    ActivityInstance.enrollment_id == enrollment.id,
                    ActivityInstance.release_activity_id == activity.id,
                    ActivityInstance.instance_key == "course",
                )
            )
            submitted = False
            if instance is not None:
                submitted = (
                    await session.scalar(
                        select(Attempt.id)
                        .where(Attempt.activity_instance_id == instance.id)
                        .limit(1)
                    )
                    is not None
                )
            if submitted:
                submitted_count += 1
            activity_views.append(
                ActivitySummary(
                    activity_id=activity.id,
                    position=activity.position,
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
                completed=bool(activity_views) and submitted_count == len(activity_views),
                submitted_count=submitted_count,
                total_count=len(activity_views),
                activities=activity_views,
            )
        )
    return result


async def _get_or_create_instance(
    session: AsyncSession,
    enrollment: Enrollment,
    day: CourseDay,
    activity: ReleaseActivity,
) -> ActivityInstance:
    del day
    return await materialize_exercise(
        session,
        enrollment,
        activity,
        activity.exercise_type,
        "course",
    )


async def _latest_version(session: AsyncSession, item_id: UUID) -> ContentVersion | None:
    return await session.scalar(
        select(ContentVersion)
        .where(ContentVersion.item_id == item_id)
        .order_by(ContentVersion.version_number.desc())
        .limit(1)
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

    activity = await session.get(ReleaseActivity, instance.release_activity_id)
    if activity is None:
        raise RuntimeError("Activity instance references a missing release activity")
    day = await session.get(CourseDay, activity.day_id)
    if day is None:
        raise RuntimeError("Release activity references a missing day")

    day_complete = await _is_day_complete(session, enrollment, day)
    if mutate and day_complete and enrollment.current_day <= day.day_number:
        enrollment.current_day = day.day_number + 1
        await session.flush()
    return day_complete, enrollment.current_day


async def _is_day_complete(
    session: AsyncSession,
    enrollment: Enrollment,
    day: CourseDay,
) -> bool:
    total = await session.scalar(
        select(func.count(ReleaseActivity.id)).where(
            ReleaseActivity.day_id == day.id,
            ReleaseActivity.required.is_(True),
        )
    )
    submitted = await session.scalar(
        select(func.count(func.distinct(ReleaseActivity.id)))
        .join(
            ActivityInstance,
            ActivityInstance.release_activity_id == ReleaseActivity.id,
        )
        .join(Attempt, Attempt.activity_instance_id == ActivityInstance.id)
        .where(
            ReleaseActivity.day_id == day.id,
            ReleaseActivity.required.is_(True),
            ActivityInstance.enrollment_id == enrollment.id,
            ActivityInstance.instance_key == "course",
        )
    )
    return int(total or 0) > 0 and int(total or 0) == int(submitted or 0)


def _instance_view(
    day_number: int,
    position: int,
    instance: ActivityInstance,
) -> ActivityInstanceView:
    choices = instance.prompt.get("choices", [])
    return ActivityInstanceView(
        id=instance.id,
        day_number=day_number,
        position=position,
        content_version_id=instance.content_version_id,
        exercise_type=instance.exercise_type,
        contract_version=instance.contract_version,
        prompt_checksum=instance.prompt_checksum,
        lemma=str(instance.prompt.get("lemma", "")),
        question=str(instance.prompt["question"]),
        choices=[ChoiceView.model_validate(choice) for choice in choices],
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
