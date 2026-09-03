export const QUICK_SET_SIZE = 8;

export type PracticeSetStats = {
  completed: number;
  correct: number;
  missed: number;
};

export const EMPTY_PRACTICE_SET: PracticeSetStats = {
  completed: 0,
  correct: 0,
  missed: 0,
};

export function recordPracticeResult(
  current: PracticeSetStats,
  correct: boolean,
): PracticeSetStats {
  return {
    completed: current.completed + 1,
    correct: current.correct + (correct ? 1 : 0),
    missed: current.missed + (correct ? 0 : 1),
  };
}

export function practiceSetProgress(stats: PracticeSetStats) {
  const completed = Math.min(QUICK_SET_SIZE, Math.max(0, stats.completed));
  return {
    completed,
    remaining: Math.max(0, QUICK_SET_SIZE - completed),
    percent: Math.round((completed / QUICK_SET_SIZE) * 100),
    complete: completed >= QUICK_SET_SIZE,
  };
}

export function practiceSetAccuracy(stats: PracticeSetStats) {
  if (!stats.completed) return 0;
  return Math.round((stats.correct / stats.completed) * 100);
}
