import hashlib
import re
import unicodedata
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import ContentVersion, VerbVersion, VersionExample, VersionLocalization
from app.models.learning import ActivityInstance, CourseDay, ReleaseActivity

ADVANCED_EXERCISE_TYPES = (
    "meaning_matching",
    "example_cloze",
    "usage_error_spotting",
    "perfect_form_typing",
    "phrase_builder",
)

ADVANCED_TARGETS: dict[str, tuple[str, str]] = {
    "meaning_matching": ("meaning_association", "recognition"),
    "example_cloze": ("contextual_recall", "production"),
    "usage_error_spotting": ("usage_discrimination", "recognition"),
    "perfect_form_typing": ("perfect_form", "production"),
    "phrase_builder": ("phrase_fluency", "construction"),
}


class UnsupportedAdvancedExerciseError(ValueError):
    pass


async def materialize_advanced(
    session: AsyncSession,
    activity: ReleaseActivity,
    version: ContentVersion,
    verb: VerbVersion,
    day: CourseDay,
    exercise_type: str,
) -> tuple[dict, dict]:
    if exercise_type == "meaning_matching":
        return await _meaning_matching(session, day.release_id, activity, version, verb)
    if exercise_type == "example_cloze":
        return await _example_cloze(session, version, verb)
    if exercise_type == "usage_error_spotting":
        return await _usage_error_spotting(session, activity, version, verb)
    if exercise_type == "perfect_form_typing":
        return await _perfect_form_typing(session, version, verb)
    if exercise_type == "phrase_builder":
        return await _phrase_builder(session, activity, version, verb)
    raise UnsupportedAdvancedExerciseError(f"Unsupported advanced exercise: {exercise_type}")


def evaluate_advanced(
    instance: ActivityInstance,
    *,
    choice_id: str | None,
    text: str | None,
    token_ids: Sequence[str] | None,
    pair_ids: Sequence[str] | None,
) -> tuple[dict, dict, bool]:
    kind = instance.exercise_type
    if kind == "meaning_matching":
        if not pair_ids:
            raise ValueError("This exercise requires completed matches")
        expected_left = {
            str(item["id"]) for item in instance.prompt.get("left_items", [])
        }
        expected_right = {
            str(item["id"]) for item in instance.prompt.get("right_items", [])
        }
        submitted = [str(pair_id) for pair_id in pair_ids]
        parsed: list[tuple[str, str]] = []
        for pair_id in submitted:
            left_id, separator, right_id = pair_id.partition(":")
            if not separator or left_id not in expected_left or right_id not in expected_right:
                raise ValueError("Submitted match is not part of this activity instance")
            parsed.append((left_id, right_id))
        if len(parsed) != len(expected_left):
            raise ValueError("Every matching item must be answered exactly once")
        if len({left_id for left_id, _ in parsed}) != len(expected_left):
            raise ValueError("A matching source item was answered more than once")
        if len({right_id for _, right_id in parsed}) != len(expected_right):
            raise ValueError("A matching destination item was reused")
        normalized_pairs = sorted(f"{left}:{right}" for left, right in parsed)
        expected_pairs = sorted(str(value) for value in instance.answer_key.get("pair_ids", []))
        return (
            {"pair_ids": submitted},
            {"pair_ids": normalized_pairs},
            normalized_pairs == expected_pairs,
        )

    if kind in {"example_cloze", "perfect_form_typing"}:
        if text is None:
            raise ValueError("This exercise requires typed text")
        normalized = _normalize_text(text)
        if not normalized:
            raise ValueError("Typed answer cannot be empty")
        return (
            {"text": text},
            {"text": normalized},
            normalized == str(instance.answer_key.get("normalized_text", "")),
        )

    if kind == "usage_error_spotting":
        if not choice_id:
            raise ValueError("This exercise requires a choice")
        valid_ids = {str(choice["id"]) for choice in instance.prompt.get("choices", [])}
        if choice_id not in valid_ids:
            raise ValueError("Choice is not part of this activity instance")
        normalized = choice_id.strip()
        return (
            {"choice_id": choice_id},
            {"choice_id": normalized},
            normalized == instance.answer_key.get("choice_id"),
        )

    if kind == "phrase_builder":
        if not token_ids:
            raise ValueError("This exercise requires an ordered phrase list")
        expected_tokens = [str(token["id"]) for token in instance.prompt.get("tokens", [])]
        submitted = [str(token_id) for token_id in token_ids]
        if len(submitted) != len(expected_tokens) or set(submitted) != set(expected_tokens):
            raise ValueError("Submitted phrases do not match this activity instance")
        return (
            {"token_ids": submitted},
            {"token_ids": submitted},
            submitted == list(instance.answer_key.get("token_ids", [])),
        )

    raise UnsupportedAdvancedExerciseError(f"No advanced evaluator registered for {kind}")


