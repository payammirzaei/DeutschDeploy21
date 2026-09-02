import hashlib
import json
import re
import unicodedata
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import ContentVersion, VerbVersion, VersionExample, VersionLocalization
from app.models.learning import ActivityInstance, CourseDay, Enrollment, ReleaseActivity

CONTRACT_VERSION = 1
SILENT_EXERCISE_TYPES = (
    "meaning_multiple_choice",
    "reverse_typing",
    "perfect_participle_choice",
    "auxiliary_choice",
    "sentence_order",
)

TARGET_BY_EXERCISE: dict[str, tuple[str, str]] = {
    "meaning_multiple_choice": ("meaning_recognition", "recognition"),
    "reverse_typing": ("lexical_recall", "production"),
    "perfect_participle_choice": ("perfect_participle", "recognition"),
    "auxiliary_choice": ("perfect_auxiliary", "recognition"),
    "sentence_order": ("sentence_structure", "construction"),
}


class UnsupportedExerciseError(ValueError):
    pass


def learning_target_for(exercise_type: str) -> tuple[str, str]:
    return TARGET_BY_EXERCISE.get(exercise_type, ("meaning_recognition", "recognition"))


async def materialize_exercise(
    session: AsyncSession,
    enrollment: Enrollment,
    activity: ReleaseActivity,
    exercise_type: str,
    instance_key: str,
) -> ActivityInstance:
    existing = await session.scalar(
        select(ActivityInstance).where(
            ActivityInstance.enrollment_id == enrollment.id,
            ActivityInstance.release_activity_id == activity.id,
            ActivityInstance.instance_key == instance_key,
        )
    )
    if existing is not None:
        return existing

    if exercise_type not in SILENT_EXERCISE_TYPES:
        raise UnsupportedExerciseError(f"Unsupported exercise type: {exercise_type}")

    version = await session.get(ContentVersion, activity.content_version_id)
    verb = await session.get(VerbVersion, activity.content_version_id)
    day = await session.get(CourseDay, activity.day_id)
    if version is None or verb is None or day is None:
        raise RuntimeError("Pinned content version cannot be materialized")

    if exercise_type == "meaning_multiple_choice":
        prompt, answer_key = await _meaning_multiple_choice(
            session,
            day.release_id,
            activity,
            version,
            verb,
        )
    elif exercise_type == "reverse_typing":
        prompt, answer_key = await _reverse_typing(session, version, verb)
    elif exercise_type == "perfect_participle_choice":
        prompt, answer_key = await _participle_choice(
            session,
            day.release_id,
            activity,
            version,
            verb,
        )
    elif exercise_type == "auxiliary_choice":
        prompt, answer_key = _auxiliary_choice(activity, version, verb)
    else:
        prompt, answer_key = await _sentence_order(session, activity, version, verb)

    checksum = hashlib.sha256(
        json.dumps(prompt, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    instance = ActivityInstance(
        enrollment_id=enrollment.id,
        release_activity_id=activity.id,
        instance_key=instance_key,
        content_version_id=version.id,
        exercise_type=exercise_type,
        contract_version=CONTRACT_VERSION,
        prompt=prompt,
        answer_key=answer_key,
        prompt_checksum=checksum,
    )
    session.add(instance)
    await session.flush()
    return instance


def evaluate_exercise(
    instance: ActivityInstance,
    *,
    choice_id: str | None,
    text: str | None,
    token_ids: Sequence[str] | None,
) -> tuple[dict, dict, bool, int, str]:
    kind = instance.exercise_type
    if kind in {
        "meaning_multiple_choice",
        "perfect_participle_choice",
        "auxiliary_choice",
    }:
        if not choice_id:
            raise ValueError("This exercise requires a choice")
        valid_ids = {str(choice["id"]) for choice in instance.prompt.get("choices", [])}
        if choice_id not in valid_ids:
            raise ValueError("Choice is not part of this activity instance")
        normalized = choice_id.strip()
        raw = {"choice_id": choice_id}
        normalized_answer = {"choice_id": normalized}
        correct = normalized == instance.answer_key.get("choice_id")
    elif kind == "reverse_typing":
        if text is None:
            raise ValueError("This exercise requires typed text")
        normalized = _normalize_text(text)
        if not normalized:
            raise ValueError("Typed answer cannot be empty")
        raw = {"text": text}
        normalized_answer = {"text": normalized}
        correct = normalized == str(instance.answer_key.get("normalized_text", ""))
    elif kind == "sentence_order":
        if not token_ids:
            raise ValueError("This exercise requires an ordered token list")
        expected_tokens = [str(token["id"]) for token in instance.prompt.get("tokens", [])]
        submitted = [str(token_id) for token_id in token_ids]
        if len(submitted) != len(expected_tokens) or set(submitted) != set(expected_tokens):
            raise ValueError("Submitted tokens do not match this activity instance")
        raw = {"token_ids": submitted}
        normalized_answer = {"token_ids": submitted}
        correct = submitted == list(instance.answer_key.get("token_ids", []))
    else:
        raise UnsupportedExerciseError(f"No evaluator registered for {kind}")

    return (
        raw,
        normalized_answer,
        correct,
        100 if correct else 0,
        "correct" if correct else "review_needed",
    )


async def _meaning_multiple_choice(
    session: AsyncSession,
    release_id: UUID,
    activity: ReleaseActivity,
    version: ContentVersion,
    verb: VerbVersion,
) -> tuple[dict, dict]:
    correct = await _translation(session, version.id, "fa")
    if correct is None:
        raise UnsupportedExerciseError("Pinned verb has no Persian translation")
    distractors = await _release_translations(session, release_id, version.id, correct)
    choices = _choice_list(activity.id, version.id, "meaning", [correct, *distractors])
    correct_id = _choice_id(version.id, "meaning", correct)
    return (
        {
            "kind": "meaning_multiple_choice",
            "input": "choice",
            "lemma": verb.infinitive,
            "cefr": version.cefr,
            "question": f"معنی «{verb.infinitive}» کدام است؟",
            "choices": choices,
        },
        {"choice_id": correct_id},
    )


async def _reverse_typing(
    session: AsyncSession,
    version: ContentVersion,
    verb: VerbVersion,
) -> tuple[dict, dict]:
    translation = await _translation(session, version.id, "fa")
    if translation is None:
        raise UnsupportedExerciseError("Pinned verb has no Persian translation")
    return (
        {
            "kind": "reverse_typing",
            "input": "text",
            "cefr": version.cefr,
            "question": "این معنی را به فعل آلمانی تبدیل کن.",
            "clue": translation,
            "placeholder": "فعل آلمانی را تایپ کن…",
        },
        {
            "text": verb.infinitive,
            "normalized_text": _normalize_text(verb.infinitive),
        },
    )


async def _participle_choice(
    session: AsyncSession,
    release_id: UUID,
    activity: ReleaseActivity,
    version: ContentVersion,
    verb: VerbVersion,
) -> tuple[dict, dict]:
    if not verb.participle_ii:
        raise UnsupportedExerciseError("Pinned verb has no Partizip II")
    rows = await session.execute(
        select(VerbVersion.participle_ii)
        .join(ReleaseActivity, ReleaseActivity.content_version_id == VerbVersion.version_id)
        .join(CourseDay, CourseDay.id == ReleaseActivity.day_id)
        .where(
            CourseDay.release_id == release_id,
            VerbVersion.version_id != version.id,
        )
        .order_by(VerbVersion.participle_ii)
    )
    distractors = _distinct_except(rows.scalars(), verb.participle_ii)
    if len(distractors) < 3:
        raise UnsupportedExerciseError("Not enough Partizip II distractors")
    distractors = _stable_take(distractors, f"{activity.id}:participle", 3)
    values = [verb.participle_ii, *distractors]
    choices = _choice_list(activity.id, version.id, "participle", values)
    return (
        {
            "kind": "perfect_participle_choice",
            "input": "choice",
            "lemma": verb.infinitive,
            "question": f"Partizip II درست برای «{verb.infinitive}» را انتخاب کن.",
            "choices": choices,
        },
        {"choice_id": _choice_id(version.id, "participle", verb.participle_ii)},
    )


def _auxiliary_choice(
    activity: ReleaseActivity,
    version: ContentVersion,
    verb: VerbVersion,
) -> tuple[dict, dict]:
    auxiliary = verb.perfect_auxiliary.strip().casefold()
    if auxiliary not in {"haben", "sein"}:
        raise UnsupportedExerciseError("Perfect auxiliary is not haben/sein")
    values = ["haben", "sein"]
    choices = _choice_list(activity.id, version.id, "auxiliary", values)
    return (
        {
            "kind": "auxiliary_choice",
            "input": "choice",
            "lemma": verb.infinitive,
            "question": f"«{verb.infinitive}» در Perfekt با کدام فعل کمکی می‌آید؟",
            "choices": choices,
        },
        {"choice_id": _choice_id(version.id, "auxiliary", auxiliary)},
    )


async def _sentence_order(
    session: AsyncSession,
    activity: ReleaseActivity,
    version: ContentVersion,
    verb: VerbVersion,
) -> tuple[dict, dict]:
    example = await session.scalar(
        select(VersionExample)
        .where(VersionExample.version_id == version.id)
        .order_by(VersionExample.sort_order, VersionExample.external_id)
        .limit(1)
    )
    if example is None:
        raise UnsupportedExerciseError("Pinned verb has no example sentence")
    parts = _tokenize(example.text_de)
    if len(parts) < 4 or len(parts) > 22:
        raise UnsupportedExerciseError("Example sentence is outside puzzle token limits")
    ordered = [
        {"id": _token_id(version.id, index, text), "text": text}
        for index, text in enumerate(parts)
    ]
    shuffled = sorted(
        ordered,
        key=lambda token: _digest(f"{activity.id}:sentence:{token['id']}"),
    )
    if [token["id"] for token in shuffled] == [token["id"] for token in ordered]:
        shuffled = shuffled[1:] + shuffled[:1]
    return (
        {
            "kind": "sentence_order",
            "input": "token_order",
            "lemma": verb.infinitive,
            "question": "جمله‌ی مصاحبه را به ترتیب درست بساز.",
            "tokens": shuffled,
            "tap_hint": "کلمه‌ها را به ترتیب لمس کن؛ drag لازم نیست.",
        },
        {"token_ids": [token["id"] for token in ordered]},
    )


async def _translation(session: AsyncSession, version_id: UUID, locale: str) -> str | None:
    return await session.scalar(
        select(VersionLocalization.value)
        .where(
            VersionLocalization.version_id == version_id,
            VersionLocalization.locale == locale,
            VersionLocalization.field == "translation",
            VersionLocalization.position == 0,
        )
        .limit(1)
    )


async def _release_translations(
    session: AsyncSession,
    release_id: UUID,
    target_version_id: UUID,
    correct: str,
) -> list[str]:
    rows = await session.execute(
        select(VersionLocalization.value)
        .join(
            ReleaseActivity,
            ReleaseActivity.content_version_id == VersionLocalization.version_id,
        )
        .join(CourseDay, CourseDay.id == ReleaseActivity.day_id)
        .where(
            CourseDay.release_id == release_id,
            VersionLocalization.locale == "fa",
            VersionLocalization.field == "translation",
            VersionLocalization.position == 0,
            VersionLocalization.version_id != target_version_id,
        )
        .order_by(VersionLocalization.value)
    )
    values = _distinct_except(rows.scalars(), correct)
    if len(values) < 3:
        raise UnsupportedExerciseError("Not enough translation distractors")
    return _stable_take(values, str(target_version_id), 3)


def _choice_list(
    activity_id: UUID,
    version_id: UUID,
    namespace: str,
    values: list[str],
) -> list[dict[str, str]]:
    ordered = sorted(
        values,
        key=lambda value: _digest(f"{activity_id}:{namespace}:{value}"),
    )
    return [
        {
            "id": _choice_id(version_id, namespace, value),
            "text": value,
        }
        for value in ordered
    ]


def _choice_id(version_id: UUID, namespace: str, text: str) -> str:
    return _digest(f"{version_id}:{namespace}:{text}")[:16]


def _token_id(version_id: UUID, index: int, text: str) -> str:
    return _digest(f"{version_id}:{index}:{text}")[:16]


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return " ".join(normalized.strip().casefold().split())


def _tokenize(value: str) -> list[str]:
    return re.findall(r"\w+(?:[’']\w+)?|[^\w\s]", value, flags=re.UNICODE)


def _distinct_except(values: Sequence[str], excluded: str) -> list[str]:
    result: list[str] = []
    for value in values:
        if value != excluded and value not in result:
            result.append(value)
    return result


def _stable_take(values: list[str], seed: str, count: int) -> list[str]:
    return sorted(values, key=lambda value: _digest(f"{seed}:{value}"))[:count]
