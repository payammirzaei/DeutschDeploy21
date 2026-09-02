from pydantic import BaseModel, Field


class EngagementBadge(BaseModel):
    key: str
    title: str
    description: str
    earned: bool
    progress_current: int = Field(ge=0)
    progress_target: int = Field(gt=0)


class EngagementSummary(BaseModel):
    xp: int = Field(ge=0)
    level: int = Field(ge=1)
    level_progress_percent: int = Field(ge=0, le=100)
    next_level_xp: int = Field(gt=0)
    current_streak_days: int = Field(ge=0)
    longest_streak_days: int = Field(ge=0)
    total_reps: int = Field(ge=0)
    correct_reps: int = Field(ge=0)
    accuracy_percent: int = Field(ge=0, le=100)
    mastered_targets: int = Field(ge=0)
    timezone: str
    badges: list[EngagementBadge] = Field(default_factory=list)
