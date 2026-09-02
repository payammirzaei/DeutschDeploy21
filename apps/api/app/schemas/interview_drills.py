from uuid import UUID

from pydantic import BaseModel, Field


class InterviewDrillActivityView(BaseModel):
    id: UUID
    source_key: str
    exercise_type: str
    category: str
    contract_version: int
    prompt_checksum: str
    prompt: dict = Field(default_factory=dict)
    attempt_count: int


class InterviewDrillNextResponse(BaseModel):
    mode: str = "interview_drills"
    activity: InterviewDrillActivityView
    available_types: list[str] = Field(default_factory=list)
