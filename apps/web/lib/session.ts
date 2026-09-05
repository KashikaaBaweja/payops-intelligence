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

export function forgetInvestigation(id?: string | null): void {
  if (typeof window === "undefined") {
    return;
  }
  if (!id || window.localStorage.getItem(KEY) === id) {
    window.localStorage.removeItem(KEY);
  }
}
