"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/src/lib/api";

import styles from "./speak.module.css";

type SpeakingPrompt = {
  id: string;
  category: string;
  question: string;
  support: string[];
  target_duration_seconds: number;
};

type SpeechConsent = {
  policy_version: string;
  accepted: boolean;
  accepted_at: string | null;
};

type Transcript = {
  id: string;
  kind: string;
  revision_number: number;
  text: string;
  language: string;
  provider: string | null;
  model: string | null;
  confidence: number | null;
  created_at: string;
};

type SpeechFeedback = {
  id: string;
  transcript_id: string;
  evaluator_type: string;
  evaluator_version: number;
  overall_score: number;
  summary: string;
  dimensions: Record<string, unknown>;
  corrections: Array<Record<string, string>>;
  next_action: string;
  created_at: string;
};

type SpeechAttempt = {
  id: string;
  source_key: string;
  prompt: {
    id?: string;
    category?: string;
    question?: string;
    support?: string[];
    target_duration_seconds?: number;
  };
  prompt_checksum: string;
  language: string;
  target_duration_seconds: number;
  status: string;
  media: {
    id: string;
    status: string;
    content_type: string;
    byte_size: number;
    sha256: string;
    duration_ms: number | null;
  } | null;
  transcription_job_id: string | null;
  transcription_retry_count: number;
  transcripts: Transcript[];
  feedback: SpeechFeedback | null;
  created_at: string;
  updated_at: string;
};

const PENDING_STATES = new Set(["queued", "transcribing"]);

function latestTranscript(attempt: SpeechAttempt): Transcript | null {
  const corrected = [...attempt.transcripts]
    .reverse()
    .find((item) => item.kind === "learner_corrected" || item.kind === "manual");
  if (corrected) return corrected;
  return [...attempt.transcripts].reverse().find((item) => item.kind === "provider_raw") ?? null;
}

function displayMetric(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "yes" : "no";
  return String(value);
}

