from __future__ import annotations

import json
import os
from typing import Any

from payops_core.config import get_settings


class LLMClient:
    def complete_json(self, system: str, user: str, schema_hint: str) -> dict[str, Any]:
        raise NotImplementedError


class DemoLLM(LLMClient):
    """Deterministic, tool-grounded planner/writer used when no API key is set."""

    def complete_json(self, system: str, user: str, schema_hint: str) -> dict[str, Any]:
        payload = json.loads(user) if user.strip().startswith("{") else {"text": user}
        hint = schema_hint.lower()
        if "investigationplan" in hint:
            return self._plan(payload)
        if "sufficiencyverdict" in hint:
            return self._sufficiency(payload)
        if "hypothesis" in hint:
            return self._hypotheses(payload)
        if "verifiedclaim" in hint:
            return self._verify(payload)
        if "critiqueresult" in hint:
            return self._critique(payload)
        if "incidentreport" in hint:
            return self._report(payload)
        return {"ok": True}

    def _plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        question = payload.get("question", "")
        merchant_id = payload.get("merchant_id")
        window = payload.get("time_window")
        tasks = [
            {
                "task_id": "t1",
                "task_type": "retrieve_docs",
                "rationale": "Collect policy and failure-code context.",
                "query": question,
                "merchant_id": merchant_id,
                "evidence_category": "docs",
            },
            {
                "task_id": "t2",
                "task_type": "query_metrics",
                "rationale": "Measure success/failure in the window.",
                "query": question,
                "merchant_id": merchant_id,
                "evidence_category": "metrics",
            },
        ]
        if "webhook" in question.lower() or merchant_id == "M201":
            tasks.append(
                {
                    "task_id": "t3",
                    "task_type": "inspect_webhooks",
                    "rationale": "Check delivery delays that can look like payment failures.",
                    "query": question,
                    "merchant_id": merchant_id,
                    "evidence_category": "webhooks",
                }
            )
        if merchant_id == "M102":
            tasks[1]["method_id"] = "upi"
        return {
            "goal": question,
            "merchant_id": merchant_id,
            "time_window": window,
            "tasks": tasks,
        }

    def _sufficiency(self, payload: dict[str, Any]) -> dict[str, Any]:
        items = payload.get("evidence", {}).get("items", [])
        merchant_id = payload.get("merchant_id")
        has_metric = any(i.get("source") == "metric" for i in items)
        has_doc = any(i.get("source") == "doc" for i in items)
        has_webhook = any(i.get("source") == "webhook" for i in items)
        if merchant_id == "M305":
            return {
                "sufficient": False,
                "missing": [
                    {
                        "description": "Volume is too low to support a confident cause.",
                        "next_task_type": "query_metrics",
                        "suggested_query": "Need more payments in window",
                    }
                ],
                "next_action": "stop_incomplete",
                "reason": "Sparse merchant has insufficient evidence by design.",
            }
        if merchant_id == "M201" and not has_webhook:
            return {
                "sufficient": False,
                "missing": [
                    {
                        "description": "Webhook delivery metrics are missing.",
                        "next_task_type": "inspect_webhooks",
                        "suggested_query": "delivery delays",
                    }
                ],
                "next_action": "refine",
                "reason": "Need webhook inspection before concluding.",
            }
        sufficient = has_metric and has_doc
        return {
            "sufficient": sufficient,
            "missing": []
            if sufficient
            else [
                {
                    "description": "Need both metric and document evidence.",
                    "next_task_type": "retrieve_docs",
                    "suggested_query": payload.get("question"),
                }
            ],
            "next_action": "continue" if sufficient else "refine",
            "reason": "Have docs+metrics" if sufficient else "Missing a required evidence category",
        }

    def _hypotheses(self, payload: dict[str, Any]) -> dict[str, Any]:
        items = payload.get("evidence", {}).get("items", [])
        ids = [i.get("evidence_id") for i in items if i.get("evidence_id")]
        snippets = " ".join(i.get("text_snippet", "") for i in items).lower()
        if "gateway_timeout" in snippets or "upi" in snippets:
            cause = "UPI gateway timeouts at the method processor"
            category = "gateway"
            confidence = 0.86
        elif "webhook" in snippets and "delay" in snippets:
            cause = "Webhook delivery delays after successful capture"
            category = "webhooks"
            confidence = 0.81
        else:
            cause = "No dominant cause identified from current evidence"
            category = "unknown"
            confidence = 0.35
        return {
            "hypotheses": [
                {
                    "cause": cause,
                    "supporting_evidence_ids": ids[:6],
                    "confidence": confidence,
                    "category": category,
                }
            ]
        }

    def _verify(self, payload: dict[str, Any]) -> dict[str, Any]:
        hypothesis = payload.get("hypothesis", {})
        ids = hypothesis.get("supporting_evidence_ids", [])
        return {
            "claims": [
                {
                    "claim": hypothesis.get("cause", ""),
                    "evidence_ids": ids,
                    "supported": bool(ids),
                    "note": None if ids else "Hypothesis has no evidence ids.",
                }
            ]
        }

    def _critique(self, payload: dict[str, Any]) -> dict[str, Any]:
        report = payload.get("report", {})
        if not report.get("evidence_sufficient") and report.get("merchant_id") != "M305":
            return {
                "approved": False,
                "issues": ["Report marks evidence insufficient without exhausting retrieval."],
                "revision_instructions": "State remaining gaps clearly and keep confidence low.",
            }
        return {"approved": True, "issues": [], "revision_instructions": None}

    def _report(self, payload: dict[str, Any]) -> dict[str, Any]:
        merchant_id = payload.get("merchant_id")
        window = payload.get("time_window")
        evidence = payload.get("evidence", {}).get("items", [])
        hypotheses = payload.get("hypotheses", [])
        sufficient = payload.get("sufficient", True)
        lead = hypotheses[0] if hypotheses else {
            "cause": "Insufficient evidence to name a cause",
            "supporting_evidence_ids": [],
            "confidence": 0.2,
            "category": "unknown",
        }
        refs = [
            {
                "evidence_id": item.get("evidence_id"),
                "source": item.get("source"),
                "label": item.get("doc_id") or item.get("source"),
            }
            for item in evidence[:12]
        ]
        severity = "low"
        if lead.get("category") == "gateway":
            severity = "high"
        elif lead.get("category") == "webhooks":
            severity = "medium"
        findings = [item.get("text_snippet", "")[:240] for item in evidence[:5]]
        actions = [
            "Page the method processor if gateway timeouts remain elevated.",
            "Publish a merchant status note with the affected method and window.",
            "Keep the investigation open until success rate recovers.",
        ]
        if not sufficient:
            actions = [
                "Do not declare a root cause.",
                "Request a wider time window or additional logs.",
                "Re-run the investigation when more payments exist.",
            ]
        return {
            "executive_summary": (
                f"Investigation for {merchant_id or 'unknown merchant'}: {lead.get('cause')}. "
                f"Evidence sufficient: {sufficient}."
            ),
            "merchant_id": merchant_id,
            "incident_id": f"INV-{merchant_id or 'UNK'}",
            "time_window": window,
            "severity": severity if sufficient else "low",
            "observed_metrics": payload.get("metrics", []),
            "findings": findings or ["No findings beyond the current evidence bundle."],
            "evidence": refs,
            "likely_cause": lead,
            "alternative_hypotheses": hypotheses[1:],
            "confidence": lead.get("confidence", 0.2) if sufficient else min(lead.get("confidence", 0.2), 0.35),
            "recommended_actions": actions,
            "sources": refs,
            "agent_execution_summary": [],
            "evidence_sufficient": sufficient,
        }


class OpenAILLM(LLMClient):
    def __init__(self, model: str) -> None:
        from openai import OpenAI

        self.model = model
        self.client = OpenAI()

    def complete_json(self, system: str, user: str, schema_hint: str) -> dict[str, Any]:
        response = self.client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": f"{system}\nReturn JSON matching {schema_hint}. Cite only evidence ids you were given.",
                },
                {"role": "user", "content": user},
            ],
            temperature=0,
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)


def get_llm() -> LLMClient:
    settings = get_settings()
    provider = settings.llm_provider.lower()
    if provider == "openai" and os.getenv("OPENAI_API_KEY"):
        return OpenAILLM(settings.llm_model)
    return DemoLLM()
