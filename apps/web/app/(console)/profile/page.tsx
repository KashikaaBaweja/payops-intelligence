"use client";

import { FormEvent, useState } from "react";
import { useAuth } from "../../../components/auth/AuthProvider";
import { updateProfile } from "../../../lib/auth";
import { ApiError } from "../../../lib/types";

export default function ProfilePage() {
  const { user, refresh } = useAuth();
  const [name, setName] = useState(user?.name ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      await updateProfile(name);
      await refresh();
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update profile.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1 className="page-title">Profile</h1>
      <p className="page-lead">Account details visible to you. Passwords are never shown here.</p>
      <section className="panel">
        <div className="panel-hd">Operator</div>
        <div className="panel-bd">
          <form onSubmit={onSubmit}>
            <label className="field">
              <span>Full name</span>
              <input value={name} onChange={(event) => setName(event.target.value)} required />
            </label>
            <dl className="kv" style={{ marginTop: 16 }}>
              <dt>Email</dt>
              <dd>{user?.email}</dd>
              <dt>Role</dt>
              <dd>{user?.role}</dd>
              <dt>Status</dt>
              <dd>{user?.status}</dd>
            </dl>
            {error ? <p className="auth-error">{error}</p> : null}
            {saved ? <p className="auth-success">Profile updated.</p> : null}
            <button className="btn btn-primary" type="submit" disabled={busy} style={{ width: "auto", marginTop: 16 }}>
              {busy ? "Saving…" : "Save"}
            </button>
          </form>
        </div>
      </section>
    </>
  );
}
