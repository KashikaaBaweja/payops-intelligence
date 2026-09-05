from fastapi import APIRouter, Depends, HTTPException
from payops_core.models.api import ErrorResponse
from payops_core.models.schemas import EvidenceItem

from apps.api.deps import get_current_user, get_store
from apps.api.query import require_id
from apps.api.store import InvestigationStore

router = APIRouter(tags=["evidence"], dependencies=[Depends(get_current_user)])


@router.get(
    "/evidence/{id}",
    response_model=EvidenceItem,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid evidence id"},
        404: {"model": ErrorResponse, "description": "Evidence not found"},
    },
    summary="Get evidence by ID",
    description="Resolve a cited evidence_id from a prior investigation or metrics call.",
)
def get_evidence(
    id: str,
    store: InvestigationStore = Depends(get_store),
) -> EvidenceItem:
    require_id(id, "id")
    item = store.get_evidence(id)
    if item is None:
        raise HTTPException(status_code=404, detail="evidence not found")
    return item
