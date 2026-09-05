"""Query history is transcript metadata only — no audio, and operators can delete it."""

from pathlib import Path

from tests.integration.test_intelligence_api import api_client as api_client

QUERY_VOICE = "Why did settlement delays increase?"
QUERY_TEXT = "Compare merchant failure rates"


def test_history_lists_transcript_method_status_and_duration(api_client) -> None:
    voice = api_client.post(
        "/investigations",
        json={"query": QUERY_VOICE, "input_method": "voice", "max_iterations": 2},
    )
    typed = api_client.post(
        "/investigations",
        json={"query": QUERY_TEXT, "input_method": "text", "max_iterations": 2},
    )
    assert voice.status_code == 201
    assert typed.status_code == 201
    assert voice.json()["duration_ms"] is not None
    assert voice.json()["duration_ms"] >= 0
    assert typed.json()["duration_ms"] is not None

    listed = api_client.get("/investigations").json()
    by_id = {item["investigation_id"]: item for item in listed["items"]}
    voice_row = by_id[voice.json()["investigation_id"]]
    text_row = by_id[typed.json()["investigation_id"]]
    assert voice_row["question"] == QUERY_VOICE
    assert voice_row["input_method"] == "voice"
    assert voice_row["status"] == "completed"
    assert voice_row["created_at"]
    assert voice_row["duration_ms"] >= 0
    assert text_row["question"] == QUERY_TEXT
    assert text_row["input_method"] == "text"
    assert text_row["status"] == "completed"


def test_delete_one_query_removes_persisted_transcript(api_client) -> None:
    created = api_client.post(
        "/investigations",
        json={"query": QUERY_VOICE, "input_method": "voice", "max_iterations": 2},
    )
    investigation_id = created.json()["investigation_id"]
    deleted = api_client.delete(f"/investigations/{investigation_id}")
    assert deleted.status_code == 204
    assert api_client.get(f"/investigations/{investigation_id}").status_code == 404
    remaining = api_client.get("/investigations").json()["items"]
    assert investigation_id not in {item["investigation_id"] for item in remaining}


def test_clear_history_deletes_persisted_queries(api_client) -> None:
    api_client.post(
        "/investigations",
        json={"query": QUERY_VOICE, "input_method": "voice", "max_iterations": 2},
    )
    api_client.post(
        "/investigations",
        json={"query": QUERY_TEXT, "input_method": "text", "max_iterations": 2},
    )
    cleared = api_client.delete("/investigations")
    assert cleared.status_code == 200
    assert cleared.json()["deleted"] >= 2
    empty = api_client.get("/investigations").json()
    assert empty["total"] == 0
    assert empty["items"] == []


def test_query_history_ui_does_not_store_audio() -> None:
    root = Path("apps/web")
    sources = [
        (root / "components/research/QueryHistory.tsx").read_text(),
        (root / "lib/speech.ts").read_text(),
        (root / "lib/session.ts").read_text(),
    ]
    joined = "\n".join(sources)
    assert "MediaRecorder" not in joined
    assert "audio/webm" not in joined
    assert "indexedDB" not in joined.lower()
    assert "Voice Query History" in sources[0]
