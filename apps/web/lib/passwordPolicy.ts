export type PasswordRule = {
  code: string;
  label: string;
  ok: boolean;
};

const SPECIAL = /[^A-Za-z0-9]/;

export function evaluatePassword(password: string, minLength = 10): PasswordRule[] {
  return [
    { code: "length", label: `Minimum ${minLength} characters`, ok: password.length >= minLength },
    { code: "upper", label: "Uppercase", ok: /[A-Z]/.test(password) },
    { code: "lower", label: "Lowercase", ok: /[a-z]/.test(password) },
    { code: "number", label: "Number", ok: /\d/.test(password) },
    { code: "special", label: "Special character", ok: SPECIAL.test(password) },
  ];
}

export function passwordStrength(password: string, minLength = 10): number {
  return evaluatePassword(password, minLength).filter((rule) => rule.ok).length;
}

export function safeNext(value: string | null | undefined): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("://")) {
    return "/dashboard";
  }
  return value;
}
