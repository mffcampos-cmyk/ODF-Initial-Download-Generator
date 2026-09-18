"""Non-ARC disciplines must derive participants and schedule from the
Common Codes tables (EVENT / EVENT_UNIT / LOCATION), not from the old
3-random-unit / 6-participant placeholder dataset."""
from lxml import etree

from generator.builders import partic, schedule
from generator.dataset import build_dataset
from generator.refdata import RefData
from tests.conftest import PACK


def rd():
    return RefData(PACK)


def _expected_units(discipline):
    """Scheduled competitive event units for the discipline, per EVENT_UNIT."""
    table = PACK.codes.table("EVENT_UNIT")
    out = []
    for code, row in table._rows.items():
        f = row.fields
        if (f.get("Discipline") == discipline and f.get("Level") == "Unit"
                and f.get("Schedule") == "Y" and f.get("Phase") != "VICT"
                and f.get("Event") not in ("GEN---------------",
                                           "------------------")):
            out.append(code)
    return out


def test_wst_schedule_units_come_from_event_unit_table():
    expected = set(_expected_units("WST"))
    assert expected, "pack must define WST event units"
    xml = schedule.build(rd(), "WST", seed=1)
    root = etree.fromstring(xml)
    got = {u.get("Code") for u in root.iter("Unit")}
    assert got == expected  # real RSCs, not synthetic random tails


def test_wst_schedule_units_have_names_sessions_and_times():
    xml = schedule.build(rd(), "WST", seed=1)
    root = etree.fromstring(xml)
    sessions = list(root.iter("Session"))
    assert sessions
    session_codes = {s.get("SessionCode") for s in sessions}
    for u in root.iter("Unit"):
        assert u.get("SessionCode") in session_codes
        assert u.get("StartDate") and u.get("EndDate")
        assert u.find("ItemName").get("Value") not in ("", "Round")


def test_wst_athlete_count_derived_from_event_structure():
    # WST: 4 individual events (M/W Changquan & Taijiquan Combined) with no
    # bracket phase -> default 8 entrants each = 32 athletes.
    ds = build_dataset(rd(), "WST", seed=1)
    athletes = [p for p in ds.participants if not p.is_official]
    assert len(athletes) == 32
    officials = [p for p in ds.participants if p.is_official]
    assert officials  # coaches/judges present


def test_jud_athletes_match_bracket_size():
    # JUD: 8 weight classes, each with an R32 bracket (16 matches) -> 32
    # entrants per event = 256 athletes.
    ds = build_dataset(rd(), "JUD", seed=1)
    athletes = [p for p in ds.participants if not p.is_official]
    assert len(athletes) == 256


def test_partic_counts_flow_through_to_message():
    xml = partic.build(rd(), "WST", seed=1)
    root = etree.fromstring(xml)
    ps = list(root.iter("Participant"))
    athletes = [p for p in ps if p.get("MainFunctionId") == "AA01"]
    assert len(athletes) == 32
    for p in ps:
        assert p.get("Parent") == p.get("Code")
