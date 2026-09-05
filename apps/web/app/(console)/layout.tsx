import type { ReactNode } from "react";
import { AuthProvider } from "../../components/auth/AuthProvider";
import { AppShell } from "../../components/shell/AppShell";

export default function ConsoleLayout({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <AppShell>{children}</AppShell>
    </AuthProvider>
  );
}
