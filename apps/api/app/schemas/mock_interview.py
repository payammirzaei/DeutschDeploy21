from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.speech import SpeechAttemptView

MockMode = Literal["guided", "practice", "realistic"]
MockPurpose = Literal["practice", "baseline", "final"]


class MockModeView(BaseModel):
    mode: MockMode
    turn_count: int
    prep_seconds: int
    support: str


class MockBlueprintView(BaseModel):
    key: str
    version: int
    title: str
    target_cefr: str
    checksum: str
    modes: list[MockModeView]


class MockSessionCreateIn(BaseModel):
    mode: MockMode
    purpose: MockPurpose = "practice"
    seed: str | None = Field(default=None, min_length=4, max_length=64)


class MockTextAnswerIn(BaseModel):
    text: str = Field(min_length=1, max_length=8000)


class MockTurnEvaluationView(BaseModel):
    id: UUID
    rubric_version: int
    overall_score: int
    dimensions: dict
    evidence: dict
    summary: str
    next_action: str
    created_at: datetime


class MockTurnView(BaseModel):
    id: UUID
    position_key: str
    question_key: str
    category: str
    question: str
    intent: str | None
    hints: list[str]
    hint_available: bool
    hint_used: bool
    target_duration_seconds: int
    status: str
    is_follow_up: bool
    parent_turn_id: UUID | None
    follow_up_reason: str | None
    speech_attempt_id: UUID | None
    answer_source: str | None
    evaluation: MockTurnEvaluationView | None


class MockReadinessReportView(BaseModel):
    id: UUID
    rubric_version: int
    overall_score: int
    confidence: float
    dimensions: dict
    strengths: list
    priorities: list
    comparison: dict
    created_at: datetime


class MockSessionView(BaseModel):
    id: UUID
    blueprint_key: str
    blueprint_version: int
    blueprint_checksum: str
    mode: MockMode
    purpose: MockPurpose
    status: str
    current_turn_key: str | None
    answered_turns: int
    total_turns: int
    turns: list[MockTurnView]
    report: MockReadinessReportView | None
    created_at: datetime
    completed_at: datetime | None


class MockSessionList(BaseModel):
    sessions: list[MockSessionView]


class MockHintView(BaseModel):
    hints: list[str]


class MockSpeechAttemptView(BaseModel):
    speech_attempt: SpeechAttemptView
