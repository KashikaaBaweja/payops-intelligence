"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useState } from "react";
import { AuthSplit } from "../../components/auth/AuthSplit";
import { PasswordRules } from "../../components/auth/PasswordRules";
import { resetPassword } from "../../lib/auth";
import { ApiError } from "../../lib/types";

function ResetForm() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await resetPassword({ token, password, confirm_password: confirm });
      router.replace("/login");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reset the password.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthSplit>
      <div className="auth-card">
        <h1>Choose a new password</h1>
        <p className="auth-sub">The reset link can be used once.</p>
        {!token ? (
          <p className="auth-error" role="alert">
            This reset link is missing a token. Request a new one.
          </p>
        ) : (
          <form onSubmit={onSubmit} noValidate>
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
              {busy ? "Updating…" : "Update password"}
            </button>
          </form>
        )}
        <p className="auth-links">
          <Link href="/login">Back to sign in</Link>
        </p>
      </div>
    </AuthSplit>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="auth-boot">Loading reset form…</div>}>
      <ResetForm />
    </Suspense>
  );
}
