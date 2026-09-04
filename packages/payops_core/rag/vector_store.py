from pathlib import Path

from payops_core.config import get_settings
from payops_core.rag.pipeline import LexicalStore, chunk_document

_STORE: LexicalStore | None = None


def build_store(corpus_dir: Path | None = None) -> LexicalStore:
    global _STORE
    settings = get_settings()
    directory = corpus_dir or settings.corpus_dir
    store = LexicalStore()
    for path in sorted(directory.glob("*.md")):
        store.add(chunk_document(path))
    persist_path = Path(settings.vector_dir) / "lexical.json"
    store.persist(persist_path)
    _STORE = store
    return store


def get_store() -> LexicalStore:
    global _STORE
    if _STORE is None:
        settings = get_settings()
        persist_path = Path(settings.vector_dir) / "lexical.json"
        if persist_path.exists():
            _STORE = LexicalStore.load(persist_path)
        else:
            _STORE = build_store()
    return _STORE
