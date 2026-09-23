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




def test_arc_schedule_matches_the_real_feed_shape():
    # ARC schedules through the codes model like every discipline. Its plan
    # matches the real SYOG26 ARC schedule exactly: 91 rows, 75 scheduled.
    rd = RefData(PACK)
    root = etree.fromstring(schedule.build(rd, "ARC", seed=1))
    units = list(root.iter("Unit"))
    assert len(units) == 91
    sched = [u for u in units if u.get("ScheduleStatus") == "SCHEDULED"]
    assert len(sched) == 75
    assert {u.get("Venue") for u in sched} == {"SAW"}
    golds = [u for u in units if u.get("Medal") == "1"]
    bronzes = [u for u in units if u.get("Medal") == "3"]
    assert len(golds) == 3 and len(bronzes) == 3
