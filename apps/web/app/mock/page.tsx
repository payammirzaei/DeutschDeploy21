"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api } from "@/src/lib/api";
import { createIdempotencyKey } from "@/src/lib/offline-attempts";

import styles from "./mock.module.css";

type Mode = "guided" | "practice" | "realistic";
type Purpose = "practice" | "baseline" | "final";

type BlueprintMode = {
  mode: Mode;
  turn_count: number;
  prep_seconds: number;
  support: string;
};

type Blueprint = {
  key: string;
  version: number;
  title: string;
  target_cefr: string;
  checksum: string;
  modes: BlueprintMode[];
};

type Evaluation = {
  overall_score: number;
  dimensions: Record<string, number>;
  evidence: Record<string, unknown>;
  summary: string;
  next_action: string;
};

type Turn = {
  id: string;
  position_key: string;
  question_key: string;
  category: string;
  question: string;
  intent: string | null;
  hints: string[];
  hint_available: boolean;
  hint_used: boolean;
  target_duration_seconds: number;
  status: string;
  is_follow_up: boolean;
  parent_turn_id: string | null;
  follow_up_reason: string | null;
  speech_attempt_id: string | null;
  answer_source: string | null;
  evaluation: Evaluation | null;
};

type Report = {
  id: string;
  rubric_version: number;
  overall_score: number;
  confidence: number;
  dimensions: Record<string, number>;
  strengths: Array<{ dimension: string; score: number }>;
  priorities: Array<{ dimension: string; score: number }>;
  comparison: {
    baseline_report_id?: string;
    baseline_overall_score?: number;
    overall_delta?: number;
    dimension_deltas?: Record<string, number>;
  };
};

type Session = {
  id: string;
  blueprint_key: string;
  blueprint_version: number;
  blueprint_checksum: string;
  mode: Mode;
  purpose: Purpose;
  status: string;
  current_turn_key: string | null;
  answered_turns: number;
  total_turns: number;
  turns: Turn[];
  report: Report | null;
  created_at: string;
  completed_at: string | null;
};

type SpeechAttempt = {
  id: string;
  status: string;
  source_key: string;
  media: { status: string } | null;
};

type SpeechConsent = {
  accepted: boolean;
};

const PENDING_SPEECH = new Set(["queued", "transcribing"]);

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    credentials: "include",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

function modeCopy(mode: Mode): { title: string; text: string } {
  if (mode === "guided") {
    return {
      title: "Guided",
      text: "Intent and hints stay visible. Best for learning the answer shape.",
    };
  }
  if (mode === "practice") {
    return {
      title: "Practice",
      text: "Question first, hints only when requested. Build independence.",
    };
  }
  return {
    title: "Realistic",
    text: "No hints. Timed preparation and evidence-based readiness scoring.",
  };
}

function displayDimension(name: string): string {
  return name.replaceAll("_", " ");
}

