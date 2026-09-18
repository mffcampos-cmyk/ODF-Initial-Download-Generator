import io
import zipfile
from fastapi.testclient import TestClient
from api.app import app

client = TestClient(app)


def test_zip_contains_all_messages():
    r = client.get("/api/generate.zip", params={"discipline": "ARC", "seed": 1})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    names = set(zipfile.ZipFile(io.BytesIO(r.content)).namelist())
    # Singleton documents always present; DT_ENTRIES is one file per event.
    assert {"DT_PARTIC.xml", "DT_PARTIC_TEAMS.xml", "DT_SCHEDULE.xml"} <= names
    assert [n for n in names if n.startswith("DT_ENTRIES_") and n.endswith(".xml")]
    assert all(n.endswith(".xml") for n in names)
