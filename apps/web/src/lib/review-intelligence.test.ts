import { describe, expect, it } from "vitest";

import {
  relativeDueLabel,
  reviewSessionProgress,
  reviewUrgency,
  sortDueQueue,
  sortMasteryTargets,
} from "./review-intelligence";

const NOW = Date.parse("2026-09-03T12:00:00Z");

describe("smart review presentation logic", () => {
  it("prioritizes recent failures and heavily overdue reviews", () => {
    const critical = {
      target_id: "a",
      lemma: "testen",
      due_at: "2026-09-03T11:50:00Z",
      overdue: true,
      priority: 100,
      reason_code: "recent_failure",
      state: "review",
    };
    const normal = {
      target_id: "b",
      lemma: "lernen",
      due_at: "2026-09-03T11:00:00Z",
      overdue: true,
      priority: 50,
      reason_code: "building_recall",
      state: "review",
    };

    expect(reviewUrgency(critical, NOW)).toBe("critical");
    expect(reviewUrgency(normal, NOW)).toBe("high");
    expect(sortDueQueue([normal, critical], NOW)[0].target_id).toBe("a");
  });

  it("surfaces weak mastery before stable targets", () => {
    const sorted = sortMasteryTargets([
      {
        target_id: "stable",
        lemma: "bauen",
        skill_dimension: "sentence_structure",
        state: "stable",
        confidence: 0.8,
        success_streak: 4,
        lapses: 0,
        evidence_count: 5,
        next_review_at: "2026-09-10T12:00:00Z",
      },
      {
        target_id: "weak",
        lemma: "sprechen",
        skill_dimension: "lexical_recall",
        state: "review",
        confidence: 0.4,
        success_streak: 0,
        lapses: 2,
        evidence_count: 3,
        next_review_at: "2026-09-03T12:10:00Z",
      },
    ]);

    expect(sorted.map((item) => item.target_id)).toEqual(["weak", "stable"]);
  });

  it("computes queue progress without exceeding the session start", () => {
    expect(reviewSessionProgress(8, 5)).toEqual({
      completed: 3,
      remaining: 5,
      percent: 38,
    });
    expect(reviewSessionProgress(0, 0).percent).toBe(100);
  });

  it("formats review timing for a human queue", () => {
    expect(relativeDueLabel("2026-09-03T12:00:20Z", NOW)).toBe("due now");
    expect(relativeDueLabel("2026-09-03T13:30:00Z", NOW)).toBe("in 2h");
    expect(relativeDueLabel("2026-09-04T13:00:00Z", NOW)).toBe("tomorrow");
    expect(relativeDueLabel("2026-09-03T10:00:00Z", NOW)).toBe("2h overdue");
  });
});
