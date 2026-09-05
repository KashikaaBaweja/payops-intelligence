export const ADMIN_NAV = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/users", label: "Users" },
  { href: "/admin/research", label: "Research Runs" },
  { href: "/admin/documents", label: "Documents" },
  { href: "/admin/agents", label: "Agents" },
  { href: "/admin/ml", label: "ML Models" },
  { href: "/admin/transactions", label: "Transactions" },
  { href: "/admin/health", label: "System Health" },
  { href: "/admin/audit", label: "Audit Logs" },
  { href: "/admin/settings", label: "Settings" },
] as const;

export function dash(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  return String(value);
}
