"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { initials } from "../../lib/auth";
import { useAuth } from "../auth/AuthProvider";

export function ProfileMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDoc(event: MouseEvent) {
      if (!wrap.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  if (!user) {
    return null;
  }

  return (
    <div className="profile-menu" ref={wrap}>
      <button
        type="button"
        className="profile-trigger"
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={() => setOpen((value) => !value)}
      >
        <span className="avatar" aria-hidden>
          {initials(user.name)}
        </span>
        <span className="profile-copy">
          <strong>{user.name}</strong>
          <small>{user.email}</small>
        </span>
      </button>
      {open ? (
        <div className="profile-dropdown" role="menu">
          <Link href="/profile" role="menuitem" onClick={() => setOpen(false)}>
            Profile
          </Link>
          <Link href="/settings" role="menuitem" onClick={() => setOpen(false)}>
            Settings
          </Link>
          <Link href="/security" role="menuitem" onClick={() => setOpen(false)}>
            Security
          </Link>
          {user.role === "admin" ? (
            <Link href="/admin" role="menuitem" onClick={() => setOpen(false)}>
              Admin console
            </Link>
          ) : null}
          <button type="button" role="menuitem" onClick={() => void logout()}>
            Logout
          </button>
        </div>
      ) : null}
    </div>
  );
}
