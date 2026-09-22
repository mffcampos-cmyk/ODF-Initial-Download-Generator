"""Live-operations realism options, modeled on the real CTO1/AWAARC1 feeds
and extrapolated to every discipline. All default to off — the baseline stays
strictly Common-Codes-driven."""
import math

from lxml import etree

from generator import eventstructure
from generator.builders import entries, partic, schedule
from generator.bundle import build_bundle
from generator.dataset import build_dataset
from generator.overrides import Overrides
from generator.refdata import RefData
from tests.conftest import PACK


def rd():
    return RefData(PACK)


def _entry_counts(msgs):
    return {rsc: len(list(etree.fromstring(xml).iter("Entry")))
            for rsc, xml in msgs}


def _scheduled_unit_codes(discipline: str) -> set[str]:
    """The unit codes Common Codes says belong on a schedule, read from the
    table rather than from eventstructure, so this is a second opinion on the
    same rule and not a restatement of the implementation."""
    table = PACK.codes.table("EVENT_UNIT")
    return {code for code, row in table._rows.items()
            if row.fields.get("Discipline") == discipline
            and row.fields.get("Level") == "Unit"
            and row.fields.get("Schedule") == "Y"
            and row.fields.get("Phase") != "VICT"
            and row.fields.get("Event") not in eventstructure.GEN_EVENTS}


def test_defaults_unchanged_without_options():
    """With every option off, the schedule is exactly what Common Codes marks
    scheduled -- no invented units, none dropped.

    Derived rather than hardcoded, and the reason is on the record. This
    assertion read `== 94` until Common Codes v_2_4, which retired the
    `Schedule = "S"` flag: 463 unit rows carried it (SWM 416, ATH 42, SKB 4,
    ARC 1) and the generator schedules only `Y`, so SWM's heats had never been
    emitted. v_2_4 resolved each row to `Y` or `N` and SWM went from 94 units
    to 492 overnight. A constant could only ever record what the workbook said
    on the day it was written; what this test means is the relationship."""
    expected = _scheduled_unit_codes("SWM")
    assert expected, "no scheduled SWM units in the pack -- check the workbook"
    xml = schedule.build(rd(), "SWM", seed=1)
    emitted = [u.get("Code") for u in etree.fromstring(xml).iter("Unit")]
    assert len(emitted) == len(set(emitted)), "a unit was emitted twice"
    assert set(emitted) == expected


def test_realistic_entries_scale_up_pooled_events():
    ov = Overrides(realistic_entries=True)
    counts = _entry_counts(entries.build_all(rd(), "SWM", seed=1, overrides=ov))
    assert len(counts) == 30
    assert all(24 <= n <= 120 for n in counts.values())
    assert len(set(counts.values())) > 3  # varied, not uniform
    # participant pool grows accordingly
    ds = build_dataset(rd(), "SWM", seed=1, overrides=ov)
    athletes = [p for p in ds.participants if not p.is_official]
    assert len(athletes) > 150


def test_realistic_entries_leave_bracket_events_alone():
    ov = Overrides(realistic_entries=True)
    counts = _entry_counts(entries.build_all(rd(), "JUD", seed=1, overrides=ov))
    assert all(n == 32 for n in counts.values())  # R32 bracket size


def test_seeded_heats_follow_entry_counts():
    from generator import eventstructure
    ov = Overrides(realistic_entries=True, seeded_heats=True)
    counts = _entry_counts(entries.build_all(rd(), "SWM", seed=1, overrides=ov))
    xml = schedule.build(rd(), "SWM", seed=1, overrides=ov)
    root = etree.fromstring(xml)
    table = PACK.codes.table("EVENT_UNIT")._rows
    pool = eventstructure.heat_pool(rd(), "SWM")
    heat_events = {f"SWM{g}{e}"[:22] for (g, e) in pool}
    heats = {}
    for u in root.iter("Unit"):
        code = u.get("Code")
        assert code in table  # real RSCs from the codes, never invented
        if code[22:26] == "HEAT":
            ev = code[:22]
            heats[ev] = heats.get(ev, 0) + 1
    checked = 0
    for rsc, n in counts.items():
        if rsc[:22] not in heat_events:
            continue  # 400m/800m freestyle are timed finals (no heats)
        expected = min(math.ceil(n / 8), 18)  # 18 heat rows defined per event
        assert heats.get(rsc[:22]) == expected, rsc
        checked += 1
    assert checked == 26  # 30 events minus the four timed-final events


def test_victory_ceremonies_added_for_any_discipline():
    for disc, expected in (("SWM", 30), ("WST", 4), ("JUD", 8)):
        ov = Overrides(victory_ceremonies=True)
        xml = schedule.build(rd(), disc, seed=1, overrides=ov)
        root = etree.fromstring(xml)
        vict = [u for u in root.iter("Unit") if u.get("Code")[22:26] == "VICT"]
        assert len(vict) == expected, disc


def test_historical_athletes_added_but_not_entered():
    ov = Overrides(historical_athletes=True)
    xml = partic.build(rd(), "SWM", seed=1, overrides=ov)
    root = etree.fromstring(xml)
    hist = [p for p in root.iter("Participant") if p.get("Status") == "HIS"]
    assert hist
    for p in hist:
        assert p.get("Code").startswith("A")  # spec: historical athlete IDs
        assert int(p.get("BirthDate")[:4]) < 2005
    hist_codes = {p.get("Code") for p in hist}
    for _rsc, exml in entries.build_all(rd(), "SWM", seed=1, overrides=ov):
        for e in etree.fromstring(exml).iter("Entry"):
            assert e.get("Code") not in hist_codes


def test_all_options_bundle_validates_clean():
    ov = Overrides(realistic_entries=True, seeded_heats=True,
                   victory_ceremonies=True, historical_athletes=True)
    for disc in ("SWM", "WST", "ARC", "TKW"):
        bundle = build_bundle(rd(), disc, seed=1, overrides=ov)
        for key, (_xml, errs) in bundle.items():
            assert errs == [], f"{disc}/{key}: {errs[:2]}"
