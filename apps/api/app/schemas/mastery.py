from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MasteryTargetView(BaseModel):
    target_id: UUID
    target_kind: str
    target_label: str
    content_version_id: UUID | None = None
    lemma: str
    skill_dimension: str
    state: str
    stability: float
    difficulty: float
    confidence: float
    success_streak: int
    lapses: int
    evidence_count: int
    next_review_at: datetime
    explanation_code: str


class ReviewQueueItem(BaseModel):
    target_id: UUID
    target_kind: str
    activity_instance_id: UUID
    content_version_id: UUID | None = None
    lemma: str
    due_at: datetime
    overdue: bool
    priority: int
    reason_code: str
    state: str


class ReviewHome(BaseModel):
    due_count: int
    scheduled_count: int
    weak_count: int
    mastered_count: int
    next_due_at: datetime | None = None
    due: list[ReviewQueueItem] = Field(default_factory=list)
    mastery: list[MasteryTargetView] = Field(default_factory=list)


class ReviewActivityView(BaseModel):
    target_id: UUID
    target_kind: str
    activity_instance_id: UUID
    content_version_id: UUID | None = None
    exercise_type: str
    contract_version: int
    prompt_checksum: str
    prompt: dict = Field(default_factory=dict)
    lemma: str
    question: str
    choices: list[dict[str, str]] = Field(default_factory=list)
    reason_code: str
    due_at: datetime
    state: str


class ReviewNextResponse(BaseModel):
    completed: bool
    activity: ReviewActivityView | None = None


class RebuildMasteryResult(BaseModel):
    event_count: int
    target_count: int
    queue_count: int
