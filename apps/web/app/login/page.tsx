"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useState } from "react";
import { AuthSplit } from "../../components/auth/AuthSplit";
import { login } from "../../lib/auth";
import { safeNext } from "../../lib/passwordPolicy";
import { ApiError } from "../../lib/types";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login({ email, password });
      router.replace(safeNext(params.get("next")));
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === "network_error") {
          setError("Cannot reach PayIntel AI. Check your connection and try again.");
        } else if (err.status >= 500) {
          setError("Something went wrong on our side. Try again shortly.");
        } else {
          setError(err.message);
        }
      } else {
        setError("Sign in failed.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthSplit>
      <div className="auth-card">
        <h1>Welcome back</h1>
        <p className="auth-sub">Sign in to continue to PayIntel AI.</p>
        <form onSubmit={onSubmit} noValidate>
          <label className="field">
            <span>Email</span>
            <input
              type="email"
              name="email"
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
          <label className="field">
            <span>Password</span>
            <input
              type="password"
              name="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
          {error ? (
            <p className="auth-error" role="alert">
              {error}
            </p>
          ) : null}
          <button className="btn btn-primary auth-submit" type="submit" disabled={busy}>
            {busy ? "Signing in…" : "Sign In"}
          </button>
        </form>
        <p className="auth-links">
          <Link href="/forgot-password">Forgot password?</Link>
        </p>
        <p className="auth-links">
          Don&apos;t have an account? <Link href="/signup">Create account</Link>
        </p>
      </div>
    </AuthSplit>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="auth-boot">Loading sign in…</div>}>
      <LoginForm />
    </Suspense>
  );
}
