from __future__ import annotations

from hashlib import sha256

from payops_core.ml.features import FEATURE_NAMES, FeatureRow


def dataset_version(rows: list[FeatureRow]) -> str:
    if not rows:
        return "payments-empty"
    fails = sum(1 for row in rows if row.failed)
    payload = (
        f"{len(rows)}|{rows[0].created_at.isoformat()}|{rows[-1].created_at.isoformat()}|{fails}"
    )
    return f"payments-{sha256(payload.encode()).hexdigest()[:12]}"


def model_version(algorithm: str, dataset: str, train_rows: int) -> str:
    payload = f"{algorithm}|{dataset}|{','.join(FEATURE_NAMES)}|{train_rows}"
    return f"{algorithm}-{sha256(payload.encode()).hexdigest()[:12]}"