export default function MockInterviewPage() {
  const router = useRouter();
  const [blueprint, setBlueprint] = useState<Blueprint | null>(null);
  const [recent, setRecent] = useState<Session[]>([]);
  const [session, setSession] = useState<Session | null>(null);
  const [mode, setMode] = useState<Mode>("guided");
  const [purpose, setPurpose] = useState<Purpose>("practice");
  const [answer, setAnswer] = useState("");
  const [revealedHints, setRevealedHints] = useState<string[]>([]);
  const [consent, setConsent] = useState<SpeechConsent | null>(null);
  const [recording, setRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [speechAttempt, setSpeechAttempt] = useState<SpeechAttempt | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef<number | null>(null);
  const timerRef = useRef<number | null>(null);

  const activeTurn = useMemo(
    () => session?.turns.find((turn) => turn.status === "active") ?? null,
    [session],
  );

  const selectedMode = blueprint?.modes.find((item) => item.mode === mode) ?? null;

  const refreshRecent = useCallback(async () => {
    const data = await requestJson<{ sessions: Session[] }>(
      "/api/v1/mock-interviews/sessions?limit=6",
    );
    setRecent(data.sessions);
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      api.GET("/api/v1/auth/me"),
      requestJson<Blueprint>("/api/v1/mock-interviews/blueprint"),
      requestJson<{ sessions: Session[] }>("/api/v1/mock-interviews/sessions?limit=6"),
      requestJson<SpeechConsent>("/api/v1/speech/consent"),
    ])
      .then(([me, blueprintData, recentData, consentData]) => {
        if (cancelled) return;
        if (me.response.status === 401) {
          router.replace("/login");
          return;
        }
        setBlueprint(blueprintData);
        setRecent(recentData.sessions);
        setConsent(consentData);
        setLoading(false);
      })
      .catch((reason) => {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : "Mock Interview could not load.");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [router]);

  useEffect(() => {
    return () => {
      if (timerRef.current !== null) window.clearInterval(timerRef.current);
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  async function startSession() {
    setBusy(true);
    setError(null);
    setAnswer("");
    setRevealedHints([]);
    setSpeechAttempt(null);
    try {
      const next = await requestJson<Session>("/api/v1/mock-interviews/sessions", {
        method: "POST",
        body: JSON.stringify({ mode, purpose }),
      });
      setSession(next);
      await refreshRecent();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Session could not start.");
    } finally {
      setBusy(false);
    }
  }

  async function openSession(id: string) {
    setBusy(true);
    setError(null);
    try {
      const next = await requestJson<Session>(`/api/v1/mock-interviews/sessions/${id}`);
      setSession(next);
      setMode(next.mode);
      setPurpose(next.purpose);
      setAnswer("");
      setRevealedHints([]);
      setSpeechAttempt(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Session could not be opened.");
    } finally {
      setBusy(false);
    }
  }

  async function revealHint() {
    if (!session || !activeTurn) return;
    setBusy(true);
    setError(null);
    try {
      const result = await requestJson<{ hints: string[] }>(
        `/api/v1/mock-interviews/sessions/${session.id}/turns/${activeTurn.id}/hint`,
        { method: "POST", body: "{}" },
      );
      setRevealedHints(result.hints);
      const refreshed = await requestJson<Session>(
        `/api/v1/mock-interviews/sessions/${session.id}`,
      );
      setSession(refreshed);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Hint could not be opened.");
    } finally {
      setBusy(false);
    }
  }

  async function submitText() {
    if (!session || !activeTurn || !answer.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const next = await requestJson<Session>(
        `/api/v1/mock-interviews/sessions/${session.id}/turns/${activeTurn.id}/text`,
        {
          method: "POST",
          headers: { "Idempotency-Key": createIdempotencyKey() },
          body: JSON.stringify({ text: answer }),
        },
      );
      setSession(next);
      setAnswer("");
      setRevealedHints([]);
      setSpeechAttempt(null);
      await refreshRecent();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Answer could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  async function enableVoice() {
    setBusy(true);
    setError(null);
    try {
      const next = await requestJson<SpeechConsent>("/api/v1/speech/consent", {
        method: "POST",
        body: JSON.stringify({ accepted: true }),
      });
      setConsent(next);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Voice consent could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  function chooseMimeType(): string {
    if (typeof MediaRecorder === "undefined") return "";
    return ["audio/webm;codecs=opus", "audio/mp4", "audio/webm"].find((type) =>
      MediaRecorder.isTypeSupported(type),
    ) ?? "";
  }

  async function startVoiceAnswer(event: { timeStamp: number }) {
    if (!session || !activeTurn) return;
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("This browser cannot record audio here. Text answer remains available.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      let linked = speechAttempt;
      if (!linked) {
        const payload = await requestJson<{ speech_attempt: SpeechAttempt }>(
          `/api/v1/mock-interviews/sessions/${session.id}/turns/${activeTurn.id}/speech-attempt`,
          { method: "POST", body: "{}" },
        );
        linked = payload.speech_attempt;
        setSpeechAttempt(linked);
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];
      const mimeType = chooseMimeType();
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);
      recorderRef.current = recorder;
      recorder.ondataavailable = (mediaEvent) => {
        if (mediaEvent.data.size > 0) chunksRef.current.push(mediaEvent.data);
      };
      recorder.onstop = async () => {
        const duration = startedAtRef.current
          ? Math.max(500, Date.now() - startedAtRef.current)
          : null;
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || mimeType || "audio/webm",
        });
        streamRef.current?.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        if (timerRef.current !== null) {
          window.clearInterval(timerRef.current);
          timerRef.current = null;
        }
        setRecording(false);
        await uploadVoice(linked!.id, blob, duration);
      };
      startedAtRef.current = performance.timeOrigin + event.timeStamp;
      setRecordingSeconds(0);
      recorder.start(250);
      setRecording(true);
      timerRef.current = window.setInterval(() => {
        if (startedAtRef.current) {
          setRecordingSeconds(Math.floor((Date.now() - startedAtRef.current) / 1000));
        }
      }, 250);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Microphone could not start.");
    } finally {
      setBusy(false);
    }
  }

  function stopVoiceAnswer() {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") recorder.stop();
  }

  async function uploadVoice(attemptId: string, blob: Blob, durationMs: number | null) {
    setBusy(true);
    setError(null);
    try {
      const upload = await fetch(`/api/v1/speech/attempts/${attemptId}/audio`, {
        method: "PUT",
        credentials: "include",
        headers: {
          "Content-Type": blob.type || "audio/webm",
          ...(durationMs ? { "X-Audio-Duration-Ms": String(Math.min(durationMs, 180000)) } : {}),
        },
        body: blob,
      });
      if (!upload.ok) {
        const payload = await upload.json().catch(() => null);
        throw new Error(payload?.detail ?? "Voice upload failed.");
      }
      const payload = (await upload.json()) as { attempt: SpeechAttempt };
      setSpeechAttempt(payload.attempt);
      await waitForSpeech(payload.attempt.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Voice answer could not be processed.");
    } finally {
      setBusy(false);
    }
  }

  async function waitForSpeech(attemptId: string) {
    if (!session || !activeTurn) return;
    for (let index = 0; index < 70; index += 1) {
      const attempt = await requestJson<SpeechAttempt>(`/api/v1/speech/attempts/${attemptId}`);
      setSpeechAttempt(attempt);
      if (attempt.status === "feedback_ready") {
        const next = await requestJson<Session>(
          `/api/v1/mock-interviews/sessions/${session.id}/turns/${activeTurn.id}/sync-speech`,
          { method: "POST", body: "{}" },
        );
        setSession(next);
        setAnswer("");
        setRevealedHints([]);
        setSpeechAttempt(null);
        await refreshRecent();
        return;
      }
      if (attempt.status === "failed") {
        throw new Error("Transcription failed. The speech attempt is preserved and can be retried.");
      }
      if (!PENDING_SPEECH.has(attempt.status) && attempt.status !== "created") break;
      await new Promise((resolve) => window.setTimeout(resolve, 850));
    }
    throw new Error("Speech processing is still pending. You can reopen this session later.");
  }

  if (loading) {
    return <main className={styles.shell}><p>Loading Mock Interview…</p></main>;
  }

  const progress = session
    ? Math.round((session.answered_turns / Math.max(1, session.total_turns)) * 100)
    : 0;
  const previousAnswered = session
    ? [...session.turns].reverse().find((turn) => turn.status === "answered") ?? null
    : null;

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <Link href="/dashboard" className="brand">DD<span>21</span></Link>
        <nav className={styles.nav}>
          <Link href="/drills" className="text-link">Interview Lab</Link>
          <Link href="/speak" className="text-link">Speak</Link>
          <Link href="/dashboard" className="text-link">Dashboard</Link>
        </nav>
      </header>

      <section className={styles.hero}>
        <div>
          <div className="eyebrow">PHASE 7 · MOCK INTERVIEW</div>
          <h1>Stop rehearsing. Perform.</h1>
          <p>
            Run a durable German software interview, answer by text or voice, receive contextual
            follow-ups, and finish with a versioned readiness report you can compare over time.
          </p>
        </div>
        <div className={styles.heroBadge}>
          <span>READINESS</span>
          <strong>{session?.report?.overall_score ?? "—"}</strong>
          <small>{session ? `${session.mode} · ${session.purpose}` : "choose a mode"}</small>
        </div>
      </section>

      {error ? <p className={styles.error} role="alert">{error}</p> : null}

      {!session ? (
        <section className={styles.launchGrid}>
          <div className={styles.launchPanel}>
            <span className="card-kicker">INTERVIEW MODE</span>
            <h2>How much support do you want?</h2>
            <div className={styles.modeGrid}>
              {(["guided", "practice", "realistic"] as Mode[]).map((item) => {
                const copy = modeCopy(item);
                const config = blueprint?.modes.find((entry) => entry.mode === item);
                return (
                  <button
                    key={item}
                    className={`${styles.modeCard} ${mode === item ? styles.selected : ""}`}
                    onClick={() => setMode(item)}
                  >
                    <span>{copy.title}</span>
                    <strong>{config?.turn_count ?? "—"} core questions</strong>
                    <p>{copy.text}</p>
                    <small>{config?.prep_seconds ?? 0}s preparation · {config?.support}</small>
                  </button>
                );
              })}
            </div>

            <div className={styles.purposeRow}>
              {(["practice", "baseline", "final"] as Purpose[]).map((item) => (
                <button
                  key={item}
                  className={purpose === item ? styles.purposeActive : styles.purposeButton}
                  onClick={() => setPurpose(item)}
                >
                  {item}
                </button>
              ))}
            </div>

            <div className={styles.launchSummary}>
              <div><span>Blueprint</span><strong>v{blueprint?.version ?? "—"}</strong></div>
              <div><span>Target</span><strong>{blueprint?.target_cefr ?? "A2–B1"}</strong></div>
              <div><span>Prep</span><strong>{selectedMode?.prep_seconds ?? 0}s</strong></div>
            </div>
            <button className="button button-accent" onClick={startSession} disabled={busy}>
              {busy ? "Starting…" : "Start interview"}
            </button>
          </div>

          <aside className={styles.historyPanel}>
            <span className="card-kicker">RECENT SESSIONS</span>
            <h2>Resume the evidence.</h2>
            {recent.length ? recent.map((item) => (
              <button key={item.id} className={styles.historyItem} onClick={() => openSession(item.id)}>
                <span>{item.status}</span>
                <strong>{item.mode} · {item.purpose}</strong>
                <small>{item.answered_turns}/{item.total_turns} answered</small>
              </button>
            )) : <p className={styles.muted}>No interview sessions yet.</p>}
          </aside>
        </section>
      ) : (
        <>
          <section className={styles.sessionTopbar}>
            <div>
              <span>{session.mode.toUpperCase()} · {session.purpose.toUpperCase()}</span>
              <strong>{session.answered_turns} / {session.total_turns} answered</strong>
            </div>
            <div className={styles.progressTrack} aria-label={`${progress}% complete`}>
              <span style={{ width: `${progress}%` }} />
            </div>
            <button className="text-button" onClick={() => setSession(null)}>Exit session</button>
          </section>

          {session.status === "completed" && session.report ? (
            <section className={styles.reportCard}>
              <div className={styles.reportLead}>
                <span className="card-kicker">READINESS REPORT · RUBRIC V{session.report.rubric_version}</span>
                <h2>{session.report.overall_score}/100</h2>
                <p>
                  Confidence {Math.round(session.report.confidence * 100)}%. Readiness is kept separate
                  from vocabulary mastery and reflects performance under this interview mode.
                </p>
                {typeof session.report.comparison.overall_delta === "number" ? (
                  <div className={styles.delta}>
                    Baseline → final: {session.report.comparison.overall_delta >= 0 ? "+" : ""}
                    {session.report.comparison.overall_delta} points
                  </div>
                ) : null}
              </div>
              <div className={styles.dimensionGrid}>
                {Object.entries(session.report.dimensions).map(([name, score]) => (
                  <div key={name} className={styles.dimension}>
                    <span>{displayDimension(name)}</span>
                    <strong>{score}</strong>
                    <div><i style={{ width: `${score}%` }} /></div>
                  </div>
                ))}
              </div>
              <div className={styles.reportColumns}>
                <div>
                  <span className="card-kicker">STRENGTHS</span>
                  {session.report.strengths.map((item) => (
                    <p key={item.dimension}><strong>{displayDimension(item.dimension)}</strong> · {item.score}</p>
                  ))}
                </div>
                <div>
                  <span className="card-kicker">PRIORITIES</span>
                  {session.report.priorities.map((item) => (
                    <p key={item.dimension}><strong>{displayDimension(item.dimension)}</strong> · {item.score}</p>
                  ))}
                </div>
              </div>
              <div className={styles.reportActions}>
                <button className="button button-accent" onClick={() => setSession(null)}>New interview</button>
                <Link className="button" href="/review">Open mastery review</Link>
              </div>
            </section>
          ) : activeTurn ? (
            <section className={styles.interviewGrid}>
              <aside className={styles.turnRail}>
                {session.turns.map((turn) => (
                  <div
                    key={turn.id}
                    className={`${styles.turnDot} ${styles[`turn_${turn.status}`] ?? ""}`}
                    title={`${turn.position_key} · ${turn.category}`}
                  >
                    <span>{turn.position_key}</span>
                    <small>{turn.is_follow_up ? "follow-up" : turn.category}</small>
                  </div>
                ))}
              </aside>

              <div className={styles.interviewStage}>
                <section className={styles.questionCard}>
                  <div className={styles.questionMeta}>
                    <span>{activeTurn.category.toUpperCase()}</span>
                    <strong>{activeTurn.target_duration_seconds}s target</strong>
                  </div>
                  {activeTurn.is_follow_up ? <div className={styles.followUp}>CONTEXTUAL FOLLOW-UP</div> : null}
                  <h2 lang="de">{activeTurn.question}</h2>
                  {activeTurn.intent ? <p className={styles.intent}>{activeTurn.intent}</p> : null}

                  {revealedHints.length ? (
                    <div className={styles.hints}>
                      {revealedHints.map((hint) => <span key={hint}>{hint}</span>)}
                    </div>
                  ) : activeTurn.hint_available ? (
                    <button className="text-button" onClick={revealHint} disabled={busy}>
                      Show one interview hint
                    </button>
                  ) : (
                    <p className={styles.realisticNote}>Realistic mode · no hints</p>
                  )}

                  <textarea
                    className={styles.answerBox}
                    value={answer}
                    onChange={(event) => setAnswer(event.target.value)}
                    rows={7}
                    placeholder="Type the answer you would give in German…"
                    lang="de"
                  />
                  <div className={styles.answerActions}>
                    <button
                      className="button button-accent"
                      onClick={submitText}
                      disabled={busy || !answer.trim()}
                    >
                      {busy ? "Saving…" : "Submit text answer"}
                    </button>
                    {!consent?.accepted ? (
                      <button className="button" onClick={enableVoice} disabled={busy}>Enable voice</button>
                    ) : !recording ? (
                      <button className="button" onClick={startVoiceAnswer} disabled={busy}>
                        🎙 Answer by voice
                      </button>
                    ) : (
                      <button className="button" onClick={stopVoiceAnswer}>Stop · {recordingSeconds}s</button>
                    )}
                  </div>
                  {speechAttempt ? (
                    <p className={styles.speechState}>
                      Voice evidence: <strong>{speechAttempt.status.replaceAll("_", " ")}</strong>
                    </p>
                  ) : null}
                </section>

                {previousAnswered?.evaluation ? (
                  <section className={styles.feedbackCard}>
                    <div className={styles.feedbackScore}>
                      <span>LAST TURN</span>
                      <strong>{previousAnswered.evaluation.overall_score}</strong>
                    </div>
                    <div>
                      <p>{previousAnswered.evaluation.summary}</p>
                      <strong>{previousAnswered.evaluation.next_action}</strong>
                    </div>
                  </section>
                ) : null}
              </div>
            </section>
          ) : null}
        </>
      )}
    </main>
  );
}