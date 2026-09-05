from pathlib import Path

from payops_core.agents import ResearcherAgent
from payops_core.models.schemas import RetrievalHit, SearchQuery
from payops_core.rag.analysis import analyze_query
from payops_core.rag.ingest import ingest_corpus
from payops_core.rag.loop import run_agentic_rag
from payops_core.rag.retriever import DocumentRetriever
from payops_core.rag.vector_store import InMemoryVectorStore

CORPUS = Path(__file__).resolve().parents[2] / "docs" / "corpus"


def _corpus_agent(**kwargs) -> ResearcherAgent:
    store, _count = ingest_corpus(CORPUS, store=InMemoryVectorStore())
    return ResearcherAgent(DocumentRetriever(store), **kwargs)


def _timeout_hit(**kwargs) -> RetrievalHit:
    payload = {
        "document_id": "error-codes",
        "chunk_id": "error-codes-gateway",
        "source": "docs/corpus/error-codes.json",
        "section": "GATEWAY_TIMEOUT",
        "text": "GATEWAY_TIMEOUT means the method processor did not respond.",
        "score": 0.91,
        "metadata": {"doc_id": "error-codes"},
    }
    payload.update(kwargs)
    return RetrievalHit(**payload)


def test_sufficient_evidence_returns_citations_and_latency() -> None:
    result = _corpus_agent().research("What does GATEWAY_TIMEOUT mean?")
    assert result.rag is not None
    assert result.rag.sufficient is True
    assert result.rag.iterations >= 1
    assert result.rag.iterations <= result.rag.max_iterations
    assert result.rag.latency_ms >= 0
    assert result.rag.citations
    assert result.rag.sources_verified is True
    assert "GATEWAY_TIMEOUT" in result.rag.grounded_excerpt
    assert "answer" not in result.model_fields
    assert result.evidence.items


def test_insufficient_evidence_rejects_irrelevant_hits() -> None:
    agent = ResearcherAgent(_FixedRetriever(_timeout_hit()))
    result = agent.research("How do kubernetes xenon quark diplodocus certificates rotate?")
    assert result.evidence.items == []
    assert result.rejected_count >= 1
    assert result.rag is not None
    assert result.rag.sufficient is False
    assert result.rag.rounds
    assert result.rag.rounds[0].decision in {"rewrite", "exhausted", "no_results"}


def test_query_rewriting_after_empty_first_search() -> None:
    hit = _timeout_hit()
    retriever = _ScriptedRetriever([[], [hit]])
    result = ResearcherAgent(retriever).research("What does GATEWAY_TIMEOUT mean?")
    assert result.rag is not None
    assert result.rag.iterations >= 2
    assert any(step.rewritten_from for step in result.rag.rounds)
    assert any(step.decision == "rewrite" for step in result.rag.rounds[:-1])
    assert result.rag.sufficient is True
    assert result.evidence.items
    assert retriever.calls >= 2


def test_maximum_iterations_stops_the_loop() -> None:
    agent = ResearcherAgent(_EmptyRetriever(), max_iterations=2)
    result = agent.research("What does GATEWAY_TIMEOUT mean?")
    assert result.rag is not None
    assert result.rag.iterations == 2
    assert result.rag.max_iterations == 2
    assert result.rag.sufficient is False
    assert result.rag.rounds[-1].decision in {"exhausted", "no_results"}
    assert result.rag.iterations <= result.rag.max_iterations


def test_no_result_retrieval() -> None:
    result = ResearcherAgent(DocumentRetriever(InMemoryVectorStore())).research(
        "What does GATEWAY_TIMEOUT mean?"
    )
    assert result.evidence.items == []
    assert result.rag is not None
    assert result.rag.sufficient is False
    assert any(step.decision == "no_results" for step in result.rag.rounds)
    assert result.rag.grounded_excerpt.startswith("No document evidence")


def test_conflicting_sources_are_flagged_not_resolved() -> None:
    timeout = _timeout_hit()
    funds = RetrievalHit(
        document_id="issuer-declines",
        chunk_id="issuer-declines-0",
        source="docs/corpus/error-codes.json",
        section="INSUFFICIENT_FUNDS",
        text="INSUFFICIENT_FUNDS is an issuer decline, not a processor timeout.",
        score=0.9,
        metadata={"doc_id": "issuer-declines"},
    )
    rag = run_agentic_rag(
        "Compare GATEWAY_TIMEOUT and INSUFFICIENT_FUNDS",
        retrieve=lambda _query, _doc_type: [timeout, funds],
        seed_queries=[
            SearchQuery(query="Compare GATEWAY_TIMEOUT and INSUFFICIENT_FUNDS", rationale="seed")
        ],
        analysis=analyze_query("Compare GATEWAY_TIMEOUT and INSUFFICIENT_FUNDS"),
        max_iterations=1,
    )
    assert rag.conflicting is True
    assert rag.conflict_note
    assert "GATEWAY_TIMEOUT" in rag.conflict_note
    assert rag.sufficient is False
    assert rag.citations
    assert "unresolved" in rag.grounded_excerpt.lower()


class _FixedRetriever:
    def __init__(self, hit: RetrievalHit) -> None:
        self.hit = hit

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        doc_type: str | None = None,
    ) -> list[RetrievalHit]:
        if not query.strip():
            return []
        return [self.hit]


class _EmptyRetriever:
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        doc_type: str | None = None,
    ) -> list[RetrievalHit]:
        return []


class _ScriptedRetriever:
    def __init__(self, batches: list[list[RetrievalHit]]) -> None:
        self.batches = batches
        self.calls = 0

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        doc_type: str | None = None,
    ) -> list[RetrievalHit]:
        index = min(self.calls, len(self.batches) - 1)
        self.calls += 1
        return list(self.batches[index])
