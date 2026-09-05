"""Voice is an input modality only — same LangGraph path as typed queries."""

from tests.integration.test_intelligence_api import api_client as api_client

QUERY = "What does GATEWAY_TIMEOUT mean?"


def _nodes(events: list[dict]) -> list[str]:
    return [event["node"] for event in events]


def _plan_decisions(events: list[dict]) -> list[str]:
    return [event["decision"] for event in events if event["action"] == "plan"]


def test_typed_query_uses_normal_pipeline(api_client) -> None:
    created = api_client.post(
        "/investigations",
        json={"query": QUERY, "input_method": "text", "max_iterations": 2},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["question"] == QUERY
    assert body["input_method"] == "text"
    assert body["report"]["executive_summary"]
    events = api_client.get(f"/investigations/{body['investigation_id']}/trace").json()["events"]
    assert {"planner", "writer"} <= {event["node"] for event in events}
    accept = next(event for event in events if event["action"] == "accept_query")
    assert accept["node"] == "planner"
    assert accept["search_query"] == QUERY
    assert accept["decision"] == "text"


def test_voice_transcript_uses_same_pipeline(api_client) -> None:
    typed = api_client.post(
        "/investigations",
        json={"question": QUERY, "max_iterations": 2},
    )
    voice = api_client.post(
        "/investigations",
        json={"query": QUERY, "input_method": "voice", "max_iterations": 2},
    )
    assert typed.status_code == 201
    assert voice.status_code == 201
    assert typed.json()["question"] == voice.json()["question"] == QUERY
    assert typed.json()["input_method"] == "text"
    assert voice.json()["input_method"] == "voice"
    typed_events = api_client.get(
        f"/investigations/{typed.json()['investigation_id']}/trace"
    ).json()["events"]
    voice_events = api_client.get(
        f"/investigations/{voice.json()['investigation_id']}/trace"
    ).json()["events"]
    assert _nodes(typed_events) == _nodes(voice_events)
    assert _plan_decisions(typed_events) == _plan_decisions(voice_events)
    voice_accept = [event for event in voice_events if event["action"] == "accept_query"]
    assert voice_accept and voice_accept[0]["decision"] == "voice"
    assert "voice" not in {event["node"] for event in voice_events}


def test_edited_voice_transcript_sends_edited_query(api_client) -> None:
    edited = "Why did settlement delays increase for merchants in the last quarter?"
    created = api_client.post(
        "/investigations",
        json={"query": edited, "input_method": "voice", "max_iterations": 2},
    )
    assert created.status_code == 201
    assert created.json()["question"] == edited
    assert created.json()["input_method"] == "voice"
    events = api_client.get(f"/investigations/{created.json()['investigation_id']}/trace").json()[
        "events"
    ]
    accept = next(event for event in events if event["action"] == "accept_query")
    assert accept["search_query"] == edited
    plan = next(event for event in events if event["action"] == "plan")
    assert plan["search_query"] == edited


def test_empty_transcript_does_not_start_investigation(api_client) -> None:
    before = api_client.get("/investigations").json()["total"]
    empty = api_client.post("/investigations", json={"query": "", "input_method": "voice"})
    blank = api_client.post("/investigations", json={"query": "  ", "input_method": "voice"})
    short = api_client.post("/investigations", json={"query": "no", "input_method": "voice"})
    assert empty.status_code == 422
    assert blank.status_code == 422
    assert short.status_code == 422
    after = api_client.get("/investigations").json()["total"]
    assert after == before
