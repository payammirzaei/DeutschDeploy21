import os
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import SessionFactory
from app.models.learning import (
    ActivityInstance,
    Attempt,
    CourseDay,
    Enrollment,
    ReleaseActivity,
)
from app.repositories.users import get_user_by_email
from app.schemas.learning import AttemptIn
from app.services.bootstrap import ensure_bootstrap_user
from app.services.curriculum import (
    ensure_curriculum_releases,
    load_curriculum_manifest,
    manifest_activity_count,
)
from app.services.exercise_registry import ALL_SILENT_EXERCISE_TYPES
from app.services.interview_drills import load_interview_drills
from app.services.learning import (
    get_day_view,
    get_learning_home,
    get_next_activity,
    submit_attempt,
    upgrade_to_latest_release,
)


def test_full_curriculum_manifest_has_required_coverage() -> None:
    manifest = load_curriculum_manifest()
    assert manifest["release_version"] == 3
    assert len(manifest["days"]) == 21
    assert manifest_activity_count(manifest) == 133
    assert [day["day"] for day in manifest["days"]] == list(
        range(1, 22)
    )

    introduced = [
        activity["external_id"]
        for day in manifest["days"][:15]
        for activity in day["activities"]
        if activity["source_kind"] == "content"
    ]
    assert len(introduced) == 100
    assert len(set(introduced)) == 100

    content_types = {
        activity["exercise_type"]
        for day in manifest["days"]
        for activity in day["activities"]
        if activity["source_kind"] == "content"
    }
    assert content_types == set(ALL_SILENT_EXERCISE_TYPES)

    first_three_types = [
        {activity["exercise_type"] for activity in day["activities"]}
        for day in manifest["days"][:3]
    ]
    assert all(len(exercise_types) >= 6 for exercise_types in first_three_types)

    covered_drills = {
        activity["external_id"]
        for day in manifest["days"]
        for activity in day["activities"]
        if activity["source_kind"] == "interview_drill"
    }
    catalog_drills = {
        str(drill["external_id"])
        for drill in load_interview_drills()
    }
    assert covered_drills == catalog_drills


