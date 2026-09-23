from lxml import etree
from generator.builders import schedule
from generator.refdata import RefData
from generator.selfcheck import errors
from tests.conftest import PACK


def test_schedule_validates_clean_for_arc():
    rd = RefData(PACK)
    xml = schedule.build(rd, "ARC", seed=1)
    assert errors(xml, PACK) == []


def test_schedule_has_sessions_units_and_34char_unit_codes():
    rd = RefData(PACK)
    xml = schedule.build(rd, "ARC", seed=1)
    assert b'DocumentType="DT_SCHEDULE"' in xml
    root = etree.fromstring(xml)
    units = list(root.iter("Unit"))
    assert units and all(len(u.get("Code")) == 34 for u in units)




def test_schedule_arc_matches_real_life_profile():
    # ARC uses the embedded real-life profile: 9 sessions, 83 units, and
    # Common Codes venue/location (SAW / AR1).
    rd = RefData(PACK)
    xml = schedule.build(rd, "ARC", seed=1)
    root = etree.fromstring(xml)
    assert len(list(root.iter("Session"))) == 9
    units = list(root.iter("Unit"))
    assert len(units) == 83
    assert {u.get("Venue") for u in units} == {"SAW"}
    assert {u.get("Location") for u in units} == {"AR1"}
    medals = [u.get("Medal") for u in units if u.get("Medal") in ("1", "3")]
    assert sorted(medals) == ["1", "1", "1", "3", "3", "3"]  # 3 gold + 3 bronze matches
