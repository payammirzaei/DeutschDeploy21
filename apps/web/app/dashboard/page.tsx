"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api } from "@/src/lib/api";

type User = { id: string; email: string };
type Job = {
  id: string;
  job_type: string;
  status: string;
  attempt_count: number;
  result: Record<string, unknown> | null;
  error_code: string | null;
};
type ReviewSummary = {
  due_count: number;
  scheduled_count: number;
  weak_count: number;
  mastered_count: number;
};

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [review, setReview] = useState<ReviewSummary | null>(null);
  const [running, setRunning] = useState(false);
  const [system, setSystem] = useState<"checking" | "ready" | "degraded">("checking");

  useEffect(() => {
    let cancelled = false;

    Promise.all([
      api.GET("/api/v1/auth/me"),
      api.GET("/api/v1/health/ready"),
      api.GET("/api/v1/review/home"),
    ])
      .then(([{ data: me, response: meResponse }, { data: health }, { data: reviewData }]) => {
        if (cancelled) return;
        if (meResponse.status === 401) {
          router.replace("/login");
          return;
        }
        if (me) setUser(me as User);
        if (reviewData) setReview(reviewData as ReviewSummary);
        setSystem(health?.status === "ok" ? "ready" : "degraded");
      })
      .catch(() => {
        if (!cancelled) setSystem("degraded");
      });

    return () => {
      cancelled = true;
    };
  }, [router]);

  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status)) return;
    const timer = window.setInterval(async () => {
      const { data } = await api.GET("/api/v1/platform/jobs/{job_id}", {
        params: { path: { job_id: job.id } },
      });
      if (data) {
        const next = data as Job;
        setJob(next);
        if (!["queued", "running"].includes(next.status)) setRunning(false);
      }
    }, 650);
    return () => window.clearInterval(timer);
  }, [job]);

  async function runWorkerCheck() {
    setRunning(true);
    const key = crypto.randomUUID();
    const { data, response } = await api.POST("/api/v1/platform/jobs", {
      params: { header: { "Idempotency-Key": key } },
      body: { message: "Web → API → PostgreSQL → Redis → Worker → PostgreSQL" },
    });
    if (!response.ok || !data) {
      setRunning(false);
      return;
    }
    setJob(data as Job);
  }

  async function logout() {
    await api.POST("/api/v1/auth/logout");
    router.replace("/login");
  }

  return (
    <main className="dashboard-shell">
      <header className="dashboard-header">
        <div className="brand">DD<span>21</span></div>
        <div className="header-right">
          <span className={`status-dot ${system}`} aria-label={`System ${system}`} />
          <button className="text-button" onClick={logout}>Sign out</button>
        </div>
      </header>

      <section className="dashboard-grid">
        <div className="dashboard-main">
          <div className="eyebrow">PHASE 5C · INTERVIEW DRILLS</div>
          <h1>Guten Morgen{user ? ", developer" : ""}.</h1>
          <p className="dashboard-lead">
            Vocabulary is only the raw material. Now train how to structure HR, behavioral,
            technical and architecture answers before the microphone enters the loop.
          </p>

          <article className="check-card">
            <div>
              <span className="card-kicker">INTERVIEW LAB · 18 CURATED DRILLS</span>
              <h2>Build the answer before you have to say it.</h2>
              <p>
                Best-answer decisions, HR ordering, STAR stories, technical explanations,
                architecture sequences and timed recovery phrases train six interview skills silently.
              </p>
            </div>
            <Link className="button button-accent" href="/drills">Open Interview Lab</Link>
          </article>

          <article className="check-card">
            <div>
              <span className="card-kicker">🤫 SILENT MODE · 10 EXERCISE FAMILIES</span>
              <h2>Tap, type, match and build German without saying a word.</h2>
              <p>
                Meaning, active recall, Perfekt, sentence structure, matching, cloze, error spotting
                and phrase building rotate through one commute-friendly practice loop.
              </p>
            </div>
            <Link className="button" href="/practice">Start silent practice</Link>
          </article>

          <article className="check-card">
            <div>
              <span className="card-kicker">SPACED REVIEW · {review?.due_count ?? 0} DUE</span>
              <h2>Review vocabulary and interview structure in one queue.</h2>
              <p>
                {review?.scheduled_count
                  ? `${review.scheduled_count} targets are scheduled, ${review.weak_count} are still learning/review, and ${review.mastered_count} are currently mastered.`
                  : "Your queue is built automatically from submitted learning attempts."}
              </p>
            </div>
            <Link className="button" href="/review">
              {review?.due_count ? "Review now" : "Open mastery"}
            </Link>
          </article>

          <article className="check-card">
            <div>
              <span className="card-kicker">DAYS 1–3</span>
              <h2>Continue the structured learning loop.</h2>
              <p>
                Twenty-one required activities keep curriculum progress separate from unlimited
                optional practice and interview drills, so commute sessions never fake course completion.
              </p>
            </div>
            <Link className="button" href="/learn">Continue learning</Link>
          </article>

          <article className="check-card">
            <div>
              <span className="card-kicker">CONTENT CATALOG</span>
              <h2>Browse the versioned 100-verb foundation.</h2>
              <p>
                Search German interview verbs, Persian and English meanings, Perfekt forms and
                interview-focused examples. Published content remains immutable under historical evidence.
              </p>
            </div>
            <Link className="button" href="/catalog">Open catalog</Link>
          </article>

          <article className="check-card">
            <div>
              <span className="card-kicker">PLATFORM PROOF</span>
              <h2>The durable worker path remains testable.</h2>
              <p>
                Browser → API → PostgreSQL → Redis → worker → PostgreSQL remains available as an
                operational smoke test while the learning product grows.
              </p>
            </div>
            <button className="button" onClick={runWorkerCheck} disabled={running}>
              {running ? "Running…" : "Run platform check"}
            </button>
          </article>

          {job ? (
            <article className="job-result" aria-live="polite">
              <div className="job-row"><span>Status</span><strong>{job.status}</strong></div>
              <div className="job-row"><span>Attempts</span><strong>{job.attempt_count}</strong></div>
              <div className="job-row"><span>Job</span><code>{job.id.slice(0, 8)}</code></div>
              {job.result ? <pre>{JSON.stringify(job.result, null, 2)}</pre> : null}
            </article>
          ) : null}
        </div>

        <aside className="phase-card">
          <span className="card-kicker">DELIVERY</span>
          <ol className="phase-list">
            <li className="done"><span>01</span> Platform skeleton</li>
            <li className="done"><span>02</span> Content & publishing</li>
            <li className="done"><span>03</span> Learning loop</li>
            <li className="done"><span>04</span> Mastery & review</li>
            <li className="done"><span>05A</span> Silent engine</li>
            <li className="done"><span>05B</span> Exercise explosion</li>
            <li className="active"><span>05C</span> Interview drills</li>
          </ol>
          <div className="identity-chip">
            <span>Signed in as</span>
            <strong>{user?.email ?? "…"}</strong>
          </div>
        </aside>
      </section>
    </main>
  );
}
