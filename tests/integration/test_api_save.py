from pathlib import Path

from fastapi.testclient import TestClient

import api.app as appmod

client = TestClient(appmod.app)


def test_save_returns_relative_paths(monkeypatch):
    def fake_export(refdata, discipline, seed, *a, **k):
        base = appmod.PROJECT_ROOT / "output" / discipline
        return [base / "DT_PARTIC.xml", base / "DT_PARTIC_TEAMS.xml",
                base / "DT_ENTRIES.xml", base / "DT_SCHEDULE.xml"]

    monkeypatch.setattr(appmod, "export_bundle", fake_export)
    r = client.post("/api/save", json={"discipline": "ARC", "seed": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 4
    assert body["saved"][0] == str(Path("output") / "ARC" / "DT_PARTIC.xml")


def test_save_rejects_unknown_discipline():
    r = client.post("/api/save", json={"discipline": "ZZZ", "seed": 1})
    assert r.status_code == 400


def test_save_reports_validation_errors(monkeypatch):
    def fake_export(refdata, discipline, seed, *a, **k):
        raise ValueError("refusing to export un-clean messages")

    monkeypatch.setattr(appmod, "export_bundle", fake_export)
    r = client.post("/api/save", json={"discipline": "ARC", "seed": 1})
    assert r.status_code == 422
    assert "error" in r.json()
