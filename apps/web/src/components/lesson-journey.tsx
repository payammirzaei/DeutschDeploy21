import {
  LESSON_STAGE_ORDER,
  JourneyActivity,
  LessonStageKey,
  activeLessonStage,
  lessonStageStatus,
} from "@/src/lib/lesson-journey";

import styles from "./lesson-journey.module.css";

type Props = {
  activities: JourneyActivity[];
  activityPosition?: number | null;
  dayComplete: boolean;
};

const STAGE_COPY: Record<
  LessonStageKey,
  { label: string; short: string }
> = {
  learn: {
    label: "Learn",
    short: "See the pattern in context.",
  },
  recognize: {
    label: "Recognize",
    short: "Spot the right form quickly.",
  },
  build: {
    label: "Build",
    short: "Put useful German together.",
  },
  recall: {
    label: "Recall",
    short: "Retrieve it with less support.",
  },
  challenge: {
    label: "Challenge",
    short: "Use mixed evidence under pressure.",
  },
  complete: {
    label: "Complete",
    short: "Lock in today’s learning evidence.",
  },
};

export function LessonJourney({
  activities,
  activityPosition = null,
  dayComplete,
}: Props) {
  const activeStage = activeLessonStage({
    activities,
    activityPosition,
    dayComplete,
  });
  const submitted = activities.filter((activity) => activity.submitted).length;
  const activeCopy = STAGE_COPY[activeStage];

  return (
    <section className={styles.journey} aria-label="Daily lesson journey">
      <div className={styles.summary}>
        <div>
          <span className={styles.kicker}>TODAY’S FLOW</span>
          <strong>{activeCopy.label}</strong>
          <small>{activeCopy.short}</small>
        </div>
        <span className={styles.counter}>
          {submitted}/{activities.length} activities
        </span>
      </div>

      <ol className={styles.steps}>
        {LESSON_STAGE_ORDER.map((stage, index) => {
          const status = lessonStageStatus({
            stage,
            activeStage,
            activities,
          });
          const copy = STAGE_COPY[stage];
          return (
            <li
              key={stage}
              className={`${styles.step} ${styles[status]}`}
              aria-current={status === "active" ? "step" : undefined}
            >
              <span className={styles.marker} aria-hidden="true">
                {status === "done" ? "✓" : index + 1}
              </span>
              <span className={styles.stepCopy}>
                <strong>{copy.label}</strong>
                <small>{copy.short}</small>
              </span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
