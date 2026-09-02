"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { api } from "@/src/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);

    const { response } = await api.POST("/api/v1/auth/login", {
      body: { email, password },
    });

    setPending(false);
    if (!response.ok) {
      setError("That email or password did not work.");
      return;
    }
    router.replace("/dashboard");
  }

  return (
    <main className="auth-shell">
      <Link href="/" className="brand auth-brand" aria-label="DeutschDeploy21 home">
        DD<span>21</span>
      </Link>
      <section className="auth-card">
        <div className="eyebrow">PRIVATE WORKSPACE</div>
        <h1>Welcome back.</h1>
        <p>Sign in with the bootstrap account configured for your environment.</p>

        <form onSubmit={submit} className="auth-form">
          <label>
            <span>Email</span>
            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <label>
            <span>Password</span>
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          {error ? (
            <div className="form-error" role="alert">
              {error}
            </div>
          ) : null}
          <button className="button button-primary full" disabled={pending} type="submit">
            {pending ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}
