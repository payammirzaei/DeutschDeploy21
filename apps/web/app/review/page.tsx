"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  ExerciseAnswer,
  ExercisePlayer,
  ExercisePrompt,
} from "@/src/components/exercise-player";
import { LearningFeedback } from "@/src/components/learning-feedback";
import { api } from "@/src/lib/api";
import {
  ATTEMPT_SYNCED_EVENT,
  AttemptSyncDetail,
  learningAttemptUrl,
  submitLearningAttemptSafely,
} from "@/src/lib/offline-attempts";
import {
  relativeDueLabel,
  reviewSessionProgress,
  reviewUrgency,
  sortDueQueue,
  sortMasteryTargets,
} from "@/src/lib/review-intelligence";

import styles from "./review.module.css";

type MasteryTarget = {
  target_id: string;
  target_kind: string;
  content_version_id: string | null;
  lemma: string;
  skill_dimension: string;
  state: string;
  stability: number;
  difficulty: number;
  confidence: number;
  success_streak: number;
  lapses: number;
  evidence_count: number;
  next_review_at: string;
  explanation_code: string;
};

type ReviewQueueItem = {
  target_id: string;
  target_kind: string;
  activity_instance_id: string;
  content_version_id: string | null;
  lemma: string;
  due_at: string;
  overdue: boolean;
  priority: number;
  reason_code: string;
  state: string;
};

type ReviewHome = {
  due_count: number;
  scheduled_count: number;
  weak_count: number;
  mastered_count: number;
  next_due_at: string | null;
  due: ReviewQueueItem[];
  mastery: MasteryTarget[];
};

type ReviewActivity = {
  target_id: string;
  target_kind: string;
  activity_instance_id: string;
  content_version_id: string | null;
  exercise_type: string;
  contract_version: number;
  prompt_checksum: string;
  prompt: ExercisePrompt;
  lemma: string;
  question: string;
  reason_code: string;
  due_at: string;
  state: string;
};

type AttemptResult = {
  attempt_id: string;
  evaluation_id: string;
  correct: boolean;
  score: number;
  feedback_code: string;
};

type MasteryFilter = "weak" | "all" | "mastered";

const reasonCopy: Record<string, { title: string; body: string }> = {
  recent_failure: {
    title: "Fresh miss",
    body: "You missed this recently, so the scheduler shortened the interval and moved it to the front.",
  },
  first_success: {
    title: "Check the first memory",
    body: "One correct answer is not mastery yet. This review checks whether the pattern survived the first gap.",
  },
  building_recall: {
    title: "Build the interval",
    body: "Recall is improving. Another clean retrieval lets the scheduler expand the gap again.",
  },
  stable_recall: {
    title: "Maintenance check",
    body: "This target looks stable. A quick retrieval protects it from fading without over-practicing it.",
  },
  mastery_maintenance: {
    title: "Long-term maintenance",
    body: "This is already strong. It only comes back occasionally to keep the memory durable.",
  },
};

const urgencyCopy = {
  critical: "Fix now",
  high: "High priority",
  due: "Due review",
} as const;

