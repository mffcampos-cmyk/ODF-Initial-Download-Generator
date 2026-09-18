from fastapi.testclient import TestClient
from api.app import app

client = TestClient(app)


def test_disciplines_endpoint():
    r = client.get("/api/disciplines")
    assert r.status_code == 200
    assert "ARC" in r.json()["disciplines"]


def test_generate_returns_clean_messages():
    r = client.post("/api/generate", json={"discipline": "ARC", "seed": 1})
    assert r.status_code == 200
    body = r.json()
    msgs = body["messages"]
    keys = set(msgs)
    # The three singleton documents are always present.
    assert {"DT_PARTIC", "DT_PARTIC_TEAMS", "DT_SCHEDULE"} <= keys
    # DT_ENTRIES is a per-event message (DocumentCode = Event RSC), so it is
    # keyed DT_ENTRIES_<event>, never a single flat "DT_ENTRIES".
    assert [k for k in keys if k.startswith("DT_ENTRIES_")]
    assert "DT_ENTRIES" not in keys
    for doc_type, payload in msgs.items():
        assert payload["errors"] == [], f"{doc_type}: {payload['errors']}"
        assert payload["xml"].startswith("<?xml")


def test_index_page_renders_select():
    r = client.get("/")
    assert r.status_code == 200 and "<select" in r.text


def test_generate_rejects_unknown_discipline():
    r = client.post("/api/generate", json={"discipline": "ZZZ", "seed": 1})
    assert r.status_code == 400
