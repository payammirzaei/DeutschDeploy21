import hashlib
import json
import unicodedata
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.learning import ActivityInstance, Attempt, Enrollment
from app.models.user import User
from app.schemas.interview_drills import InterviewDrillActivityView, InterviewDrillNextResponse
from app.services.learning import ensure_starter_learning, get_active_enrollment

CONTRACT_VERSION = 1
INTERVIEW_DRILL_TYPES = (
    "interview_best_answer",
    "hr_answer_order",
    "star_builder",
    "technical_explanation_order",
    "architecture_sequence",
    "timed_quick_recall",
)


class UnsupportedInterviewDrillError(ValueError):
    pass


def load_interview_drills() -> list[dict]:
    path = Path(__file__).resolve().parents[4] / "content" / "interview-drills.json"
    payload = json.loads(path.read_text())
    if not isinstance(payload, list):
        raise RuntimeError("Interview drill catalog must be a list")
    required = {
        "external_id",
        "family",
        "category",
        "question",
        "target_key",
        "target_label",
        "skill_dimension",
        "production_mode",
    }
    seen: set[str] = set()
    for drill in payload:
        if not isinstance(drill, dict) or not required.issubset(drill):
            raise RuntimeError("Interview drill catalog contains an invalid entry")
        external_id = str(drill["external_id"])
        if external_id in seen:
            raise RuntimeError(f"Duplicate interview drill id: {external_id}")
        if drill["family"] not in INTERVIEW_DRILL_TYPES:
            raise RuntimeError(f"Unsupported interview drill family: {drill['family']}")
        seen.add(external_id)
    return payload


async def get_next_interview_drill(
    session: AsyncSession,
    user: User,
) -> InterviewDrillNextResponse:
    await ensure_starter_learning(session, user)
    enrollment = await get_active_enrollment(session, user.id)
    if enrollment is None:
        raise RuntimeError("Interview drills require an active learning enrollment")

    drills = load_interview_drills()
    counts = await _attempt_counts(session, enrollment)
    total_attempts = sum(counts.values())
    start_index = total_attempts % len(INTERVIEW_DRILL_TYPES)
    type_order = INTERVIEW_DRILL_TYPES[start_index:] + INTERVIEW_DRILL_TYPES[:start_index]

    for family in type_order:
        candidates = [drill for drill in drills if drill["family"] == family]
        candidates.sort(
            key=lambda drill: (
                counts.get(str(drill["external_id"]), 0),
                _digest(f"{user.id}:{drill['external_id']}"),
            )
        )
        for drill in candidates:
            instance = await materialize_interview_drill(session, enrollment, drill)
            return InterviewDrillNextResponse(
                activity=InterviewDrillActivityView(
                    id=instance.id,
                    source_key=instance.source_key,
                    exercise_type=instance.exercise_type,
                    category=str(drill["category"]),
                    contract_version=instance.contract_version,
                    prompt_checksum=instance.prompt_checksum,
                    prompt=instance.prompt,
                    attempt_count=counts.get(instance.source_key, 0),
                ),
                available_types=list(INTERVIEW_DRILL_TYPES),
            )
    raise RuntimeError("No interview drill could be materialized")


