from __future__ import annotations

import re

from payops_core.rag.types import Chunk, ParsedDocument

_HEADING = re.compile(r"^#{1,3} ", re.M)


def chunk_document(
    document: ParsedDocument,
    target_chars: int = 1200,
    overlap: int = 160,
) -> list[Chunk]:
    """Split a parsed document into overlapping, section-aware chunks."""

    sections = _split_sections(document.text)
    chunks: list[Chunk] = []
    for section_index, (title, body) in enumerate(sections):
        parts = _window(body, target_chars, overlap) or [body]
        for part_index, part in enumerate(parts):
            text = f"{title}\n{part}".strip()
            chunk_id = f"{document.document_id}-{section_index}-{part_index}"
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    document_id=document.document_id,
                    source=document.source,
                    section=title,
                    text=text,
                    metadata={**document.metadata, "section_title": title},
                )
            )
    return chunks


def _split_sections(text: str) -> list[tuple[str, str]]:
    if not _HEADING.search(text):
        return [("Document", text.strip())]
    pieces = re.split(r"\n(?=#{1,3} )", text)
    sections: list[tuple[str, str]] = []
    for piece in pieces:
        first, _, rest = piece.strip().partition("\n")
        title = first.lstrip("# ").strip() or "Document"
        sections.append((title, rest.strip() or first))
    return sections


def _window(text: str, target_chars: int, overlap: int) -> list[str]:
    if len(text) <= target_chars:
        return [text] if text else []
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + target_chars, len(text))
        parts.append(text[start:end])
        if end == len(text):
            break
        start = max(end - overlap, start + 1)
    return parts
