import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import ContentItem, ContentVersion
from app.models.learning import Course, CourseDay, CourseRelease, ReleaseActivity
from app.models.user import User
from app.services.content import (
    apply_verb_import,
    dry_run_verbs,
    load_starter_verbs,
    publish_item,
)
from app.services.exercise_registry import ALL_SILENT_EXERCISE_TYPES
from app.services.interview_drills import INTERVIEW_DRILL_TYPES, load_interview_drills

COURSE_SLUG = "software-interview-21d"
LATEST_RELEASE_VERSION = 3
CURRICULUM_ROOT = Path(__file__).resolve().parents[4] / "content" / "curriculum"
V2_CURRICULUM_PATH = CURRICULUM_ROOT / "software-interview-21d.v2.json"
CURRICULUM_PATH = CURRICULUM_ROOT / "software-interview-21d.v3.json"

LEGACY_STARTER_DAYS = [
    {
        "day": 1,
        "title": "Introduce yourself",
        "objective": (
            "Build the vocabulary for a clear 60-second professional introduction."
        ),
        "verbs": [
            "verb.vorstellen",
            "verb.arbeiten",
            "verb.lernen",
            "verb.sprechen",
            "verb.erklaeren",
            "verb.beschreiben",
            "verb.fragen",
        ],
    },
    {
        "day": 2,
        "title": "Explain what you build",
        "objective": (
            "Describe software work, tools and implementation responsibilities."
        ),
        "verbs": [
            "verb.entwickeln",
            "verb.programmieren",
            "verb.implementieren",
            "verb.bauen",
            "verb.erstellen",
            "verb.verwenden",
            "verb.nutzen",
        ],
    },
    {
        "day": 3,
        "title": "Problems and delivery",
        "objective": (
            "Explain testing, debugging, problem solving and improvement work."
        ),
        "verbs": [
            "verb.testen",
            "verb.pruefen",
            "verb.analysieren",
            "verb.loesen",
            "verb.finden",
            "verb.beheben",
            "verb.verbessern",
        ],
    },
]


def _load_curriculum_manifest(
    path: Path,
    expected_release_version: int,
) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuntimeError("Curriculum manifest must be a JSON object")
    payload = _expand_manifest(raw)
    _validate_manifest(payload, expected_release_version)
    return payload


def load_curriculum_manifest() -> dict[str, Any]:
    return _load_curriculum_manifest(CURRICULUM_PATH, LATEST_RELEASE_VERSION)


def _expand_manifest(raw: dict[str, Any]) -> dict[str, Any]:
    payload = {key: value for key, value in raw.items() if key != "days"}
    expanded_days: list[dict[str, Any]] = []
    for raw_day in raw.get("days", []):
        activities: list[dict[str, Any]] = []
        for verb in raw_day.get("verbs", []):
            if not isinstance(verb, list) or len(verb) != 2:
                raise RuntimeError("Curriculum verb entry must be [id, exercise]")
            activities.append(
                {
                    "source_kind": "content",
                    "external_id": str(verb[0]),
                    "exercise_type": str(verb[1]),
                    "required": True,
                }
            )
        for external_id in raw_day.get("drills", []):
            activities.append(
                {
                    "source_kind": "interview_drill",
                    "external_id": str(external_id),
                    "required": True,
                }
            )
        expanded_days.append(
            {
                "day": raw_day.get("day"),
                "title": raw_day.get("title"),
                "objective": raw_day.get("objective"),
                "activities": activities,
            }
        )
    payload["days"] = expanded_days
    return payload


def curriculum_manifest_checksum(manifest: dict[str, Any] | None = None) -> str:
    payload = manifest or load_curriculum_manifest()
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def manifest_activity_count(manifest: dict[str, Any] | None = None) -> int:
    payload = manifest or load_curriculum_manifest()
    return sum(len(day["activities"]) for day in payload["days"])


async def ensure_curriculum_releases(
    session: AsyncSession,
    user: User,
) -> tuple[Course, CourseRelease, CourseRelease]:
    legacy_manifest = _load_curriculum_manifest(V2_CURRICULUM_PATH, 2)
    latest_manifest = load_curriculum_manifest()
    await _ensure_all_starter_content(session, user)

    course = await session.scalar(select(Course).where(Course.slug == COURSE_SLUG))
    if course is None:
        course = Course(
            slug=COURSE_SLUG,
            title=str(latest_manifest["title"]),
            target_language="de",
            target_cefr=str(latest_manifest["target_cefr"]),
            duration_days=21,
        )
        session.add(course)
        await session.flush()

    legacy = await _release_by_version(session, course.id, 1)
    if legacy is None:
        legacy = CourseRelease(
            course_id=course.id,
            version_number=1,
            status="published",
            manifest_checksum=None,
        )
        session.add(legacy)
        await session.flush()
        await _build_legacy_release(session, legacy)

    await _ensure_manifest_release(session, course.id, legacy_manifest)
    latest = await _ensure_manifest_release(session, course.id, latest_manifest)
    return course, legacy, latest


