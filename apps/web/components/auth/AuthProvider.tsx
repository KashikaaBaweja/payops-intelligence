"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getMe, logout as logoutRequest, type AuthUser } from "../../lib/auth";
import { ApiError } from "../../lib/types";
import { LoadingState } from "../states/PageState";

type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return value;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const next = await getMe();
    setUser(next);
  }

  useEffect(() => {
    let cancelled = false;
    getMe()
      .then((next) => {
        if (!cancelled) {
          setUser(next);
          setError(null);
        }
      })
      .catch((err) => {
        if (cancelled) {
          return;
        }
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          const next = encodeURIComponent(`${pathname}${window.location.search}`);
          router.replace(`/login?next=${next}`);
          return;
        }
        setError(err instanceof ApiError ? err.message : "Could not verify your session.");
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [pathname, router]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      refresh,
      logout: async () => {
        await logoutRequest();
        setUser(null);
        router.replace("/login");
      },
    }),
    [user, loading, router],
  );

  if (loading) {
    return (
      <div className="auth-boot">
        <LoadingState label="Checking your session…" />
      </div>
    );
  }
  if (error) {
    return (
      <div className="auth-boot">
        <p className="error-box" role="alert">
          {error}
        </p>
      </div>
    );
  }
  if (!user) {
    return (
      <div className="auth-boot">
        <LoadingState label="Redirecting to sign in…" />
      </div>
    );
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
