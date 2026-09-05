import type { MetricResult } from "./types";

export const SAMPLE_QUESTIONS = [
  {
    label: "Settlement delays",
    question: "Why did settlement delays increase for merchants in the last quarter?",
    merchant_id: "M102",
  },
  {
    label: "M102 UPI GATEWAY_TIMEOUT",
    question: "Why did Harbor Retail M102 UPI payments fail with GATEWAY_TIMEOUT?",
    merchant_id: "M102",
  },
  {
    label: "Error code meaning",
    question: "What does GATEWAY_TIMEOUT mean?",
    merchant_id: null,
  },
  {
    label: "M201 webhook delays",
    question: "Find delayed webhook events for M201",
    merchant_id: "M201",
  },
  {
    label: "M102 success rate",
    question: "What is the payment success rate for M102?",
    merchant_id: "M102",
  },
  {
    label: "M102 health scorecard",
    question: "Merchant health scorecard for Harbor Retail M102",
    merchant_id: "M102",
  },
  {
    label: "M102 predicted risk",
    question: "What is the predicted payment risk and expected loss for M102?",
    merchant_id: "M102",
  },
  {
    label: "M102 capture latency",
    question: "What is the predicted capture latency for M102?",
    merchant_id: "M102",
  },
  {
    label: "M102 transaction integrity",
    question: "Are Harbor Retail M102 payments transactionally consistent under ACID invariants?",
    merchant_id: "M102",
  },
] as const;

export const MERCHANTS = [
  { id: "M102", name: "Harbor Retail" },
  { id: "M201", name: "Cedar Digital Goods" },
  { id: "M305", name: "Low-volume Labs" },
] as const;

export function merchantFromQuestion(question: string): string | null {
  const match = question.match(/\bM\d{3}\b/i);
  if (match) {
    return match[0].toUpperCase();
  }
  const lowered = question.toLowerCase();
  if (lowered.includes("harbor")) {
    return "M102";
  }
  if (lowered.includes("cedar")) {
    return "M201";
  }
  if (lowered.includes("low-volume")) {
    return "M305";
  }
  return null;
}

export function formatMetricValue(metric: MetricResult): string {
  if (typeof metric.value === "number") {
    if (metric.unit === "ratio") {
      return `${(metric.value * 100).toFixed(1)}%`;
    }
    return metric.value.toLocaleString();
  }
  return JSON.stringify(metric.value);
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) {
    return "—";
  }
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) {
    return iso.replace("T", " ").slice(0, 19);
  }
  return parsed.toISOString().replace("T", " ").slice(0, 19) + " UTC";
}

export function shortId(value: string): string {
  if (value.length <= 12) {
    return value;
  }
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}
