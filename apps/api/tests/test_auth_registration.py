import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_PLATFORM_INTEGRATION") != "1",
    reason="requires PostgreSQL integration service",
)


def test_public_registration_creates_an_authenticated_account() -> None:
    email = f"signup-{uuid4()}@example.com"
    password = "strong-test-password-123"

    with TestClient(app) as client:
        weak = client.post(
            "/api/v1/auth/register",
            json={"email": f"weak-{uuid4()}@example.com", "password": "short"},
        )
        assert weak.status_code == 422

        register = client.post(
            "/api/v1/auth/register",
            json={"email": email.upper(), "password": password},
        )
        assert register.status_code == 201
        assert register.json()["email"] == email
        assert client.cookies.get("dd21_session")

        me = client.get("/api/v1/auth/me")
        assert me.status_code == 200
        assert me.json()["email"] == email

        duplicate = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "another-valid-password"},
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["detail"] == "An account with this email already exists"

        logout = client.post("/api/v1/auth/logout")
        assert logout.status_code == 204
        assert client.get("/api/v1/auth/me").status_code == 401

        login = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login.status_code == 200
        assert login.json()["email"] == email
        assert client.get("/api/v1/auth/me").status_code == 200
