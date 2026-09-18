from generator.builders import partic_teams
from generator.refdata import RefData
from generator.selfcheck import errors
from tests.conftest import PACK


def test_partic_teams_validates_clean_for_arc():
    rd = RefData(PACK)
    xml = partic_teams.build(rd, "ARC", seed=1)
    assert errors(xml, PACK) == []


def test_partic_teams_document_type_and_team_element():
    rd = RefData(PACK)
    xml = partic_teams.build(rd, "ARC", seed=1)
    assert b'DocumentType="DT_PARTIC_TEAMS"' in xml
    assert b"<Team" in xml