async def _ensure_manifest_release(
    session: AsyncSession,
    course_id: UUID,
    manifest: dict[str, Any],
) -> CourseRelease:
    version = int(manifest["release_version"])
    checksum = curriculum_manifest_checksum(manifest)
    release = await _release_by_version(session, course_id, version)
    if release is None:
        release = CourseRelease(
            course_id=course_id,
            version_number=version,
            status="published",
            manifest_checksum=checksum,
        )
        session.add(release)
        await session.flush()
        await _build_manifest_release(session, release, manifest)
    elif release.manifest_checksum != checksum:
        raise RuntimeError(
            f"Published curriculum release v{version} differs from the checked-in "
            "manifest. Create a new immutable release version instead of mutating it."
        )
    return release


async def _ensure_all_starter_content(
    session: AsyncSession,
    user: User,
) -> None:
    payloads = load_starter_verbs()
    report = await dry_run_verbs(session, payloads)
    actions = {row.external_id: row.action for row in report.rows}
    missing = [
        payload
        for payload in payloads
        if actions.get(payload.external_id) == "create"
    ]
    if missing:
        await apply_verb_import(session, user, missing)

    for payload in payloads:
        item = await session.scalar(
            select(ContentItem).where(
                ContentItem.external_id == payload.external_id
            )
        )
        if item is None:
            raise RuntimeError(
                f"Required content item missing: {payload.external_id}"
            )
        latest = await _latest_content_version(session, item.id)
        if latest is None:
            await publish_item(session, user, item.id)


async def _build_legacy_release(
    session: AsyncSession,
    release: CourseRelease,
) -> None:
    for day_spec in LEGACY_STARTER_DAYS:
        day = CourseDay(
            release_id=release.id,
            day_number=int(day_spec["day"]),
            title=str(day_spec["title"]),
            objective=str(day_spec["objective"]),
        )
        session.add(day)
        await session.flush()

        for position, external_id in enumerate(day_spec["verbs"], start=1):
            version = await _published_version_for_external_id(
                session,
                str(external_id),
            )
            session.add(
                ReleaseActivity(
                    day_id=day.id,
                    position=position,
                    source_kind="content",
                    source_key=str(external_id),
                    exercise_type="meaning_multiple_choice",
                    contract_version=1,
                    content_version_id=version.id,
                    required=True,
                )
            )
    await session.flush()


async def _build_manifest_release(
    session: AsyncSession,
    release: CourseRelease,
    manifest: dict[str, Any],
) -> None:
    drills = {
        str(drill["external_id"]): drill
        for drill in load_interview_drills()
    }
    for day_spec in manifest["days"]:
        day = CourseDay(
            release_id=release.id,
            day_number=int(day_spec["day"]),
            title=str(day_spec["title"]),
            objective=str(day_spec["objective"]),
        )
        session.add(day)
        await session.flush()

        for position, spec in enumerate(day_spec["activities"], start=1):
            source_kind = str(spec["source_kind"])
            external_id = str(spec["external_id"])
            if source_kind == "content":
                version = await _published_version_for_external_id(
                    session,
                    external_id,
                )
                exercise_type = str(spec["exercise_type"])
                content_version_id = version.id
            else:
                drill = drills[external_id]
                exercise_type = str(drill["family"])
                content_version_id = None

            session.add(
                ReleaseActivity(
                    day_id=day.id,
                    position=position,
                    source_kind=source_kind,
                    source_key=external_id,
                    exercise_type=exercise_type,
                    contract_version=1,
                    content_version_id=content_version_id,
                    required=bool(spec.get("required", True)),
                )
            )
    await session.flush()


async def _release_by_version(
    session: AsyncSession,
    course_id: UUID,
    version: int,
) -> CourseRelease | None:
    return await session.scalar(
        select(CourseRelease)
        .where(
            CourseRelease.course_id == course_id,
            CourseRelease.version_number == version,
        )
        .limit(1)
    )


async def _published_version_for_external_id(
    session: AsyncSession,
    external_id: str,
) -> ContentVersion:
    item = await session.scalar(
        select(ContentItem).where(ContentItem.external_id == external_id)
    )
    if item is None:
        raise RuntimeError(f"Curriculum content missing: {external_id}")
    version = await _latest_content_version(session, item.id)
    if version is None:
        raise RuntimeError(
            f"Curriculum content has no published version: {external_id}"
        )
    return version


