export type ReviewQueueItemLike = {
  target_id: string;
  lemma: string;
  due_at: string;
  overdue: boolean;
  priority: number;
  reason_code: string;
  state: string;
};

export type MasteryTargetLike = {
  target_id: string;
  lemma: string;
  skill_dimension: string;
  state: string;
  confidence: number;
  success_streak: number;
  lapses: number;
  evidence_count: number;
  next_review_at: string;
};

export type ReviewUrgency = "critical" | "high" | "due";

const STATE_RANK: Record<string, number> = {
  review: 0,
  learning: 1,
  stable: 2,
  mastered: 3,
};

export function reviewUrgency(
  item: ReviewQueueItemLike,
  nowMs = Date.now(),
): ReviewUrgency {
  const overdueMs = Math.max(0, nowMs - new Date(item.due_at).getTime());
  if (item.priority >= 90 || overdueMs >= 24 * 60 * 60 * 1000) {
    return "critical";
  }
  if (item.overdue || item.priority >= 70) return "high";
  return "due";
}

export function sortDueQueue(
  items: ReviewQueueItemLike[],
  nowMs = Date.now(),
) {
  return [...items].sort((a, b) => {
    const urgencyRank = { critical: 0, high: 1, due: 2 } as const;
    const urgencyDelta =
      urgencyRank[reviewUrgency(a, nowMs)] -
      urgencyRank[reviewUrgency(b, nowMs)];
    if (urgencyDelta) return urgencyDelta;
    if (a.priority !== b.priority) return b.priority - a.priority;
    return new Date(a.due_at).getTime() - new Date(b.due_at).getTime();
  });
}

export function sortMasteryTargets<T extends MasteryTargetLike>(items: T[]) {
  return [...items].sort((a, b) => {
    const stateDelta =
      (STATE_RANK[a.state] ?? 4) - (STATE_RANK[b.state] ?? 4);
    if (stateDelta) return stateDelta;
    if (a.lapses !== b.lapses) return b.lapses - a.lapses;
    if (a.confidence !== b.confidence) return a.confidence - b.confidence;
    return a.lemma.localeCompare(b.lemma, "de");
  });
}

export function reviewSessionProgress(initialDue: number, currentDue: number) {
  const safeInitial = Math.max(0, initialDue);
  const remaining = Math.max(0, Math.min(currentDue, safeInitial));
  const completed = Math.max(0, safeInitial - remaining);
  const percent = safeInitial
    ? Math.round((completed / safeInitial) * 100)
    : 100;
  return { completed, remaining, percent };
}

export function relativeDueLabel(iso: string, nowMs = Date.now()) {
  const deltaMs = new Date(iso).getTime() - nowMs;
  const absoluteMs = Math.abs(deltaMs);
  const minute = 60 * 1000;
  const hour = 60 * minute;
  const day = 24 * hour;

  if (absoluteMs < minute) return "due now";
  if (deltaMs < 0) {
    if (absoluteMs < hour) return `${Math.max(1, Math.round(absoluteMs / minute))}m overdue`;
    if (absoluteMs < day) return `${Math.max(1, Math.round(absoluteMs / hour))}h overdue`;
    return `${Math.max(1, Math.round(absoluteMs / day))}d overdue`;
  }
  if (deltaMs < hour) return `in ${Math.max(1, Math.round(deltaMs / minute))}m`;
  if (deltaMs < day) return `in ${Math.max(1, Math.round(deltaMs / hour))}h`;
  if (deltaMs < 2 * day) return "tomorrow";
  return `in ${Math.max(2, Math.round(deltaMs / day))}d`;
}
