import os
import subprocess
import sys
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_PLATFORM_INTEGRATION") != "1",
    reason="requires PostgreSQL and Redis integration services",
)


def test_private_platform_job_roundtrip() -> None:
    worker = subprocess.Popen(
        [sys.executable, "-m", "app.worker.main"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        with TestClient(app) as client:
            login = client.post(
                "/api/v1/auth/login",
                json={
                    "email": os.environ["APP_BOOTSTRAP_EMAIL"],
                    "password": os.environ["APP_BOOTSTRAP_PASSWORD"],
                },
            )
            assert login.status_code == 200

            ready = client.get("/api/v1/health/ready")
            assert ready.status_code == 200
            assert ready.json()["status"] == "ok"

            key = f"ci-{uuid4()}"
            create = client.post(
                "/api/v1/platform/jobs",
                headers={"Idempotency-Key": key},
                json={"message": "CI proves the Phase 1 platform path"},
            )
            assert create.status_code == 202
            job_id = create.json()["id"]

            duplicate = client.post(
                "/api/v1/platform/jobs",
                headers={"Idempotency-Key": key},
                json={"message": "This duplicate must not create a second job"},
            )
            assert duplicate.status_code == 202
            assert duplicate.json()["id"] == job_id

            deadline = time.monotonic() + 15
            latest: dict | None = None
            while time.monotonic() < deadline:
                if worker.poll() is not None:
                    output = worker.stdout.read() if worker.stdout else ""
                    pytest.fail(f"worker exited before completing the job: {output}")
                response = client.get(f"/api/v1/platform/jobs/{job_id}")
                assert response.status_code == 200
                latest = response.json()
                if latest["status"] in {"succeeded", "failed"}:
                    break
                time.sleep(0.25)

            assert latest is not None
            assert latest["status"] == "succeeded"
            assert latest["attempt_count"] == 1
            assert latest["result"] == {
                "echo": "CI proves the Phase 1 platform path",
                "worker": "deutschdeploy21-worker",
                "schema_version": 1,
            }
    finally:
        if worker.poll() is None:
            worker.terminate()
        try:
            worker.wait(timeout=5)
        except subprocess.TimeoutExpired:
            worker.kill()
            worker.wait(timeout=5)
