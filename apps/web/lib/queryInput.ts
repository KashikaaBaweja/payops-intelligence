import { type LanguageChoice } from "./queryLanguage";

export type InputMethod = "text" | "voice";

export type NormalizedQuery = {
  query: string;
  input_method: InputMethod;
  language: LanguageChoice;
};

export const MIN_QUERY_LEN = 3;
export const MAX_QUERY_LEN = 4000;

export function normalizeInputMethod(value: string | null | undefined): InputMethod {
  return value === "voice" ? "voice" : "text";
}

export function normalizeLanguageChoice(value: string | null | undefined): LanguageChoice {
  if (value === "en" || value === "hi" || value === "hi-latn" || value === "auto") {
    return value;
  }
  return "auto";
}

export function normalizeResearchQuery(
  raw: string | null | undefined,
  inputMethod: string = "text",
  language: string = "auto",
): NormalizedQuery | null {
  const query = (raw ?? "").trim();
  if (query.length < MIN_QUERY_LEN || query.length > MAX_QUERY_LEN) {
    return null;
  }
  return {
    query,
    input_method: normalizeInputMethod(inputMethod),
    language: normalizeLanguageChoice(language),
  };
}

export function buildResearchRequest(
  raw: string | null | undefined,
  inputMethod: string = "text",
  merchantId?: string | null,
  maxIterations = 3,
  language: string = "auto",
): {
  query: string;
  input_method: InputMethod;
  language: LanguageChoice;
  merchant_id?: string;
  max_iterations: number;
} | null {
  const normalized = normalizeResearchQuery(raw, inputMethod, language);
  if (!normalized) {
    return null;
  }
  return {
    query: normalized.query,
    input_method: normalized.input_method,
    language: normalized.language,
    max_iterations: maxIterations,
    ...(merchantId ? { merchant_id: merchantId } : {}),
  };
}

export function buildLandingAnalyzeHref(
  raw: string | null | undefined,
  inputMethod: string = "text",
): string | null {
  const normalized = normalizeResearchQuery(raw, inputMethod);
  if (!normalized) {
    return null;
  }
  const params = new URLSearchParams({
    q: normalized.query,
    run: "1",
    input: normalized.input_method,
  });
  return `/research?${params.toString()}`;
}
