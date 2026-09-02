import asyncio
import os
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionFactory
from app.models.mastery import LearnerMastery, ReviewQueueEntry
from app.models.user import User

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


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def assert_ok(response: httpx.Response, label: str) -> dict:
    if response.is_error:
        raise RuntimeError(
            f"{label} failed: HTTP {response.status_code}: {response.text[:500]}"
        )
    if not response.content:
        return {}
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} returned a non-object JSON payload")
    return payload


def learning_answer(activity: dict) -> dict:
    prompt = activity["prompt"]
    exercise_type = activity["exercise_type"]
    if exercise_type in CHOICE_TYPES:
        return {
            "choice_id": prompt["choices"][0]["id"],
            "duration_ms": 900,
        }
    if exercise_type in TEXT_TYPES:
        return {"text": "probe", "duration_ms": 900}
    if exercise_type in ORDER_TYPES:
        return {
            "token_ids": [token["id"] for token in prompt["tokens"]],
            "duration_ms": 900,
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
            "duration_ms": 900,
        }
    raise RuntimeError(f"Unsupported smoke exercise type: {exercise_type}")


def review_answer(activity: dict) -> dict:
    prompt = activity["prompt"]
    input_kind = prompt.get("input")
    if input_kind == "choice":
        return {"choice_id": prompt["choices"][0]["id"], "duration_ms": 900}
    if input_kind == "text":
        return {"text": "probe", "duration_ms": 900}
    if input_kind == "token_order":
        return {
            "token_ids": [token["id"] for token in prompt["tokens"]],
            "duration_ms": 900,
        }
    if input_kind == "matching":
        return {
            "pair_ids": [
                f"{left['id']}:{right['id']}"
                for left, right in zip(
                    prompt["left_items"],
                    prompt["right_items"],
                    strict=True,
                )
            ],
            "duration_ms": 900,
        }
    raise RuntimeError(f"Unsupported review input kind: {input_kind}")


async def create_smoke_user() -> tuple[UUID, str, str]:
    email = f"release-smoke-{uuid4().hex}@example.com"
    password = f"Dd21-{secrets.token_urlsafe(24)}"
    user = User(email=email, password_hash=hash_password(password))
    async with SessionFactory() as session:
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user.id, email, password


async def delete_smoke_user(user_id: UUID) -> None:
    async with SessionFactory() as session:
        user = await session.get(User, user_id)
        if user is None:
            return
        await session.delete(user)
        await session.commit()


async def force_target_due(user_id: UUID, target_id: UUID) -> None:
    due_at = datetime.now(UTC) - timedelta(minutes=1)
    async with SessionFactory() as session:
        mastery = await session.scalar(
            select(LearnerMastery).where(
                LearnerMastery.user_id == user_id,
                LearnerMastery.target_id == target_id,
            )
        )
        queue_entry = await session.scalar(
            select(ReviewQueueEntry).where(
                ReviewQueueEntry.user_id == user_id,
                ReviewQueueEntry.target_id == target_id,
            )
        )
        if mastery is None or queue_entry is None:
            raise RuntimeError("Attempt did not produce a review projection")
        mastery.next_review_at = due_at
        queue_entry.due_at = due_at
        await session.commit()


async def poll_job(client: httpx.AsyncClient, job_id: str) -> dict:
    for _ in range(80):
        body = assert_ok(
            await client.get(f"/api/v1/platform/jobs/{job_id}"),
            "worker job poll",
        )
        if body["status"] == "succeeded":
            return body
        if body["status"] == "failed":
            raise RuntimeError(f"worker job failed: {body}")
        await asyncio.sleep(0.25)
    raise RuntimeError("worker round-trip did not complete within 20 seconds")


async def next_unfinished_activity(client: httpx.AsyncClient) -> tuple[int, dict]:
    home = assert_ok(await client.get("/api/v1/learning/home"), "learning home")
    for day in home["days"]:
        if day["completed"]:
            continue
        body = assert_ok(
            await client.post(f"/api/v1/learning/days/{day['day_number']}/next"),
            "next learning activity",
        )
        if not body["completed"] and body.get("activity"):
            return day["day_number"], body["activity"]
    raise RuntimeError("No unfinished curriculum activity is available for smoke testing")


