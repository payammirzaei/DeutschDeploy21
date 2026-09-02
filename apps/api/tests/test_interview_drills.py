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
    "interview_best_answer",
    "hr_answer_order",
    "star_builder",
    "technical_explanation_order",
    "architecture_sequence",
    "timed_quick_recall",
}
EXPECTED_DIMENSIONS = {
    "answer_quality",
    "hr_structure",
    "star_structure",
    "technical_explanation",
    "architecture_sequence",
    "recovery_recall",
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
    if exercise_type == "interview_best_answer":
        return {"choice_id": prompt["choices"][0]["id"], "duration_ms": 1400}
    if exercise_type in {
        "hr_answer_order",
        "star_builder",
        "technical_explanation_order",
        "architecture_sequence",
    }:
        return {
            "token_ids": [token["id"] for token in prompt["tokens"]],
            "duration_ms": 2200,
        }
    if exercise_type == "timed_quick_recall":
        return {"text": "probe", "duration_ms": 3000}
    raise AssertionError(f"Unhandled interview drill type: {exercise_type}")


def test_interview_drills_cover_six_families_without_advancing_course() -> None:
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

        seen_types: set[str] = set()
        seen_sources: set[str] = set()
        for _ in range(18):
            next_response = client.post("/api/v1/interview-drills/next")
            assert next_response.status_code == 200
            body = next_response.json()
            activity = body["activity"]
            seen_types.add(activity["exercise_type"])
            seen_sources.add(activity["source_key"])
            assert set(body["available_types"]) == EXPECTED_TYPES

            attempt = client.post(
                f"/api/v1/learning/instances/{activity['id']}/attempts",
                headers={"Idempotency-Key": f"interview-{uuid4()}"},
                json=_answer_for(activity),
            )
            assert attempt.status_code == 200
            assert attempt.json()["day_complete"] is False

        assert seen_types == EXPECTED_TYPES
        assert len(seen_sources) == 18

        after_response = client.get("/api/v1/learning/home")
        assert after_response.status_code == 200
        after = after_response.json()
        assert after["current_day"] == before_current_day
        assert {
            day["day_number"]: day["submitted_count"] for day in after["days"]
        } == before_progress

        review = client.get("/api/v1/review/home")
        assert review.status_code == 200
        interview_targets = [
            target
            for target in review.json()["mastery"]
            if target["target_kind"] == "interview_skill"
        ]
        dimensions = {target["skill_dimension"] for target in interview_targets}
        assert EXPECTED_DIMENSIONS.issubset(dimensions)
        assert len({target["target_label"] for target in interview_targets}) == 6