export default function SpeakPage() {
  const router = useRouter();
  const [prompts, setPrompts] = useState<SpeakingPrompt[]>([]);
  const [selectedPromptId, setSelectedPromptId] = useState("");
  const [consent, setConsent] = useState<SpeechConsent | null>(null);
  const [attempt, setAttempt] = useState<SpeechAttempt | null>(null);
  const [recent, setRecent] = useState<SpeechAttempt[]>([]);
  const [transcriptText, setTranscriptText] = useState("");
  const [recording, setRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);
  const [recordedUrl, setRecordedUrl] = useState<string | null>(null);
  const [recordedDurationMs, setRecordedDurationMs] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [micUnavailable, setMicUnavailable] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const recordingStartedAtRef = useRef<number | null>(null);
  const timerRef = useRef<number | null>(null);

  const applyAttempt = useCallback((next: SpeechAttempt) => {
    setAttempt(next);
    const transcript = latestTranscript(next);
    if (transcript) setTranscriptText(transcript.text);
  }, []);

  const loadRecent = useCallback(async () => {
    const { data, response } = await api.GET("/api/v1/speech/attempts", {
      params: { query: { limit: 6 } },
    });
    if (response.ok && data) {
      setRecent((data as { attempts: SpeechAttempt[] }).attempts);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      api.GET("/api/v1/auth/me"),
      api.GET("/api/v1/speech/prompts"),
      api.GET("/api/v1/speech/consent"),
      api.GET("/api/v1/speech/attempts", { params: { query: { limit: 6 } } }),
    ]).then(([me, promptResult, consentResult, attemptsResult]) => {
      if (cancelled) return;
      if (me.response.status === 401) {
        router.replace("/login");
        return;
      }
      if (promptResult.response.ok && promptResult.data) {
        const nextPrompts = promptResult.data as SpeakingPrompt[];
        setPrompts(nextPrompts);
        setSelectedPromptId(nextPrompts[0]?.id ?? "");
      }
      if (consentResult.response.ok && consentResult.data) {
        setConsent(consentResult.data as SpeechConsent);
      }
      if (attemptsResult.response.ok && attemptsResult.data) {
        setRecent((attemptsResult.data as { attempts: SpeechAttempt[] }).attempts);
      }
      setLoading(false);
    }).catch(() => {
      if (!cancelled) {
        setError("Speech practice could not be loaded.");
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [router]);

  const pendingAttemptId =
    attempt && PENDING_STATES.has(attempt.status) ? attempt.id : null;

  useEffect(() => {
    if (!pendingAttemptId) return;
    let cancelled = false;
    const id = pendingAttemptId;
    const timer = window.setInterval(async () => {
      const { data, response } = await api.GET("/api/v1/speech/attempts/{attempt_id}", {
        params: { path: { attempt_id: id } },
      });
      if (cancelled || !response.ok || !data) return;
      const next = data as SpeechAttempt;
      applyAttempt(next);
      if (!PENDING_STATES.has(next.status)) {
        window.clearInterval(timer);
        void loadRecent();
      }
    }, 850);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [pendingAttemptId, applyAttempt, loadRecent]);

  useEffect(() => {
    return () => {
      if (timerRef.current !== null) window.clearInterval(timerRef.current);
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
      if (recordedUrl) URL.revokeObjectURL(recordedUrl);
    };
  }, [recordedUrl]);

  async function acceptConsent() {
    setBusy(true);
    setError(null);
    const { data, response } = await api.POST("/api/v1/speech/consent", {
      body: { accepted: true },
    });
    if (!response.ok || !data) {
      setError("Consent could not be saved.");
    } else {
      setConsent(data as SpeechConsent);
    }
    setBusy(false);
  }

  function pickMimeType(): string {
    const candidates = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm"];
    return candidates.find((candidate) => MediaRecorder.isTypeSupported(candidate)) ?? "";
  }

  async function startRecording() {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setMicUnavailable(true);
      setError("This browser cannot record audio here. You can use the text fallback below.");
      return;
    }
    setError(null);
    setMicUnavailable(false);
    setRecordedBlob(null);
    if (recordedUrl) {
      URL.revokeObjectURL(recordedUrl);
      setRecordedUrl(null);
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      chunksRef.current = [];
      const mimeType = pickMimeType();
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const duration = recordingStartedAtRef.current
          ? Math.max(500, Date.now() - recordingStartedAtRef.current)
          : null;
        const type = recorder.mimeType || mimeType || "audio/webm";
        const blob = new Blob(chunksRef.current, { type });
        const url = URL.createObjectURL(blob);
        setRecordedBlob(blob);
        setRecordedUrl(url);
        setRecordedDurationMs(duration);
        setRecording(false);
        mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
        mediaStreamRef.current = null;
        if (timerRef.current !== null) {
          window.clearInterval(timerRef.current);
          timerRef.current = null;
        }
      };

      recordingStartedAtRef.current = Date.now();
      setRecordingSeconds(0);
      recorder.start(250);
      setRecording(true);
      timerRef.current = window.setInterval(() => {
        const started = recordingStartedAtRef.current;
        if (started) setRecordingSeconds(Math.floor((Date.now() - started) / 1000));
      }, 250);
    } catch {
      setMicUnavailable(true);
      setError("Microphone access was denied or unavailable. Text fallback is still available.");
    }
  }

  function stopRecording() {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== "inactive") recorder.stop();
  }

  async function ensureAttempt(): Promise<SpeechAttempt | null> {
    if (attempt && attempt.source_key === selectedPromptId && attempt.status === "created") {
      return attempt;
    }
    const { data, response } = await api.POST("/api/v1/speech/attempts", {
      body: { prompt_id: selectedPromptId },
    });
    if (!response.ok || !data) {
      setError(
        response.status === 403
          ? "Accept the recording consent before starting a speaking attempt."
          : "The speaking attempt could not be created.",
      );
      return null;
    }
    const next = data as SpeechAttempt;
    applyAttempt(next);
    return next;
  }

  async function uploadRecording() {
    if (!recordedBlob || !selectedPromptId) return;
    setBusy(true);
    setError(null);
    const target = await ensureAttempt();
    if (!target) {
      setBusy(false);
      return;
    }
    const response = await fetch(`/api/v1/speech/attempts/${target.id}/audio`, {
      method: "PUT",
      credentials: "include",
      headers: {
        "Content-Type": recordedBlob.type || "audio/webm",
        ...(recordedDurationMs
          ? { "X-Audio-Duration-Ms": String(Math.min(recordedDurationMs, 180000)) }
          : {}),
      },
      body: recordedBlob,
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      setError(payload?.detail ?? "Audio upload failed. The attempt itself is still saved.");
      setBusy(false);
      return;
    }
    const payload = (await response.json()) as { attempt: SpeechAttempt; queued: boolean };
    applyAttempt(payload.attempt);
    await loadRecent();
    setBusy(false);
  }

  async function submitManualTranscript() {
    if (!transcriptText.trim() || !selectedPromptId) return;
    setBusy(true);
    setError(null);
    const target = attempt?.status === "created" ? attempt : await ensureAttempt();
    if (!target) {
      setBusy(false);
      return;
    }
    const { data, response } = await api.POST(
      "/api/v1/speech/attempts/{attempt_id}/manual-transcript",
      {
        params: { path: { attempt_id: target.id } },
        body: { text: transcriptText },
      },
    );
    if (!response.ok || !data) {
      setError("Text fallback could not be saved.");
    } else {
      applyAttempt(data as SpeechAttempt);
      await loadRecent();
    }
    setBusy(false);
  }

  async function saveCorrection() {
    if (!attempt || !transcriptText.trim()) return;
    setBusy(true);
    setError(null);
    const { data, response } = await api.POST(
      "/api/v1/speech/attempts/{attempt_id}/correct-transcript",
      {
        params: { path: { attempt_id: attempt.id } },
        body: { text: transcriptText },
      },
    );
    if (!response.ok || !data) {
      setError("Transcript correction could not be saved.");
    } else {
      applyAttempt(data as SpeechAttempt);
      await loadRecent();
    }
    setBusy(false);
  }

  async function retryTranscription() {
    if (!attempt) return;
    setBusy(true);
    setError(null);
    const { data, response } = await api.POST(
      "/api/v1/speech/attempts/{attempt_id}/retry-transcription",
      { params: { path: { attempt_id: attempt.id } } },
    );
    if (!response.ok || !data) {
      setError("Transcription retry could not be queued.");
    } else {
      applyAttempt(data as SpeechAttempt);
    }
    setBusy(false);
  }

  async function deleteAudio() {
    if (!attempt?.media) return;
    setBusy(true);
    const { response } = await api.DELETE("/api/v1/speech/attempts/{attempt_id}/audio", {
      params: { path: { attempt_id: attempt.id } },
    });
    if (!response.ok) {
      setError("Audio could not be deleted.");
    } else {
      const detail = await api.GET("/api/v1/speech/attempts/{attempt_id}", {
        params: { path: { attempt_id: attempt.id } },
      });
      if (detail.data) applyAttempt(detail.data as SpeechAttempt);
      await loadRecent();
    }
    setBusy(false);
  }

  function resetSession() {
    setAttempt(null);
    setTranscriptText("");
    setRecordedBlob(null);
    setRecordedDurationMs(null);
    if (recordedUrl) URL.revokeObjectURL(recordedUrl);
    setRecordedUrl(null);
    setError(null);
  }

  if (loading) {
    return <main className={styles.shell}><p>Loading Speak Mode…</p></main>;
  }

  const selectedPrompt = prompts.find((item) => item.id === selectedPromptId) ?? null;
  const rawTranscript = attempt?.transcripts.find((item) => item.kind === "provider_raw") ?? null;
  const feedback = attempt?.feedback ?? null;
  const dimensions = feedback?.dimensions ?? {};

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <Link href="/dashboard" className="brand">DD<span>21</span></Link>
        <nav className={styles.nav}>
          <Link href="/practice" className="text-link">Silent</Link>
          <Link href="/drills" className="text-link">Interview Lab</Link>
          <Link href="/dashboard" className="text-link">Dashboard</Link>
        </nav>
      </header>

      <section className={styles.hero}>
        <div>
          <div className="eyebrow">PHASE 6 · SPEAK MODE</div>
          <h1>Say the answer.</h1>
          <p>
            Record a real answer, keep the original evidence, inspect the transcript,
            correct it if needed, then repeat. Provider failures never erase the attempt.
          </p>
        </div>
        <div className={styles.modeBadge}>
          <span>{attempt?.status ?? "ready"}</span>
          <strong>🎙</strong>
          <small>audio → transcript → feedback</small>
        </div>
      </section>

      {error ? <p className={styles.error} role="alert">{error}</p> : null}

      {!consent?.accepted ? (
        <section className={styles.consentCard}>
          <div>
            <span className="card-kicker">VOICE CONSENT · {consent?.policy_version}</span>
            <h2>Your recording is optional.</h2>
            <p>
              Audio is private and used only for your speaking practice and transcription.
              You can delete the audio later while keeping the derived transcript and feedback.
              Silent Practice remains fully available without consent.
            </p>
          </div>
          <button className="button button-accent" onClick={acceptConsent} disabled={busy}>
            {busy ? "Saving…" : "Enable Speak Mode"}
          </button>
        </section>
      ) : (
        <section className={styles.workspace}>
          <aside className={styles.promptRail}>
            <div className={styles.railTitle}>
              <span className="card-kicker">PROMPTS</span>
              <strong>{prompts.length} focused answers</strong>
            </div>
            {prompts.map((prompt) => (
              <button
                key={prompt.id}
                className={`${styles.promptButton} ${selectedPromptId === prompt.id ? styles.active : ""}`}
                onClick={() => {
                  setSelectedPromptId(prompt.id);
                  resetSession();
                }}
                disabled={recording}
              >
                <span>{prompt.category}</span>
                <strong>{prompt.question}</strong>
                <small>{prompt.target_duration_seconds}s target</small>
              </button>
            ))}
          </aside>

          <div className={styles.stage}>
            {selectedPrompt ? (
              <section className={styles.questionCard}>
                <div className={styles.questionMeta}>
                  <span>{selectedPrompt.category}</span>
                  <strong>{selectedPrompt.target_duration_seconds}s</strong>
                </div>
                <h2>{selectedPrompt.question}</h2>
                <div className={styles.support}>
                  {selectedPrompt.support.map((item) => <span key={item}>{item}</span>)}
                </div>

                <div className={styles.recorder}>
                  <div className={`${styles.pulse} ${recording ? styles.recording : ""}`} aria-hidden="true" />
                  <div>
                    <span>{recording ? "RECORDING" : recordedBlob ? "RECORDED" : "MICROPHONE READY"}</span>
                    <strong>
                      {recording ? `${recordingSeconds}s` : recordedDurationMs ? `${Math.round(recordedDurationMs / 1000)}s` : "—"}
                    </strong>
                  </div>
                  {!recording ? (
                    <button className="button button-primary" onClick={startRecording} disabled={busy}>
                      {recordedBlob ? "Record again" : "Start recording"}
                    </button>
                  ) : (
                    <button className="button button-accent" onClick={stopRecording}>
                      Stop & keep
                    </button>
                  )}
                </div>

                {recordedUrl ? (
                  <div className={styles.preview}>
                    <audio controls src={recordedUrl} />
                    <button className="button button-accent" onClick={uploadRecording} disabled={busy}>
                      {busy ? "Uploading…" : "Upload & transcribe"}
                    </button>
                  </div>
                ) : null}

                {micUnavailable || !recordedBlob ? (
                  <details className={styles.fallback}>
                    <summary>Can’t speak right now? Use text fallback</summary>
                    <textarea
                      value={transcriptText}
                      onChange={(event) => setTranscriptText(event.target.value)}
                      placeholder="Type the answer you would say in German…"
                      rows={5}
                    />
                    <button
                      className="button"
                      onClick={submitManualTranscript}
                      disabled={busy || !transcriptText.trim()}
                    >
                      Save text practice
                    </button>
                  </details>
                ) : null}
              </section>
            ) : null}

            {attempt ? (
              <section className={styles.resultCard} aria-live="polite">
                <div className={styles.statusRow}>
                  <span>ATTEMPT {attempt.id.slice(0, 8)}</span>
                  <strong>{attempt.status.replaceAll("_", " ")}</strong>
                </div>

                {PENDING_STATES.has(attempt.status) ? (
                  <div className={styles.processing}>
                    <strong>Transcript is processing.</strong>
                    <p>The attempt and audio metadata are already durable. You can leave this screen.</p>
                  </div>
                ) : null}

                {attempt.status === "failed" ? (
                  <div className={styles.failed}>
                    <strong>Transcription failed, not the attempt.</strong>
                    <p>Your audio reference and attempt are preserved. Retry when the provider is healthy.</p>
                    <button className="button button-accent" onClick={retryTranscription} disabled={busy}>
                      Retry transcription
                    </button>
                  </div>
                ) : null}

                {rawTranscript ? (
                  <div className={styles.transcriptPanel}>
                    <div className={styles.panelTitle}>
                      <span>RAW PROVIDER TRANSCRIPT · IMMUTABLE</span>
                      <code>{rawTranscript.provider}/{rawTranscript.model}</code>
                    </div>
                    <p lang="de">{rawTranscript.text}</p>
                  </div>
                ) : null}

                {attempt.transcripts.length ? (
                  <div className={styles.correctionPanel}>
                    <label htmlFor="corrected-transcript">Transcript you want feedback to use</label>
                    <textarea
                      id="corrected-transcript"
                      value={transcriptText}
                      onChange={(event) => setTranscriptText(event.target.value)}
                      rows={6}
                    />
                    {rawTranscript ? (
                      <button className="button" onClick={saveCorrection} disabled={busy || !transcriptText.trim()}>
                        Save correction & re-score
                      </button>
                    ) : null}
                  </div>
                ) : null}

                {feedback ? (
                  <div className={styles.feedback}>
                    <div className={styles.score}>
                      <span>TEXT-LEVEL SCORE</span>
                      <strong>{feedback.overall_score}</strong>
                      <small>pronunciation is intentionally not scored</small>
                    </div>
                    <p>{feedback.summary}</p>
                    <div className={styles.metrics}>
                      <div><span>Words</span><strong>{displayMetric(dimensions.word_count)}</strong></div>
                      <div><span>WPM</span><strong>{displayMetric(dimensions.words_per_minute)}</strong></div>
                      <div><span>Fillers</span><strong>{displayMetric(dimensions.filler_count)}</strong></div>
                      <div><span>Structure</span><strong>{displayMetric(dimensions.structure_signal_score)}</strong></div>
                    </div>
                    {feedback.corrections.length ? (
                      <ul className={styles.corrections}>
                        {feedback.corrections.map((item, index) => (
                          <li key={`${item.code ?? "fix"}-${index}`}>{item.message}</li>
                        ))}
                      </ul>
                    ) : null}
                    <div className={styles.nextAction}>
                      <span>NEXT REP</span>
                      <strong>{feedback.next_action}</strong>
                    </div>
                  </div>
                ) : null}

                <div className={styles.resultActions}>
                  <button className="button button-accent" onClick={resetSession}>New rep</button>
                  {attempt.media && attempt.media.status !== "deleted" ? (
                    <button className="text-button" onClick={deleteAudio} disabled={busy}>
                      Delete raw audio
                    </button>
                  ) : null}
                </div>
              </section>
            ) : null}
          </div>
        </section>
      )}

      {recent.length ? (
        <section className={styles.history}>
          <div>
            <span className="card-kicker">RECENT REPS</span>
            <h2>Evidence, not disposable recordings.</h2>
          </div>
          <div className={styles.historyGrid}>
            {recent.map((item) => (
              <button
                key={item.id}
                className={styles.historyItem}
                onClick={() => {
                  setSelectedPromptId(item.source_key);
                  applyAttempt(item);
                }}
              >
                <span>{item.status.replaceAll("_", " ")}</span>
                <strong>{item.prompt.question ?? item.source_key}</strong>
                <small>{new Date(item.created_at).toLocaleString()}</small>
              </button>
            ))}
          </div>
        </section>
      ) : null}
    </main>
  );
}
