"use client";

import { useEffect, useState } from "react";
import { ErrorState, LoadingState } from "../../../../components/states/PageState";
import {
  activateUser,
  changeUserRole,
  getAdminUsers,
  suspendUser,
  type AuthUser,
} from "../../../../lib/auth";
import { dash } from "../../../../lib/adminNav";
import { ApiError } from "../../../../lib/types";

function fmt(value: string | null): string {
  return value ? new Date(value).toLocaleString() : "—";
}

export default function AdminUsersPage() {
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [selected, setSelected] = useState<AuthUser | null>(null);

  async function reload() {
    const body = await getAdminUsers();
    setUsers(body.items);
  }

  useEffect(() => {
    reload()
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load users."))
      .finally(() => setLoading(false));
  }, []);

  async function run(id: string, action: () => Promise<AuthUser>) {
    if (!window.confirm("Confirm this account change?")) {
      return;
    }
    setBusyId(id);
    try {
      await action();
      await reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Action failed.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <h1 className="page-title">Users</h1>
      <p className="page-lead">Role and status changes are enforced on the server and written to the audit log.</p>
      {loading ? <LoadingState label="Loading operators…" /> : null}
      {error ? <ErrorState message={error} /> : null}
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Role</th>
              <th>Status</th>
              <th>Created</th>
              <th>Last Active</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((item) => (
              <tr key={item.user_id}>
                <td>{item.name}</td>
                <td>{item.email}</td>
                <td>{item.role}</td>
                <td>{item.status}</td>
                <td>{fmt(item.created_at)}</td>
                <td>{fmt(item.last_active_at)}</td>
                <td>
                  <div className="cta-row" style={{ marginTop: 0 }}>
                    <button className="btn btn-ghost" type="button" onClick={() => setSelected(item)}>
                      View
                    </button>
                    {item.status === "active" ? (
                      <button
                        className="btn btn-ghost"
                        type="button"
                        disabled={busyId === item.user_id}
                        onClick={() => void run(item.user_id, () => suspendUser(item.user_id))}
                      >
                        Suspend
                      </button>
                    ) : (
                      <button
                        className="btn btn-ghost"
                        type="button"
                        disabled={busyId === item.user_id}
                        onClick={() => void run(item.user_id, () => activateUser(item.user_id))}
                      >
                        Activate
                      </button>
                    )}
                    <button
                      className="btn btn-ghost"
                      type="button"
                      disabled={busyId === item.user_id}
                      onClick={() =>
                        void run(item.user_id, () =>
                          changeUserRole(item.user_id, item.role === "admin" ? "user" : "admin"),
                        )
                      }
                    >
                      {item.role === "admin" ? "Make user" : "Make admin"}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {selected ? (
        <section className="panel" style={{ marginTop: 20 }}>
          <div className="panel-hd">User detail</div>
          <div className="panel-bd">
            <dl className="kv">
              <dt>Name</dt>
              <dd>{selected.name}</dd>
              <dt>Email</dt>
              <dd>{selected.email}</dd>
              <dt>Role</dt>
              <dd>{selected.role}</dd>
              <dt>Status</dt>
              <dd>{selected.status}</dd>
              <dt>Created</dt>
              <dd>{fmt(selected.created_at)}</dd>
              <dt>Last login</dt>
              <dd>{dash(fmt(selected.last_login_at))}</dd>
            </dl>
          </div>
        </section>
      ) : null}
    </>
  );
}
