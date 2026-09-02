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

import styles from "./practice.module.css";

type PracticeActivity = {
  id: string;
  content_version_id: string;
  exercise_type: string;
  contract_version: number;
  prompt_checksum: string;
  prompt: ExercisePrompt;
  attempt_count: number;
};

type PracticeNext = {
  mode: string;
  activity: PracticeActivity;
  available_types: string[];
};

type AttemptResult = {
  correct: boolean;
  score: number;
  feedback_code: string;
};

const typeMeta: Record<string, { label: string; icon: string }> = {
  meaning_multiple_choice: { label: "Meaning", icon: "Aa" },
  reverse_typing: { label: "Type", icon: "⌨" },
  perfect_participle_choice: { label: "Partizip", icon: "II" },
  auxiliary_choice: { label: "haben / sein", icon: "±" },
  sentence_order: { label: "Sentence", icon: "↔" },
  meaning_matching: { label: "Match", icon: "⇄" },
  example_cloze: { label: "Fill gap", icon: "__" },
  usage_error_spotting: { label: "Spot error", icon: "!" },
  perfect_form_typing: { label: "Perfekt type", icon: "⌨II" },
  phrase_builder: { label: "Phrase", icon: "▦" },
};

export default function PracticePage() {
  const router = useRouter();
  const [activity, setActivity] = useState<PracticeActivity | null>(null);
  const [availableTypes, setAvailableTypes] = useState<string[]>([]);
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionCount, setSessionCount] = useState(0);
  const startedAt = useRef(0);

  const loadNext = useCallback(async () => {
    setLoading(true);
    setError(null);
    const { data, response } = await api.POST("/api/v1/practice/silent/next");
    if (response.status === 401) {
      router.replace("/login");
      return;
    }
    if (!response.ok || !data) {
      setError("Silent practice could not be prepared.");
      setLoading(false);
      return;
    }
    const next = data as PracticeNext;
    setActivity(next.activity);
    setAvailableTypes(next.available_types);
    setResult(null);
    startedAt.current = Date.now();
    setLoading(false);
  }, [router]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadNext();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadNext]);

  async function submit(answer: ExerciseAnswer) {
    if (!activity || submitting) return;
    setSubmitting(true);
    setError(null);
    const durationMs = startedAt.current
      ? Math.max(0, Date.now() - startedAt.current)
      : null;
    const { data, response } = await api.POST(
      "/api/v1/learning/instances/{instance_id}/attempts",
      {
        params: {
          path: { instance_id: activity.id },
          header: { "Idempotency-Key": crypto.randomUUID() },
        },
        body: { ...answer, duration_ms: durationMs },
      },
    );
    if (!response.ok || !data) {
      setError("Your answer was not saved. Try once more.");
      setSubmitting(false);
      return;
    }
    setResult(data as AttemptResult);
    setSessionCount((count) => count + 1);
    setSubmitting(false);
  }

  async function continuePractice() {
    await loadNext();
  }

  const currentMeta = activity ? typeMeta[activity.exercise_type] : null;

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <Link href="/dashboard" className="brand" aria-label="Back to dashboard">
          DD<span>21</span>
        </Link>
        <nav>
          <Link href="/learn" className="text-link">Learn</Link>
          <Link href="/review" className="text-link">Review</Link>
        </nav>
      </header>

      <section className={styles.hero}>
        <div>
          <span className="eyebrow">🤫 SILENT MODE · 10 EXERCISE FAMILIES</span>
          <h1>Practice anywhere.<br />No microphone needed.</h1>
          <p>
            Tap, type, match, fill gaps and rebuild interview language on the bus, train or in the
            office while one mastery engine learns what you can actually recall.
          </p>
        </div>
        <div className={styles.sessionCard}>
          <span>THIS SESSION</span>
          <strong>{sessionCount}</strong>
          <small>exercises completed</small>
        </div>
      </section>

      <section className={styles.modeStrip} aria-label="Silent exercise mix">
        {(availableTypes.length ? availableTypes : Object.keys(typeMeta)).map((type) => {
          const meta = typeMeta[type] ?? { label: type, icon: "•" };
          const active = activity?.exercise_type === type;
          return (
            <div key={type} className={`${styles.modeChip} ${active ? styles.activeChip : ""}`}>
              <span>{meta.icon}</span>
              <strong>{meta.label}</strong>
            </div>
          );
        })}
      </section>

      {error ? <p className={styles.error} role="alert">{error}</p> : null}

      <section className={styles.workspace}>
        <aside className={styles.contextPanel}>
          <span className="card-kicker">WHY THIS MODE</span>
          <h2>Repetition without boredom.</h2>
          <p>
            The same interview vocabulary comes back through recognition, active recall, grammar,
            matching, context and sentence construction instead of one repeated card shape.
          </p>
          <div className={styles.contextFacts}>
            <div><strong>10</strong><span>exercise types</span></div>
            <div><strong>30–90s</strong><span>per drill</span></div>
            <div><strong>1</strong><span>mastery graph</span></div>
          </div>
          <Link href="/review" className="text-link">Open due reviews →</Link>
        </aside>

        <div className={styles.stage}>
          {loading ? (
            <div className={styles.loadingCard}>
              <span className="card-kicker">BUILDING NEXT DRILL</span>
              <h2>Picking a different kind of challenge…</h2>
            </div>
          ) : null}

          {!loading && activity && !result ? (
            <article className={styles.exerciseCard}>
              <div className={styles.exerciseMeta}>
                <span>{currentMeta?.icon ?? "•"}</span>
                <div>
                  <strong>{currentMeta?.label ?? activity.exercise_type}</strong>
                  <small>
                    {activity.attempt_count
                      ? `Seen ${activity.attempt_count}× before`
                      : "Fresh variation"}
                  </small>
                </div>
                <code>v{activity.contract_version}</code>
              </div>
              <ExercisePlayer
                key={activity.id}
                exerciseType={activity.exercise_type}
                prompt={activity.prompt}
                submitting={submitting}
                onSubmit={submit}
              />
            </article>
          ) : null}

          {!loading && activity && result ? (
            <article
              className={`${styles.feedbackCard} ${result.correct ? styles.correct : styles.review}`}
              aria-live="polite"
            >
              <span className="card-kicker">
                {result.correct ? "LOCKED IN" : "SCHEDULED FOR REVIEW"}
              </span>
              <h2>{result.correct ? "Sauber." : "Good miss. Keep moving."}</h2>
              <p>
                {result.correct
                  ? "That skill got positive evidence. The scheduler can now widen its interval."
                  : "No retry wall. The miss becomes targeted evidence and comes back at the right time."}
              </p>
              <div className={styles.scoreRow}>
                <strong>{result.score}</strong>
                <span>/ 100</span>
                <code>{result.feedback_code}</code>
              </div>
              <button className="button button-accent" onClick={continuePractice}>
                Next drill
              </button>
            </article>
          ) : null}
        </div>
      </section>
    </main>
  );
}
