from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from payops_core.rag.errors import IngestError
from payops_core.rag.types import ParsedDocument

FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt", ".json", ".pdf"}


def parse_file(path: Path) -> ParsedDocument:
    if not path.exists():
        raise IngestError(f"Document not found: {path}")
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise IngestError(f"Unsupported document type: {path.suffix}")
    raw = path.read_bytes()
    if not raw.strip():
        raise IngestError(f"Empty document: {path}")
    if suffix in {".md", ".markdown"}:
        return _parse_markdown(path, raw.decode("utf-8", errors="replace"))
    if suffix == ".txt":
        return _parse_text(path, raw.decode("utf-8", errors="replace"))
    if suffix == ".json":
        return _parse_json(path, raw.decode("utf-8", errors="replace"))
    return _parse_pdf(path, raw)


def _base_meta(path: Path) -> dict[str, Any]:
    return {
        "source_path": str(path),
        "filename": path.name,
        "doc_id": path.stem,
        "doc_type": "unknown",
        "product_area": "payments",
    }


def _parse_markdown(path: Path, text: str) -> ParsedDocument:
    meta = _base_meta(path)
    meta["doc_type"] = "markdown"
    body = text
    match = FRONT_MATTER_RE.match(text)
    if match:
        for line in match.group(1).splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                meta[key.strip()] = value.strip()
        body = text[match.end() :]
    if not body.strip():
        raise IngestError(f"Markdown document has no body: {path}")
    document_id = str(meta.get("doc_id") or path.stem)
    return ParsedDocument(document_id=document_id, source=str(path), text=body, metadata=meta)


def _parse_text(path: Path, text: str) -> ParsedDocument:
    meta = _base_meta(path)
    meta["doc_type"] = "txt"
    return ParsedDocument(document_id=path.stem, source=str(path), text=text, metadata=meta)


def _parse_json(path: Path, text: str) -> ParsedDocument:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise IngestError(f"Malformed JSON document: {path}") from exc
    if not isinstance(payload, dict):
        raise IngestError(f"JSON document must be an object: {path}")
    meta = _base_meta(path)
    meta["doc_type"] = str(payload.get("doc_type") or "json")
    if "metadata" in payload and isinstance(payload["metadata"], dict):
        meta.update(payload["metadata"])
    for key in ("doc_id", "title", "product_area", "version"):
        if key in payload:
            meta[key] = payload[key]
    if "sections" in payload:
        if not isinstance(payload["sections"], list):
            raise IngestError(f"JSON sections must be a list: {path}")
        parts: list[str] = []
        for section in payload["sections"]:
            if not isinstance(section, dict) or "text" not in section:
                raise IngestError(f"JSON section missing text: {path}")
            heading = str(section.get("heading") or section.get("title") or "Section")
            parts.append(f"## {heading}\n{section['text']}")
        body = "\n\n".join(parts)
    elif "text" in payload:
        body = str(payload["text"])
    else:
        raise IngestError(f"JSON document needs text or sections: {path}")
    if not body.strip():
        raise IngestError(f"JSON document has no text: {path}")
    document_id = str(meta.get("doc_id") or path.stem)
    return ParsedDocument(document_id=document_id, source=str(path), text=body, metadata=meta)


def _parse_pdf(path: Path, raw: bytes) -> ParsedDocument:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise IngestError("pypdf is required to ingest PDF files") from exc
    try:
        reader = PdfReader(path)
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # noqa: BLE001
        raise IngestError(f"Malformed PDF document: {path}") from exc
    body = "\n\n".join(pages).strip()
    if not body:
        raise IngestError(f"PDF contained no extractable text: {path}")
    meta = _base_meta(path)
    meta["doc_type"] = "pdf"
    meta["page_count"] = len(reader.pages)
    return ParsedDocument(document_id=path.stem, source=str(path), text=body, metadata=meta)
