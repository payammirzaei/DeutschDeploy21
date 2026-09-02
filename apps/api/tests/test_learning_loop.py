import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_PLATFORM_INTEGRATION") != "1",
    reason="requires PostgreSQL integration service",
)

CHOICE_TYPES = {
    "meaning_multiple_choice",
    "perfect_participle_choice",
    "auxiliary_choice",
    "usage_error_spotting",
    "interview_best_answer",
}
TEXT_TYPES = {
    "reverse_typing",
    "example_cloze",
    "perfect_form_typing",
    "timed_quick_recall",
}
ORDER_TYPES = {
    "sentence_order",
    "phrase_builder",
    "hr_answer_order",
    "star_builder",
    "technical_explanation_order",
    "architecture_sequence",
}


def _login(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": os.environ["APP_BOOTSTRAP_EMAIL"],
            "password": os.environ["APP_BOOTSTRAP_PASSWORD"],
        },
    )
    assert response.status_code == 200


def _next_unfinished(client: TestClient) -> tuple[int, dict]:
    home = client.get("/api/v1/learning/home")
    assert home.status_code == 200
    for day in home.json()["days"]:
        if day["completed"]:
            continue
        response = client.post(
            f"/api/v1/learning/days/{day['day_number']}/next"
        )
        assert response.status_code == 200
        body = response.json()
        if not body["completed"] and body["activity"]:
            return day["day_number"], body["activity"]
    raise AssertionError("Expected an unfinished curriculum activity")


def _answer_for(activity: dict) -> dict:
    prompt = activity["prompt"]
    exercise_type = activity["exercise_type"]
    if exercise_type in CHOICE_TYPES:
        return {
            "choice_id": prompt["choices"][0]["id"],
            "duration_ms": 1200,
        }
    if exercise_type in TEXT_TYPES:
        return {"text": "probe", "duration_ms": 1200}
    if exercise_type in ORDER_TYPES:
        return {
            "token_ids": [
                token["id"]
                for token in prompt["tokens"]
            ],
            "duration_ms": 1200,
        }
    if exercise_type == "meaning_matching":
        return {
            "pair_ids": [
                f"{left['id']}:{right['id']}"
                for left, right in zip(
                    prompt["left_items"],
                    prompt["right_items"],
                    strict=True,
                )
            ],
            "duration_ms": 1200,
        }
    raise AssertionError(
        f"Unhandled curriculum exercise type: {exercise_type}"
    )


def test_start_release_pins_133_activities_and_attempt_is_idempotent() -> None:
    with TestClient(app) as client:
        _login(client)

        start = client.post("/api/v1/learning/start")
        assert start.status_code == 200
        assert start.json()["release_version"] == 2
        assert start.json()["pinned_activity_count"] == 133

        home = client.get("/api/v1/learning/home")
        assert home.status_code == 200
        body = home.json()
        assert body["enrolled"] is True
        assert body["release_version"] == 2
        assert body["available_through_day"] == 21
        assert len(body["days"]) == 21
        assert [day["total_count"] for day in body["days"]] == [
            *([7] * 14),
            *([5] * 7),
        ]
        assert sum(day["total_count"] for day in body["days"]) == 133

        day_number, activity = _next_unfinished(client)
        assert activity["day_number"] == day_number
        assert activity["prompt_checksum"]
        assert activity["source_kind"] in {
            "release_activity",
            "interview_drill",
        }

        key = f"learning-{uuid4()}"
        payload = _answer_for(activity)
        first_attempt = client.post(
            f"/api/v1/learning/instances/{activity['id']}/attempts",
            headers={"Idempotency-Key": key},
            json=payload,
        )
        assert first_attempt.status_code == 200
        assert first_attempt.json()["score"] in {0, 100}

        duplicate = client.post(
            f"/api/v1/learning/instances/{activity['id']}/attempts",
            headers={"Idempotency-Key": key},
            json=payload,
        )
        assert duplicate.status_code == 200
        assert (
            duplicate.json()["attempt_id"]
            == first_attempt.json()["attempt_id"]
        )
        assert (
            duplicate.json()["evaluation_id"]
            == first_attempt.json()["evaluation_id"]
        )

        next_after_submit = client.post(
            f"/api/v1/learning/days/{day_number}/next"
        )
        assert next_after_submit.status_code == 200
        next_body = next_after_submit.json()
        if not next_body["completed"]:
            assert next_body["activity"]["id"] != activity["id"]


def test_day_completion_advances_after_submissions_not_only_correct_answers() -> None:
    with TestClient(app) as client:
        _login(client)
        start = client.post("/api/v1/learning/start")
        assert start.status_code == 200

        home_before = client.get("/api/v1/learning/home")
        assert home_before.status_code == 200
        before = home_before.json()
        active_day = next(
            day
            for day in before["days"]
            if not day["completed"]
        )
        day_number = active_day["day_number"]

        safety = 0
        max_steps = active_day["total_count"] + 2
        while safety < max_steps:
            safety += 1
            next_response = client.post(
                f"/api/v1/learning/days/{day_number}/next"
            )
            assert next_response.status_code == 200
            body = next_response.json()
            if body["completed"]:
                break
            activity = body["activity"]
            attempt = client.post(
                f"/api/v1/learning/instances/{activity['id']}/attempts",
                headers={
                    "Idempotency-Key": f"complete-day-{uuid4()}"
                },
                json=_answer_for(activity),
            )
            assert attempt.status_code == 200

        assert body["completed"] is True
        home = client.get("/api/v1/learning/home")
        assert home.status_code == 200
        after = home.json()
        completed_day = next(
            day
            for day in after["days"]
            if day["day_number"] == day_number
        )
        assert completed_day["completed"] is True
        assert (
            completed_day["submitted_count"]
            == completed_day["total_count"]
        )
        assert after["current_day"] > day_number
