# Evaluation

The suite lives in `packages/payops_core/eval/` and `tests/agent_eval/`.

```bash
PYTHONPATH=packages:. payops-eval
# or
PYTHONPATH=packages:. python -m apps.eval
```

It runs ≥25 deterministic investigation questions across documentation-only, SQL, webhook, multi-source, insufficient-evidence, ambiguous, conflicting, and anomaly cases. Metrics: tool selection, unnecessary tool calls, retrieval relevance, evidence grounding, citation correctness, completion, unsupported claims, and loop termination.
