from pathlib import Path

from fastapi import APIRouter, Depends
from payops_core.config import Settings
from payops_core.models.api import CorpusDocument, CorpusResponse

from apps.api.deps import get_app_settings, get_current_user

router = APIRouter(tags=["documents"], dependencies=[Depends(get_current_user)])


@router.get(
    "/documents",
    response_model=CorpusResponse,
    summary="Indexed research corpus",
)
def list_documents(settings: Settings = Depends(get_app_settings)) -> CorpusResponse:
    root = Path(settings.corpus_dir)
    documents: list[CorpusDocument] = []
    if root.is_dir():
        for path in sorted(root.iterdir()):
            if not path.is_file() or path.name.startswith("."):
                continue
            documents.append(
                CorpusDocument(
                    document_id=path.stem,
                    name=path.name,
                    kind=path.suffix.lstrip(".") or "text",
                    bytes=path.stat().st_size,
                )
            )
    return CorpusResponse(backend=settings.vector_backend, documents=documents)
