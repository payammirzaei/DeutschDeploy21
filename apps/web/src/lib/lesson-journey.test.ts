import { describe, expect, it } from "vitest";

import {
  activeLessonStage,
  lessonStageForPosition,
  lessonStageStatus,
} from "./lesson-journey";

describe("daily lesson journey", () => {
  it("maps a seven-activity day across the five learning stages", () => {
    expect(
      Array.from({ length: 7 }, (_, index) =>
        lessonStageForPosition(index + 1, 7),
      ),
    ).toEqual([
      "learn",
      "learn",
      "recognize",
      "build",
      "build",
      "recall",
      "challenge",
    ]);
  });

  it("maps a five-activity day to a linear journey", () => {
    expect(
      Array.from({ length: 5 }, (_, index) =>
        lessonStageForPosition(index + 1, 5),
      ),
    ).toEqual([
      "learn",
      "recognize",
      "build",
      "recall",
      "challenge",
    ]);
  });

  it("uses the active activity position instead of fake percentage progress", () => {
    const activities = Array.from({ length: 7 }, (_, index) => ({
      position: index + 1,
      submitted: index < 3,
    }));

    expect(
      activeLessonStage({
        activities,
        activityPosition: 4,
        dayComplete: false,
      }),
    ).toBe("build");
  });

  it("marks completed stage activity groups as done", () => {
    const activities = Array.from({ length: 5 }, (_, index) => ({
      position: index + 1,
      submitted: index < 2,
    }));
    const activeStage = activeLessonStage({
      activities,
      activityPosition: 3,
      dayComplete: false,
    });

    expect(
      lessonStageStatus({ stage: "learn", activeStage, activities }),
    ).toBe("done");
    expect(
      lessonStageStatus({ stage: "recognize", activeStage, activities }),
    ).toBe("done");
    expect(
      lessonStageStatus({ stage: "build", activeStage, activities }),
    ).toBe("active");
  });

  it("finishes only when the real day is complete", () => {
    const activities = Array.from({ length: 5 }, (_, index) => ({
      position: index + 1,
      submitted: true,
    }));

    expect(
      activeLessonStage({
        activities,
        activityPosition: null,
        dayComplete: true,
      }),
    ).toBe("complete");
  });

  it("prefers authored stages over position buckets", () => {
    expect(lessonStageForPosition(1, 7, ["learn", "recognize"])).toBe("learn");
    expect(lessonStageForPosition(2, 7, ["learn", "recognize"])).toBe("recognize");
  });

  it("marks authored learn activities done only after those positions are submitted", () => {
    const authored = [
      "learn",
      "learn",
      "recognize",
      "build",
      "build",
      "recall",
      "challenge",
    ];
    const activities = Array.from({ length: 7 }, (_, index) => ({
      position: index + 1,
      submitted: index < 2,
    }));
    expect(
      lessonStageStatus({
        stage: "learn",
        activeStage: "recognize",
        activities,
        authoredStages: authored,
      }),
    ).toBe("done");
  });
});