export default function ReviewPage() {
  const router = useRouter();
  const [home, setHome] = useState<ReviewHome | null>(null);
  const [activity, setActivity] = useState<ReviewActivity | null>(null);
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [lastAnswer, setLastAnswer] = useState<ExerciseAnswer | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [queued, setQueued] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionStartDue, setSessionStartDue] = useState<number | null>(null);
  const [sessionCorrect, setSessionCorrect] = useState(0);
  const [sessionMissed, setSessionMissed] = useState(0);
  const [masteryFilter, setMasteryFilter] = useState<MasteryFilter>("weak");
  const startedAt = useRef<number | null>(null);
  const recordedEvaluations = useRef(new Set<string>());

  const loadHome = useCallback(async () => {
    const { data, response } = await api.GET("/api/v1/review/home");
    if (response.status === 401) {
      router.replace("/login");
      return null;
    }
    if (!response.ok || !data) {
      setError("Review data could not be loaded.");
      return null;
    }
    const next = data as ReviewHome;
    setHome(next);
    setError(null);
    return next;
  }, [router]);

  const loadNext = useCallback(async () => {
    const { data, response } = await api.POST("/api/v1/review/next");
    if (response.status === 401) {
      router.replace("/login");
      return;
    }
    if (!response.ok || !data) {
      setError("The next review could not be prepared.");
      return;
    }
    const body = data as {
      completed: boolean;
      activity: ReviewActivity | null;
    };
    setActivity(body.activity);
    setResult(null);
    setLastAnswer(null);
    setQueued(false);
    startedAt.current = body.activity ? Date.now() : null;
  }, [router]);

  const recordResult = useCallback((next: AttemptResult) => {
    if (!recordedEvaluations.current.has(next.evaluation_id)) {
      recordedEvaluations.current.add(next.evaluation_id);
      if (next.correct) setSessionCorrect((value) => value + 1);
      else setSessionMissed((value) => value + 1);
    }
    setResult(next);
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const nextHome = await loadHome();
      if (cancelled) return;
      setSessionStartDue(nextHome?.due_count ?? 0);
      if (nextHome?.due_count) await loadNext();
      if (!cancelled) setLoading(false);
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [loadHome, loadNext]);

  useEffect(() => {
    if (!activity) return;
    const expectedUrl = learningAttemptUrl(activity.activity_instance_id);
    const onSynced = (event: Event) => {
      const detail = (event as CustomEvent<AttemptSyncDetail<AttemptResult>>).detail;
      if (detail.url !== expectedUrl) return;
      recordResult(detail.data);
      setQueued(false);
      setSubmitting(false);
      setError(null);
      void loadHome();
    };
    window.addEventListener(ATTEMPT_SYNCED_EVENT, onSynced);
    return () => window.removeEventListener(ATTEMPT_SYNCED_EVENT, onSynced);
  }, [activity, loadHome, recordResult]);

  const sortedDue = useMemo(() => sortDueQueue(home?.due ?? []), [home]);
  const sortedMastery = useMemo(
    () => sortMasteryTargets(home?.mastery ?? []),
    [home],
  );
  const visibleMastery = useMemo(() => {
    if (masteryFilter === "weak") {
      return sortedMastery.filter((target) =>
        ["review", "learning"].includes(target.state),
      );
    }
    if (masteryFilter === "mastered") {
      return sortedMastery.filter((target) => target.state === "mastered");
    }
    return sortedMastery;
  }, [masteryFilter, sortedMastery]);
  const sessionProgress = reviewSessionProgress(
    sessionStartDue ?? home?.due_count ?? 0,
    home?.due_count ?? 0,
  );
  const activeReason = activity
    ? reasonCopy[activity.reason_code] ?? {
        title: "Scheduled review",
        body: "This target is due from your learning evidence and current memory interval.",
      }
    : null;

  async function submit(answer: ExerciseAnswer) {
    if (!activity || submitting) return;
    setSubmitting(true);
    setQueued(false);
    setLastAnswer(answer);
    setError(null);
    try {
      const duration = startedAt.current === null
        ? 0
        : Math.max(0, Date.now() - startedAt.current);
      const submission = await submitLearningAttemptSafely<AttemptResult>(
        activity.activity_instance_id,
        { ...answer, duration_ms: duration },
      );
      if (submission.status === "queued") {
        setQueued(true);
        setError(
          "Answer saved on this device. Tap Check again to retry sync.",
        );
        return;
      }
      if (submission.status === "error") {
        setError("Your review answer was not saved. Please try again.");
        return;
      }
      recordResult(submission.data);
      setQueued(false);
      void loadHome();
    } catch {
      setError("Your review answer was not saved. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  async function continueReview() {
    if (submitting) return;
    setSubmitting(true);
    await loadNext();
    await loadHome();
    setSubmitting(false);
  }

  if (loading) {
    return (
      <main className={styles.shell}>
        <p className={styles.loading}>Building your smart review queue…</p>
      </main>
    );
  }

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <Link href="/dashboard" className="brand">
          DD<span>21</span>
        </Link>
        <nav>
          <Link href="/practice" className="text-link">Silent practice</Link>
          <Link href="/learn" className="text-link">Learn</Link>
        </nav>
      </header>

      <section className={styles.hero}>
        <div>
          <span className="eyebrow">SMART REVIEW · SPACED PRACTICE</span>
          <h1>Practice what<br />is about to fade.</h1>
          <p>
            Weak targets return sooner. Stable targets wait longer. Every card has a reason,
            a due time, and evidence from your own answers.
          </p>
        </div>
        <div className={styles.stats}>
          <div><strong>{home?.due_count ?? 0}</strong><span>due now</span></div>
          <div><strong>{home?.weak_count ?? 0}</strong><span>weak targets</span></div>
          <div><strong>{home?.mastered_count ?? 0}</strong><span>mastered</span></div>
        </div>
      </section>

      {error ? <p className={styles.error} role="alert">{error}</p> : null}

      <section className={styles.sessionBar} aria-label="Review session progress">
        <div>
          <span>THIS SESSION</span>
          <strong>{sessionProgress.completed} reviewed</strong>
          <small>{sessionCorrect} correct · {sessionMissed} missed</small>
        </div>
        <div className={styles.sessionTrack} aria-hidden="true">
          <div style={{ width: `${sessionProgress.percent}%` }} />
        </div>
        <span>{sessionProgress.percent}%</span>
      </section>

      <section className={styles.workspace}>
        <div className={styles.reviewStage}>
          {sortedDue.length ? (
            <section className={styles.queuePreview} aria-label="Due review queue">
              <div className={styles.sectionTitle}>
                <div>
                  <span className="card-kicker">DUE QUEUE</span>
                  <strong>{sortedDue.length} waiting</strong>
                </div>
                <small>Failures and overdue items rise to the front.</small>
              </div>
              <div className={styles.queueList}>
                {sortedDue.slice(0, 5).map((item, index) => {
                  const urgency = reviewUrgency(item);
                  const isActive = item.target_id === activity?.target_id;
                  return (
                    <article
                      key={item.target_id}
                      className={`${styles.queueItem} ${isActive ? styles.queueActive : ""}`}
                    >
                      <span className={styles.queueIndex}>{String(index + 1).padStart(2, "0")}</span>
                      <div>
                        <strong>{item.lemma}</strong>
                        <small>{reasonCopy[item.reason_code]?.title ?? "Scheduled review"}</small>
                      </div>
                      <div className={styles.queueMeta}>
                        <span className={styles[urgency]}>{urgencyCopy[urgency]}</span>
                        <small>{relativeDueLabel(item.due_at)}</small>
                      </div>
                    </article>
                  );
                })}
              </div>
            </section>
          ) : null}

          {activity && !result ? (
            <article className={styles.exercise}>
              <div className={styles.exerciseMeta}>
                <span>{activity.state.toUpperCase()}</span>
                <code>{activity.lemma}</code>
              </div>
              {activeReason ? (
                <div className={styles.whyCard}>
                  <span>WHY NOW?</span>
                  <strong>{activeReason.title}</strong>
                  <p>{activeReason.body}</p>
                  <small>{relativeDueLabel(activity.due_at)}</small>
                </div>
              ) : null}
              <ExercisePlayer
                key={activity.activity_instance_id}
                exerciseType={activity.exercise_type}
                prompt={activity.prompt}
                submitting={submitting}
                submitLabel={queued ? "Retry sync" : "Check review"}
                onSubmit={submit}
              />
            </article>
          ) : null}

          {activity && result ? (
            <LearningFeedback
              exerciseType={activity.exercise_type}
              prompt={activity.prompt}
              fallbackLemma={activity.lemma}
              answer={lastAnswer}
              correct={result.correct}
              score={result.score}
              feedbackCode={result.feedback_code}
              dayComplete={false}
              nextDay={0}
              availableThroughDay={21}
              continueLabelI18n={{ en: "Next review", fa: "مرور بعدی" }}
              onContinue={continueReview}
            />
          ) : null}

          {!activity ? (
            <article className={styles.clear}>
              <span className="card-kicker">
                {sessionStartDue ? "SESSION CLEAR" : "QUEUE CLEAR"}
              </span>
              <h2>
                {sessionStartDue
                  ? "You cleared what was due."
                  : "Nothing needs review right now."}
              </h2>
              <p>
                {home?.next_due_at
                  ? `Next memory check is ${relativeDueLabel(home.next_due_at)}. The scheduler will wait instead of making you over-practice stable material.`
                  : "Complete learning activities and the scheduler will build your queue automatically."}
              </p>
              {sessionStartDue ? (
                <div className={styles.sessionSummary}>
                  <div><strong>{sessionCorrect}</strong><span>correct</span></div>
                  <div><strong>{sessionMissed}</strong><span>missed</span></div>
                  <div><strong>{sessionProgress.completed}</strong><span>reviewed</span></div>
                </div>
              ) : null}
              <div className={styles.clearActions}>
                <Link href="/learn" className="button button-accent">Continue learning</Link>
                <Link href="/practice" className="button">Free silent practice</Link>
              </div>
            </article>
          ) : null}
        </div>

        <aside className={styles.masteryPanel}>
          <div className={styles.panelTitle}>
            <div>
              <span className="card-kicker">MASTERY MAP</span>
              <strong>{home?.scheduled_count ?? 0} tracked targets</strong>
            </div>
            <div className={styles.filters} role="group" aria-label="Filter mastery targets">
              {(["weak", "all", "mastered"] as MasteryFilter[]).map((filter) => (
                <button
                  key={filter}
                  type="button"
                  className={masteryFilter === filter ? styles.filterActive : ""}
                  aria-pressed={masteryFilter === filter}
                  onClick={() => setMasteryFilter(filter)}
                >
                  {filter}
                </button>
              ))}
            </div>
          </div>
          <div className={styles.masteryList}>
            {visibleMastery.slice(0, 28).map((target) => (
              <article key={target.target_id} className={styles.masteryRow}>
                <div className={styles.masteryMain}>
                  <div>
                    <strong>{target.lemma}</strong>
                    <span>{target.skill_dimension.replaceAll("_", " ")}</span>
                  </div>
                  <span className={`${styles.statePill} ${styles[target.state] ?? ""}`}>
                    {target.state}
                  </span>
                </div>
                <div className={styles.confidenceTrack} aria-hidden="true">
                  <div style={{ width: `${Math.round(target.confidence * 100)}%` }} />
                </div>
                <div className={styles.masteryNumbers}>
                  <small>{Math.round(target.confidence * 100)}% confidence</small>
                  <small>{target.success_streak} streak · {target.lapses} lapses</small>
                  <small>{relativeDueLabel(target.next_review_at)}</small>
                </div>
              </article>
            ))}
            {!visibleMastery.length ? (
              <p className={styles.emptyMastery}>
                No targets match this filter yet.
              </p>
            ) : null}
          </div>
        </aside>
      </section>
    </main>
  );
}
