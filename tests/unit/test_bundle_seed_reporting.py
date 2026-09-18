"""build_bundle reports which seed actually produced the bundle.

The retry loop walks seed..seed+4 looking for a clean result and returns
whichever it got. That is reasonable, and it was silent: a caller asking for
seed 1 could be handed seed 5's data for every message with no indication.
Generation is seed-deterministic, so the seed is what makes a bundle
reproducible.
"""
from __future__ import annotations

from generator import bundle as bundle_mod
from generator.bundle import Bundle, build_bundle
from generator.refdata import RefData
from tests.conftest import PACK

RD = RefData(PACK)


def test_bundle_is_still_a_plain_mapping():
    """Every existing caller iterates .items(); that must keep working."""
    b = build_bundle(RD, "ARC", seed=1)
    assert isinstance(b, dict)
    for key, (xml, errs) in b.items():
        assert isinstance(key, str) and isinstance(xml, bytes)
        assert isinstance(errs, list)


def test_clean_bundle_reports_the_requested_seed():
    b = build_bundle(RD, "ARC", seed=1)
    assert b.clean is True
    assert b.seed_used == 1
    assert b.errors == {}


def test_seed_used_reflects_the_retry(monkeypatch):
    """Force the first two seeds to look dirty and check the third is reported."""
    real = bundle_mod.check_errors

    def fake(xml, pack, ctx=None, _state={"n": 0}):
        _state["n"] += 1
        # Fail everything built from the first two candidate seeds.
        return ["synthetic finding"] if _state["n"] <= 12 else real(xml, pack, ctx)

    monkeypatch.setattr(bundle_mod, "check_errors", fake)
    b = build_bundle(RD, "ARC", seed=1)
    assert b.seed_used > 1, "retry happened but seed_used still says 1"
    assert b.clean is True


def test_exhausted_retries_are_reported_not_hidden(monkeypatch):
    monkeypatch.setattr(bundle_mod, "check_errors",
                        lambda xml, pack, ctx=None: ["always dirty"])
    b = build_bundle(RD, "ARC", seed=1, max_retries=3)
    assert b.clean is False, "a bundle that never came clean claims to be clean"
    assert b.seed_used == 3, "should report the last seed tried"
    assert b.errors, "errors property should expose the residual findings"


def test_errors_property_matches_the_messages():
    b = Bundle({"A": (b"<a/>", []), "B": (b"<b/>", ["x"])},
               seed_used=7, clean=False)
    assert b.errors == {"B": ["x"]}
