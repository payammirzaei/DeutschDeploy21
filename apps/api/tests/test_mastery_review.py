import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import mastery as mastery_service

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


def _next_available_activity(client: TestClient) -> dict:
    start = client.post("/api/v1/learning/start")
    assert start.status_code == 200
    home = client.get("/api/v1/learning/home")
    assert home.status_code == 200
    for day in home.json()["days"]:
        response = client.post(f"/api/v1/learning/days/{day['day_number']}/next")
        assert response.status_code == 200
        body = response.json()
        if not body["completed"]:
            return body["activity"]
    raise AssertionError("Expected at least one unfinished starter activity")


def _target_for_activity(home: dict, activity: dict) -> dict:
    return next(
        row
        for row in home["mastery"]
        if row["content_version_id"] == activity["content_version_id"]
    )


def _target_by_id(home: dict, target_id: str) -> dict:
    return next(row for row in home["mastery"] if row["target_id"] == target_id)


def test_attempt_projects_mastery_and_duplicate_is_idempotent() -> None:
    with TestClient(app) as client:
        _login(client)
        activity = _next_available_activity(client)
        key = f"mastery-{uuid4()}"
        payload = {"choice_id": activity["choices"][0]["id"], "duration_ms": 3200}
        first = client.post(
            f"/api/v1/learning/instances/{activity['id']}/attempts",
            headers={"Idempotency-Key": key},
            json=payload,
        )
        assert first.status_code == 200

        duplicate = client.post(
            f"/api/v1/learning/instances/{activity['id']}/attempts",
            headers={"Idempotency-Key": key},
            json=payload,
        )
        assert duplicate.status_code == 200
        assert duplicate.json()["attempt_id"] == first.json()["attempt_id"]

        home = client.get("/api/v1/review/home")
        assert home.status_code == 200
        body = home.json()
        assert body["scheduled_count"] >= 1
        target = _target_for_activity(body, activity)
        assert target["evidence_count"] == 1
        assert target["state"] in {"learning", "review"}
        assert target["explanation_code"] in {"first_success", "recent_failure"}


def test_due_review_reuses_frozen_prompt_and_updates_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TestClient(app) as client:
        _login(client)
        activity = _next_available_activity(client)
        first_attempt = client.post(
            f"/api/v1/learning/instances/{activity['id']}/attempts",
            headers={"Idempotency-Key": f"seed-review-{uuid4()}"},
            json={"choice_id": activity["choices"][0]["id"]},
        )
        assert first_attempt.status_code == 200

        future = datetime.now(UTC) + timedelta(days=2)
        monkeypatch.setattr(mastery_service, "utcnow", lambda: future)

        due_home = client.get("/api/v1/review/home")
        assert due_home.status_code == 200
        due_body = due_home.json()
        assert due_body["due_count"] >= 1

        review = client.post("/api/v1/review/next")
        assert review.status_code == 200
        review_body = review.json()
        assert review_body["completed"] is False
        review_activity = review_body["activity"]

        queue_item = next(
            row
            for row in due_body["due"]
            if row["activity_instance_id"] == review_activity["activity_instance_id"]
        )
        assert review_activity["target_id"] == queue_item["target_id"]
        assert review_activity["content_version_id"] == queue_item["content_version_id"]
        assert review_activity["lemma"] == queue_item["lemma"]
        assert review_activity["reason_code"] == queue_item["reason_code"]
        assert review_activity["state"] == queue_item["state"]
        assert review_activity["question"]
        assert len(review_activity["choices"]) == 4
        assert len({choice["id"] for choice in review_activity["choices"]}) == 4
        assert len({choice["text"] for choice in review_activity["choices"]}) == 4

        before_target = _target_by_id(due_body, review_activity["target_id"])
        retry = client.post(
            f"/api/v1/learning/instances/{review_activity['activity_instance_id']}/attempts",
            headers={"Idempotency-Key": f"review-{uuid4()}"},
            json={"choice_id": review_activity["choices"][0]["id"]},
        )
        assert retry.status_code == 200

        home = client.get("/api/v1/review/home")
        assert home.status_code == 200
        after_target = _target_by_id(home.json(), review_activity["target_id"])
        assert after_target["evidence_count"] == before_target["evidence_count"] + 1
        assert after_target["next_review_at"] != before_target["next_review_at"]


def test_mastery_projection_rebuild_is_replayable() -> None:
    with TestClient(app) as client:
        _login(client)
        activity = _next_available_activity(client)
        response = client.post(
            f"/api/v1/learning/instances/{activity['id']}/attempts",
            headers={"Idempotency-Key": f"rebuild-{uuid4()}"},
            json={"choice_id": activity["choices"][0]["id"]},
        )
        assert response.status_code == 200

        before = client.get("/api/v1/review/home")
        assert before.status_code == 200
        before_target = _target_for_activity(before.json(), activity)

        rebuild = client.post("/api/v1/review/rebuild")
        assert rebuild.status_code == 200
        assert rebuild.json()["event_count"] >= 1
        assert rebuild.json()["target_count"] >= 1

        after = client.get("/api/v1/review/home")
        assert after.status_code == 200
        after_target = _target_for_activity(after.json(), activity)
        assert after_target["state"] == before_target["state"]
        assert after_target["success_streak"] == before_target["success_streak"]
        assert after_target["lapses"] == before_target["lapses"]
        assert after_target["evidence_count"] == before_target["evidence_count"]
