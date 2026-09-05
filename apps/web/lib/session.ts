const KEY = "payintel.lastInvestigation";

export function rememberInvestigation(id: string): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(KEY, id);
}

export function lastInvestigationId(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(KEY);
}
