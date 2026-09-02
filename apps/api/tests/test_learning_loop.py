import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_PLATFORM_INTEGRATION") != "1",
    reason="requires PostgreSQL integration service",
)


def _login(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": os.environ["APP_BOOTSTRAP_EMAIL"],
            "password": os.environ["APP_BOOTSTRAP_PASSWORD"],
        },
    )
    assert response.status_code == 200


def test_start_release_pins_21_activities_and_attempt_is_idempotent() -> None:
    with TestClient(app) as client:
        _login(client)

        start = client.post("/api/v1/learning/start")
        assert start.status_code == 200
        assert start.json()["pinned_activity_count"] == 21

        home = client.get("/api/v1/learning/home")
        assert home.status_code == 200
        assert home.json()["enrolled"] is True
        assert len(home.json()["days"]) == 3
        assert [day["total_count"] for day in home.json()["days"]] == [7, 7, 7]

        day = client.get("/api/v1/learning/days/1")
        assert day.status_code == 200
        first_pinned_version = day.json()["activities"][0]["content_version_id"]

        next_response = client.post("/api/v1/learning/days/1/next")
        assert next_response.status_code == 200
        activity = next_response.json()["activity"]
        assert activity["content_version_id"] == first_pinned_version
        assert len(activity["choices"]) == 4

        key = f"learning-{uuid4()}"
        payload = {"choice_id": activity["choices"][0]["id"], "duration_ms": 5000}
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
        assert duplicate.json()["attempt_id"] == first_attempt.json()["attempt_id"]
        assert duplicate.json()["evaluation_id"] == first_attempt.json()["evaluation_id"]

        next_after_submit = client.post("/api/v1/learning/days/1/next")
        assert next_after_submit.status_code == 200
        assert next_after_submit.json()["activity"]["id"] != activity["id"]


def test_day_completion_advances_after_submissions_not_only_correct_answers() -> None:
    with TestClient(app) as client:
        _login(client)
        start = client.post("/api/v1/learning/start")
        assert start.status_code == 200

        safety = 0
        while safety < 10:
            safety += 1
            next_response = client.post("/api/v1/learning/days/1/next")
            assert next_response.status_code == 200
            body = next_response.json()
            if body["completed"]:
                break
            activity = body["activity"]
            choice = activity["choices"][0]["id"]
            attempt = client.post(
                f"/api/v1/learning/instances/{activity['id']}/attempts",
                headers={"Idempotency-Key": f"complete-day-{uuid4()}"},
                json={"choice_id": choice},
            )
            assert attempt.status_code == 200

        assert body["completed"] is True
        home = client.get("/api/v1/learning/home")
        assert home.status_code == 200
        assert home.json()["current_day"] == 2
        day_one = next(day for day in home.json()["days"] if day["day_number"] == 1)
        assert day_one["completed"] is True
        assert day_one["submitted_count"] == 7
