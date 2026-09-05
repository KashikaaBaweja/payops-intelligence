"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { AuthSplit } from "../../components/auth/AuthSplit";
import { forgotPassword } from "../../lib/auth";
import { ApiError } from "../../lib/types";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body = await forgotPassword(email);
      setMessage(body.message);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not submit the request.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthSplit>
      <div className="auth-card">
        <h1>Reset your password</h1>
        <p className="auth-sub">Enter the email on your PayIntel account.</p>
        <form onSubmit={onSubmit} noValidate>
          <label className="field">
            <span>Email</span>
            <input
              type="email"
              name="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
          {error ? (
            <p className="auth-error" role="alert">
              {error}
            </p>
          ) : null}
          {message ? (
            <p className="auth-success" role="status">
              {message}
            </p>
          ) : null}
          <button className="btn btn-primary auth-submit" type="submit" disabled={busy}>
            {busy ? "Sending…" : "Send reset link"}
          </button>
        </form>
        <p className="auth-links">
          <Link href="/login">Back to sign in</Link>
        </p>
      </div>
    </AuthSplit>
  );
}
