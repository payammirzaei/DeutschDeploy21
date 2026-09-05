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
    assert manifest["release_version"] == 4
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

    day_one = manifest["days"][0]
    assert day_one["focus_grammar"]
    assert day_one["focus_interview"]
    assert day_one["lesson_flow"]

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


def test_v3_manifest_remains_immutable_and_loadable() -> None:
    from app.services.curriculum import V3_CURRICULUM_PATH, _load_curriculum_manifest

    manifest = _load_curriculum_manifest(V3_CURRICULUM_PATH, 3)
    assert manifest["release_version"] == 3
    assert manifest_activity_count(manifest) == 133


def test_v4_lesson_overlay_is_authored_and_outside_manifest() -> None:
    from app.services.curriculum import load_curriculum_manifest
    from app.services.lesson_overlay import (
        V4_TEACHING_OVERLAY_PIN,
        compute_overlay_checksum,
        load_v4_lesson_overlay,
        teaching_block_for_position,
        verify_overlay_payload,
    )

    manifest = load_curriculum_manifest()
    assert "teaching_blocks" not in manifest["days"][0]
    overlay = load_v4_lesson_overlay()
    assert overlay.release_version == 4
    assert overlay.overlay_id == V4_TEACHING_OVERLAY_PIN.overlay_id
    assert overlay.overlay_version == V4_TEACHING_OVERLAY_PIN.overlay_version
    assert overlay.checksum == V4_TEACHING_OVERLAY_PIN.checksum
    day_one = overlay.days["1"]
    assert day_one.context_de
    assert any(block.type == "grammar" for block in day_one.teaching_blocks)
    intro = teaching_block_for_position(1, 1)
    assert intro is not None
    assert intro.example_de.startswith("Ich stelle")
    assert teaching_block_for_position(1, 2) is not None
    assert teaching_block_for_position(1, 6) is not None
    assert teaching_block_for_position(2, 4) is not None
    assert day_one.activity_stages == [
        "learn",
        "learn",
        "recognize",
        "build",
        "recall",
        "challenge",
        "challenge",
    ]
    assert day_one.activity_stages.index("recall") < day_one.activity_stages.index(
        "challenge"
    )
    assert day_one.prompt_overrides and day_one.prompt_overrides[0].activity_position == 6
    transfer = day_one.prompt_overrides[0]
    assert transfer.chunks == [
        "Ich stelle mich kurz vor.",
        "Ich arbeite als Backend-Entwickler.",
        "Zurzeit arbeite ich an einer internen API.",
    ]
    clarification = teaching_block_for_position(1, 7)
    assert clarification is not None
    assert "nachfragen" in clarification.example_de.lower() or "nachfrage" in (
        clarification.explanation_i18n.en.lower()
    )
    day_three = overlay.days["3"]
    assert "entwickelt habe" in (day_three.context_de or "")
    assert "an den APIs gearbeitet" in (day_three.context_de or "")
    positions = [block.activity_position for block in day_three.teaching_blocks]
    assert len(positions) == len(set(positions))
    arbeiten = next(item for item in overlay.days["2"].spiral if item.lemma == "arbeiten")
    assert arbeiten.stage == "reinforced"
    entwickeln = next(item for item in day_three.spiral if item.lemma == "entwickeln")
    assert entwickeln.stage == "reinforced"
    planned = day_three.planned_future
    assert planned and planned[0].status == "planned"

    mutated = overlay.model_dump(mode="json")
    mutated["days"]["1"]["context_de"] = "MUTATED CONTEXT MUST FAIL"
    with pytest.raises(RuntimeError, match="checksum"):
        verify_overlay_payload(mutated, V4_TEACHING_OVERLAY_PIN)
    assert compute_overlay_checksum(mutated) != V4_TEACHING_OVERLAY_PIN.checksum


