from uuid import UUID

from pydantic import BaseModel, Field


class ChoiceView(BaseModel):
    id: str
    text: str


class ActivitySummary(BaseModel):
    activity_id: UUID
    position: int
    content_version_id: UUID
    exercise_type: str
    submitted: bool


class DayView(BaseModel):
    day_number: int
    title: str
    objective: str
    completed: bool
    submitted_count: int
    total_count: int
    activities: list[ActivitySummary]


class LearningHome(BaseModel):
    enrolled: bool
    enrollment_id: UUID | None = None
    course_title: str | None = None
    release_version: int | None = None
    current_day: int = 1
    available_through_day: int = 3
    days: list[DayView] = Field(default_factory=list)


class ActivityInstanceView(BaseModel):
    id: UUID
    day_number: int
    position: int
    content_version_id: UUID
    exercise_type: str
    contract_version: int
    prompt_checksum: str
    lemma: str
    question: str
    choices: list[ChoiceView]


class NextActivityResponse(BaseModel):
    completed: bool
    activity: ActivityInstanceView | None = None


class AttemptIn(BaseModel):
    choice_id: str = Field(min_length=2, max_length=80)
    duration_ms: int | None = Field(default=None, ge=0, le=3_600_000)


class AttemptResult(BaseModel):
    attempt_id: UUID
    evaluation_id: UUID
    correct: bool
    score: int
    feedback_code: str
    day_complete: bool
    next_day: int


class StartLearningResult(BaseModel):
    enrollment_id: UUID
    course_release_id: UUID
    created_enrollment: bool
    pinned_activity_count: int
