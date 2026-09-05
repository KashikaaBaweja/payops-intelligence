"""Hindi/Hinglish and English share the existing investigation graph."""

from payops_core.agents.writer import WriterAgent
from payops_core.models.schemas import EvidenceBundle, SufficiencyVerdict

from tests.integration.test_intelligence_api import api_client as api_client

HINGLISH = "Is transaction ka risk kitna hai?"
ENGLISH = "What is the transaction risk for M102?"


def test_hinglish_voice_keeps_original_query_and_uses_same_pipeline(api_client) -> None:
    voice = api_client.post(
        "/investigations",
        json={
            "query": HINGLISH,
            "input_method": "voice",
            "language": "auto",
            "merchant_id": "M102",
            "max_iterations": 2,
        },
    )
    typed = api_client.post(
        "/investigations",
        json={
            "query": ENGLISH,
            "input_method": "text",
            "merchant_id": "M102",
            "max_iterations": 2,
        },
    )
    assert voice.status_code == 201
    assert typed.status_code == 201
    body = voice.json()
    assert body["question"] == HINGLISH
    assert body["original_query"] == HINGLISH
    assert body["query_language"] == "hi-latn"
    assert body["response_language"] == "hi-latn"
    assert body["retrieval_query"]
    assert body["retrieval_query"] != HINGLISH
    assert HINGLISH in body["retrieval_query"]
    assert body["report"]["original_query"] == HINGLISH
    assert body["report"]["executive_summary"]
    assert HINGLISH in body["report"]["executive_summary"]

    voice_events = api_client.get(f"/investigations/{body['investigation_id']}/trace").json()[
        "events"
    ]
    typed_events = api_client.get(
        f"/investigations/{typed.json()['investigation_id']}/trace"
    ).json()["events"]
    voice_nodes = {event["node"] for event in voice_events}
    typed_nodes = {event["node"] for event in typed_events}
    assert {"planner", "investigate", "writer"} <= voice_nodes
    assert voice_nodes == typed_nodes
    assert "voice" not in voice_nodes
    voice_plan = next(event for event in voice_events if event["action"] == "plan")
    typed_plan = next(event for event in typed_events if event["action"] == "plan")
    assert "score_risk" in voice_plan["decision"]
    assert "score_risk" in typed_plan["decision"]
    language_event = next(event for event in voice_events if event["action"] == "query_language")
    assert language_event["search_query"] == HINGLISH
    assert language_event["decision"] == "hi-latn"


def test_selected_english_answer_does_not_rewrite_hinglish_query(api_client) -> None:
    created = api_client.post(
        "/investigations",
        json={
            "query": HINGLISH,
            "input_method": "voice",
            "language": "en",
            "merchant_id": "M102",
            "max_iterations": 2,
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["question"] == HINGLISH
    assert body["query_language"] == "hi-latn"
    assert body["response_language"] == "en"
    assert "Investigation of" in body["report"]["executive_summary"]


def test_writer_uses_supported_response_language() -> None:
    hindi = WriterAgent().write(
        question=HINGLISH,
        merchant_id="M102",
        window=None,
        evidence=EvidenceBundle(),
        metrics=[],
        hypotheses=[],
        sufficiency=SufficiencyVerdict(sufficient=False),
        claims=[],
        critique=None,
        trace=[],
        response_language="hi-latn",
        query_language="hi-latn",
    )
    assert hindi.original_query == HINGLISH
    assert "Incomplete investigation" in hindi.executive_summary
    assert HINGLISH in hindi.executive_summary