@pytest.mark.skipif(
    os.getenv("RUN_PLATFORM_INTEGRATION") != "1",
    reason="requires PostgreSQL integration service",
)
@pytest.mark.asyncio
async def test_v4_activity_instance_keeps_pinned_content_version_pedagogy() -> None:
    from app.models.content import ContentItem, ContentVersion, VersionLocalization
    from app.services.content import (
        PEDAGOGY_FIELD,
        PEDAGOGY_LOCALE,
        apply_verb_import,
        load_starter_verbs,
        load_version_pedagogy,
        publish_item,
    )
    from app.services.exercise_registry import materialize_registered_exercise
    from app.services.learning import ensure_starter_learning, get_active_enrollment
    from app.services.lesson_overlay import load_overlay_for_release

    await ensure_bootstrap_user()
    settings = get_settings()
    assert settings.app_bootstrap_email is not None

    async with SessionFactory() as session:
        user = await get_user_by_email(session, str(settings.app_bootstrap_email))
        assert user is not None
        _, _, latest = await ensure_curriculum_releases(session, user)
        assert latest.version_number == 4
        assert load_overlay_for_release(4) is not None

        day_one = await session.scalar(
            select(CourseDay).where(
                CourseDay.release_id == latest.id,
                CourseDay.day_number == 1,
            )
        )
        assert day_one is not None
        arbeiten = await session.scalar(
            select(ReleaseActivity).where(
                ReleaseActivity.day_id == day_one.id,
                ReleaseActivity.position == 2,
            )
        )
        assert arbeiten is not None
        pinned_id = arbeiten.content_version_id
        assert pinned_id is not None

        payloads = load_starter_verbs()
        arbeiten_payload = next(
            payload for payload in payloads if payload.external_id == "verb.arbeiten"
        )
        assert arbeiten_payload.pedagogy is not None
        assert arbeiten_payload.pedagogy.usage_notes is not None
        arbeiten_payload.pedagogy.usage_notes.en = (
            "UPDATED PEDAGOGY MUST NOT LEAK INTO PINNED V4 INSTANCES"
        )
        await apply_verb_import(session, user, [arbeiten_payload])
        item = await session.scalar(
            select(ContentItem).where(ContentItem.external_id == "verb.arbeiten")
        )
        assert item is not None
        published = await publish_item(session, user, item.id)
        assert published.version_id != pinned_id

        latest_version = await session.scalar(
            select(ContentVersion)
            .where(ContentVersion.item_id == item.id)
            .order_by(ContentVersion.version_number.desc())
        )
        assert latest_version is not None
        assert latest_version.id == published.version_id

        refreshed = await session.get(ReleaseActivity, arbeiten.id)
        assert refreshed is not None
        assert refreshed.content_version_id == pinned_id

        await ensure_starter_learning(session, user)
        enrollment = await get_active_enrollment(session, user.id)
        assert enrollment is not None
        assert enrollment.course_release_id == latest.id

        instance = await materialize_registered_exercise(
            session,
            enrollment,
            refreshed,
            refreshed.exercise_type,
            "course",
        )
        assert instance.content_version_id == pinned_id

        pinned_pedagogy = await load_version_pedagogy(session, pinned_id)
        latest_pedagogy = await load_version_pedagogy(session, latest_version.id)
        assert pinned_pedagogy is not None and latest_pedagogy is not None
        assert pinned_pedagogy.usage_notes is not None
        assert latest_pedagogy.usage_notes is not None
        assert "UPDATED PEDAGOGY MUST NOT LEAK" not in pinned_pedagogy.usage_notes.en
        assert "UPDATED PEDAGOGY MUST NOT LEAK" in latest_pedagogy.usage_notes.en

        pinned_row = await session.scalar(
            select(VersionLocalization).where(
                VersionLocalization.version_id == pinned_id,
                VersionLocalization.field == PEDAGOGY_FIELD,
                VersionLocalization.locale == PEDAGOGY_LOCALE,
            )
        )
        latest_row = await session.scalar(
            select(VersionLocalization).where(
                VersionLocalization.version_id == latest_version.id,
                VersionLocalization.field == PEDAGOGY_FIELD,
                VersionLocalization.locale == PEDAGOGY_LOCALE,
            )
        )
        assert pinned_row is not None and latest_row is not None
        assert pinned_row.value != latest_row.value
        await session.commit()


