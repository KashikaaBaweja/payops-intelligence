"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { getApiHealth, listInvestigations } from "../../lib/api";
import { NAV } from "../../lib/nav";
import { SAMPLE_QUESTIONS } from "../../lib/format";

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [notesOpen, setNotesOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [environment, setEnvironment] = useState("local");
  const [failedRuns, setFailedRuns] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function ping() {
      try {
        const health = await getApiHealth();
        const runs = await listInvestigations().catch(() => ({ items: [], total: 0 }));
        if (!cancelled) {
          setApiOk(true);
          setEnvironment(health.environment);
          setFailedRuns(runs.items.filter((item) => item.status === "failed").length);
        }
      } catch {
        if (!cancelled) {
          setApiOk(false);
        }
      }
    }
    ping();
    const timer = window.setInterval(ping, 20000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        setNotesOpen(false);
        setQuery("");
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const matches = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (needle.length < 2) {
      return [];
    }
    const navHits = NAV.filter((item) => item.label.toLowerCase().includes(needle));
    const qHits = SAMPLE_QUESTIONS.filter((item) =>
      item.question.toLowerCase().includes(needle),
    );
    return [
      ...navHits.map((item) => ({ href: item.href, label: item.label })),
      ...qHits.map((item) => ({
        href: `/research?q=${encodeURIComponent(item.question)}`,
        label: item.question,
      })),
    ].slice(0, 6);
  }, [query]);

  return (
    <div className="console">
      <aside className={`sidebar ${open ? "open" : ""}`} id="app-nav">
        <Link href="/" className="brand-lockup" onClick={() => setOpen(false)}>
          <span className="mark" aria-hidden>
            PI
          </span>
          <span>
            <strong>PayIntel AI</strong>
            <small>Payment intelligence</small>
          </span>
        </Link>
        <nav aria-label="Product">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`nav-link ${pathname === item.href || pathname.startsWith(`${item.href}/`) ? "active" : ""}`}
              onClick={() => setOpen(false)}
            >
              <span>{item.label}</span>
              <small>{item.hint}</small>
            </Link>
          ))}
        </nav>
      </aside>
      <div className="console-main">
        <header className="console-top">
          <button
            className="btn nav-toggle"
            type="button"
            aria-expanded={open}
            aria-controls="app-nav"
            onClick={() => setOpen((value) => !value)}
          >
            Menu
          </button>
          <label className="search">
            <span className="sr-only">Global search</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search research questions or pages"
              onKeyDown={(event) => {
                if (event.key === "Enter" && matches[0]) {
                  router.push(matches[0].href);
                  setQuery("");
                }
              }}
            />
            {matches.length ? (
              <ul className="search-hits">
                {matches.map((item) => (
                  <li key={item.href + item.label}>
                    <Link href={item.href} onClick={() => setQuery("")}>
                      {item.label}
                    </Link>
                  </li>
                ))}
              </ul>
            ) : null}
          </label>
          <div className="top-meta">
            <div className="note-wrap">
              <button
                className={`chip ${failedRuns ? "warn" : "idle"}`}
                type="button"
                aria-expanded={notesOpen}
                onClick={() => setNotesOpen((value) => !value)}
              >
                {failedRuns} notifications
              </button>
              {notesOpen ? (
                <div className="search-hits note-hits" role="status">
                  {failedRuns
                    ? `${failedRuns} investigation run${failedRuns === 1 ? "" : "s"} failed. Open Reports to inspect.`
                    : "No failed investigation runs in the current store."}
                </div>
              ) : null}
            </div>
            <span className="chip idle">
              <span className={`dot ${apiOk === true ? "ok" : apiOk === false ? "bad" : ""}`} />
              {apiOk === true ? "API live" : apiOk === false ? "API down" : "Checking"}
            </span>
            <span className="chip idle">{environment}</span>
            <span className="chip idle" title="Local demo profile">
              Local operator
            </span>
          </div>
        </header>
        <div className="console-body">{children}</div>
      </div>
      {open ? (
        <button
          className="nav-backdrop"
          type="button"
          aria-label="Close navigation"
          onClick={() => setOpen(false)}
        />
      ) : null}
    </div>
  );
}
