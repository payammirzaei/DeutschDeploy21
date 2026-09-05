"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  ExerciseAnswer,
  ExercisePlayer,
  ExercisePrompt,
} from "@/src/components/exercise-player";
import { api } from "@/src/lib/api";
import {
  ATTEMPT_SYNCED_EVENT,
  AttemptSyncDetail,
  learningAttemptUrl,
  submitLearningAttemptSafely,
} from "@/src/lib/offline-attempts";

import styles from "./drills.module.css";

type DrillActivity = {
  id: string;
  source_key: string;
  exercise_type: string;
  category: string;
  contract_version: number;
  prompt_checksum: string;
  prompt: ExercisePrompt;
  attempt_count: number;
};

type DrillNext = {
  activity: DrillActivity;
  available_types: string[];
};

type AttemptResult = {
  correct: boolean;
  score: number;
  feedback_code: string;
};

const typeMeta: Record<string, { label: string; icon: string; note: string }> = {
  interview_best_answer: { label: "Best Answer", icon: "★", note: "Spot the strongest response" },
  hr_answer_order: { label: "HR Builder", icon: "HR", note: "Structure concise answers" },
  star_builder: { label: "STAR", icon: "S→R", note: "Build behavioral stories" },
  technical_explanation_order: { label: "Technical", icon: "</>", note: "Explain reasoning clearly" },
  architecture_sequence: { label: "Architecture", icon: "▦", note: "Sequence system explanations" },
  timed_quick_recall: { label: "Quick Recall", icon: "15s", note: "Recover under pressure" },
};

