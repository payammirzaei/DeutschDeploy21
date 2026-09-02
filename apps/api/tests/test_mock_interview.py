import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_PLATFORM_INTEGRATION") != "1",
    reason="requires PostgreSQL and Redis integration services",
)


STRONG_ANSWER = (
    "Ich arbeite als Softwareentwickler und habe in einem Projekt ein Web-System entwickelt. "
    "Zuerst prüfe ich die Anforderungen und das Ziel. Dann plane ich Frontend, API, Backend, "
    "Service und Datenbank. Ich war für eine Aufgabe verantwortlich und habe die Schnittstelle "
    "implementiert, Tests und Validierung ergänzt und Fehler mit Logging und Monitoring analysiert "
    "und behoben. Weil Messwerte wichtig sind, prüfe ich das Ergebnis, die Last und mögliche "
    "Engpässe vor der Skalierung. Wenn ich eine Frage nicht verstehe, sage ich: Könnten Sie die "
    "Frage bitte noch einmal wiederholen? Dann erkläre ich, was ich verstanden habe. Am Ende "
    "beschreibe ich das Ergebnis und warum die Lösung relevant ist."
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


def _active_turn(session: dict) -> dict:
    active = [turn for turn in session["turns"] if turn["status"] == "active"]
    assert len(active) == 1
    return active[0]


def _complete_text_session(client: TestClient, session: dict) -> dict:
    current = session
    for _ in range(20):
        if current["status"] == "completed":
            return current
        turn = _active_turn(current)
        response = client.post(
            f"/api/v1/mock-interviews/sessions/{current['id']}/turns/{turn['id']}/text",
            headers={"Idempotency-Key": f"mock-{uuid4()}"},
            json={"text": STRONG_ANSWER},
        )
        assert response.status_code == 200, response.text
        current = response.json()
    pytest.fail("mock interview did not complete within 20 turns")


def test_guided_mock_is_durable_contextual_and_idempotent() -> None:
    with TestClient(app) as client:
        _login(client)

        blueprint = client.get("/api/v1/mock-interviews/blueprint")
        assert blueprint.status_code == 200
        assert {item["mode"] for item in blueprint.json()["modes"]} == {
            "guided",
            "practice",
            "realistic",
        }

        created = client.post(
            "/api/v1/mock-interviews/sessions",
            json={"mode": "guided", "purpose": "baseline"},
        )
        assert created.status_code == 201
        session = created.json()
        assert session["total_turns"] == 5
        first = _active_turn(session)
        assert first["intent"]
        assert first["hints"]

        key = f"mock-{uuid4()}"
        weak = client.post(
            f"/api/v1/mock-interviews/sessions/{session['id']}/turns/{first['id']}/text",
            headers={"Idempotency-Key": key},
            json={"text": "Okay."},
        )
        assert weak.status_code == 200
        body = weak.json()
        assert body["total_turns"] == 6
        first_after = next(turn for turn in body["turns"] if turn["id"] == first["id"])
        assert first_after["evaluation"]["overall_score"] < 60
        follow_up = _active_turn(body)
        assert follow_up["position_key"] == "01a"
        assert follow_up["is_follow_up"] is True
        assert follow_up["parent_turn_id"] == first["id"]

        duplicate = client.post(
            f"/api/v1/mock-interviews/sessions/{session['id']}/turns/{first['id']}/text",
            headers={"Idempotency-Key": key},
            json={"text": "Okay."},
        )
        assert duplicate.status_code == 200
        assert duplicate.json()["total_turns"] == 6

        realistic = client.post(
            "/api/v1/mock-interviews/sessions",
            json={"mode": "realistic", "purpose": "practice"},
        )
        assert realistic.status_code == 201
        realistic_turn = _active_turn(realistic.json())
        hidden_hint = client.post(
            f"/api/v1/mock-interviews/sessions/{realistic.json()['id']}/turns/"
            f"{realistic_turn['id']}/hint"
        )
        assert hidden_hint.status_code == 403


def test_realistic_baseline_and_final_reports_are_comparable() -> None:
    with TestClient(app) as client:
        _login(client)

        baseline = client.post(
            "/api/v1/mock-interviews/sessions",
            json={"mode": "realistic", "purpose": "baseline", "seed": "baseline-v1"},
        )
        assert baseline.status_code == 201
        baseline_body = _complete_text_session(client, baseline.json())
        assert baseline_body["status"] == "completed"
        assert baseline_body["report"] is not None
        assert 0 <= baseline_body["report"]["overall_score"] <= 100
        assert 0 < baseline_body["report"]["confidence"] <= 1
        assert baseline_body["report"]["comparison"] == {}

        final = client.post(
            "/api/v1/mock-interviews/sessions",
            json={"mode": "realistic", "purpose": "final", "seed": "final-v1"},
        )
        assert final.status_code == 201
        final_body = _complete_text_session(client, final.json())
        report = final_body["report"]
        assert report is not None
        assert report["comparison"]["baseline_report_id"] == baseline_body["report"]["id"]
        assert "overall_delta" in report["comparison"]
        assert "dimension_deltas" in report["comparison"]
        assert report["rubric_version"] == baseline_body["report"]["rubric_version"] == 1


def test_mock_turn_reuses_phase6_speech_attempt() -> None:
    with TestClient(app) as client:
        _login(client)
        consent = client.post("/api/v1/speech/consent", json={"accepted": True})
        assert consent.status_code == 200

        session_response = client.post(
            "/api/v1/mock-interviews/sessions",
            json={"mode": "practice", "purpose": "practice"},
        )
        assert session_response.status_code == 201
        session = session_response.json()
        turn = _active_turn(session)

        linked = client.post(
            f"/api/v1/mock-interviews/sessions/{session['id']}/turns/{turn['id']}/speech-attempt"
        )
        assert linked.status_code == 201
        speech = linked.json()["speech_attempt"]
        assert speech["source_key"] == f"{session['id']}:{turn['id']}"
        assert speech["prompt"]["question"] == turn["question"]

        manual = client.post(
            f"/api/v1/speech/attempts/{speech['id']}/manual-transcript",
            json={"text": STRONG_ANSWER},
        )
        assert manual.status_code == 200
        assert manual.json()["status"] == "feedback_ready"

        synced = client.post(
            f"/api/v1/mock-interviews/sessions/{session['id']}/turns/{turn['id']}/sync-speech"
        )
        assert synced.status_code == 200, synced.text
        body = synced.json()
        first_after = next(item for item in body["turns"] if item["id"] == turn["id"])
        assert first_after["status"] == "answered"
        assert first_after["answer_source"] == "speech_manual"
        assert first_after["speech_attempt_id"] == speech["id"]
        assert first_after["evaluation"] is not None
        assert body["answered_turns"] >= 1
