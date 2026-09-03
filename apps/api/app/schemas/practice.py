from uuid import UUID

from pydantic import BaseModel, Field


class PracticeActivityView(BaseModel):
    id: UUID
    content_version_id: UUID
    exercise_type: str
    contract_version: int
    prompt_checksum: str
    prompt: dict = Field(default_factory=dict)
    attempt_count: int = 0


class PracticeNextResponse(BaseModel):
    mode: str = "silent"
    strategy: str = "explore_mix"
    selection_reason_code: str = "fresh_family"
    selection_reason: str = "Building broad practice evidence."
    interaction_mode: str = "tap"
    mastery_state: str = "new"
    confidence: float = 0.0
    lapses: int = 0
    activity: PracticeActivityView
    available_types: list[str] = Field(default_factory=list)
