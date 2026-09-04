from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    section: str
    text: str
    metadata: dict


def parse_markdown(path: Path) -> tuple[dict, str]:
    raw = path.read_text()
    meta: dict = {"doc_id": path.stem, "doc_type": "unknown", "product_area": "payments"}
    match = FRONT_MATTER_RE.match(raw)
    body = raw
    if match:
        for line in match.group(1).splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                meta[key.strip()] = value.strip()
        body = raw[match.end() :]
    return meta, body


def chunk_document(path: Path, target_chars: int = 1400) -> list[Chunk]:
    meta, body = parse_markdown(path)
    sections = re.split(r"\n## ", body)
    chunks: list[Chunk] = []
    for index, section in enumerate(sections):
        title, _, rest = section.partition("\n")
        title = title.strip("# ").strip() or meta.get("title") or path.stem
        text = f"{title}\n{rest.strip()}".strip()
        parts = [text[i : i + target_chars] for i in range(0, len(text), target_chars)] or [text]
        for part_index, part in enumerate(parts):
            chunk_id = f"{meta['doc_id']}-{index}-{part_index}"
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    doc_id=meta["doc_id"],
                    section=title,
                    text=part,
                    metadata={**meta, "section_title": title},
                )
            )
    return chunks


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class LexicalStore:
    def __init__(self) -> None:
        self.chunks: list[Chunk] = []
        self.df: dict[str, int] = {}

    def add(self, chunks: list[Chunk]) -> None:
        self.chunks.extend(chunks)
        self.df = {}
        for chunk in self.chunks:
            for token in set(tokenize(chunk.text)):
                self.df[token] = self.df.get(token, 0) + 1

    def search(self, query: str, doc_type: str | None = None, top_k: int = 5) -> list[tuple[Chunk, float]]:
        query_tokens = tokenize(query)
        scored: list[tuple[Chunk, float]] = []
        n_docs = max(len(self.chunks), 1)
        for chunk in self.chunks:
            if doc_type and chunk.metadata.get("doc_type") != doc_type:
                continue
            tf: dict[str, int] = {}
            for token in tokenize(chunk.text):
                tf[token] = tf.get(token, 0) + 1
            score = 0.0
            for token in query_tokens:
                if token not in tf:
                    continue
                idf = math.log((n_docs + 1) / (self.df.get(token, 0) + 1)) + 1
                score += (tf[token] / max(sum(tf.values()), 1)) * idf
            if score > 0:
                scored.append((chunk, round(score, 4)))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]

    def persist(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "chunk_id": c.chunk_id,
                "doc_id": c.doc_id,
                "section": c.section,
                "text": c.text,
                "metadata": c.metadata,
            }
            for c in self.chunks
        ]
        path.write_text(json.dumps(payload))

    @classmethod
    def load(cls, path: Path) -> "LexicalStore":
        store = cls()
        if path.exists():
            rows = json.loads(path.read_text())
            store.add([Chunk(**row) for row in rows])
        return store


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]
