import { describe, expect, it } from "vitest";

import {
  EMPTY_PRACTICE_SET,
  QUICK_SET_SIZE,
  practiceSetAccuracy,
  practiceSetProgress,
  recordPracticeResult,
} from "./practice-session";

describe("silent practice quick sets", () => {
  it("records correct and missed drills independently", () => {
    const afterCorrect = recordPracticeResult(EMPTY_PRACTICE_SET, true);
    const afterMiss = recordPracticeResult(afterCorrect, false);

    expect(afterMiss).toEqual({ completed: 2, correct: 1, missed: 1 });
    expect(practiceSetAccuracy(afterMiss)).toBe(50);
  });

  it("completes at eight drills and clamps visual progress", () => {
    expect(QUICK_SET_SIZE).toBe(8);
    expect(practiceSetProgress({ completed: 7, correct: 6, missed: 1 })).toEqual({
      completed: 7,
      remaining: 1,
      percent: 88,
      complete: false,
    });
    expect(practiceSetProgress({ completed: 9, correct: 8, missed: 1 })).toEqual({
      completed: 8,
      remaining: 0,
      percent: 100,
      complete: true,
    });
  });

  it("reports zero accuracy before the first answer", () => {
    expect(practiceSetAccuracy(EMPTY_PRACTICE_SET)).toBe(0);
  });
});
