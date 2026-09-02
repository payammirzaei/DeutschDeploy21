import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_PLATFORM_INTEGRATION") != "1",
    reason="requires PostgreSQL integration service",
)

EXPECTED_TYPES = {
    "meaning_multiple_choice",
    "reverse_typing",
    "perfect_participle_choice",
    "auxiliary_choice",
    "sentence_order",
}
EXPECTED_DIMENSIONS = {
    "meaning_recognition",
    "lexical_recall",
    "perfect_participle",
    "perfect_auxiliary",
    "sentence_structure",
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


def _answer_for(activity: dict) -> dict:
    prompt = activity["prompt"]
    exercise_type = activity["exercise_type"]
    if exercise_type in {
        "meaning_multiple_choice",
        "perfect_participle_choice",
        "auxiliary_choice",
    }:
        return {"choice_id": prompt["choices"][0]["id"], "duration_ms": 1200}
    if exercise_type == "reverse_typing":
        return {"text": "probe", "duration_ms": 1200}
    if exercise_type == "sentence_order":
        return {
            "token_ids": [token["id"] for token in prompt["tokens"]],
            "duration_ms": 1200,
        }
    raise AssertionError(f"Unhandled exercise type: {exercise_type}")


def test_silent_practice_rotates_types_without_completing_course_days() -> None:
    with TestClient(app) as client:
        _login(client)
        start = client.post("/api/v1/learning/start")
        assert start.status_code == 200

        before_response = client.get("/api/v1/learning/home")
        assert before_response.status_code == 200
        before = before_response.json()
        before_progress = {
            day["day_number"]: day["submitted_count"] for day in before["days"]
        }
        before_current_day = before["current_day"]

        seen_types: list[str] = []
        for _ in range(5):
            next_response = client.post("/api/v1/practice/silent/next")
            assert next_response.status_code == 200
            body = next_response.json()
            activity = body["activity"]
            seen_types.append(activity["exercise_type"])
            assert set(body["available_types"]) == EXPECTED_TYPES

            attempt = client.post(
                f"/api/v1/learning/instances/{activity['id']}/attempts",
                headers={"Idempotency-Key": f"silent-{uuid4()}"},
                json=_answer_for(activity),
            )
            assert attempt.status_code == 200
            assert attempt.json()["day_complete"] is False

        assert set(seen_types) == EXPECTED_TYPES

        after_response = client.get("/api/v1/learning/home")
        assert after_response.status_code == 200
        after = after_response.json()
        assert after["current_day"] == before_current_day
        assert {
            day["day_number"]: day["submitted_count"] for day in after["days"]
        } == before_progress

        review = client.get("/api/v1/review/home")
        assert review.status_code == 200
        dimensions = {target["skill_dimension"] for target in review.json()["mastery"]}
        assert EXPECTED_DIMENSIONS.issubset(dimensions)
