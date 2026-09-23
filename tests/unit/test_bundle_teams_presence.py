"""DT_PARTIC_TEAMS is sent for every discipline, as in the real SYOG26 feed
(25 messages, 15 of them empty). It carries teams exactly when the
discipline's entry events include a team event; otherwise it is a bare
OdfBody with no Competition (GEN DD: Competition (0,1))."""
from lxml import etree

from generator import eventstructure
from generator.bundle import build_bundle
from generator.refdata import RefData
from tests.conftest import PACK, REFUSED_DISCIPLINES


def rd():
    return RefData(PACK)


def test_disciplines_without_team_events_send_a_bare_teams_message():
    for disc in ("SWM", "ATH", "JUD", "TRI"):
        xml, errs = build_bundle(rd(), disc, seed=1)["DT_PARTIC_TEAMS"]
        assert errs == [], disc
        assert etree.fromstring(xml).find("Competition") is None, disc


def test_tkw_mixed_team_event_gets_teams_message():
    bundle = build_bundle(rd(), "TKW", seed=1)
    xml, errs = bundle["DT_PARTIC_TEAMS"]
    assert errs == []
    teams = list(etree.fromstring(xml).iter("Team"))
    assert len(teams) == 8  # X TEAM4: default 8 entrant slots


def test_teams_message_has_teams_exactly_when_team_events_exist():
    for disc in rd().disciplines():
        if disc in REFUSED_DISCIPLINES:
            continue
        xml, _errs = build_bundle(rd(), disc, seed=1)["DT_PARTIC_TEAMS"]
        has_teams = bool(list(etree.fromstring(xml).iter("Team")))
        assert has_teams == eventstructure.has_team_events(rd(), disc), disc
