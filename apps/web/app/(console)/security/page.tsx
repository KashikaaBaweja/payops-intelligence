"use client";

import { FormEvent, useState } from "react";
import { PasswordRules } from "../../../components/auth/PasswordRules";
import { changePassword } from "../../../lib/auth";
import { ApiError } from "../../../lib/types";

export default function SecurityPage() {
  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      await changePassword({
        current_password: current,
        password,
        confirm_password: confirm,
      });
      setCurrent("");
      setPassword("");
      setConfirm("");
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update password.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1 className="page-title">Security</h1>
      <p className="page-lead">Change your password. Other sessions are signed out.</p>
      <section className="panel">
        <div className="panel-hd">Password</div>
        <div className="panel-bd">
          <form onSubmit={onSubmit}>
            <label className="field">
              <span>Current password</span>
              <input
                type="password"
                autoComplete="current-password"
                value={current}
                onChange={(event) => setCurrent(event.target.value)}
                required
              />
            </label>
            <label className="field">
              <span>New password</span>
              <input
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </label>
            <PasswordRules password={password} />
            <label className="field">
              <span>Confirm new password</span>
              <input
                type="password"
                autoComplete="new-password"
                value={confirm}
                onChange={(event) => setConfirm(event.target.value)}
                required
              />
            </label>
            {error ? <p className="auth-error">{error}</p> : null}
            {saved ? <p className="auth-success">Password updated.</p> : null}
            <button className="btn btn-primary" type="submit" disabled={busy} style={{ width: "auto", marginTop: 16 }}>
              {busy ? "Updating…" : "Update password"}
            </button>
          </form>
        </div>
      </section>
    </>
  );
}