export default function DrillsPage() {
  const router = useRouter();
  const [activity, setActivity] = useState<DrillActivity | null>(null);
  const [availableTypes, setAvailableTypes] = useState<string[]>([]);
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [queued, setQueued] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionCount, setSessionCount] = useState(0);
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);
  const startedAt = useRef(0);

  const loadNext = useCallback(async () => {
    setLoading(true);
    setError(null);
    setQueued(false);
    const { data, response } = await api.POST("/api/v1/interview-drills/next");
    if (response.status === 401) {
      router.replace("/login");
      return;
    }
    if (!response.ok || !data) {
      setError("Interview Lab could not prepare the next drill.");
      setLoading(false);
      return;
    }
    const next = data as DrillNext;
    setActivity(next.activity);
    setAvailableTypes(next.available_types);
    setResult(null);
    setSecondsLeft(next.activity.prompt.time_limit_seconds ?? null);
    startedAt.current = Date.now();
    setLoading(false);
  }, [router]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadNext(), 0);
    return () => window.clearTimeout(timer);
  }, [loadNext]);

  useEffect(() => {
    if (secondsLeft === null || secondsLeft <= 0 || result) return;
    const timer = window.setInterval(() => {
      setSecondsLeft((current) => (current === null ? null : Math.max(0, current - 1)));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [secondsLeft, result]);

  useEffect(() => {
    if (!activity) return;
    const expectedUrl = learningAttemptUrl(activity.id);
    const onSynced = (event: Event) => {
      const detail = (event as CustomEvent<AttemptSyncDetail<AttemptResult>>).detail;
      if (detail.url !== expectedUrl) return;
      setResult(detail.data);
      setQueued(false);
      setSubmitting(false);
      setError(null);
      setSessionCount((count) => count + 1);
    };
    window.addEventListener(ATTEMPT_SYNCED_EVENT, onSynced);
    return () => window.removeEventListener(ATTEMPT_SYNCED_EVENT, onSynced);
  }, [activity]);

  async function submit(answer: ExerciseAnswer) {
    if (!activity || submitting) return;
    setSubmitting(true);
    setQueued(false);
    setError(null);
    try {
      const durationMs = startedAt.current ? Math.max(0, Date.now() - startedAt.current) : null;
      const submission = await submitLearningAttemptSafely<AttemptResult>(activity.id, {
        ...answer,
        duration_ms: durationMs,
      });
      if (submission.status === "queued") {
        setQueued(true);
        setError("Answer saved on this device. Tap Check again to retry sync.");
        return;
      }
      if (submission.status === "error") {
        setError("Your drill answer was not saved. Try again.");
        return;
      }
      setResult(submission.data);
      setQueued(false);
      setSessionCount((count) => count + 1);
    } catch {
      setError("Your drill answer was not saved. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  const meta = activity ? typeMeta[activity.exercise_type] : null;
  const timeExpired = activity?.exercise_type === "timed_quick_recall" && secondsLeft === 0;

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <Link href="/dashboard" className="brand" aria-label="Back to dashboard">DD<span>21</span></Link>
        <nav>
          <Link href="/practice" className="text-link">Silent Practice</Link>
          <Link href="/review" className="text-link">Review</Link>
        </nav>
      </header>

      <section className={styles.hero}>
        <div>
          <span className="eyebrow">INTERVIEW LAB · SILENT FIRST</span>
          <h1>Train the answer.<br />Not just the vocabulary.</h1>
          <p>
            Build HR, behavioral, technical and architecture responses with short tactile drills.
            Speaking comes later; the interview logic can already become automatic on the bus.
          </p>
        </div>
        <div className={styles.counter}>
          <span>THIS SESSION</span>
          <strong>{sessionCount}</strong>
          <small>interview drills</small>
        </div>
      </section>

      <section className={styles.modeGrid} aria-label="Interview drill mix">
        {(availableTypes.length ? availableTypes : Object.keys(typeMeta)).map((type) => {
          const item = typeMeta[type] ?? { label: type, icon: "•", note: "Interview drill" };
          return (
            <div key={type} className={`${styles.modeCard} ${activity?.exercise_type === type ? styles.active : ""}`}>
              <span>{item.icon}</span>
              <strong>{item.label}</strong>
              <small>{item.note}</small>
            </div>
          );
        })}
      </section>

      {error ? <p className={styles.error} role="alert">{error}</p> : null}

      <section className={styles.workspace}>
        <aside className={styles.sideCard}>
          <span className="card-kicker">WHY THIS MATTERS</span>
          <h2>Interview structure becomes muscle memory.</h2>
          <p>
            Six skill targets are tracked separately: answer quality, HR structure, STAR,
            technical explanation, architecture sequencing and recovery under pressure.
          </p>
          <div className={styles.factRow}>
            <div><strong>18</strong><span>curated drills</span></div>
            <div><strong>6</strong><span>interview skills</span></div>
          </div>
        </aside>

        <div className={styles.stage}>
          {loading ? (
            <article className={styles.loadingCard}>
              <span className="card-kicker">PREPARING DRILL</span>
              <h2>Switching interview skill…</h2>
            </article>
          ) : null}

          {!loading && activity && !result ? (
            <article className={styles.exerciseCard}>
              <div className={styles.exerciseMeta}>
                <span>{meta?.icon ?? "•"}</span>
                <div><strong>{meta?.label ?? activity.exercise_type}</strong><small>{activity.category}</small></div>
                {secondsLeft !== null ? (
                  <code className={timeExpired ? styles.expired : ""}>{secondsLeft}s</code>
                ) : <code>v{activity.contract_version}</code>}
              </div>
              {timeExpired ? <p className={styles.timeNote}>Time is up — answer anyway. The duration is still stored as evidence.</p> : null}
              <ExercisePlayer
                key={activity.id}
                exerciseType={activity.exercise_type}
                prompt={activity.prompt}
                submitting={submitting}
                submitLabel={
                  queued
                    ? "Retry sync"
                    : timeExpired
                      ? "Submit after time"
                      : "Check answer"
                }
                onSubmit={submit}
              />
            </article>
          ) : null}

          {!loading && activity && result ? (
            <article className={`${styles.feedbackCard} ${result.correct ? styles.correct : styles.review}`} aria-live="polite">
              <span className="card-kicker">{result.correct ? "INTERVIEW PATTERN LOCKED" : "TARGETED REVIEW ADDED"}</span>
              <h2>{result.correct ? "Sauber aufgebaut." : "Good. Keep the structure moving."}</h2>
              <p>
                {result.correct
                  ? "This interview skill received positive evidence and can be spaced further out."
                  : "The miss is stored against this interview skill and returns through the same review system."}
              </p>
              <button className="button button-accent" onClick={loadNext}>Next interview drill</button>
            </article>
          ) : null}
        </div>
      </section>
    </main>
  );
}
