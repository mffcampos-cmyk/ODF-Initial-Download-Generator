"""DT_PARTIC_TEAMS must be emitted exactly for disciplines whose Common
Codes define scheduled team events — not per the validator-rule heuristic.

Regression: has_teams() (rule-based) emitted an *empty* DT_PARTIC_TEAMS for
SWM/ATH/JUD/... (no team events at SYOG2026) and *omitted* the message for
TKW, whose mixed TEAM4 event is scheduled in EVENT_UNIT."""
from lxml import etree

from generator.bundle import build_bundle
from generator.refdata import RefData
from tests.conftest import PACK, REFUSED_DISCIPLINES


def rd():
    return RefData(PACK)


def test_no_teams_message_for_disciplines_without_team_events():
    # SYOG2026 swimming has no relays; athletics/judo/triathlon etc. have no
    # team events either — no DT_PARTIC_TEAMS should be produced.
    for disc in ("SWM", "ATH", "JUD", "TRI"):
        bundle = build_bundle(rd(), disc, seed=1)
        assert "DT_PARTIC_TEAMS" not in bundle, disc


def test_tkw_mixed_team_event_gets_teams_message():
    bundle = build_bundle(rd(), "TKW", seed=1)
    assert "DT_PARTIC_TEAMS" in bundle
    xml, errs = bundle["DT_PARTIC_TEAMS"]
    assert errs == []
    teams = list(etree.fromstring(xml).iter("Team"))
    assert len(teams) == 8  # X TEAM4: default 8 entrant slots


def test_team_disciplines_never_emit_empty_teams_message():
    for disc in rd().disciplines():
        if disc in REFUSED_DISCIPLINES:
            continue
        bundle = build_bundle(rd(), disc, seed=1)
        if "DT_PARTIC_TEAMS" in bundle:
            xml, _errs = bundle["DT_PARTIC_TEAMS"]
            assert list(etree.fromstring(xml).iter("Team")), \
                f"{disc}: DT_PARTIC_TEAMS emitted with zero teams"
