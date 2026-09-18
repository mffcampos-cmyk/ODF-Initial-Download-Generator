"""Entry-count and seed inputs are bounded, and rejections are readable.

These are loop counts: every unit builds participants and build_bundle retries
up to 5 seeds, so an unbounded value is a resource-exhaustion primitive, not
just a large request. It mattered most on /api/generate.zip, which is a GET --
a cross-origin page can fire it from an <img src> with no preflight and no
need to read the response.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

import api.app as appmod

client = TestClient(appmod.app)

OVER = appmod.MAX_COUNT + 1


def _post(**kw):
    body = {"discipline": "ARC", "seed": 1}
    body.update(kw)
    return client.post("/api/generate", json=body)


def test_counts_above_the_ceiling_are_rejected():
    for field in ("athletes", "teams", "coaches"):
        r = _post(**{field: OVER})
        assert r.status_code == 422, f"{field}={OVER} was accepted"


def test_negative_counts_are_rejected_not_silently_ignored():
    """Overrides.normalize() maps any value < 0 to None, so before this the
    API answered 200 and quietly generated defaults -- a typo produced a
    plausible-looking bundle that ignored the field."""
    for field in ("athletes", "teams", "coaches"):
        r = _post(**{field: -5})
        assert r.status_code == 422, f"{field}=-5 was silently ignored"


def test_seed_is_bounded():
    assert _post(seed=appmod.MAX_SEED + 1).status_code == 422
    assert _post(seed=-1).status_code == 422


def test_zip_endpoint_is_bounded_too():
    """The GET path is the one reachable cross-origin without a preflight."""
    r = client.get("/api/generate.zip",
                   params={"discipline": "ARC", "athletes": OVER})
    assert r.status_code == 422


def test_validation_errors_use_the_client_error_shape():
    """The client reads data.error; FastAPI's native 422 body is
    {"detail": [...]}, which renders as a bare "Error: 422"."""
    r = _post(athletes=OVER)
    body = r.json()
    assert "error" in body, f"expected an 'error' key, got {sorted(body)}"
    assert isinstance(body["error"], str) and body["error"]
    assert "athletes" in body["error"], (
        f"error should name the offending field: {body['error']!r}")


def test_values_at_the_ceiling_are_still_accepted():
    """The bound is a guard, not a new business rule: MAX_COUNT itself is
    valid input and must not 422."""
    r = client.post("/api/generate", json={
        "discipline": "ARC", "seed": 1, "teams": appmod.MAX_COUNT})
    assert r.status_code != 422
