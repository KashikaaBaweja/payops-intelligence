from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from payops_core.rag.retriever import DocumentRetriever


@dataclass
class GraphRuntime:
    retriever: DocumentRetriever
    session: Session
    timeout_seconds: float
    started_at: float

    def expired(self) -> bool:
        return time.monotonic() - self.started_at >= self.timeout_seconds
