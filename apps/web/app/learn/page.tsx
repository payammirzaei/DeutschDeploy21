"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

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

import styles from "./learn.module.css";

type Activity = {
  id: string;
  day_number: number;
  position: number;
  source_kind: string;
  source_key: string;
  content_version_id: string | null;
  exercise_type: string;
  contract_version: number;
  prompt_checksum: string;
  lemma: string;
  question: string;
  prompt: ExercisePrompt;
};

type ActivitySummary = {
  activity_id: string;
  position: number;
  source_kind: string;
  source_key: string;
  content_version_id: string | null;
  exercise_type: string;
  submitted: boolean;
};

type Day = {
  day_number: number;
  title: string;
  objective: string;
  completed: boolean;
  submitted_count: number;
  total_count: number;
  activities: ActivitySummary[];
};

type LearningHome = {
  enrolled: boolean;
  enrollment_id: string | null;
  course_title: string | null;
  release_version: number | null;
  latest_release_version: number;
  upgrade_available: boolean;
  current_day: number;
  available_through_day: number;
  course_complete: boolean;
  days: Day[];
};

type AttemptResult = {
  attempt_id: string;
  evaluation_id: string;
  correct: boolean;
  score: number;
  feedback_code: string;
  day_complete: boolean;
  next_day: number;
};

const EMPTY_HOME: LearningHome = {
  enrolled: false,
  enrollment_id: null,
  course_title: null,
  release_version: null,
  latest_release_version: 3,
  upgrade_available: false,
  current_day: 1,
  available_through_day: 21,
  course_complete: false,
  days: [],
};