@pytest.mark.skipif(
    os.getenv("RUN_PLATFORM_INTEGRATION") != "1",
    reason="requires PostgreSQL integration service",
)
@pytest.mark.asyncio
async def test_v4_overlay_exercise_contract_stays_pinned_for_historical_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Decision B: overlay prompt overrides change the graded contract and must pin.

    Historical ActivityInstances keep overlay_id / overlay_version / overlay_checksum
    and never silently grade against a newer teaching overlay.
    """
    from app.services.exercise_registry import (
        _enrich_once,
        evaluate_registered_exercise,
        materialize_registered_exercise,
    )
    from app.services.learning import ensure_starter_learning, get_active_enrollment
    from app.services.learning_experience import enrich_learning_instance
    from app.services.lesson_overlay import (
        V4_TEACHING_OVERLAY_PIN,
        LocalizedNote,
        PromptOverride,
        load_overlay_for_release,
    )

    await ensure_bootstrap_user()
    settings = get_settings()
    assert settings.app_bootstrap_email is not None

    async with SessionFactory() as session:
        user = await get_user_by_email(session, str(settings.app_bootstrap_email))
        assert user is not None
        _, _, latest = await ensure_curriculum_releases(session, user)
        assert latest.version_number == 4
        await ensure_starter_learning(session, user)
        enrollment = await get_active_enrollment(session, user.id)
        assert enrollment is not None
        enrollment.course_release_id = latest.id
        enrollment.status = "active"
        await session.flush()

        day_one = await session.scalar(
            select(CourseDay).where(
                CourseDay.release_id == latest.id,
                CourseDay.day_number == 1,
            )
        )
        assert day_one is not None
        transfer = await session.scalar(
            select(ReleaseActivity).where(
                ReleaseActivity.day_id == day_one.id,
                ReleaseActivity.position == 6,
            )
        )
        assert transfer is not None

        instance = await materialize_registered_exercise(
            session,
            enrollment,
            transfer,
            transfer.exercise_type,
            f"overlay-contract-{uuid4()}",
        )
        assert instance.exercise_type == "phrase_builder"
        contract = instance.prompt.get("overlay_contract")
        assert isinstance(contract, dict)
        assert contract["overlay_id"] == V4_TEACHING_OVERLAY_PIN.overlay_id
        assert contract["overlay_version"] == V4_TEACHING_OVERLAY_PIN.overlay_version
        assert contract["overlay_checksum"] == V4_TEACHING_OVERLAY_PIN.checksum
        assert contract["changes_answer_key"] is True
        assert instance.answer_key.get("overlay_contract") == contract
        pinned_token_ids = list(instance.answer_key["token_ids"])
        assert pinned_token_ids
        assert "Zurzeit arbeite ich an einer internen API." in [
            token.get("text") for token in instance.prompt.get("tokens") or []
        ]

        idem_key = f"overlay-hist-{uuid4()}"
        first = await submit_attempt(
            session,
            user,
            instance.id,
            idem_key,
            AttemptIn(token_ids=pinned_token_ids, duration_ms=1200),
        )
        assert first.correct is True
        first_score = first.score
        first_attempt_id = first.attempt_id

        newer_identity = {
            "overlay_id": V4_TEACHING_OVERLAY_PIN.overlay_id,
            "overlay_version": 99,
            "schema_version": V4_TEACHING_OVERLAY_PIN.schema_version,
            "checksum": "f" * 64,
        }
        newer_override = PromptOverride(
            activity_position=6,
            question_i18n=LocalizedNote(
                en="Hypothetical newer transfer prompt",
                fa="فرضی",
            ),
            chunks=[
                "This would be a completely different graded contract.",
                "Historical attempts must ignore it.",
            ],
        )

        monkeypatch.setattr(
            "app.services.learning_experience.overlay_identity_for_release",
            lambda _release: newer_identity,
        )
        monkeypatch.setattr(
            "app.services.learning_experience.prompt_override_for_position",
            lambda *_args, **_kwargs: newer_override,
        )
        monkeypatch.setattr(
            "app.services.exercise_registry.prompt_override_for_position",
            lambda *_args, **_kwargs: newer_override,
        )
        load_overlay_for_release.cache_clear()

        # Direct enrich must keep the frozen contract even if callers bypass
        # _enrich_once and the "latest" overlay advertises a new answer key.
        await enrich_learning_instance(session, instance, transfer)
        await session.refresh(instance)
        assert instance.prompt["overlay_contract"]["overlay_version"] == (
            V4_TEACHING_OVERLAY_PIN.overlay_version
        )
        assert instance.prompt["overlay_contract"]["overlay_checksum"] == (
            V4_TEACHING_OVERLAY_PIN.checksum
        )
        assert instance.answer_key["token_ids"] == pinned_token_ids
        assert "This would be a completely different graded contract." not in [
            token.get("text") for token in instance.prompt.get("tokens") or []
        ]

        reloaded = await _enrich_once(session, instance, transfer)
        assert reloaded.id == instance.id
        assert reloaded.answer_key["token_ids"] == pinned_token_ids
        assert reloaded.prompt["overlay_contract"]["overlay_checksum"] == (
            V4_TEACHING_OVERLAY_PIN.checksum
        )
        # Checksum may refresh for teaching presentation, but graded identity stays.
        assert reloaded.answer_key.get("overlay_contract") == contract

        _, _, still_correct, _, _ = evaluate_registered_exercise(
            instance,
            choice_id=None,
            text=None,
            token_ids=pinned_token_ids,
            pair_ids=None,
        )
        assert still_correct is True

        reversed_ids = list(reversed(pinned_token_ids))
        _, _, wrong_order, _, _ = evaluate_registered_exercise(
            instance,
            choice_id=None,
            text=None,
            token_ids=reversed_ids,
            pair_ids=None,
        )
        assert wrong_order is False

        # Hypothetical newer overlay chunk ids are rejected by the pinned instance.
        with pytest.raises(ValueError, match="do not match this activity instance"):
            evaluate_registered_exercise(
                instance,
                choice_id=None,
                text=None,
                token_ids=["overlay-6-0", "overlay-6-1"],
                pair_ids=None,
            )
        replay = await submit_attempt(
            session,
            user,
            instance.id,
            idem_key,
            AttemptIn(token_ids=pinned_token_ids, duration_ms=9999),
        )
        assert replay.attempt_id == first_attempt_id
        assert replay.correct is True
        assert replay.score == first_score
        await session.commit()


@pytest.mark.skipif(
    os.getenv("RUN_PLATFORM_INTEGRATION") != "1",
    reason="requires PostgreSQL integration service",
)
def test_v4_day1_learner_smoke_wrong_answer_and_overlay() -> None:
    import asyncio
    from uuid import UUID as UUIDType

    from fastapi.testclient import TestClient

    from app.core.security import hash_password
    from app.main import app
    from app.models.user import User
    from app.services.lesson_overlay import V4_TEACHING_OVERLAY_PIN

    smoke_email = f"v4-smoke-{uuid4().hex[:10]}@example.com"
    smoke_password = "local-test-password-not-for-production"

    async def _ensure_smoke_user() -> None:
        async with SessionFactory() as session:
            session.add(
                User(
                    email=smoke_email,
                    password_hash=hash_password(smoke_password),
                )
            )
            await session.commit()

    async def _wrong_choice_id(instance_id: str) -> str:
        async with SessionFactory() as session:
            instance = await session.get(ActivityInstance, UUIDType(instance_id))
            assert instance is not None
            correct = str(instance.answer_key.get("choice_id"))
            for choice in instance.prompt.get("choices") or []:
                if str(choice.get("id")) != correct:
                    return str(choice["id"])
            raise AssertionError("Expected a distractor choice for wrong-answer smoke")

    asyncio.run(_ensure_smoke_user())

    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={
                "email": smoke_email,
                "password": smoke_password,
            },
        )
        assert login.status_code == 200

        start = client.post("/api/v1/learning/start")
        assert start.status_code == 200
        assert start.json()["release_version"] == 4

        home = client.get("/api/v1/learning/home")
        assert home.status_code == 200
        body = home.json()
        assert body["release_version"] == 4
        assert body["teaching_overlay"]["overlay_id"] == V4_TEACHING_OVERLAY_PIN.overlay_id
        assert body["teaching_overlay"]["checksum"] == V4_TEACHING_OVERLAY_PIN.checksum

        day = client.get("/api/v1/learning/days/1")
        assert day.status_code == 200
        day_body = day.json()
        assert day_body["objective"]
        assert day_body["context_de"]
        assert day_body["activity_stages"]
        assert day_body["teaching_blocks"]
        assert day_body["spiral"]
        assert day_body["activity_stages"] == [
            "learn",
            "learn",
            "recognize",
            "build",
            "recall",
            "challenge",
            "challenge",
        ]
        assert day_body["activity_stages"].index("recall") < day_body[
            "activity_stages"
        ].index("challenge")

        next_response = client.post("/api/v1/learning/days/1/next")
        assert next_response.status_code == 200
        activity = next_response.json()["activity"]
        assert activity is not None
        assert activity["prompt"]["lesson"].get("teaching_block")
        assert activity["exercise_type"] == "meaning_multiple_choice"
        assert activity["position"] == 1

        wrong_payload = {
            "choice_id": asyncio.run(_wrong_choice_id(activity["id"])),
            "duration_ms": 900,
        }
        attempt = client.post(
            f"/api/v1/learning/instances/{activity['id']}/attempts",
            headers={"Idempotency-Key": f"v4-smoke-wrong-{uuid4()}"},
            json=wrong_payload,
        )
        assert attempt.status_code == 200
        result = attempt.json()
        assert result["correct"] is False
        teaching = result["teaching"]
        assert teaching is not None
        assert teaching["submitted_answer"]
        assert teaching["correct_answer"] or teaching["correct_example_de"]
        assert teaching["why_i18n"]["en"]
        assert teaching["rule_i18n"]["en"]
        assert teaching["correct_example_de"]
        assert result["review_scheduled"] is True

        review = client.get("/api/v1/review/home")
        assert review.status_code == 200
        review_body = review.json()
        assert (
            review_body["due_count"]
            + review_body["scheduled_count"]
            + review_body["weak_count"]
        ) >= 1

        home_after = client.get("/api/v1/learning/home")
        assert home_after.status_code == 200
        assert home_after.json()["current_day"] == 1
        assert home_after.json()["days"][0]["completed"] is False



def test_days_1_3_pedagogy_covers_reference_verbs() -> None:
    from app.services.content import load_days_1_3_pedagogy, load_starter_verbs

    pedagogy = load_days_1_3_pedagogy()
    assert len(pedagogy) == 21
    deep = [verb for verb in load_starter_verbs() if verb.pedagogy is not None]
    assert len(deep) == 21
    for verb in deep:
        assert verb.pedagogy is not None
        assert verb.pedagogy.mistakes
        assert verb.pedagogy.structures
        assert len(verb.examples) >= 2
        assert any(example.skill == "interview" for example in verb.examples)


@pytest.mark.skipif(
    os.getenv("RUN_PLATFORM_INTEGRATION") != "1",
    reason="requires PostgreSQL integration service",
)
@pytest.mark.asyncio
async def test_v1_upgrade_keeps_history_and_uses_v4_learning_contract() -> None:
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
            if legacy_enrollment.current_day < 1:
                legacy_enrollment.current_day = 1
        await session.flush()

        for _ in range(7):
            next_response = await get_next_activity(
                session,
                user,
                1,
            )
            if next_response.completed:
                break
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
        assert old_attempt_count >= 7
        assert legacy_enrollment.current_day >= 2

        result = await upgrade_to_latest_release(session, user)
        assert result.from_release_version == 1
        assert result.to_release_version == 4
        assert result.pinned_activity_count == 133

        home = await get_learning_home(session, user)
        assert home.release_version == 4
        assert home.upgrade_available is False
        assert home.available_through_day == 21
        assert len(home.days) == 21
        assert [day.total_count for day in home.days] == [
            *([7] * 14),
            *([5] * 7),
        ]
        assert sum(day.total_count for day in home.days) == 133

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

        probe_day = 1
        first_course_activity = await get_next_activity(session, user, probe_day)
        if first_course_activity.completed:
            probe_day = 2
            first_course_activity = await get_next_activity(session, user, probe_day)
        assert first_course_activity.activity is not None
        assert first_course_activity.activity.contract_version == 3
        assert first_course_activity.activity.prompt["question_i18n"]["en"]
        assert first_course_activity.activity.prompt["question_i18n"]["fa"]
        assert first_course_activity.activity.prompt["lesson"]["example_de"]
        assert first_course_activity.activity.prompt["lesson"]["mistakes"]
        assert first_course_activity.activity.prompt["lesson"]["structures"]
        assert first_course_activity.activity.prompt["lesson"]["teaching_feedback"]

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
