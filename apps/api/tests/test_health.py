from fastapi.testclient import TestClient

from app.main import app


def test_live_health() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": None, "redis": None}
    assert response.headers.get("X-Correlation-ID")