async def _meaning_matching(
    session: AsyncSession,
    release_id: UUID,
    activity: ReleaseActivity,
    version: ContentVersion,
    verb: VerbVersion,
) -> tuple[dict, dict]:
    rows = (
        await session.execute(
            select(
                ReleaseActivity.content_version_id,
                VerbVersion.infinitive,
                VersionLocalization.value,
            )
            .join(CourseDay, CourseDay.id == ReleaseActivity.day_id)
            .join(
                VerbVersion,
                VerbVersion.version_id == ReleaseActivity.content_version_id,
            )
            .join(
                VersionLocalization,
                VersionLocalization.version_id == ReleaseActivity.content_version_id,
            )
            .where(
                CourseDay.release_id == release_id,
                VersionLocalization.locale == "fa",
                VersionLocalization.field == "translation",
                VersionLocalization.position == 0,
            )
        )
    ).all()
    by_version: dict[UUID, tuple[str, str]] = {}
    for content_version_id, infinitive, translation in rows:
        by_version.setdefault(content_version_id, (infinitive, translation))

    current_translation = by_version.get(version.id)
    if current_translation is None:
        raise UnsupportedAdvancedExerciseError("Pinned verb has no Persian translation")

    other_ids = [content_id for content_id in by_version if content_id != version.id]
    selected_ids = [
        version.id,
        *_stable_take_ids(other_ids, f"{activity.id}:matching", 2),
    ]
    if len(selected_ids) < 3:
        raise UnsupportedAdvancedExerciseError("Not enough release verbs for matching")

    left_items = [
        {
            "id": _item_id(content_id, "left"),
            "text": by_version[content_id][0],
        }
        for content_id in selected_ids
    ]
    right_items = [
        {
            "id": _item_id(content_id, "right"),
            "text": by_version[content_id][1],
        }
        for content_id in selected_ids
    ]
    left_items.sort(key=lambda item: _digest(f"{activity.id}:left:{item['id']}"))
    right_items.sort(key=lambda item: _digest(f"{activity.id}:right:{item['id']}"))
    pair_ids = sorted(
        f"{_item_id(content_id, 'left')}:{_item_id(content_id, 'right')}"
        for content_id in selected_ids
    )
    return (
        {
            "kind": "meaning_matching",
            "input": "matching",
            "lemma": verb.infinitive,
            "question": "سه فعل را به معنی فارسی درست وصل کن.",
            "left_items": left_items,
            "right_items": right_items,
            "tap_hint": "اول فعل، بعد معنی را لمس کن.",
        },
        {"pair_ids": pair_ids},
    )


async def _example_cloze(
    session: AsyncSession,
    version: ContentVersion,
    verb: VerbVersion,
) -> tuple[dict, dict]:
    example = await _example(session, version.id)
    cloze = _replace_exact_word(example.text_de, verb.infinitive, "____")
    if cloze is None:
        raise UnsupportedAdvancedExerciseError(
            "Example sentence does not contain the exact infinitive"
        )
    return (
        {
            "kind": "example_cloze",
            "input": "text",
            "lemma": verb.infinitive,
            "question": "جای خالی جمله‌ی مصاحبه را کامل کن.",
            "clue": cloze,
            "placeholder": "فعل آلمانی…",
        },
        {
            "text": verb.infinitive,
            "normalized_text": _normalize_text(verb.infinitive),
        },
    )


async def _usage_error_spotting(
    session: AsyncSession,
    activity: ReleaseActivity,
    version: ContentVersion,
    verb: VerbVersion,
) -> tuple[dict, dict]:
    example = await _example(session, version.id)
    participle_sentence = _replace_exact_word(
        example.text_de,
        verb.infinitive,
        verb.participle_ii,
    )
    zu_sentence = _replace_exact_word(
        example.text_de,
        verb.infinitive,
        f"zu {verb.infinitive}",
    )
    if participle_sentence is None or zu_sentence is None:
        raise UnsupportedAdvancedExerciseError(
            "Example sentence cannot produce a safe usage contrast"
        )
    if len({example.text_de, participle_sentence, zu_sentence}) < 3:
        raise UnsupportedAdvancedExerciseError("Usage contrasts are not distinct")
    values = [example.text_de, participle_sentence, zu_sentence]
    choices = _choice_list(activity.id, version.id, "usage", values)
    return (
        {
            "kind": "usage_error_spotting",
            "input": "choice",
            "lemma": verb.infinitive,
            "question": "کدام جمله از نظر ساختار فعل درست است؟",
            "choices": choices,
        },
        {"choice_id": _choice_id(version.id, "usage", example.text_de)},
    )


