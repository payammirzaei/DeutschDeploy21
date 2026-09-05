export type LessonStageKey =
  | "learn"
  | "recognize"
  | "build"
  | "recall"
  | "challenge"
  | "complete";

export type JourneyActivity = {
  position: number;
  submitted: boolean;
};

export const LESSON_STAGE_ORDER: LessonStageKey[] = [
  "learn",
  "recognize",
  "build",
  "recall",
  "challenge",
  "complete",
];

const PRACTICE_STAGES: Exclude<LessonStageKey, "complete">[] = [
  "learn",
  "recognize",
  "build",
  "recall",
  "challenge",
];

export function lessonStageForPosition(
  position: number,
  totalActivities: number,
  authoredStages?: string[] | null,
): Exclude<LessonStageKey, "complete"> {
  const authored = authoredStages?.[position - 1];
  if (
    authored === "learn" ||
    authored === "recognize" ||
    authored === "build" ||
    authored === "recall" ||
    authored === "challenge"
  ) {
    return authored;
  }
  if (totalActivities <= 1) return "challenge";

  const safePosition = Math.min(
    Math.max(Math.trunc(position), 1),
    totalActivities,
  );
  const index = Math.min(
    PRACTICE_STAGES.length - 1,
    Math.floor(
      ((safePosition - 1) * PRACTICE_STAGES.length) / totalActivities,
    ),
  );
  return PRACTICE_STAGES[index];
}

export function activeLessonStage({
  activities,
  activityPosition,
  dayComplete,
  authoredStages,
}: {
  activities: JourneyActivity[];
  activityPosition?: number | null;
  dayComplete: boolean;
  authoredStages?: string[] | null;
}): LessonStageKey {
  if (dayComplete || (activities.length > 0 && activities.every((item) => item.submitted))) {
    return "complete";
  }

  if (activityPosition) {
    return lessonStageForPosition(activityPosition, activities.length, authoredStages);
  }

  const next = activities.find((item) => !item.submitted);
  if (!next) return activities.length ? "complete" : "learn";
  return lessonStageForPosition(next.position, activities.length, authoredStages);
}

export function lessonStageStatus({
  stage,
  activeStage,
  activities,
  authoredStages,
}: {
  stage: LessonStageKey;
  activeStage: LessonStageKey;
  activities: JourneyActivity[];
  authoredStages?: string[] | null;
}): "done" | "active" | "upcoming" {
  if (stage === "complete") {
    return activeStage === "complete" ? "active" : "upcoming";
  }

  const stageActivities = activities.filter(
    (item) =>
      lessonStageForPosition(item.position, activities.length, authoredStages) ===
      stage,
  );
  if (stageActivities.length > 0 && stageActivities.every((item) => item.submitted)) {
    return "done";
  }
  if (stage === activeStage) return "active";

  const stageIndex = LESSON_STAGE_ORDER.indexOf(stage);
  const activeIndex = LESSON_STAGE_ORDER.indexOf(activeStage);
  return stageIndex < activeIndex ? "done" : "upcoming";
}
