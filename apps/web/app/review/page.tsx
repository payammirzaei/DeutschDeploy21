"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api } from "@/src/lib/api";

import styles from "./review.module.css";

type Choice = { id: string; text: string };
type MasteryTarget = {
  target_id: string;
  content_version_id: string;
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
type ReviewHome = {
  due_count: number;
  scheduled_count: number;
  weak_count: number;
  mastered_count: number;
  next_due_at: string | null;
  mastery: MasteryTarget[];
};
type ReviewActivity = {
  target_id: string;
  activity_instance_id: string;
  content_version_id: string;
  lemma: string;
  question: string;
  choices: Choice[];
  reason_code: string;
  due_at: string;
  state: string;
};
type AttemptResult = {
  correct: boolean;
  score: number;
  feedback_code: string;
};

const reasonCopy: Record<string, string> = {
  recent_failure: "You missed this recently, so it gets priority.",
  first_success: "First success. We will check whether it sticks.",
  building_recall: "Recall is improving; the interval is expanding.",
  stable_recall: "This looks stable, but still needs maintenance.",
  mastery_maintenance: "Long-term maintenance review.",
};

const stateRank: Record<string, number> = {
  review: 0,
  learning: 1,
  stable: 2,
  mastered: 3,
};

export default function ReviewPage() {
  const router = useRouter();
  const [home, setHome] = useState<ReviewHome | null>(null);
  const [activity, setActivity] = useState<ReviewActivity | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const startedAt = useRef<number>(Date.now());

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
    const body = data as { completed: boolean; activity: ReviewActivity | null };
    setActivity(body.activity);
    setSelected(null);
    setResult(null);
    startedAt.current = Date.now();
  }, [router]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const nextHome = await loadHome();
      if (cancelled) return;
      if (nextHome?.due_count) await loadNext();
      if (!cancelled) setLoading(false);
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [loadHome, loadNext]);

  const sortedMastery = useMemo(
    () =>
      [...(home?.mastery ?? [])].sort(
        (a, b) =>
          (stateRank[a.state] ?? 4) - (stateRank[b.state] ?? 4) ||
          a.lemma.localeCompare(b.lemma, "de"),
      ),
    [home],
  );

  async function submit() {
    if (!activity || !selected || submitting) return;
    setSubmitting(true);
    setError(null);
    const duration = Math.max(0, Date.now() - startedAt.current);
    const { data, response } = await api.POST(
      "/api/v1/learning/instances/{instance_id}/attempts",
      {
        params: {
          path: { instance_id: activity.activity_instance_id },
          header: { "Idempotency-Key": crypto.randomUUID() },
        },
        body: { choice_id: selected, duration_ms: duration },
      },
    );
    if (!response.ok || !data) {
      setError("Your review answer was not saved. Please try again.");
      setSubmitting(false);
      return;
    }
    setResult(data as AttemptResult);
    await loadHome();
    setSubmitting(false);
  }

  async function continueReview() {
    setSubmitting(true);
    await loadNext();
    await loadHome();
    setSubmitting(false);
  }

  if (loading) {
    return (
      <main className={styles.shell}>
        <p className={styles.loading}>Building your review queue…</p>
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
          <Link href="/learn" className="text-link">Learn</Link>
          <Link href="/catalog" className="text-link">Catalog</Link>
        </nav>
      </header>

      <section className={styles.hero}>
        <div>
          <span className="eyebrow">PHASE 4 · MASTERY & SPACED REVIEW</span>
          <h1>Remember it<br />when it matters.</h1>
          <p>
            Completion gets you forward. Mastery decides what comes back. Every review has a due
            time, a reason, and a durable evidence trail.
          </p>
        </div>
        <div className={styles.stats}>
          <div><strong>{home?.due_count ?? 0}</strong><span>due now</span></div>
          <div><strong>{home?.weak_count ?? 0}</strong><span>learning / review</span></div>
          <div><strong>{home?.mastered_count ?? 0}</strong><span>mastered</span></div>
        </div>
      </section>

      {error ? <p className={styles.error}>{error}</p> : null}

      <section className={styles.workspace}>
        <div className={styles.reviewStage}>
          {activity && !result ? (
            <article className={styles.exercise}>
              <div className={styles.exerciseMeta}>
                <span>{activity.state.toUpperCase()}</span>
                <code>{activity.reason_code}</code>
              </div>
              <p className={styles.reason}>
                {reasonCopy[activity.reason_code] ?? "Scheduled from your learning evidence."}
              </p>
              <h2>{activity.question}</h2>
              <div className={styles.choices}>
                {activity.choices.map((choice, index) => (
                  <button
                    key={choice.id}
                    className={`${styles.choice} ${selected === choice.id ? styles.selected : ""}`}
                    onClick={() => setSelected(choice.id)}
                    type="button"
                  >
                    <span>{String.fromCharCode(65 + index)}</span>
                    <strong dir="rtl">{choice.text}</strong>
                  </button>
                ))}
              </div>
              <button
                className="button button-accent"
                disabled={!selected || submitting}
                onClick={submit}
              >
                {submitting ? "Saving…" : "Check review"}
              </button>
            </article>
          ) : null}

          {activity && result ? (
            <article className={`${styles.feedback} ${result.correct ? styles.correct : styles.wrong}`}>
              <span className="card-kicker">EVIDENCE RECORDED</span>
              <h2>{result.correct ? "Still there." : "Bring this one back sooner."}</h2>
              <p>
                {result.correct
                  ? "The scheduler expanded this target’s interval based on another independent success."
                  : "This target stays in review with a shorter interval and higher priority."}
              </p>
              <div className={styles.score}><strong>{result.score}</strong><span>/ 100</span></div>
              <button
                className="button button-accent"
                onClick={continueReview}
                disabled={submitting}
              >
                {submitting ? "Loading…" : "Next review"}
              </button>
            </article>
          ) : null}

          {!activity ? (
            <article className={styles.clear}>
              <span className="card-kicker">QUEUE CLEAR</span>
              <h2>Nothing is due right now.</h2>
              <p>
                {home?.next_due_at
                  ? `Next scheduled review: ${new Date(home.next_due_at).toLocaleString()}`
                  : "Complete learning activities and the scheduler will build your queue automatically."}
              </p>
              <Link href="/learn" className="button button-accent">Continue learning</Link>
            </article>
          ) : null}
        </div>

        <aside className={styles.masteryPanel}>
          <div className={styles.panelTitle}>
            <span className="card-kicker">MASTERY MAP</span>
            <strong>{home?.scheduled_count ?? 0} tracked</strong>
          </div>
          <div className={styles.masteryList}>
            {sortedMastery.slice(0, 24).map((target) => (
              <article key={target.target_id} className={styles.masteryRow}>
                <div>
                  <strong>{target.lemma}</strong>
                  <span>{target.explanation_code.replaceAll("_", " ")}</span>
                </div>
                <div className={styles.masteryNumbers}>
                  <span>{target.state}</span>
                  <small>{Math.round(target.confidence * 100)}% evidence confidence</small>
                </div>
              </article>
            ))}
            {!sortedMastery.length ? (
              <p className={styles.emptyMastery}>
                Your first submitted answer will create the first mastery target.
              </p>
            ) : null}
          </div>
        </aside>
      </section>
    </main>
  );
}