async def _perfect_form_typing(
    session: AsyncSession,
    version: ContentVersion,
    verb: VerbVersion,
) -> tuple[dict, dict]:
    auxiliary = verb.perfect_auxiliary.strip().casefold()
    participle = verb.participle_ii.strip()
    if auxiliary not in {"haben", "sein"} or not participle:
        raise UnsupportedAdvancedExerciseError("Pinned verb has incomplete Perfekt metadata")
    translation = await _translation(session, version.id, "fa")
    expected = f"{auxiliary} {participle}"
    return (
        {
            "kind": "perfect_form_typing",
            "input": "text",
            "lemma": verb.infinitive,
            "question": "Perfekt کامل را بنویس: Hilfsverb + Partizip II.",
            "clue": translation or verb.infinitive,
            "placeholder": "z. B. haben entwickelt",
        },
        {
            "text": expected,
            "normalized_text": _normalize_text(expected),
        },
    )


async def _phrase_builder(
    session: AsyncSession,
    activity: ReleaseActivity,
    version: ContentVersion,
    verb: VerbVersion,
) -> tuple[dict, dict]:
    example = await _example(session, version.id)
    words = _tokenize(example.text_de)
    if len(words) < 5 or len(words) > 24:
        raise UnsupportedAdvancedExerciseError("Example is outside phrase-builder limits")
    chunks = _chunk_tokens(words)
    if len(chunks) < 2:
        raise UnsupportedAdvancedExerciseError("Example cannot be split into useful phrases")
    ordered = [
        {
            "id": _token_id(version.id, index, text, "phrase"),
            "text": text,
        }
        for index, text in enumerate(chunks)
    ]
    shuffled = sorted(
        ordered,
        key=lambda token: _digest(f"{activity.id}:phrase:{token['id']}"),
    )
    if [token["id"] for token in shuffled] == [token["id"] for token in ordered]:
        shuffled = shuffled[1:] + shuffled[:1]
    return (
        {
            "kind": "phrase_builder",
            "input": "token_order",
            "lemma": verb.infinitive,
            "question": "تکه‌های جواب مصاحبه را به ترتیب طبیعی بچین.",
            "tokens": shuffled,
            "tap_hint": "هر تکه چند کلمه دارد؛ به ترتیب لمس کن.",
        },
        {"token_ids": [token["id"] for token in ordered]},
    )


async def _example(session: AsyncSession, version_id: UUID) -> VersionExample:
    example = await session.scalar(
        select(VersionExample)
        .where(VersionExample.version_id == version_id)
        .order_by(VersionExample.sort_order, VersionExample.external_id)
        .limit(1)
    )
    if example is None:
        raise UnsupportedAdvancedExerciseError("Pinned verb has no example sentence")
    return example


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


def _replace_exact_word(value: str, word: str, replacement: str) -> str | None:
    pattern = re.compile(rf"(?<!\w){re.escape(word)}(?!\w)", flags=re.IGNORECASE)
    if pattern.search(value) is None:
        return None
    return pattern.sub(replacement, value, count=1)


def _choice_list(
    activity_id: UUID,
    version_id: UUID,
    namespace: str,
    values: list[str],
) -> list[dict[str, str]]:
    ordered = sorted(values, key=lambda value: _digest(f"{activity_id}:{namespace}:{value}"))
    return [
        {"id": _choice_id(version_id, namespace, value), "text": value}
        for value in ordered
    ]


def _choice_id(version_id: UUID, namespace: str, text: str) -> str:
    return _digest(f"{version_id}:{namespace}:{text}")[:16]


def _item_id(version_id: UUID, side: str) -> str:
    return _digest(f"{version_id}:matching:{side}")[:16]


def _token_id(version_id: UUID, index: int, text: str, namespace: str) -> str:
    return _digest(f"{version_id}:{namespace}:{index}:{text}")[:16]


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return " ".join(normalized.strip().casefold().split())


def _tokenize(value: str) -> list[str]:
    return re.findall(r"\w+(?:[’']\w+)?|[^\w\s]", value, flags=re.UNICODE)


def _chunk_tokens(tokens: list[str]) -> list[str]:
    chunks: list[str] = []
    index = 0
    while index < len(tokens):
        width = 3 if len(tokens) - index >= 6 else 2
        part = tokens[index : index + width]
        chunks.append(_join_tokens(part))
        index += width
    return chunks


def _join_tokens(tokens: list[str]) -> str:
    result = ""
    punctuation = {".", ",", "!", "?", ":", ";"}
    for token in tokens:
        if not result:
            result = token
        elif token in punctuation:
            result += token
        else:
            result += f" {token}"
    return result


def _stable_take_ids(values: list[UUID], seed: str, count: int) -> list[UUID]:
    return sorted(values, key=lambda value: _digest(f"{seed}:{value}"))[:count]
