from payops_core.rag.chunking import chunk_document
from payops_core.rag.cleaning import clean_text
from payops_core.rag.enrichment import enrich_chunks
from payops_core.rag.types import ParsedDocument


def test_chunking_is_section_aware() -> None:
    document = ParsedDocument(
        document_id="lifecycle",
        source="docs/corpus/payment-lifecycle.md",
        text=(
            "# Overview\nFirst section body.\n\n"
            "## Failures\nSecond section body about GATEWAY_TIMEOUT."
        ),
        metadata={"doc_type": "api_docs", "product_area": "payments"},
    )
    chunks = chunk_document(document)
    sections = {chunk.section for chunk in chunks}
    assert "Overview" in sections
    assert "Failures" in sections
    failure = next(chunk for chunk in chunks if chunk.section == "Failures")
    assert "GATEWAY_TIMEOUT" in failure.text
    assert failure.document_id == "lifecycle"
    assert failure.source == document.source


def test_chunking_uses_overlap_on_long_sections() -> None:
    body = "alpha " * 400
    document = ParsedDocument(
        document_id="long",
        source="long.txt",
        text=body,
        metadata={"doc_id": "long"},
    )
    chunks = chunk_document(document, target_chars=200, overlap=40)
    assert len(chunks) > 1
    first_body = chunks[0].text.removeprefix("Document\n")
    second_body = chunks[1].text.removeprefix("Document\n")
    assert first_body[-40:] == second_body[:40]


def test_metadata_is_preserved_on_every_chunk(tmp_path) -> None:
    document = ParsedDocument(
        document_id="refund-policy",
        source=str(tmp_path / "refunds.md"),
        text="# Refunds\nRefunds attach to succeeded payments.",
        metadata={
            "doc_id": "refund-policy",
            "doc_type": "refund_policy",
            "product_area": "refunds",
            "version": "2024-06",
        },
    )
    chunks = enrich_chunks(chunk_document(document), source_path=tmp_path / "refunds.md")
    assert chunks
    for index, chunk in enumerate(chunks):
        assert chunk.document_id == "refund-policy"
        assert chunk.source == document.source
        assert chunk.section
        assert chunk.metadata["doc_id"] == "refund-policy"
        assert chunk.metadata["doc_type"] == "refund_policy"
        assert chunk.metadata["product_area"] == "refunds"
        assert chunk.metadata["version"] == "2024-06"
        assert chunk.metadata["section"] == chunk.section
        assert chunk.metadata["filename"] == "refunds.md"
        assert chunk.metadata["chunk_index"] == index


def test_cleaning_strips_boilerplate() -> None:
    cleaned = clean_text("Confidential\n\nRefund policy\n\n\nINTERNAL USE ONLY\n")
    assert cleaned == "Refund policy"
    assert "Confidential" not in cleaned
