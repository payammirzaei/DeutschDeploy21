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
  EMPTY_PRACTICE_SET,
  PracticeSetStats,
  QUICK_SET_SIZE,
  practiceSetAccuracy,
  practiceSetProgress,
  recordPracticeResult,
} from "@/src/lib/practice-session";

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
  strategy: string;
  selection_reason_code: string;
  selection_reason: string;
  interaction_mode: "tap" | "keyboard" | string;
  mastery_state: string;
  confidence: number;
  lapses: number;
  activity: PracticeActivity;
  available_types: string[];
};

type AttemptResult = {
  correct: boolean;
  score: number;
  feedback_code: string;
};

const typeMeta: Record<string, { label: string; icon: string; tapFirst: boolean }> = {
  meaning_multiple_choice: { label: "Meaning", icon: "Aa", tapFirst: true },
  reverse_typing: { label: "Recall", icon: "⌨", tapFirst: false },
  perfect_participle_choice: { label: "Partizip", icon: "II", tapFirst: true },
  auxiliary_choice: { label: "haben / sein", icon: "±", tapFirst: true },
  sentence_order: { label: "Sentence", icon: "↔", tapFirst: true },
  meaning_matching: { label: "Match", icon: "⇄", tapFirst: true },
  example_cloze: { label: "Fill gap", icon: "__", tapFirst: false },
  usage_error_spotting: { label: "Spot error", icon: "!", tapFirst: true },
  perfect_form_typing: { label: "Perfekt", icon: "⌨II", tapFirst: false },
  phrase_builder: { label: "Phrase", icon: "▦", tapFirst: true },
};

const strategyCopy: Record<string, string> = {
  explore_mix: "Building broad evidence across different exercise families.",
  adaptive_weakness: "Choosing from your weaker skills before spending time on stable ones.",
};

