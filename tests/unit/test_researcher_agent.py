from pathlib import Path

import pytest
from payops_core.agents import ResearcherAgent
from payops_core.models.schemas import ResearcherResult, RetrievalHit, Task
from payops_core.rag.ingest import ingest_corpus
from payops_core.rag.retriever import DocumentRetriever
from payops_core.rag.vector_store import InMemoryVectorStore

CORPUS = Path(__file__).resolve().parents[2] / "docs" / "corpus"


def _agent() -> ResearcherAgent:
    store, _count = ingest_corpus(CORPUS, store=InMemoryVectorStore())
    return ResearcherAgent(DocumentRetriever(store))


def test_relevant_retrieval() -> None:
    result = _agent().research("What does GATEWAY_TIMEOUT mean for Harbor Retail UPI payments?")
    assert result.queries
    assert result.evidence.items
    combined = " ".join(item.text_snippet for item in result.evidence.items)
    assert "GATEWAY_TIMEOUT" in combined
    assert "answer" not in ResearcherResult.model_fields
    assert "executive_summary" not in ResearcherResult.model_fields


def test_irrelevant_retrieval_is_rejected() -> None:
    hit = RetrievalHit(
        document_id="payment-failures",
        chunk_id="payment-failures-0-0",
        source="docs/corpus/payment-failures.md",
        section="Payment failures",
        text="GATEWAY_TIMEOUT means the method processor did not respond.",
        score=0.91,
        metadata={"doc_id": "payment-failures"},
    )
    agent = ResearcherAgent(_FixedRetriever(hit))
    result = agent.research("How do kubernetes xenon quark diplodocus certificates rotate?")
    assert result.evidence.items == []
    assert result.rejected_count >= 1


def test_multiple_searches_cover_distinct_topics() -> None:
    result = _agent().research(
        "Harbor Retail UPI GATEWAY_TIMEOUT and Cedar Digital Goods webhook delays"
    )
    assert len(result.queries) >= 2
    doc_ids = {item.doc_id for item in result.evidence.items}
    assert "payment-failures" in doc_ids or "error-codes" in doc_ids
    assert "webhook-docs" in doc_ids


def test_no_evidence_when_index_is_empty() -> None:
    agent = ResearcherAgent(DocumentRetriever(InMemoryVectorStore()))
    result = agent.research("What does GATEWAY_TIMEOUT mean?")
    assert result.queries
    assert result.evidence.items == []
    assert agent.research("   ").evidence.items == []


def test_source_references_are_preserved() -> None:
    result = _agent().research("Cedar Digital Goods delayed webhook ACK")
    assert result.evidence.items
    for item in result.evidence.items:
        assert item.source == "doc"
        assert item.doc_id
        assert item.chunk_id
        assert item.section
        assert item.evidence_id == f"doc-{item.chunk_id}"
        assert item.metadata.get("source")
        assert item.metadata["document_id"] == item.doc_id
        assert item.metadata["section"] == item.section


def test_researcher_only_runs_retrieve_docs_tasks() -> None:
    agent = _agent()
    task = Task(
        task_id="t1",
        task_type="retrieve_docs",
        rationale="look up webhook delays",
        query="webhook delayed ACK Cedar Digital Goods",
    )
    result = agent.research("Investigate webhook delays", task=task)
    assert any(query.query == task.query for query in result.queries)
    with pytest.raises(ValueError, match="retrieve_docs"):
        agent.research(
            "success rate",
            task=Task(task_id="t2", task_type="query_metrics", rationale="metrics"),
        )


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
