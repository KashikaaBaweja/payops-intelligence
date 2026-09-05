"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useAuth } from "../../../components/auth/AuthProvider";
import { ADMIN_NAV } from "../../../lib/adminNav";

export default function AdminLayout({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const pathname = usePathname();

  if (user && user.role !== "admin") {
    return (
      <section className="panel">
        <div className="panel-hd">Access denied</div>
        <div className="panel-bd">
          <h1 className="page-title">You don’t have access to the admin console.</h1>
          <p className="page-lead">
            This area is restricted to PayIntel administrators. Your account role is {user.role}.
          </p>
          <Link className="btn btn-primary" href="/dashboard" style={{ width: "auto" }}>
            Return to overview
          </Link>
        </div>
      </section>
    );
  }

  return (
    <div className="admin-layout">
      <aside className="admin-side" aria-label="Admin">
        {ADMIN_NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`nav-link ${pathname === item.href ? "active" : ""}`}
          >
            <span>{item.label}</span>
          </Link>
        ))}
      </aside>
      <div className="admin-main">{children}</div>
    </div>
  );
}
