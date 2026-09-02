"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
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

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [running, setRunning] = useState(false);
  const [system, setSystem] = useState<"checking" | "ready" | "degraded">("checking");

  const load = useCallback(async () => {
    const [{ data: me, response: meResponse }, { data: health }] = await Promise.all([
      api.GET("/api/v1/auth/me"),
      api.GET("/api/v1/health/ready"),
    ]);

    if (meResponse.status === 401) {
      router.replace("/login");
      return;
    }
    if (me) setUser(me as User);
    setSystem(health?.status === "ok" ? "ready" : "degraded");
  }, [router]);

  useEffect(() => {
    void load();
  }, [load]);

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
        <div className="brand">
          DD<span>21</span>
        </div>
        <div className="header-right">
          <span className={`status-dot ${system}`} aria-label={`System ${system}`} />
          <button className="text-button" onClick={logout}>
            Sign out
          </button>
        </div>
      </header>

      <section className="dashboard-grid">
        <div className="dashboard-main">
          <div className="eyebrow">PHASE 1 · PLATFORM SKELETON</div>
          <h1>Guten Morgen{user ? ", developer" : ""}.</h1>
          <p className="dashboard-lead">
            The learning engine comes next. First, prove the foundation can carry it.
          </p>

          <article className="check-card">
            <div>
              <span className="card-kicker">END-TO-END CHECK</span>
              <h2>Run one durable background job.</h2>
              <p>
                This creates an authenticated API write, persists it in PostgreSQL, signals Redis,
                executes in the worker, then reads the durable result back.
              </p>
            </div>
            <button className="button button-accent" onClick={runWorkerCheck} disabled={running}>
              {running ? "Running…" : "Run platform check"}
            </button>
          </article>

          {job ? (
            <article className="job-result" aria-live="polite">
              <div className="job-row">
                <span>Status</span>
                <strong>{job.status}</strong>
              </div>
              <div className="job-row">
                <span>Attempts</span>
                <strong>{job.attempt_count}</strong>
              </div>
              <div className="job-row">
                <span>Job</span>
                <code>{job.id.slice(0, 8)}</code>
              </div>
              {job.result ? <pre>{JSON.stringify(job.result, null, 2)}</pre> : null}
            </article>
          ) : null}
        </div>

        <aside className="phase-card">
          <span className="card-kicker">FOUNDATION</span>
          <ol className="phase-list">
            <li className="done">
              <span>01</span> Product architecture
            </li>
            <li className="active">
              <span>02</span> Platform skeleton
            </li>
            <li>
              <span>03</span> Content & publishing
            </li>
            <li>
              <span>04</span> Learning loop
            </li>
            <li>
              <span>05</span> Mastery & review
            </li>
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
