import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_PLATFORM_INTEGRATION") != "1",
    reason="requires PostgreSQL and Redis integration services",
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


def test_speech_attempt_survives_async_transcription_and_correction() -> None:
    media_root = Path(os.environ["MEDIA_ROOT"])
    media_root.mkdir(parents=True, exist_ok=True)

    with TestClient(app) as client:
        _login(client)

        reset_consent = client.post(
            "/api/v1/speech/consent",
            json={"accepted": False},
        )
        assert reset_consent.status_code == 200
        assert reset_consent.json()["accepted"] is False

        consent = client.get("/api/v1/speech/consent")
        assert consent.status_code == 200
        assert consent.json()["accepted"] is False

        prompts = client.get("/api/v1/speech/prompts")
        assert prompts.status_code == 200
        assert len(prompts.json()) == 8
        prompt = prompts.json()[0]

        blocked = client.post(
            "/api/v1/speech/attempts",
            json={"prompt_id": prompt["id"]},
        )
        assert blocked.status_code == 403

        accepted = client.post(
            "/api/v1/speech/consent",
            json={"accepted": True},
        )
        assert accepted.status_code == 200
        assert accepted.json()["accepted"] is True

        created = client.post(
            "/api/v1/speech/attempts",
            json={"prompt_id": prompt["id"]},
        )
        assert created.status_code == 201
        created_body = created.json()
        assert created_body["status"] == "created"
        assert created_body["prompt"]["question"] == prompt["question"]
        assert len(created_body["prompt_checksum"]) == 64
        attempt_id = created_body["id"]

        worker = subprocess.Popen(
            [sys.executable, "-m", "app.worker.main"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            upload = client.put(
                f"/api/v1/speech/attempts/{attempt_id}/audio",
                headers={
                    "Content-Type": "audio/wav",
                    "X-Audio-Duration-Ms": "42000",
                },
                content=b"RIFF" + (b"phase6-audio" * 200),
            )
            assert upload.status_code == 202
            assert upload.json()["queued"] is True
            assert upload.json()["attempt"]["status"] == "queued"
            assert upload.json()["attempt"]["media"]["byte_size"] > 0

            deadline = time.monotonic() + 20
            detail = None
            while time.monotonic() < deadline:
                if worker.poll() is not None:
                    output = worker.stdout.read() if worker.stdout else ""
                    pytest.fail(f"worker exited before speech job completed: {output}")
                response = client.get(f"/api/v1/speech/attempts/{attempt_id}")
                assert response.status_code == 200
                detail = response.json()
                if detail["status"] in {"feedback_ready", "failed"}:
                    break
                time.sleep(0.25)

            assert detail is not None
            assert detail["status"] == "feedback_ready"
            raw = next(item for item in detail["transcripts"] if item["kind"] == "provider_raw")
            assert raw["provider"] == "mock"
            assert raw["text"].startswith("Ich arbeite als Softwareentwickler")
            assert detail["feedback"]["dimensions"]["pronunciation_assessed"] is False
            assert detail["feedback"]["dimensions"]["duration_seconds"] == 42.0

            original_raw_text = raw["text"]
            corrected = client.post(
                f"/api/v1/speech/attempts/{attempt_id}/correct-transcript",
                json={
                    "text": (
                        "Ich arbeite als Softwareentwickler. Zuerst beschreibe ich das Problem, "
                        "dann meine Lösung und am Ende das Ergebnis."
                    )
                },
            )
            assert corrected.status_code == 200
            corrected_body = corrected.json()
            raw_after = next(
                item for item in corrected_body["transcripts"] if item["kind"] == "provider_raw"
            )
            learner = next(
                item
                for item in corrected_body["transcripts"]
                if item["kind"] == "learner_corrected"
            )
            assert raw_after["text"] == original_raw_text
            assert learner["text"] != original_raw_text
            assert corrected_body["feedback"]["transcript_id"] == learner["id"]

            deleted = client.delete(f"/api/v1/speech/attempts/{attempt_id}/audio")
            assert deleted.status_code == 204
            after_delete = client.get(f"/api/v1/speech/attempts/{attempt_id}")
            assert after_delete.status_code == 200
            assert after_delete.json()["media"]["status"] == "deleted"
            assert after_delete.json()["transcripts"]
        finally:
            if worker.poll() is None:
                worker.terminate()
            try:
                worker.wait(timeout=5)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait(timeout=5)


def test_manual_text_fallback_works_without_microphone() -> None:
    with TestClient(app) as client:
        _login(client)
        client.post("/api/v1/speech/consent", json={"accepted": True})
        prompt_id = client.get("/api/v1/speech/prompts").json()[1]["id"]
        created = client.post(
            "/api/v1/speech/attempts",
            json={"prompt_id": prompt_id},
        )
        assert created.status_code == 201
        attempt_id = created.json()["id"]

        manual = client.post(
            f"/api/v1/speech/attempts/{attempt_id}/manual-transcript",
            json={
                "text": (
                    "In meinem Projekt habe ich eine API entwickelt. "
                    "Zuerst habe ich die Anforderungen geprüft, dann die Schnittstelle "
                    "implementiert und am Ende automatisierte Tests ergänzt."
                )
            },
        )
        assert manual.status_code == 200
        body = manual.json()
        assert body["status"] == "feedback_ready"
        assert body["media"] is None
        assert body["transcripts"][-1]["kind"] == "manual"
        assert body["feedback"]["dimensions"]["pronunciation_assessed"] is False