export default function LearnPage() {
  const router = useRouter();
  const [home, setHome] = useState<LearningHome>(EMPTY_HOME);
  const [activeDay, setActiveDay] = useState(1);
  const [activity, setActivity] = useState<Activity | null>(null);
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [lastAnswer, setLastAnswer] = useState<ExerciseAnswer | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [upgrading, setUpgrading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [queued, setQueued] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);

  async function loadHome() {
    const { data, response } = await api.GET("/api/v1/learning/home");
    if (response.status === 401) {
      router.replace("/login");
      return null;
    }
    if (!response.ok) {
      setError("Your learning plan could not be loaded.");
      return null;
    }
    const nextHome = (data ?? EMPTY_HOME) as LearningHome;
    setHome(nextHome);
    setActiveDay((current) => {
      if (
        nextHome.days.some(
          (day) => day.day_number === current && !day.completed,
        )
      ) {
        return current;
      }
      if (nextHome.course_complete) {
        return nextHome.available_through_day;
      }
      return Math.min(
        nextHome.current_day,
        nextHome.available_through_day,
      );
    });
    setError(null);
    return nextHome;
  }

  useEffect(() => {
    let cancelled = false;

    api.GET("/api/v1/learning/home").then(({ data, response }) => {
      if (cancelled) return;
      if (response.status === 401) {
        router.replace("/login");
        return;
      }
      if (!response.ok) {
        setError("Your learning plan could not be loaded.");
      } else {
        const nextHome = (data ?? EMPTY_HOME) as LearningHome;
        setHome(nextHome);
        setActiveDay(
          nextHome.course_complete
            ? nextHome.available_through_day
            : Math.min(
                nextHome.current_day,
                nextHome.available_through_day,
              ),
        );
      }
      setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [router]);

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
    };
    window.addEventListener(ATTEMPT_SYNCED_EVENT, onSynced);
    return () => window.removeEventListener(ATTEMPT_SYNCED_EVENT, onSynced);
  }, [activity]);

  const currentDay = useMemo(
    () =>
      home.days.find((day) => day.day_number === activeDay) ?? null,
    [activeDay, home.days],
  );

  const totalSubmitted = home.days.reduce(
    (sum, day) => sum + day.submitted_count,
    0,
  );
  const totalActivities = home.days.reduce(
    (sum, day) => sum + day.total_count,
    0,
  );
  const overallProgress = totalActivities
    ? Math.round((totalSubmitted / totalActivities) * 100)
    : 0;

  async function initializeLearning() {
    setStarting(true);
    setError(null);

    const catalog = await api.POST("/api/v1/content/starter-catalog");
    if (!catalog.response.ok) {
      setError("The starter catalog could not be prepared.");
      setStarting(false);
      return;
    }

    const started = await api.POST("/api/v1/learning/start");
    if (!started.response.ok) {
      setError("The 21-day learning release could not be created.");
      setStarting(false);
      return;
    }

    const nextHome = await loadHome();
    if (nextHome) {
      setActiveDay(nextHome.current_day);
    }
    setStarting(false);
  }

  async function upgradeLearning() {
    if (upgrading) return;
    setUpgrading(true);
    setError(null);
    setActivity(null);
    setResult(null);
    setLastAnswer(null);
    setQueued(false);

    const { data, response } = await api.POST(
      "/api/v1/learning/upgrade",
    );
    if (!response.ok || !data) {
      setError(
        "Your existing release was not changed. The upgrade could not be completed.",
      );
      setUpgrading(false);
      return;
    }

    const nextHome = await loadHome();
    if (nextHome) {
      setActiveDay(
        Math.min(nextHome.current_day, nextHome.available_through_day),
      );
    }
    setUpgrading(false);
  }

  async function openNextActivity(dayNumber: number) {
    setActiveDay(dayNumber);
    setActivity(null);
    setResult(null);
    setLastAnswer(null);
    setQueued(false);
    setError(null);

    const { data, response } = await api.POST(
      "/api/v1/learning/days/{day_number}/next",
      {
        params: { path: { day_number: dayNumber } },
      },
    );
    if (!response.ok) {
      setError("The next activity could not be prepared.");
      return;
    }

    const next = data as {
      completed: boolean;
      activity: Activity | null;
    };
    if (next.completed || !next.activity) {
      await loadHome();
      return;
    }

    setActivity(next.activity);
    setStartedAt(Date.now());
  }

  async function submitAnswer(answer: ExerciseAnswer) {
    if (!activity || submitting || queued) return;
    setSubmitting(true);
    setLastAnswer(answer);
    setError(null);

    const durationMs = startedAt
      ? Math.max(0, Date.now() - startedAt)
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
      setError(
        "Your answer could not be saved. Nothing was marked complete.",
      );
      setSubmitting(false);
      return;
    }

    setResult(submission.data);
    await loadHome();
    setSubmitting(false);
  }

  async function continueLearning() {
    const nextDay = result?.day_complete
      ? result.next_day
      : activeDay;
    setActivity(null);
    setResult(null);
    setLastAnswer(null);
    setQueued(false);

    if (nextDay > home.available_through_day) {
      await loadHome();
      return;
    }
    await openNextActivity(nextDay);
  }

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <Link
          href="/dashboard"
          className="brand"
          aria-label="Back to dashboard"
        >
          DD<span>21</span>
        </Link>
        <nav className={styles.nav} aria-label="Learning navigation">
          <Link href="/practice" className="text-link">
            Practice
          </Link>
          <Link href="/drills" className="text-link">
            Interview Lab
          </Link>
          <Link href="/dashboard" className="text-link">
            Dashboard
          </Link>
        </nav>
      </header>

      <section className={styles.hero}>
        <div>
          <div className="eyebrow">LEARNING V3 · CONTEXT FIRST</div>
          <h1>Learn it. Build it. Use it.</h1>
          <p>
            Start from real German interview sentences, notice the pattern, then
            retrieve, rebuild and use it. Vocabulary is mixed with word order,
            Perfekt, usage decisions and interview-ready chunks from day one.
          </p>
        </div>
        <div className={styles.progressCard}>
          <span>21-DAY PROGRESS</span>
          <strong>{overallProgress}%</strong>
          <div className={styles.progressTrack} aria-hidden="true">
            <div style={{ width: `${overallProgress}%` }} />
          </div>
          <small>
            {totalSubmitted} / {totalActivities || 133} required activities
            submitted
          </small>
        </div>
      </section>

      {loading ? (
        <p className={styles.state}>Loading your learning plan…</p>
      ) : null}
      {error ? (
        <p className={styles.error} role="alert">
          {error}
        </p>
      ) : null}

      {!loading && !home.enrolled ? (
        <section className={styles.onboarding}>
          <div>
            <span className="card-kicker">CONTEXT-FIRST RELEASE V3</span>
            <h2>Start with usable German, not isolated translations.</h2>
            <p>
              The 21-day release still contains 133 deterministic activities,
              but the first days now mix context, recall, sentence building,
              cloze, matching, usage and Perfekt practice. Exercise guidance can
              switch between English and Persian while the target language stays
              German.
            </p>
          </div>
          <button
            className="button button-accent"
            onClick={initializeLearning}
            disabled={starting}
          >
            {starting ? "Building your plan…" : "Start 21-day path"}
          </button>
        </section>
      ) : null}

      {home.enrolled && home.upgrade_available ? (
        <section className={styles.upgradeCard}>
          <div>
            <span className="card-kicker">
              RELEASE V{home.release_version} → V{home.latest_release_version}
            </span>
            <h2>Your previous learning release stays in history.</h2>
            <p>
              Move to the context-first curriculum without rewriting old
              attempts. Exact compatible submissions can still count as prior
              evidence, while changed activities are learned again in their new
              teaching format.
            </p>
          </div>
          <button
            className="button button-accent"
            onClick={upgradeLearning}
            disabled={upgrading}
          >
            {upgrading ? "Upgrading…" : "Upgrade to learning v3"}
          </button>
        </section>
      ) : null}

      {home.enrolled ? (
        <section className={styles.workspace}>
          <aside className={styles.dayRail}>
            <div className={styles.courseMeta}>
              <span>{home.course_title}</span>
              <small>
                Release v{home.release_version} · {home.days.length} days
              </small>
            </div>
            {home.days.map((day) => {
              const percent = day.total_count
                ? Math.round(
                    (day.submitted_count / day.total_count) * 100,
                  )
                : 0;
              return (
                <button
                  key={day.day_number}
                  className={`${styles.dayButton} ${
                    activeDay === day.day_number ? styles.active : ""
                  }`}
                  onClick={() => {
                    setActiveDay(day.day_number);
                    setActivity(null);
                    setResult(null);
                    setLastAnswer(null);
                    setQueued(false);
                  }}
                >
                  <span className={styles.dayNumber}>
                    {String(day.day_number).padStart(2, "0")}
                  </span>
                  <span className={styles.dayCopy}>
                    <strong>{day.title}</strong>
                    <small>
                      {day.completed
                        ? "Complete"
                        : `${percent}% · ${day.submitted_count}/${day.total_count}`}
                    </small>
                  </span>
                  <span className={styles.dayMark}>
                    {day.completed ? "✓" : "→"}
                  </span>
                </button>
              );
            })}
          </aside>

          <div className={styles.stage}>
            {home.course_complete && !activity && !result ? (
              <section className={styles.dayIntro}>
                <span className="card-kicker">21 / 21 COMPLETE</span>
                <h2>The deterministic path is complete.</h2>
                <p>
                  Your vocabulary, structure and interview-transfer evidence is
                  now durable. Spaced review stays active while the next product
                  phase adds speech and open-answer evidence.
                </p>
                <div className={styles.nextActions}>
                  <Link className="button button-accent" href="/review">
                    Review weak targets
                  </Link>
                  <Link className="button" href="/drills">
                    Keep interview skills warm
                  </Link>
                </div>
              </section>
            ) : null}

            {!home.course_complete && !activity && !result && currentDay ? (
              <section className={styles.dayIntro}>
                <span className="card-kicker">
                  DAY {currentDay.day_number} / {home.available_through_day}
                </span>
                <h2>{currentDay.title}</h2>
                <p>{currentDay.objective}</p>
                <div className={styles.dayStats}>
                  <div>
                    <strong>{currentDay.total_count}</strong>
                    <span>required activities</span>
                  </div>
                  <div>
                    <strong>{currentDay.submitted_count}</strong>
                    <span>submitted</span>
                  </div>
                  <div>
                    <strong>
                      {currentDay.completed ? "100%" : "active"}
                    </strong>
                    <span>status</span>
                  </div>
                </div>
                {currentDay.completed ? (
                  <p className={styles.completeNote}>
                    Day {currentDay.day_number} is complete.
                  </p>
                ) : (
                  <button
                    className="button button-accent"
                    onClick={() =>
                      openNextActivity(currentDay.day_number)
                    }
                  >
                    {currentDay.submitted_count
                      ? "Continue day"
                      : "Start day"}
                  </button>
                )}
              </section>
            ) : null}

            {activity && !result ? (
              <section className={styles.exercise}>
                <div className={styles.exerciseTop}>
                  <span>
                    DAY {activity.day_number} · ACTIVITY {activity.position}
                  </span>
                  <code>{activity.lemma}</code>
                </div>
                <ExercisePlayer
                  key={activity.id}
                  exerciseType={activity.exercise_type}
                  prompt={activity.prompt}
                  submitting={submitting || queued}
                  onSubmit={submitAnswer}
                />
                <div className={styles.exerciseFooter}>
                  <span>
                    See the pattern, use it, get feedback, then meet it again in
                    another form. Wrong answers become review evidence instead of
                    blocking the lesson.
                  </span>
                </div>
              </section>
            ) : null}

            {result && activity ? (
              <LearningFeedback
                exerciseType={activity.exercise_type}
                prompt={activity.prompt}
                fallbackLemma={activity.lemma}
                answer={lastAnswer}
                correct={result.correct}
                score={result.score}
                feedbackCode={result.feedback_code}
                dayComplete={result.day_complete}
                nextDay={result.next_day}
                availableThroughDay={home.available_through_day}
                onContinue={continueLearning}
              />
            ) : null}
          </div>
        </section>
      ) : null}
    </main>
  );
}
