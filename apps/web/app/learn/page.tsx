"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { api } from "@/src/lib/api";

import styles from "./learn.module.css";

type Choice = { id: string; text: string };
type Activity = {
  id: string;
  day_number: number;
  position: number;
  content_version_id: string;
  exercise_type: string;
  contract_version: number;
  prompt_checksum: string;
  lemma: string;
  question: string;
  choices: Choice[];
};
type ActivitySummary = {
  activity_id: string;
  position: number;
  content_version_id: string;
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
  current_day: number;
  available_through_day: number;
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
  current_day: 1,
  available_through_day: 3,
  days: [],
};

export default function LearnPage() {
  const router = useRouter();
  const [home, setHome] = useState<LearningHome>(EMPTY_HOME);
  const [activeDay, setActiveDay] = useState(1);
  const [activity, setActivity] = useState<Activity | null>(null);
  const [selectedChoice, setSelectedChoice] = useState<string | null>(null);
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [submitting, setSubmitting] = useState(false);
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
      if (nextHome.days.some((day) => day.day_number === current && !day.completed)) return current;
      return nextHome.current_day;
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
        setActiveDay(nextHome.current_day);
      }
      setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [router]);

  const currentDay = useMemo(
    () => home.days.find((day) => day.day_number === activeDay) ?? null,
    [activeDay, home.days],
  );

  const totalSubmitted = home.days.reduce((sum, day) => sum + day.submitted_count, 0);
  const totalActivities = home.days.reduce((sum, day) => sum + day.total_count, 0);
  const overallProgress = totalActivities ? Math.round((totalSubmitted / totalActivities) * 100) : 0;

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
      setError("The first learning release could not be created.");
      setStarting(false);
      return;
    }

    const nextHome = await loadHome();
    if (nextHome) setActiveDay(nextHome.current_day);
    setStarting(false);
  }

  async function openNextActivity(dayNumber: number) {
    setActiveDay(dayNumber);
    setActivity(null);
    setResult(null);
    setSelectedChoice(null);
    setError(null);

    const { data, response } = await api.POST("/api/v1/learning/days/{day_number}/next", {
      params: { path: { day_number: dayNumber } },
    });
    if (!response.ok) {
      setError("The next activity could not be prepared.");
      return;
    }

    const next = data as { completed: boolean; activity: Activity | null };
    if (next.completed || !next.activity) {
      await loadHome();
      return;
    }

    setActivity(next.activity);
    setStartedAt(Date.now());
  }

  async function submitAnswer() {
    if (!activity || !selectedChoice || submitting) return;
    setSubmitting(true);
    setError(null);

    const durationMs = startedAt ? Math.max(0, Date.now() - startedAt) : null;
    const { data, response } = await api.POST("/api/v1/learning/instances/{instance_id}/attempts", {
      params: {
        path: { instance_id: activity.id },
        header: { "Idempotency-Key": crypto.randomUUID() },
      },
      body: { choice_id: selectedChoice, duration_ms: durationMs },
    });

    if (!response.ok || !data) {
      setError("Your answer could not be saved. Nothing was marked complete.");
      setSubmitting(false);
      return;
    }

    setResult(data as AttemptResult);
    await loadHome();
    setSubmitting(false);
  }

  async function continueLearning() {
    const nextDay = result?.day_complete ? result.next_day : activeDay;
    setActivity(null);
    setResult(null);
    setSelectedChoice(null);
    await openNextActivity(Math.min(nextDay, home.available_through_day));
  }

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <Link href="/dashboard" className="brand" aria-label="Back to dashboard">
          DD<span>21</span>
        </Link>
        <nav className={styles.nav} aria-label="Learning navigation">
          <Link href="/catalog" className="text-link">
            Catalog
          </Link>
          <Link href="/dashboard" className="text-link">
            Dashboard
          </Link>
        </nav>
      </header>

      <section className={styles.hero}>
        <div>
          <div className="eyebrow">PHASE 3 · DETERMINISTIC LEARNING</div>
          <h1>Learn by doing.</h1>
          <p>
            Three focused days turn the first interview verbs into active recall. Every answer is
            stored against the exact published content version you saw.
          </p>
        </div>
        <div className={styles.progressCard}>
          <span>FOUNDATION PROGRESS</span>
          <strong>{overallProgress}%</strong>
          <div className={styles.progressTrack} aria-hidden="true">
            <div style={{ width: `${overallProgress}%` }} />
          </div>
          <small>
            {totalSubmitted} / {totalActivities || 21} activities submitted
          </small>
        </div>
      </section>

      {loading ? <p className={styles.state}>Loading your learning plan…</p> : null}
      {error ? <p className={styles.error} role="alert">{error}</p> : null}

      {!loading && !home.enrolled ? (
        <section className={styles.onboarding}>
          <div>
            <span className="card-kicker">YOUR FIRST RELEASE</span>
            <h2>Build Days 1–3 from the published verb catalog.</h2>
            <p>
              This creates one pinned course release and 21 deterministic activities. Future
              content edits will not silently change activities you already started.
            </p>
          </div>
          <button className="button button-accent" onClick={initializeLearning} disabled={starting}>
            {starting ? "Building your plan…" : "Start learning"}
          </button>
        </section>
      ) : null}

      {home.enrolled ? (
        <section className={styles.workspace}>
          <aside className={styles.dayRail}>
            <div className={styles.courseMeta}>
              <span>{home.course_title}</span>
              <small>Release v{home.release_version}</small>
            </div>
            {home.days.map((day) => {
              const percent = day.total_count
                ? Math.round((day.submitted_count / day.total_count) * 100)
                : 0;
              return (
                <button
                  key={day.day_number}
                  className={`${styles.dayButton} ${activeDay === day.day_number ? styles.active : ""}`}
                  onClick={() => {
                    setActiveDay(day.day_number);
                    setActivity(null);
                    setResult(null);
                    setSelectedChoice(null);
                  }}
                >
                  <span className={styles.dayNumber}>0{day.day_number}</span>
                  <span className={styles.dayCopy}>
                    <strong>{day.title}</strong>
                    <small>{day.completed ? "Complete" : `${percent}% · ${day.submitted_count}/${day.total_count}`}</small>
                  </span>
                  <span className={styles.dayMark}>{day.completed ? "✓" : "→"}</span>
                </button>
              );
            })}
          </aside>

          <div className={styles.stage}>
            {!activity && !result && currentDay ? (
              <section className={styles.dayIntro}>
                <span className="card-kicker">DAY {currentDay.day_number}</span>
                <h2>{currentDay.title}</h2>
                <p>{currentDay.objective}</p>
                <div className={styles.dayStats}>
                  <div>
                    <strong>{currentDay.total_count}</strong>
                    <span>activities</span>
                  </div>
                  <div>
                    <strong>{currentDay.submitted_count}</strong>
                    <span>submitted</span>
                  </div>
                  <div>
                    <strong>{currentDay.completed ? "100%" : "active"}</strong>
                    <span>status</span>
                  </div>
                </div>
                {currentDay.completed ? (
                  <p className={styles.completeNote}>Day {currentDay.day_number} is complete.</p>
                ) : (
                  <button
                    className="button button-accent"
                    onClick={() => openNextActivity(currentDay.day_number)}
                  >
                    {currentDay.submitted_count ? "Continue day" : "Start day"}
                  </button>
                )}
              </section>
            ) : null}

            {activity && !result ? (
              <section className={styles.exercise}>
                <div className={styles.exerciseTop}>
                  <span>DAY {activity.day_number} · ACTIVITY {activity.position}</span>
                  <code>{activity.lemma}</code>
                </div>
                <h2>{activity.question}</h2>
                <div className={styles.choices} role="radiogroup" aria-label="Answer choices">
                  {activity.choices.map((choice, index) => (
                    <button
                      key={choice.id}
                      className={`${styles.choice} ${selectedChoice === choice.id ? styles.selected : ""}`}
                      role="radio"
                      aria-checked={selectedChoice === choice.id}
                      onClick={() => setSelectedChoice(choice.id)}
                    >
                      <span>{String.fromCharCode(65 + index)}</span>
                      <strong>{choice.text}</strong>
                    </button>
                  ))}
                </div>
                <div className={styles.exerciseFooter}>
                  <span>Choose the best answer. Wrong answers still move forward and become review evidence.</span>
                  <button
                    className="button button-primary"
                    disabled={!selectedChoice || submitting}
                    onClick={submitAnswer}
                  >
                    {submitting ? "Saving…" : "Check answer"}
                  </button>
                </div>
              </section>
            ) : null}

            {result ? (
              <section className={`${styles.feedback} ${result.correct ? styles.correct : styles.incorrect}`} aria-live="polite">
                <span className="card-kicker">{result.correct ? "CORRECT" : "REVIEW LATER"}</span>
                <h2>{result.correct ? "Genau." : "Not this time — keep moving."}</h2>
                <p>
                  {result.correct
                    ? "This attempt is stored as positive evidence for the exact content version you practiced."
                    : "The attempt is preserved instead of overwritten. Phase 4 will use it to schedule focused review."}
                </p>
                <div className={styles.scoreRow}>
                  <strong>{result.score}</strong>
                  <span>deterministic score</span>
                  <code>{result.feedback_code}</code>
                </div>
                <button className="button button-accent" onClick={continueLearning}>
                  {result.day_complete ? "Continue to next day" : "Next activity"}
                </button>
              </section>
            ) : null}
          </div>
        </section>
      ) : null}
    </main>
  );
}
