import type { ReactNode } from "react";
import Link from "next/link";
import { ArchitectureFlow } from "./ArchitectureFlow";

export function AuthSplit({ children }: { children: ReactNode }) {
  return (
    <div className="auth-shell">
      <section className="auth-brand">
        <Link href="/" className="brand-lockup">
          <span className="mark" aria-hidden>
            PI
          </span>
          <span>
            <strong>PayIntel AI</strong>
            <small>Payment intelligence</small>
          </span>
        </Link>
        <div className="auth-brand-copy">
          <p className="auth-kicker">Intelligence for every payment decision.</p>
          <p className="auth-lede">
            Research payment data, investigate anomalies and turn financial signals into
            explainable decisions.
          </p>
        </div>
        <ArchitectureFlow />
      </section>
      <section className="auth-panel">{children}</section>
    </div>
  );
}