async def run() -> None:
    api_url = require_env("RELEASE_SMOKE_API_URL").rstrip("/")
    user_id, email, password = await create_smoke_user()
    summary: dict[str, object] = {"user_id": str(user_id)}

    try:
        async with httpx.AsyncClient(
            base_url=api_url,
            timeout=httpx.Timeout(15.0),
            follow_redirects=True,
        ) as client:
            login = assert_ok(
                await client.post(
                    "/api/v1/auth/login",
                    json={"email": email, "password": password},
                ),
                "login",
            )
            if login.get("id") != str(user_id):
                raise RuntimeError("Login returned the wrong smoke user")

            ready = assert_ok(await client.get("/api/v1/health/ready"), "readiness")
            if ready.get("status") != "ok":
                raise RuntimeError(f"readiness is not ok: {ready}")
            summary["readiness"] = ready.get("status")

            job_key = f"release-smoke-job-{uuid4()}"
            create_job = assert_ok(
                await client.post(
                    "/api/v1/platform/jobs",
                    headers={"Idempotency-Key": job_key},
                    json={"message": "Phase 8C staging worker round-trip"},
                ),
                "create worker job",
            )
            duplicate_job = assert_ok(
                await client.post(
                    "/api/v1/platform/jobs",
                    headers={"Idempotency-Key": job_key},
                    json={"message": "duplicate must reuse the original job"},
                ),
                "duplicate worker job",
            )
            if duplicate_job["id"] != create_job["id"]:
                raise RuntimeError("Platform job idempotency failed")
            completed_job = await poll_job(client, create_job["id"])
            if completed_job.get("attempt_count") != 1:
                raise RuntimeError(f"worker job executed more than once: {completed_job}")
            summary["worker_round_trip"] = "ok"

            start = assert_ok(await client.post("/api/v1/learning/start"), "learning start")
            if int(start.get("pinned_activity_count", 0)) <= 0:
                raise RuntimeError(f"learning release has no pinned activities: {start}")

            _, activity = await next_unfinished_activity(client)
            attempt_key = f"release-smoke-attempt-{uuid4()}"
            attempt_url = f"/api/v1/learning/instances/{activity['id']}/attempts"
            attempt_payload = learning_answer(activity)
            first = assert_ok(
                await client.post(
                    attempt_url,
                    headers={"Idempotency-Key": attempt_key},
                    json=attempt_payload,
                ),
                "learning attempt",
            )
            replay = assert_ok(
                await client.post(
                    attempt_url,
                    headers={"Idempotency-Key": attempt_key},
                    json=attempt_payload,
                ),
                "learning attempt replay",
            )
            if replay.get("attempt_id") != first.get("attempt_id"):
                raise RuntimeError("Learning attempt replay created a duplicate attempt")
            if replay.get("evaluation_id") != first.get("evaluation_id"):
                raise RuntimeError("Learning attempt replay created a duplicate evaluation")
            summary["attempt_replay"] = "idempotent"

            review_home = assert_ok(
                await client.get("/api/v1/review/home"),
                "review home after learning attempt",
            )
            target = next(
                (
                    row
                    for row in review_home["mastery"]
                    if row.get("content_version_id") == activity.get("content_version_id")
                    and int(row.get("evidence_count", 0)) >= 1
                ),
                None,
            )
            if target is None:
                raise RuntimeError("Learning attempt was not projected into mastery")
            await force_target_due(user_id, UUID(target["target_id"]))

            due_home = assert_ok(await client.get("/api/v1/review/home"), "due review home")
            if int(due_home.get("due_count", 0)) < 1:
                raise RuntimeError("Forced review target is not due")
            review_next = assert_ok(
                await client.post("/api/v1/review/next"),
                "next review activity",
            )
            if review_next.get("completed") or not review_next.get("activity"):
                raise RuntimeError(f"Expected a due review activity: {review_next}")
            review_activity = review_next["activity"]
            review_attempt = assert_ok(
                await client.post(
                    "/api/v1/learning/instances/"
                    f"{review_activity['activity_instance_id']}/attempts",
                    headers={"Idempotency-Key": f"release-smoke-review-{uuid4()}"},
                    json=review_answer(review_activity),
                ),
                "review attempt",
            )
            if not review_attempt.get("attempt_id"):
                raise RuntimeError("Review attempt did not return an attempt id")
            summary["review_flow"] = "ok"

            operations = assert_ok(
                await client.get("/api/v1/platform/operations"),
                "operations summary",
            )
            if operations.get("status") != "ok" or operations.get("alert_codes"):
                raise RuntimeError(f"Operations summary contains alerts: {operations}")
            summary["operations"] = "ok"

        print("RELEASE_SMOKE_OK", summary)
    finally:
        await delete_smoke_user(user_id)


if __name__ == "__main__":
    asyncio.run(run())