@pytest.mark.skipif(
    os.getenv("RUN_PLATFORM_INTEGRATION") != "1",
    reason="requires PostgreSQL integration service",
)
@pytest.mark.asyncio
async def test_v1_upgrade_keeps_history_and_uses_v3_learning_contract() -> None:
    await ensure_bootstrap_user()
    settings = get_settings()
    assert settings.app_bootstrap_email is not None

    async with SessionFactory() as session:
        user = await get_user_by_email(
            session,
            str(settings.app_bootstrap_email),
        )
        assert user is not None

        course, legacy, latest = await ensure_curriculum_releases(
            session,
            user,
        )
        enrollments = list(
            (
                await session.execute(
                    select(Enrollment).where(
                        Enrollment.user_id == user.id
                    )
                )
            ).scalars()
        )
        for enrollment in enrollments:
            enrollment.status = "superseded"

        legacy_enrollment = next(
            (
                enrollment
                for enrollment in enrollments
                if enrollment.course_release_id == legacy.id
            ),
            None,
        )
        if legacy_enrollment is None:
            legacy_enrollment = Enrollment(
                user_id=user.id,
                course_release_id=legacy.id,
                status="active",
                current_day=1,
            )
            session.add(legacy_enrollment)
        else:
            legacy_enrollment.status = "active"
            legacy_enrollment.current_day = 1
        await session.flush()

        for _ in range(7):
            next_response = await get_next_activity(
                session,
                user,
                1,
            )
            assert next_response.completed is False
            assert next_response.activity is not None
            activity = next_response.activity
            assert activity.exercise_type == "meaning_multiple_choice"
            assert activity.choices
            await submit_attempt(
                session,
                user,
                activity.id,
                f"legacy-course-{uuid4()}",
                AttemptIn(choice_id=activity.choices[0].id),
            )

        await session.flush()
        old_attempt_count = int(
            await session.scalar(
                select(func.count(Attempt.id)).where(
                    Attempt.enrollment_id == legacy_enrollment.id
                )
            )
            or 0
        )
        assert old_attempt_count == 7
        assert legacy_enrollment.current_day == 2

        result = await upgrade_to_latest_release(session, user)
        assert result.from_release_version == 1
        assert result.to_release_version == 3
        assert result.created_enrollment is True
        assert result.carried_completed_days == 0
        assert result.current_day == 1
        assert result.pinned_activity_count == 133

        home = await get_learning_home(session, user)
        assert home.release_version == 3
        assert home.upgrade_available is False
        assert home.available_through_day == 21
        assert len(home.days) == 21
        assert [day.total_count for day in home.days] == [
            *([7] * 14),
            *([5] * 7),
        ]
        assert sum(day.total_count for day in home.days) == 133
        assert home.days[0].completed is False
        assert home.current_day == 1

        legacy_day_count = int(
            await session.scalar(
                select(func.count(CourseDay.id)).where(
                    CourseDay.release_id == legacy.id
                )
            )
            or 0
        )
        legacy_activity_count = int(
            await session.scalar(
                select(func.count(ReleaseActivity.id))
                .join(
                    CourseDay,
                    CourseDay.id == ReleaseActivity.day_id,
                )
                .where(CourseDay.release_id == legacy.id)
            )
            or 0
        )
        old_attempt_count_after = int(
            await session.scalar(
                select(func.count(Attempt.id)).where(
                    Attempt.enrollment_id == legacy_enrollment.id
                )
            )
            or 0
        )
        assert legacy_day_count == 3
        assert legacy_activity_count == 21
        assert old_attempt_count_after == old_attempt_count
        assert legacy_enrollment.status == "superseded"

        active = await session.scalar(
            select(Enrollment).where(
                Enrollment.id == result.enrollment_id
            )
        )
        assert active is not None
        assert active.course_release_id == latest.id

        first_course_activity = await get_next_activity(session, user, 1)
        assert first_course_activity.activity is not None
        assert first_course_activity.activity.contract_version == 2
        assert first_course_activity.activity.prompt["question_i18n"]["en"]
        assert first_course_activity.activity.prompt["question_i18n"]["fa"]
        assert first_course_activity.activity.prompt["lesson"]["example_de"]

        first_day_fifteen = await get_next_activity(
            session,
            user,
            15,
        )
        assert first_day_fifteen.activity is not None
        first_instance = await session.get(
            ActivityInstance,
            first_day_fifteen.activity.id,
        )
        assert first_instance is not None
        await submit_attempt(
            session,
            user,
            first_instance.id,
            f"day15-first-{uuid4()}",
            _correct_payload(first_instance),
        )

        second_day_fifteen = await get_next_activity(
            session,
            user,
            15,
        )
        assert second_day_fifteen.activity is not None
        second_instance = await session.get(
            ActivityInstance,
            second_day_fifteen.activity.id,
        )
        assert second_instance is not None
        await submit_attempt(
            session,
            user,
            second_instance.id,
            f"day15-second-{uuid4()}",
            _correct_payload(second_instance),
        )

        course_drill = await get_next_activity(session, user, 15)
        assert course_drill.activity is not None
        drill_instance = await session.get(
            ActivityInstance,
            course_drill.activity.id,
        )
        assert drill_instance is not None
        assert drill_instance.source_kind == "interview_drill"
        assert drill_instance.instance_key == "course"
        assert drill_instance.release_activity_id is not None
        assert drill_instance.content_version_id is None
        assert drill_instance.exercise_type == "interview_best_answer"

        await submit_attempt(
            session,
            user,
            drill_instance.id,
            f"day15-drill-{uuid4()}",
            _correct_payload(drill_instance),
        )
        day_fifteen = await get_day_view(session, user, 15)
        assert day_fifteen.submitted_count == 3
        assert day_fifteen.total_count == 5
        assert day_fifteen.completed is False
        assert active.current_day == 1

        await session.commit()


def _correct_payload(instance: ActivityInstance) -> AttemptIn:
    if "choice_id" in instance.answer_key:
        return AttemptIn(
            choice_id=str(instance.answer_key["choice_id"])
        )
    if "token_ids" in instance.answer_key:
        return AttemptIn(
            token_ids=[
                str(token_id)
                for token_id in instance.answer_key["token_ids"]
            ]
        )
    if "pair_ids" in instance.answer_key:
        return AttemptIn(
            pair_ids=[
                str(pair_id)
                for pair_id in instance.answer_key["pair_ids"]
            ]
        )
    if "text" in instance.answer_key:
        return AttemptIn(text=str(instance.answer_key["text"]))
    normalized_texts = instance.answer_key.get("normalized_texts")
    if normalized_texts:
        return AttemptIn(text=str(normalized_texts[0]))
    raise AssertionError(
        f"Unhandled answer key for {instance.exercise_type}"
    )
