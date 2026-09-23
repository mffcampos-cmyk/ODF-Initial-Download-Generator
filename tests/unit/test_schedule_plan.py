"""schedule_plan: which Common Codes rows a DT_SCHEDULE lists, and which of
them are SCHEDULED. Spec: docs/superpowers/specs/2026-09-23-schedule-model-design.md §1.

The real SYOG26 schedule lists every EVENT_UNIT row with Schedule=Y at Unit,
Phase and Medals level. Where a scheduled block (a phase placeholder, a group
parent, JUD's TMRY blocks) covers bouts, the bouts are UNSCHEDULED."""
from __future__ import annotations

from generator import eventstructure
from generator.eventstructure import SCHEDULED, UNSCHEDULED, schedule_plan
from generator.refdata import RefData
from tests.conftest import PACK

RD = RefData(PACK)


def _by_code(discipline):
    return {r.code: r for r in schedule_plan(RD, discipline)}


def _schedule_y_rows(discipline):
    """Read from the table, not from eventstructure: a second opinion."""
    table = PACK.codes.table("EVENT_UNIT")
    return {code for code, row in table._rows.items()
            if row.fields.get("Discipline") == discipline
            and row.fields.get("Level") in ("Unit", "Phase", "Medals")
            and row.fields.get("Schedule") == "Y"
            and row.fields.get("Event") not in eventstructure.GEN_EVENTS}


def test_plan_lists_exactly_the_schedule_y_rows_once():
    for disc in RD.disciplines():
        codes = [r.code for r in schedule_plan(RD, disc)]
        assert len(codes) == len(set(codes)), f"{disc}: a row twice"
        assert set(codes) == _schedule_y_rows(disc), disc


def test_a_phase_with_several_bouts_is_a_scheduled_block_over_them():
    plan = _by_code("FEN")
    block = plan["FENMEPEE--------------8FNL--------"]
    bouts = [r for c, r in plan.items()
             if c.startswith("FENMEPEE--------------8FNL") and r.kind == "bout"]
    assert block.kind == "block" and block.status == SCHEDULED
    assert len(bouts) >= 2 and block.covered_bouts == len(bouts)
    assert {b.status for b in bouts} == {UNSCHEDULED}


def test_a_group_parent_covers_every_group():
    plan = _by_code("TTE")
    parent = plan["TTEMSINGLES-----------GP----------"]
    groups = [r for c, r in plan.items()
              if c.startswith("TTEMSINGLES-----------GP") and r.kind == "bout"]
    assert parent.status == SCHEDULED and parent.covered_bouts == len(groups)
    assert {g.phase for g in groups} >= {"GPA-", "GPH-"}
    assert {g.status for g in groups} == {UNSCHEDULED}


def test_a_single_bout_phase_schedules_the_bout_not_the_block():
    plan = _by_code("ARC")
    assert plan["ARCMINDIVID-----------QUAL--------"].status == UNSCHEDULED
    assert plan["ARCMINDIVID-----------QUAL000100--"].status == SCHEDULED


def test_judo_schedules_its_blocks_and_none_of_its_bouts():
    plan = schedule_plan(RD, "JUD")
    blocks = [r for r in plan if r.kind == "block"]
    bouts = [r for r in plan if r.kind == "bout"]
    assert blocks and all(r.phase == "TMRY" for r in blocks)
    assert {r.status for r in blocks} == {SCHEDULED}
    assert bouts and {r.status for r in bouts} == {UNSCHEDULED}


def test_ceremonies_are_always_scheduled_and_come_last_in_their_event():
    for disc in ("ATH", "SWM", "WST"):
        plan = schedule_plan(RD, disc)
        cer = [r for r in plan if r.kind == "ceremony"]
        assert cer and {r.status for r in cer} == {SCHEDULED}, disc
        for r in cer:
            same = [x for x in plan if x.event_key == r.event_key]
            assert same[-1] is r, f"{disc}: {r.code} is not last in its event"


# Regression pins, taken from schedule_plan on 2026-09-23 against Common
# Codes v_2_4. They are not claims about the real feed (spec §1 lists where
# the rule and the real feed differ). A new workbook may move them: re-derive
# deliberately, never edit a number just to make the test pass.
EXPECTED = {  # discipline: (rows, scheduled)
    "ARC": (91, 75), "ATH": (114, 114), "BDM": (114, 114), "BK3": (42, 42),
    "BKG": (64, 14), "BOX": (180, 120), "BS5": (23, 23), "CRD": (8, 8),
    "EQU": (5, 4), "FBS": (36, 36), "FEN": (468, 48), "GAR": (14, 10),
    "HBB": (50, 50), "JUD": (496, 24), "RCB": (63, 27), "RU7": (42, 42),
    "SAL": (32, 32), "SKB": (8, 8), "SWM": (548, 106), "TKW": (171, 171),
    "TRI": (4, 4), "TTE": (170, 42), "VBV": (110, 110), "WRB": (184, 184),
    "WST": (20, 20),
}


def test_plan_sizes_are_pinned():
    got = {}
    for disc in RD.disciplines():
        plan = schedule_plan(RD, disc)
        got[disc] = (len(plan), sum(r.status == SCHEDULED for r in plan))
    assert got == EXPECTED
