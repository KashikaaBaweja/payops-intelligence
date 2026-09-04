from pathlib import Path

import pytest
from payops_core.rag.errors import IngestError
from payops_core.rag.ingest import ingest_directory, ingest_file
from payops_core.rag.parsing import parse_file

from tests.helpers import write_simple_pdf

CORPUS = Path(__file__).resolve().parents[2] / "docs" / "corpus"


def test_ingest_corpus_covers_required_topics() -> None:
    chunks = ingest_directory(CORPUS)
    text = " ".join(chunk.text for chunk in chunks).lower()
    for topic in (
        "payment lifecycle",
        "gateway_timeout",
        "refund",
        "settlement",
        "dispute",
        "webhook",
        "error",
        "incident runbook",
    ):
        assert topic in text
    sources = {Path(chunk.source).suffix.lower() for chunk in chunks}
    assert {".md", ".txt", ".json", ".pdf"}.issubset(sources)
    assert chunks


def test_ingest_pdf_preserves_source_metadata(tmp_path: Path) -> None:
    path = tmp_path / "refund-faq.pdf"
    write_simple_pdf(
        path,
        "Refunds attach to succeeded payments and are not a success-rate substitute.",
    )
    chunks = ingest_file(path)
    assert chunks
    chunk = chunks[0]
    assert chunk.document_id == "refund-faq"
    assert chunk.source.endswith("refund-faq.pdf")
    assert chunk.metadata["filename"] == "refund-faq.pdf"
    assert chunk.metadata["doc_type"] == "pdf"
    assert "Refunds" in chunk.text


def test_malformed_documents_raise(tmp_path: Path) -> None:
    empty = tmp_path / "empty.md"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(IngestError, match="Empty document"):
        parse_file(empty)

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not json", encoding="utf-8")
    with pytest.raises(IngestError, match="Malformed JSON"):
        parse_file(bad_json)

    array_json = tmp_path / "array.json"
    array_json.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(IngestError, match="must be an object"):
        parse_file(array_json)

    incomplete_json = tmp_path / "incomplete.json"
    incomplete_json.write_text('{"doc_id": "x"}', encoding="utf-8")
    with pytest.raises(IngestError, match="needs text or sections"):
        parse_file(incomplete_json)

    missing = tmp_path / "missing.md"
    with pytest.raises(IngestError, match="not found"):
        parse_file(missing)

    unsupported = tmp_path / "notes.docx"
    unsupported.write_text("hello", encoding="utf-8")
    with pytest.raises(IngestError, match="Unsupported"):
        parse_file(unsupported)

    garbage_pdf = tmp_path / "garbage.pdf"
    garbage_pdf.write_bytes(b"%PDF-1.4\nthis is not a pdf")
    with pytest.raises(IngestError, match="Malformed PDF|no extractable text"):
        parse_file(garbage_pdf)

    blank_pdf = tmp_path / "blank.pdf"
    write_simple_pdf(blank_pdf, " ")
    with pytest.raises(IngestError, match="no extractable text"):
        parse_file(blank_pdf)


def test_empty_corpus_directory(tmp_path: Path) -> None:
    with pytest.raises(IngestError, match="No ingestible"):
        ingest_directory(tmp_path)
    with pytest.raises(IngestError, match="not found"):
        ingest_directory(tmp_path / "missing")
