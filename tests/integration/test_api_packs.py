from fastapi.testclient import TestClient

from api.app import app

client = TestClient(app)


def test_packs_endpoint_lists_both_with_readiness():
    r = client.get("/api/packs")
    assert r.status_code == 200
    body = r.json()
    assert body["default"] == "SYOG26"
    by_name = {p["name"]: p for p in body["packs"]}
    assert by_name["SYOG26"]["ready"] is True
    assert "ARC" in by_name["SYOG26"]["disciplines"]
    assert by_name["SOLG28"]["ready"] is False
    assert by_name["SOLG28"]["label"] == "LA 2028"
    assert by_name["SOLG28"]["disciplines"] == []
    assert any("No XSD compiles" in r_ for r_ in by_name["SOLG28"]["reasons"])


def test_generate_against_a_not_ready_pack_returns_409_with_reasons():
    r = client.post("/api/generate",
                    json={"discipline": "ARC", "seed": 1, "pack": "SOLG28"})
    assert r.status_code == 409
    body = r.json()
    assert body["pack"] == "SOLG28"
    assert body["reasons"]
    assert any("Rules/SOLG28" in reason for reason in body["reasons"])


def test_generate_against_an_unknown_pack_returns_400():
    r = client.post("/api/generate",
                    json={"discipline": "ARC", "seed": 1, "pack": "NOPE"})
    assert r.status_code == 400
    assert "SYOG26" in " ".join(r.json()["known"])


def test_generate_defaults_to_syog26_when_pack_is_omitted():
    r = client.post("/api/generate", json={"discipline": "ARC", "seed": 1})
    assert r.status_code == 200
    for payload in r.json()["messages"].values():
        assert payload["errors"] == []


def test_disciplines_endpoint_is_pack_scoped():
    r = client.get("/api/disciplines?pack=SOLG28")
    assert r.status_code == 409
    r = client.get("/api/disciplines?pack=SYOG26")
    assert r.status_code == 200 and "ARC" in r.json()["disciplines"]


def test_zip_endpoint_rejects_a_not_ready_pack():
    r = client.get("/api/generate.zip?discipline=ARC&pack=SOLG28")
    assert r.status_code == 409


# --- ODF_GAMES misconfigured: must never 500 -------------------------------
#
# REGISTRY is built once at import time from the discovered packs on disk,
# but PackRegistry.default_name() reads os.environ["ODF_GAMES"] fresh on
# every call (see generator/packs.py) rather than caching it at discovery
# time. That is what makes it possible to flip ODF_GAMES to a bogus value
# per-test with monkeypatch.setenv and have the already-built REGISTRY pick
# it up immediately, without rebuilding the registry or re-importing the app.

def test_packs_endpoint_survives_bad_odf_games(monkeypatch):
    monkeypatch.setenv("ODF_GAMES", "NOT_A_REAL_PACK")
    r = client.get("/api/packs")
    assert r.status_code == 200
    body = r.json()
    assert body["default"] is None
    assert "NOT_A_REAL_PACK" in body["default_error"]
    # The whole point of this endpoint is to still show an operator what
    # packs exist and why one is or isn't ready, even while ODF_GAMES is bad.
    by_name = {p["name"]: p for p in body["packs"]}
    assert by_name["SYOG26"]["ready"] is True
    assert by_name["SOLG28"]["ready"] is False


def test_disciplines_omitting_pack_with_bad_odf_games_is_clean_4xx(monkeypatch):
    monkeypatch.setenv("ODF_GAMES", "NOT_A_REAL_PACK")
    r = client.get("/api/disciplines")
    assert r.status_code == 400
    body = r.json()
    assert body["pack"] is None
    assert "SYOG26" in body["known"]


def test_generate_omitting_pack_with_bad_odf_games_is_clean_4xx(monkeypatch):
    monkeypatch.setenv("ODF_GAMES", "NOT_A_REAL_PACK")
    r = client.post("/api/generate", json={"discipline": "ARC", "seed": 1})
    assert r.status_code == 400
    assert "NOT_A_REAL_PACK" in r.json()["error"]


def test_save_omitting_pack_with_bad_odf_games_is_clean_4xx(monkeypatch):
    monkeypatch.setenv("ODF_GAMES", "NOT_A_REAL_PACK")
    r = client.post("/api/save", json={"discipline": "ARC", "seed": 1})
    assert r.status_code == 400


def test_zip_omitting_pack_with_bad_odf_games_is_clean_4xx(monkeypatch):
    monkeypatch.setenv("ODF_GAMES", "NOT_A_REAL_PACK")
    r = client.get("/api/generate.zip?discipline=ARC")
    assert r.status_code == 400


def test_disciplines_with_explicit_pack_is_unaffected_by_bad_odf_games(monkeypatch):
    # An explicit ?pack= should resolve normally even while the *default*
    # (ODF_GAMES) is bad, since resolve() never consults default_name() when
    # a pack name was actually given.
    monkeypatch.setenv("ODF_GAMES", "NOT_A_REAL_PACK")
    r = client.get("/api/disciplines?pack=SYOG26")
    assert r.status_code == 200
    assert "ARC" in r.json()["disciplines"]
