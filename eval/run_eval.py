from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from payops_core.data.db import apply_schema, make_engine
from payops_core.data.synthetic_generator import generate
from payops_core.graph.build_graph import build_graph, initial_state
from payops_core.llm import DemoLLM
from payops_core.models import TimeWindow
from payops_core.rag.vector_store import build_store
from payops_core.tools.sql_gateway import SqlGateway


def run_eval(path: Path | None = None) -> list[dict]:
    dataset = Path(path or Path(__file__).with_name("dataset.jsonl"))
    engine = make_engine("sqlite:///:memory:")
    apply_schema(engine)
    generate(engine, seed=42)
    build_store()
    graph = build_graph(llm=DemoLLM(), gateway=SqlGateway(engine))
    results = []
    for line in dataset.read_text().splitlines():
        row = json.loads(line)
        window = None
        if row.get("start") and row.get("end"):
            window = TimeWindow(start=datetime.fromisoformat(row["start"]), end=datetime.fromisoformat(row["end"]))
        state = initial_state(row["question"], row.get("merchant_id"), window)
        output = graph.invoke(state)
        report = output["report"]
        expect = row.get("expect", {})
        ok = True
        if "sufficient" in expect and report.evidence_sufficient != expect["sufficient"]:
            ok = False
        if expect.get("cause_contains") and expect["cause_contains"].lower() not in report.likely_cause.cause.lower():
            ok = False
        results.append(
            {
                "id": row["id"],
                "ok": ok,
                "cause": report.likely_cause.cause,
                "sufficient": report.evidence_sufficient,
            }
        )
    return results


if __name__ == "__main__":
    rows = run_eval()
    passed = sum(1 for row in rows if row["ok"])
    print(json.dumps({"passed": passed, "total": len(rows), "rows": rows}, indent=2))
