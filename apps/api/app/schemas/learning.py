from uuid import UUID

from pydantic import BaseModel, Field, model_validator


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
    prompt: dict = Field(default_factory=dict)


class NextActivityResponse(BaseModel):
    completed: bool
    activity: ActivityInstanceView | None = None


class AttemptIn(BaseModel):
    choice_id: str | None = Field(default=None, min_length=1, max_length=120)
    text: str | None = Field(default=None, max_length=600)
    token_ids: list[str] | None = Field(default=None, max_length=40)
    pair_ids: list[str] | None = Field(default=None, max_length=20)
    duration_ms: int | None = Field(default=None, ge=0, le=3_600_000)

    @model_validator(mode="after")
    def require_answer(self) -> "AttemptIn":
        if (
            self.choice_id is None
            and self.text is None
            and not self.token_ids
            and not self.pair_ids
        ):
            raise ValueError("An exercise answer is required")
        return self


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