export default function PracticePage() {
  const router = useRouter();
  const [activity, setActivity] = useState<PracticeActivity | null>(null);
  const [selection, setSelection] = useState<PracticeNext | null>(null);
  const [availableTypes, setAvailableTypes] = useState<string[]>([]);
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [lastAnswer, setLastAnswer] = useState<ExerciseAnswer | null>(null);
  const [stats, setStats] = useState<PracticeSetStats>(EMPTY_PRACTICE_SET);
  const [setComplete, setSetComplete] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [queued, setQueued] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const startedAt = useRef(0);

  const loadNext = useCallback(async () => {
    setLoading(true);
    setError(null);
    setQueued(false);
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
    setSelection(next);
    setActivity(next.activity);
    setAvailableTypes(next.available_types);
    setResult(null);
    setLastAnswer(null);
    startedAt.current = Date.now();
    setLoading(false);
  }, [router]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadNext();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadNext]);

  const recordResult = useCallback((nextResult: AttemptResult) => {
    setResult(nextResult);
    setStats((current) => recordPracticeResult(current, nextResult.correct));
  }, []);

  useEffect(() => {
    if (!activity) return;
    const expectedUrl = learningAttemptUrl(activity.id);
    const onSynced = (event: Event) => {
      const detail = (event as CustomEvent<AttemptSyncDetail<AttemptResult>>).detail;
      if (detail.url !== expectedUrl) return;
      recordResult(detail.data);
      setQueued(false);
      setSubmitting(false);
      setError(null);
    };
    window.addEventListener(ATTEMPT_SYNCED_EVENT, onSynced);
    return () => window.removeEventListener(ATTEMPT_SYNCED_EVENT, onSynced);
  }, [activity, recordResult]);

  async function submit(answer: ExerciseAnswer) {
    if (!activity || submitting || queued || result) return;
    setLastAnswer(answer);
    setSubmitting(true);
    setError(null);
    const durationMs = startedAt.current
      ? Math.max(0, Date.now() - startedAt.current)
      : null;
    const submission = await submitLearningAttemptSafely<AttemptResult>(activity.id, {
      ...answer,
      duration_ms: durationMs,
    });
    if (submission.status === "queued") {
      setQueued(true);
      setSubmitting(false);
      return;
    }
    if (submission.status === "error") {
      setError("Your answer was not saved. Try once more.");
      setSubmitting(false);
      return;
    }
    recordResult(submission.data);
    setSubmitting(false);
  }

  async function continuePractice() {
    if (practiceSetProgress(stats).complete) {
      setSetComplete(true);
      setActivity(null);
      setResult(null);
      return;
    }
    await loadNext();
  }

  async function startAnotherSet() {
    setStats(EMPTY_PRACTICE_SET);
    setSetComplete(false);
    setResult(null);
    setLastAnswer(null);
    await loadNext();
  }

  const currentMeta = activity ? typeMeta[activity.exercise_type] : null;
  const accuracy = practiceSetAccuracy(stats);
  const setProgress = practiceSetProgress(stats);
  const selectionLead = useMemo(() => {
    if (!selection) return null;
    return selection.selection_reason || strategyCopy[selection.strategy] || null;
  }, [selection]);

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
          <span className="eyebrow">🤫 ADAPTIVE SILENT PRACTICE · QUICK SET</span>
          <h1>Eight drills.<br />Zero awkwardness.</h1>
          <p>
            A short, bus-friendly mix of tap puzzles and recall. The first cycle explores every
            exercise family; after that, weaker skills move to the front automatically.
          </p>
        </div>
        <div className={styles.sessionCard}>
          <div className={styles.sessionTop}>
            <span>QUICK SET</span>
            <strong>{setProgress.completed}<small> / {QUICK_SET_SIZE}</small></strong>
          </div>
          <div
            className={styles.progressTrack}
            aria-label={`${setProgress.completed} of ${QUICK_SET_SIZE} completed`}
          >
            <span style={{ width: `${setProgress.percent}%` }} />
          </div>
          <div className={styles.sessionSplit}>
            <span><b>{stats.correct}</b> correct</span>
            <span><b>{stats.missed}</b> missed</span>
          </div>
        </div>
      </section>

      <section className={styles.modeStrip} aria-label="Silent exercise mix">
        {(availableTypes.length ? availableTypes : Object.keys(typeMeta)).map((type) => {
          const meta = typeMeta[type] ?? { label: type, icon: "•", tapFirst: true };
          const active = activity?.exercise_type === type;
          return (
            <div key={type} className={`${styles.modeChip} ${active ? styles.activeChip : ""}`}>
              <span>{meta.icon}</span>
              <strong>{meta.label}</strong>
              {meta.tapFirst ? <small>TAP</small> : null}
            </div>
          );
        })}
      </section>

      {error ? <p className={styles.error} role="alert">{error}</p> : null}

      <section className={styles.workspace}>
        <aside className={styles.contextPanel}>
          <span className="card-kicker">WHY THIS DRILL?</span>
          {selection && !setComplete ? (
            <>
              <div className={styles.strategyBadge}>
                <strong>{selection.strategy === "adaptive_weakness" ? "ADAPTIVE" : "EXPLORE"}</strong>
                <span>{selection.interaction_mode === "tap" ? "tap-first" : "keyboard recall"}</span>
              </div>
              <h2>{selectionLead ?? "Building useful practice evidence."}</h2>
              <p>
                {strategyCopy[selection.strategy] ?? "The practice engine is balancing variety and mastery evidence."}
              </p>
              <div className={styles.masteryFacts}>
                <div><span>state</span><strong>{selection.mastery_state}</strong></div>
                <div><span>confidence</span><strong>{Math.round(selection.confidence * 100)}%</strong></div>
                <div><span>lapses</span><strong>{selection.lapses}</strong></div>
              </div>
            </>
          ) : (
            <>
              <h2>Short sets beat endless scrolling.</h2>
              <p>
                Finish eight focused drills, read the summary, then decide whether to do another set
                or return to learning and review.
              </p>
            </>
          )}
          <Link href="/review" className="text-link">Open due reviews →</Link>
        </aside>

        <div className={styles.stage}>
          {setComplete ? (
            <article className={styles.summaryCard} aria-live="polite">
              <span className="card-kicker">QUICK SET COMPLETE</span>
              <h2>{stats.missed ? "Good set. Now you know what needs another pass." : "Clean set. Nice retrieval."}</h2>
              <div className={styles.summaryScore}>
                <strong>{accuracy}%</strong>
                <span>accuracy</span>
              </div>
              <div className={styles.summaryGrid}>
                <div><strong>{stats.correct}</strong><span>correct</span></div>
                <div><strong>{stats.missed}</strong><span>missed</span></div>
                <div><strong>{QUICK_SET_SIZE}</strong><span>drills</span></div>
              </div>
              <p>
                {stats.missed
                  ? "Misses are already stored as mastery evidence, so weak skills can return sooner in adaptive practice and review."
                  : "Your successful evidence can widen review intervals while the next set keeps exercise shapes varied."}
              </p>
              <div className={styles.summaryActions}>
                <button className="button button-accent" type="button" onClick={startAnotherSet}>
                  Start another set
                </button>
                <Link href={stats.missed ? "/review" : "/learn"} className="button">
                  {stats.missed ? "Review weak skills" : "Back to learning"}
                </Link>
              </div>
            </article>
          ) : null}

          {!setComplete && loading ? (
            <div className={styles.loadingCard}>
              <span className="card-kicker">BUILDING NEXT DRILL</span>
              <h2>Balancing weakness, variety and tap-first practice…</h2>
            </div>
          ) : null}

          {!setComplete && !loading && activity && !result ? (
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
                <div className={styles.metaBadges}>
                  <span>{selection?.interaction_mode === "tap" ? "TAP" : "RECALL"}</span>
                  <code>v{activity.contract_version}</code>
                </div>
              </div>
              <ExercisePlayer
                key={activity.id}
                exerciseType={activity.exercise_type}
                prompt={activity.prompt}
                submitting={submitting || queued}
                submitLabel={queued ? "Saved offline" : "Check"}
                onSubmit={submit}
              />
            </article>
          ) : null}

          {!setComplete && !loading && activity && result ? (
            <LearningFeedback
              exerciseType={activity.exercise_type}
              prompt={activity.prompt}
              fallbackLemma={activity.prompt.lemma ?? "Practice"}
              answer={lastAnswer}
              correct={result.correct}
              score={result.score}
              feedbackCode={result.feedback_code}
              dayComplete={false}
              nextDay={1}
              availableThroughDay={1}
              continueLabelI18n={setProgress.complete
                ? { en: "Finish quick set", fa: "پایان مجموعه" }
                : { en: "Next drill", fa: "تمرین بعدی" }}
              onContinue={continuePractice}
            />
          ) : null}
        </div>
      </section>
    </main>
  );
}