async def materialize_interview_drill(
    session: AsyncSession,
    enrollment: Enrollment,
    drill: dict,
) -> ActivityInstance:
    external_id = str(drill["external_id"])
    existing = await session.scalar(
        select(ActivityInstance).where(
            ActivityInstance.enrollment_id == enrollment.id,
            ActivityInstance.source_kind == "interview_drill",
            ActivityInstance.source_key == external_id,
            ActivityInstance.instance_key == "interview",
        )
    )
    if existing is not None:
        return existing

    family = str(drill["family"])
    prompt: dict = {
        "kind": family,
        "question": str(drill["question"]),
        "category": str(drill["category"]),
        "target_key": str(drill["target_key"]),
        "target_label": str(drill["target_label"]),
        "target_kind": "interview_skill",
        "skill_dimension": str(drill["skill_dimension"]),
        "production_mode": str(drill["production_mode"]),
    }

    if family == "interview_best_answer":
        values = [str(value) for value in drill.get("choices", [])]
        correct_index = int(drill.get("correct_index", -1))
        if len(values) < 2 or not 0 <= correct_index < len(values):
            raise UnsupportedInterviewDrillError("Best-answer drill has invalid choices")
        choices = [
            {"id": _stable_id(external_id, "choice", index, text), "text": text}
            for index, text in enumerate(values)
        ]
        prompt.update({"input": "choice", "choices": choices})
        answer_key = {"choice_id": choices[correct_index]["id"]}
    elif family in {
        "hr_answer_order",
        "star_builder",
        "technical_explanation_order",
        "architecture_sequence",
    }:
        chunks = [str(value) for value in drill.get("chunks", [])]
        if len(chunks) < 3:
            raise UnsupportedInterviewDrillError("Ordering drill needs at least three chunks")
        ordered = [
            {"id": _stable_id(external_id, "token", index, text), "text": text}
            for index, text in enumerate(chunks)
        ]
        shuffled = sorted(
            ordered,
            key=lambda token: _digest(f"{external_id}:shuffle:{token['id']}"),
        )
        if [item["id"] for item in shuffled] == [item["id"] for item in ordered]:
            shuffled = shuffled[1:] + shuffled[:1]
        prompt.update(
            {
                "input": "token_order",
                "tokens": shuffled,
                "tap_hint": "Baue die Antwort in einer klaren Interview-Reihenfolge auf.",
            }
        )
        answer_key = {"token_ids": [item["id"] for item in ordered]}
    elif family == "timed_quick_recall":
        answers = [str(value) for value in drill.get("accepted_answers", [])]
        if not answers:
            raise UnsupportedInterviewDrillError("Timed recall needs accepted answers")
        prompt.update(
            {
                "input": "text",
                "clue": str(drill.get("clue", "")),
                "placeholder": "Schreib die Phrase aus dem Gedächtnis …",
                "time_limit_seconds": int(drill.get("time_limit_seconds", 15)),
            }
        )
        answer_key = {"normalized_texts": [_normalize_text(value) for value in answers]}
    else:
        raise UnsupportedInterviewDrillError(f"Unsupported interview drill: {family}")

    checksum = hashlib.sha256(
        json.dumps(prompt, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    instance = ActivityInstance(
        enrollment_id=enrollment.id,
        release_activity_id=None,
        source_kind="interview_drill",
        source_key=external_id,
        instance_key="interview",
        content_version_id=None,
        exercise_type=family,
        contract_version=CONTRACT_VERSION,
        prompt=prompt,
        answer_key=answer_key,
        prompt_checksum=checksum,
    )
    session.add(instance)
    await session.flush()
    return instance


def evaluate_interview_drill(
    instance: ActivityInstance,
    *,
    choice_id: str | None,
    text: str | None,
    token_ids: Sequence[str] | None,
) -> tuple[dict, dict, bool]:
    family = instance.exercise_type
    if family == "interview_best_answer":
        if not choice_id:
            raise ValueError("This interview drill requires a choice")
        valid = {str(choice["id"]) for choice in instance.prompt.get("choices", [])}
        if choice_id not in valid:
            raise ValueError("Choice is not part of this interview drill")
        raw = {"choice_id": choice_id}
        normalized = {"choice_id": choice_id.strip()}
        correct = normalized["choice_id"] == instance.answer_key.get("choice_id")
        return raw, normalized, correct

    if family in {
        "hr_answer_order",
        "star_builder",
        "technical_explanation_order",
        "architecture_sequence",
    }:
        if not token_ids:
            raise ValueError("This interview drill requires an ordered chunk list")
        expected = [str(token["id"]) for token in instance.prompt.get("tokens", [])]
        submitted = [str(token_id) for token_id in token_ids]
        if len(submitted) != len(expected) or set(submitted) != set(expected):
            raise ValueError("Submitted chunks do not match this interview drill")
        raw = {"token_ids": submitted}
        normalized = {"token_ids": submitted}
        correct = submitted == list(instance.answer_key.get("token_ids", []))
        return raw, normalized, correct

    if family == "timed_quick_recall":
        if text is None:
            raise ValueError("This interview drill requires typed text")
        normalized_text = _normalize_text(text)
        if not normalized_text:
            raise ValueError("Typed answer cannot be empty")
        accepted = {str(value) for value in instance.answer_key.get("normalized_texts", [])}
        return (
            {"text": text},
            {"text": normalized_text},
            normalized_text in accepted,
        )

    raise UnsupportedInterviewDrillError(f"No evaluator registered for {family}")


async def _attempt_counts(session: AsyncSession, enrollment: Enrollment) -> dict[str, int]:
    rows = (
        await session.execute(
            select(ActivityInstance.source_key, func.count(Attempt.id))
            .outerjoin(Attempt, Attempt.activity_instance_id == ActivityInstance.id)
            .where(
                ActivityInstance.enrollment_id == enrollment.id,
                ActivityInstance.source_kind == "interview_drill",
            )
            .group_by(ActivityInstance.source_key)
        )
    ).all()
    return {str(source_key): int(count or 0) for source_key, count in rows}


def _stable_id(external_id: str, namespace: str, index: int, text: str) -> str:
    return _digest(f"{external_id}:{namespace}:{index}:{text}")[:16]


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return " ".join(normalized.strip().casefold().split())