async def _latest_content_version(
    session: AsyncSession,
    item_id: UUID,
) -> ContentVersion | None:
    return await session.scalar(
        select(ContentVersion)
        .where(ContentVersion.item_id == item_id)
        .order_by(ContentVersion.version_number.desc())
        .limit(1)
    )


def _validate_manifest(
    manifest: dict[str, Any],
    expected_release_version: int,
) -> None:
    required_top = {
        "schema_version",
        "course_slug",
        "release_version",
        "title",
        "target_cefr",
        "days",
    }
    if not required_top.issubset(manifest):
        raise RuntimeError("Curriculum manifest is missing required fields")
    if manifest["course_slug"] != COURSE_SLUG:
        raise RuntimeError("Curriculum manifest course slug is invalid")
    if int(manifest["release_version"]) != expected_release_version:
        raise RuntimeError("Curriculum manifest release version is invalid")

    days = manifest["days"]
    if not isinstance(days, list) or len(days) != 21:
        raise RuntimeError(
            f"Curriculum release v{expected_release_version} must contain exactly 21 days"
        )
    day_numbers = [int(day.get("day", 0)) for day in days]
    if day_numbers != list(range(1, 22)):
        raise RuntimeError("Curriculum days must be ordered from 1 through 21")

    starter_ids = {payload.external_id for payload in load_starter_verbs()}
    drill_rows = load_interview_drills()
    drill_by_id = {
        str(drill["external_id"]): drill
        for drill in drill_rows
    }
    introduced_content: list[str] = []
    covered_drills: set[str] = set()

    for day in days:
        if not str(day.get("title", "")).strip():
            raise RuntimeError("Every curriculum day needs a title")
        if not str(day.get("objective", "")).strip():
            raise RuntimeError("Every curriculum day needs an objective")
        activities = day.get("activities")
        if not isinstance(activities, list) or not activities:
            raise RuntimeError(
                f"Day {day['day']} must contain at least one activity"
            )

        content_count = 0
        for activity in activities:
            if not isinstance(activity, dict):
                raise RuntimeError("Curriculum activity must be an object")
            source_kind = str(activity.get("source_kind", ""))
            external_id = str(activity.get("external_id", ""))
            if source_kind == "content":
                content_count += 1
                if external_id not in starter_ids:
                    raise RuntimeError(
                        f"Unknown curriculum content id: {external_id}"
                    )
                exercise_type = str(activity.get("exercise_type", ""))
                if exercise_type not in ALL_SILENT_EXERCISE_TYPES:
                    raise RuntimeError(
                        f"Unsupported curriculum exercise: {exercise_type}"
                    )
                if int(day["day"]) <= 15:
                    introduced_content.append(external_id)
            elif source_kind == "interview_drill":
                drill = drill_by_id.get(external_id)
                if drill is None:
                    raise RuntimeError(
                        f"Unknown interview drill id: {external_id}"
                    )
                family = str(drill["family"])
                if family not in INTERVIEW_DRILL_TYPES:
                    raise RuntimeError(
                        f"Unsupported interview drill family: {family}"
                    )
                covered_drills.add(external_id)
            else:
                raise RuntimeError(
                    f"Unsupported curriculum source kind: {source_kind}"
                )

        day_number = int(day["day"])
        if day_number <= 14 and content_count != 7:
            raise RuntimeError(
                f"Day {day_number} must introduce exactly seven verbs"
            )
        if day_number == 15 and content_count != 2:
            raise RuntimeError("Day 15 must introduce exactly two verbs")

    if len(introduced_content) != 100:
        raise RuntimeError(
            "Days 1-15 must introduce exactly 100 content items"
        )
    if len(set(introduced_content)) != 100:
        raise RuntimeError(
            "Days 1-15 must not introduce the same verb twice"
        )
    if set(introduced_content) != starter_ids:
        raise RuntimeError(
            "Days 1-15 must cover the complete 100-verb starter catalog"
        )

    expected_drills = set(drill_by_id)
    if covered_drills != expected_drills:
        missing = sorted(expected_drills - covered_drills)
        extra = sorted(covered_drills - expected_drills)
        raise RuntimeError(
            "Curriculum interview coverage mismatch: "
            f"missing={missing}, extra={extra}"
        )

    total = sum(len(day["activities"]) for day in days)
    if total != 133:
        raise RuntimeError(
            f"Curriculum v{expected_release_version} expected 133 activities, found {total}"
        )