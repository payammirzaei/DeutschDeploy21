from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SpeakingPromptView(BaseModel):
    id: str
    category: str
    question: str
    support: list[str]
    target_duration_seconds: int


class SpeechConsentView(BaseModel):
    policy_version: str
    accepted: bool
    accepted_at: datetime | None = None


class SpeechConsentIn(BaseModel):
    accepted: bool


class SpeechAttemptCreateIn(BaseModel):
    prompt_id: str = Field(min_length=1, max_length=180)


class TranscriptTextIn(BaseModel):
    text: str = Field(min_length=1, max_length=8000)


class MediaView(BaseModel):
    id: UUID
    status: str
    content_type: str
    byte_size: int
    sha256: str
    duration_ms: int | None


class TranscriptView(BaseModel):
    id: UUID
    kind: str
    revision_number: int
    text: str
    language: str
    provider: str | None
    model: str | None
    confidence: float | None
    created_at: datetime


class SpeechFeedbackView(BaseModel):
    id: UUID
    transcript_id: UUID
    evaluator_type: str
    evaluator_version: int
    overall_score: int
    summary: str
    dimensions: dict
    corrections: list
    next_action: str
    created_at: datetime


class SpeechAttemptView(BaseModel):
    id: UUID
    source_key: str
    prompt: dict
    prompt_checksum: str
    language: str
    target_duration_seconds: int
    status: str
    media: MediaView | None = None
    transcription_job_id: UUID | None = None
    transcription_retry_count: int
    transcripts: list[TranscriptView] = Field(default_factory=list)
    feedback: SpeechFeedbackView | None = None
    created_at: datetime
    updated_at: datetime


class SpeechUploadResult(BaseModel):
    attempt: SpeechAttemptView
    queued: bool


class SpeechAttemptList(BaseModel):
    attempts: list[SpeechAttemptView]
