import os
from copy import deepcopy
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


def _verb_payload(external_id: str) -> dict:
    suffix = external_id.split(".")[-1]
    return {
        "external_id": external_id,
        "type": "verb",
        "canonical_language": "de",
        "lemma": "entwickeln",
        "display_infinitive": "entwickeln",
        "translations": {"fa": ["توسعه دادن"], "en": ["to develop"]},
        "grammar": {
            "perfect_auxiliary": "haben",
            "participle_ii": "entwickelt",
            "preterite": None,
            "separable": False,
            "separable_prefix": None,
            "reflexive": False,
            "regularity": "regular",
            "governed_case": None,
            "governed_preposition": None,
        },
        "classification": {
            "cefr": "A2",
            "domains": ["software-development", "interview"],
            "register": "neutral",
        },
        "examples": [
            {
                "external_id": f"example.{suffix}.integration.1",
                "de": "Ich habe eine REST-API entwickelt.",
                "fa": "من یک REST API توسعه داده‌ام.",
                "en": "I developed a REST API.",
                "skill": "past-experience",
            }
        ],
    }


def test_content_import_publish_and_version_history() -> None:
    external_id = f"verb.integration-{uuid4().hex[:10]}"
    first = _verb_payload(external_id)

    with TestClient(app) as client:
        _login(client)

        dry_run = client.post("/api/v1/content/import/verbs/dry-run", json=[first])
        assert dry_run.status_code == 200
        assert dry_run.json()["creates"] == 1

        apply = client.post("/api/v1/content/import/verbs/apply", json=[first])
        assert apply.status_code == 200
        assert apply.json()["created"] == 1

        drafts = client.get("/api/v1/content/drafts/verbs")
        assert drafts.status_code == 200
        item = next(row for row in drafts.json() if row["external_id"] == external_id)

        publish_v1 = client.post(f"/api/v1/content/items/{item['item_id']}/publish")
        assert publish_v1.status_code == 200
        assert publish_v1.json()["version_number"] == 1

        second = deepcopy(first)
        second["translations"]["en"] = ["to develop", "to build"]
        second["examples"][0]["de"] = "Ich habe eine robuste REST-API entwickelt."

        update = client.post("/api/v1/content/import/verbs/apply", json=[second])
        assert update.status_code == 200
        assert update.json()["updated"] == 1

        publish_v2 = client.post(f"/api/v1/content/items/{item['item_id']}/publish")
        assert publish_v2.status_code == 200
        assert publish_v2.json()["version_number"] == 2
        assert publish_v2.json()["checksum"] != publish_v1.json()["checksum"]

        versions = client.get(f"/api/v1/content/items/{item['item_id']}/versions")
        assert versions.status_code == 200
        assert [row["version_number"] for row in versions.json()] == [2, 1]

        catalog = client.get("/api/v1/content/verbs")
        assert catalog.status_code == 200
        latest = next(row for row in catalog.json() if row["external_id"] == external_id)
        assert latest["version_number"] == 2
        assert latest["translations"]["en"] == ["to develop", "to build"]
        assert latest["examples"][0]["de"] == "Ich habe eine robuste REST-API entwickelt."


def test_starter_catalog_is_100_verbs_and_idempotent() -> None:
    with TestClient(app) as client:
        _login(client)

        first = client.post("/api/v1/content/starter-catalog")
        assert first.status_code == 200
        assert first.json()["catalog_size"] == 100
        assert first.json()["imported"] + first.json()["unchanged"] == 100

        second = client.post("/api/v1/content/starter-catalog")
        assert second.status_code == 200
        assert second.json()["catalog_size"] == 100
        assert second.json()["imported"] == 0
        assert second.json()["published"] == 0
        assert second.json()["unchanged"] == 100

        catalog = client.get("/api/v1/content/verbs")
        assert catalog.status_code == 200
        starter_rows = [row for row in catalog.json() if row["external_id"].startswith("verb.")]
        assert len(starter_rows) >= 100
        entwickeln = next(row for row in starter_rows if row["external_id"] == "verb.entwickeln")
        assert entwickeln["participle_ii"] == "entwickelt"
        assert entwickeln["translations"]["fa"] == ["توسعه دادن"]
        assert entwickeln["pedagogy"] is not None
        assert entwickeln["pedagogy"]["mistakes"]
        assert len(entwickeln["examples"]) >= 2
