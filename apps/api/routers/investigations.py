from datetime import datetime

from fastapi import APIRouter
from payops_core.graph import initial_state
from payops_core.models import TimeWindow
from pydantic import BaseModel

router = APIRouter()


class InvestigateRequest(BaseModel):
    question: str
    merchant_id: str | None = None
    start: datetime | None = None
    end: datetime | None = None


@router.post("/investigations")
def create_investigation(body: InvestigateRequest) -> dict:
    from apps.api.main import get_graph

    window = TimeWindow(start=body.start, end=body.end) if body.start and body.end else None
    state = initial_state(body.question, body.merchant_id, window)
    result = get_graph().invoke(state)
    report = result["report"]
    return {
        "report": report.model_dump(mode="json"),
        "trace": [event.model_dump(mode="json") for event in result.get("trace") or []],
        "evidence": result["evidence"].model_dump(mode="json") if result.get("evidence") else {"items": []},
    }
