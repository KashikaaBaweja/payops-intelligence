export type QueryLanguage = "en" | "hi" | "hi-latn";
export type LanguageChoice = "auto" | QueryLanguage;

export const LANGUAGE_OPTIONS: { id: LanguageChoice; label: string }[] = [
  { id: "auto", label: "Auto" },
  { id: "en", label: "English" },
  { id: "hi", label: "Hindi" },
  { id: "hi-latn", label: "Hindi/Hinglish" },
];

const LANGUAGE_LABELS: Record<QueryLanguage, string> = {
  en: "English",
  hi: "Hindi",
  "hi-latn": "Hindi/Hinglish",
};

const DEVANAGARI = /[\u0900-\u097F]/;
const HINGLISH = new Set([
  "ka",
  "ki",
  "ke",
  "hai",
  "hain",
  "tha",
  "thi",
  "kya",
  "kyun",
  "kyon",
  "kitna",
  "kitni",
  "kitne",
  "nahi",
  "nahin",
  "matlab",
  "kyunki",
  "wala",
  "wali",
  "karo",
  "karna",
  "hoga",
  "bhugtan",
  "asafal",
]);
const STRONG_HINGLISH = new Set([
  "kitna",
  "kitni",
  "kitne",
  "kyun",
  "kyon",
  "matlab",
  "kya",
  "bhugtan",
  "asafal",
]);

export function detectQueryLanguage(text: string): QueryLanguage {
  if (DEVANAGARI.test(text || "")) {
    return "hi";
  }
  const tokens = (text || "").toLowerCase().match(/[a-z]+/g) ?? [];
  const hits = tokens.filter((token) => HINGLISH.has(token));
  if (tokens.some((token) => STRONG_HINGLISH.has(token)) || hits.length >= 2) {
    return "hi-latn";
  }
  return "en";
}

export function languageLabel(code: string | null | undefined): string {
  if (code === "hi" || code === "hi-latn" || code === "en") {
    return LANGUAGE_LABELS[code];
  }
  return LANGUAGE_LABELS.en;
}

export function speechRecognitionLang(choice: LanguageChoice, draft = ""): string {
  const resolved = choice === "auto" ? detectQueryLanguage(draft) : choice;
  return resolved === "en" ? "en-IN" : "hi-IN";
}
