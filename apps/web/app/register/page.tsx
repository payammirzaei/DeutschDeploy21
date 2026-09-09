"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { api } from "@/src/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setPending(true);
    const { response } = await api.POST("/api/v1/auth/register", {
      body: { email, password },
    });
    setPending(false);

    if (response.status === 409) {
      setError("An account with this email already exists.");
      return;
    }
    if (!response.ok) {
      setError("We could not create your account. Please check your details and try again.");
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
        <div className="eyebrow">CREATE YOUR ACCOUNT</div>
        <h1>Start learning.</h1>
        <p>Create an account with your email and password. No email verification is required.</p>

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
              autoComplete="new-password"
              minLength={8}
              maxLength={128}
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>

          <label>
            <span>Confirm password</span>
            <input
              type="password"
              autoComplete="new-password"
              minLength={8}
              maxLength={128}
              required
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
            />
          </label>

          {error ? (
            <div className="form-error" role="alert">
              {error}
            </div>
          ) : null}

          <button className="button button-primary full" disabled={pending} type="submit">
            {pending ? "Creating account…" : "Create account"}
          </button>
        </form>

        <p className="auth-switch">
          Already have an account? <Link href="/login">Sign in</Link>
        </p>
      </section>
    </main>
  );
}
