from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

LESSON_OVERLAY_ROOT = (
    Path(__file__).resolve().parents[4] / "content" / "lessons"
)
V4_TEACHING_OVERLAY_PATH = LESSON_OVERLAY_ROOT / "days-1-3.v4.json"

TeachingBlockType = Literal["grammar", "usage", "interview_pattern", "contrast"]
SpiralStage = Literal["introduced", "reinforced", "recalled", "applied"]


@dataclass(frozen=True)
class OverlayPin:
    overlay_id: str
    overlay_version: int
    schema_version: int
    checksum: str
    path: Path
    release_version: int = 4


# Frozen for curriculum release v4. Editing teaching content requires a new
# overlay_version (or curriculum v5) — never a silent rewrite of this pin.
V4_TEACHING_OVERLAY_PIN = OverlayPin(
    overlay_id="software-interview-21d-v4-teaching",
    overlay_version=2,
    schema_version=1,
    checksum="495e9ab911660152c891856f5c8a4908e88afa10f5c1a279db601614e934f8da",
    path=V4_TEACHING_OVERLAY_PATH,
    release_version=4,
)

RELEASE_OVERLAY_PINS: dict[int, OverlayPin] = {
    4: V4_TEACHING_OVERLAY_PIN,
}


class LocalizedNote(BaseModel):
    en: str
    fa: str


class TeachingBlock(BaseModel):
    id: str
    type: TeachingBlockType
    activity_position: int
    title_i18n: LocalizedNote
    explanation_i18n: LocalizedNote
    rule_i18n: LocalizedNote
    example_de: str
    example_i18n: LocalizedNote | None = None
    common_mistake_de: str | None = None
    corrected_example_de: str | None = None


class PromptOverride(BaseModel):
    activity_position: int
    question_i18n: LocalizedNote
    chunks: list[str]


class SpiralEntry(BaseModel):
    external_id: str
    lemma: str
    stage: SpiralStage
    day: int
    focus: str


class PlannedSpiral(BaseModel):
    external_id: str
    from_day: int
    planned_day: int
    stage: SpiralStage
    focus: str
    status: Literal["planned"] = "planned"


class DayLessonOverlay(BaseModel):
    context_de: str | None = None
    context_i18n: LocalizedNote | None = None
    activity_stages: list[str] = Field(default_factory=list)
    teaching_blocks: list[TeachingBlock] = Field(default_factory=list)
    prompt_overrides: list[PromptOverride] = Field(default_factory=list)
    spiral: list[SpiralEntry] = Field(default_factory=list)
    planned_future: list[PlannedSpiral] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_teaching_positions(self) -> DayLessonOverlay:
        positions = [block.activity_position for block in self.teaching_blocks]
        if len(positions) != len(set(positions)):
            raise ValueError("teaching_blocks must have unique activity_position values")
        override_positions = [item.activity_position for item in self.prompt_overrides]
        if len(override_positions) != len(set(override_positions)):
            raise ValueError("prompt_overrides must have unique activity_position values")
        return self


class LessonOverlayFile(BaseModel):
    overlay_id: str
    overlay_version: int
    schema_version: int
    course_slug: str
    release_version: int
    checksum: str
    days: dict[str, DayLessonOverlay]


def overlay_canonical_payload(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "course_slug": raw.get("course_slug"),
        "days": raw.get("days"),
        "overlay_id": raw.get("overlay_id"),
        "overlay_version": raw.get("overlay_version"),
        "release_version": raw.get("release_version"),
        "schema_version": raw.get("schema_version"),
    }


