"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { AuthSplit } from "../../components/auth/AuthSplit";
import { PasswordRules } from "../../components/auth/PasswordRules";
import { signup } from "../../lib/auth";
import { ApiError } from "../../lib/types";

export default function SignupPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signup({
        name,
        email,
        password,
        confirm_password: confirm,
      });
      router.replace("/dashboard");
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
        setError("Could not create your account.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthSplit>
      <div className="auth-card">
        <h1>Create your PayIntel account</h1>
        <p className="auth-sub">Operator access starts as a standard user.</p>
        <form onSubmit={onSubmit} noValidate>
          <label className="field">
            <span>Full Name</span>
            <input
              type="text"
              name="name"
              autoComplete="name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
            />
          </label>
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
          <label className="field">
            <span>Password</span>
            <input
              type="password"
              name="new-password"
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
          <PasswordRules password={password} />
          <label className="field">
            <span>Confirm Password</span>
            <input
              type="password"
              name="confirm-password"
              autoComplete="new-password"
              value={confirm}
              onChange={(event) => setConfirm(event.target.value)}
              required
            />
          </label>
          {error ? (
            <p className="auth-error" role="alert">
              {error}
            </p>
          ) : null}
          <button className="btn btn-primary auth-submit" type="submit" disabled={busy}>
            {busy ? "Creating account…" : "Create account"}
          </button>
        </form>
        <p className="auth-links">
          Already have an account? <Link href="/login">Sign in</Link>
        </p>
      </div>
    </AuthSplit>
  );
}