def compute_overlay_checksum(raw: dict[str, Any]) -> str:
    canonical = json.dumps(
        overlay_canonical_payload(raw),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def overlay_pin_for_release(release_version: int) -> OverlayPin | None:
    return RELEASE_OVERLAY_PINS.get(release_version)


def verify_overlay_payload(raw: dict[str, Any], pin: OverlayPin) -> str:
    checksum = compute_overlay_checksum(raw)
    if raw.get("overlay_id") != pin.overlay_id:
        raise RuntimeError(
            f"Teaching overlay id {raw.get('overlay_id')!r} does not match "
            f"pinned {pin.overlay_id!r}"
        )
    if int(raw.get("overlay_version") or 0) != pin.overlay_version:
        raise RuntimeError(
            "Teaching overlay_version does not match the pinned overlay for this release"
        )
    if int(raw.get("schema_version") or 0) != pin.schema_version:
        raise RuntimeError("Teaching overlay schema_version does not match the pin")
    if int(raw.get("release_version") or 0) != pin.release_version:
        raise RuntimeError("Teaching overlay release_version does not match the pin")
    if checksum != pin.checksum:
        raise RuntimeError(
            "Teaching overlay checksum does not match the immutable pin for this "
            "release. Bump overlay_version (and the pin) instead of silently rewriting."
        )
    if raw.get("checksum") != pin.checksum:
        raise RuntimeError(
            "Teaching overlay file checksum field does not match the pinned identity"
        )
    return checksum


@lru_cache(maxsize=8)
def load_overlay_for_release(release_version: int) -> LessonOverlayFile | None:
    pin = overlay_pin_for_release(release_version)
    if pin is None:
        return None
    raw = json.loads(pin.path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuntimeError("Teaching overlay must be a JSON object")
    verify_overlay_payload(raw, pin)
    return LessonOverlayFile.model_validate(raw)


def load_v4_lesson_overlay() -> LessonOverlayFile:
    overlay = load_overlay_for_release(4)
    if overlay is None:
        raise RuntimeError("v4 teaching overlay pin is missing")
    return overlay


def overlay_identity_for_release(release_version: int) -> dict[str, Any] | None:
    pin = overlay_pin_for_release(release_version)
    if pin is None:
        return None
    load_overlay_for_release(release_version)
    return {
        "overlay_id": pin.overlay_id,
        "overlay_version": pin.overlay_version,
        "schema_version": pin.schema_version,
        "checksum": pin.checksum,
    }


def overlay_for_day(day_number: int, release_version: int = 4) -> DayLessonOverlay | None:
    overlay = load_overlay_for_release(release_version)
    if overlay is None:
        return None
    return overlay.days.get(str(day_number))


def teaching_block_for_position(
    day_number: int,
    position: int,
    release_version: int = 4,
) -> TeachingBlock | None:
    day = overlay_for_day(day_number, release_version)
    if day is None:
        return None
    matches = [
        block for block in day.teaching_blocks if block.activity_position == position
    ]
    return matches[0] if matches else None


def prompt_override_for_position(
    day_number: int,
    position: int,
    release_version: int = 4,
) -> PromptOverride | None:
    day = overlay_for_day(day_number, release_version)
    if day is None:
        return None
    matches = [
        item for item in day.prompt_overrides if item.activity_position == position
    ]
    return matches[0] if matches else None


def apply_prompt_override(
    prompt: dict[str, Any],
    answer_key: dict[str, Any],
    override: PromptOverride,
    *,
    overlay_identity: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Rewrite the graded token contract and pin the overlay identity into it.

    Prompt overrides change what constitutes a correct answer, so they belong to
    the exercise contract. Historical instances must keep the identity that was
    used when the activity was materialized.
    """
    ordered = [
        {
            "id": f"overlay-{override.activity_position}-{index}",
            "text": chunk,
        }
        for index, chunk in enumerate(override.chunks)
    ]
    shuffled = sorted(
        ordered,
        key=lambda token: hashlib.sha256(
            f"{override.activity_position}:{token['id']}".encode()
        ).hexdigest(),
    )
    if [token["id"] for token in shuffled] == [token["id"] for token in ordered]:
        shuffled = shuffled[1:] + shuffled[:1]
    next_prompt = dict(prompt)
    next_prompt["kind"] = "phrase_builder"
    next_prompt["input"] = "token_order"
    next_prompt["question_i18n"] = override.question_i18n.model_dump()
    next_prompt["question"] = override.question_i18n.en
    next_prompt["tokens"] = shuffled
    next_prompt["lemma"] = "Introduction"
    next_prompt["overlay_contract"] = {
        "overlay_id": overlay_identity["overlay_id"],
        "overlay_version": overlay_identity["overlay_version"],
        "overlay_checksum": overlay_identity["checksum"],
        "schema_version": overlay_identity["schema_version"],
        "changes_answer_key": True,
        "graded_as": "phrase_builder",
    }
    next_key = {
        "token_ids": [token["id"] for token in ordered],
        "overlay_contract": dict(next_prompt["overlay_contract"]),
    }
    return next_prompt, next_key


def overlay_contract_from_instance(instance_prompt: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(instance_prompt, dict):
        return None
    contract = instance_prompt.get("overlay_contract")
    return dict(contract) if isinstance(contract, dict) else None


def teaching_block_as_prompt(block: TeachingBlock) -> dict[str, Any]:
    return {
        "id": block.id,
        "type": block.type,
        "title_i18n": block.title_i18n.model_dump(),
        "explanation_i18n": block.explanation_i18n.model_dump(),
        "rule_i18n": block.rule_i18n.model_dump(),
        "example_de": block.example_de,
        "example_i18n": block.example_i18n.model_dump() if block.example_i18n else None,
        "common_mistake_de": block.common_mistake_de,
        "corrected_example_de": block.corrected_example_de,
    }


def day_overlay_as_view(
    day_number: int,
    release_version: int = 4,
) -> dict[str, Any] | None:
    day = overlay_for_day(day_number, release_version)
    if day is None:
        return None
    identity = overlay_identity_for_release(release_version) or {}
    return {
        **identity,
        "context_de": day.context_de,
        "context_i18n": day.context_i18n.model_dump() if day.context_i18n else None,
        "activity_stages": list(day.activity_stages),
        "teaching_blocks": [
            teaching_block_as_prompt(block) for block in day.teaching_blocks
        ],
        "spiral": [item.model_dump() for item in day.spiral],
        "planned_future": [item.model_dump() for item in day.planned_future],
    }
