# Schedule Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make DT_SCHEDULE follow the real SYOG26 schedule model. That means
blocks scheduled, the bouts under them UNSCHEDULED, ceremonies always on,
`Medal` on every unit and session medal counts. Everything is derived from
Common Codes.

**Architecture:** A pure `eventstructure.schedule_plan()` decides every row's
kind and status. A new `generator/schedule_layout.py` lays the SCHEDULED rows
into sessions and returns the UNSCHEDULED ones separately. `dataset.py` (the
codes engine and ARC) consumes both, and `builders/schedule.py` serialises
them per spec §3.

**Tech Stack:** Python 3.11+, lxml, pytest, the pinned `odf-validator`.

**Spec:** `docs/superpowers/specs/2026-09-23-schedule-model-design.md`.

## Global Constraints

- **Nothing vendored.** No real-schedule data enters the repository; every
  value is derived from Common Codes.
- **New model is the default.** No option restores the all-SCHEDULED
  schedule.
- **Durations:** bout 13 min, block 30 min, ceremony 5 min.
- **Sessions:** at most 150 min; two a day at 09:30 and 14:00 (UTC+00:00);
  day 1 = 2026-11-01.
- **PhaseType:** `6` for ceremonies, `3` for everything else.
- **`victory_ceremonies`:** stays accepted by API and CLI as a documented
  no-op, and is removed from the web UI.
- **Test environment:** tests need the imported pack in `Rules/SYOG26`
  (Common Codes v_2_4 + 25 DDs). Run them with
  `/home/claude/venv/bin/python -m pytest -q -p no:cacheprovider`.
- **Regression guard:** the full suite must pass at the end of every task.
  Suite at the start: 302 passed.
- **Commits:** author `Marcos <mffcampos@gmail.com>`, with the trailers
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01KaJ7FXU5PU2Vn9C8Rprnei`.

## File map

| File | Responsibility | Change |
|---|---|---|
| `generator/eventstructure.py` | codes → event structure | + `PlannedRow`, `schedule_plan()`, `plan_sort_key()`; − `victory_units()` |
| `generator/schedule_layout.py` | plan → sessions | **new** |
| `generator/model.py` | dataclasses | `ScheduleUnit`/`Session` slimmed, `Dataset.unscheduled` |
| `generator/dataset.py` | datasets | codes engine + ARC use plan+layout; seeded heats on the plan; dead code out |
| `generator/builders/schedule.py` | DT_SCHEDULE XML | §3 attributes and ordering |
| `generator/arc_profile.py` | ARC participants | schedule constants removed |
| `generator/overrides.py`, `generator/export.py`, `api/app.py` | options | no-op documentation |
| `web/templates/index.html`, `web/static/app.js` | UI | checkbox removed |
| tests | — | new `test_schedule_plan.py`, `test_schedule_layout.py`; conformance additions; revisions |
| `README.md`, `samples/` | docs, corpus | updated, regenerated |

---

### Task 1: `schedule_plan()` — which rows, which status

**Files:**
- Modify: `generator/eventstructure.py` (after `victory_units`, before
  `has_team_events`)
- Create: `tests/unit/test_schedule_plan.py`

**Interfaces:**
- Produces:
  - `eventstructure.SCHEDULED = "SCHEDULED"` and
    `eventstructure.UNSCHEDULED = "UNSCHEDULED"`.
  - `@dataclass PlannedRow`, with fields `code, level, kind, status,
    event_key, phase, order, unit_seq, medal, name, covered_bouts`.
    - `kind` is one of `"block"`, `"bout"` or `"ceremony"`.
    - `level` is one of `"Unit"`, `"Phase"` or `"Medals"`.
    - `medal` is one of `""`, `"1"` or `"3"`.
  - `schedule_plan(refdata, discipline) -> list[PlannedRow]`, sorted by
    `plan_sort_key`.
  - `plan_sort_key(row: PlannedRow) -> tuple`.

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_schedule_plan.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/home/claude/venv/bin/python -m pytest -q -p no:cacheprovider tests/unit/test_schedule_plan.py`
Expected: collection ERROR with `ImportError: cannot import name 'SCHEDULED'`.

- [ ] **Step 3: Implement**

In `generator/eventstructure.py`, insert before `def has_team_events`:

```python
SCHEDULED = "SCHEDULED"
UNSCHEDULED = "UNSCHEDULED"
_PLAN_LEVELS = ("Unit", "Phase", "Medals")


@dataclass
class PlannedRow:
    """One row of a discipline's DT_SCHEDULE and whether it gets a slot.

    kind: "block" (a Phase row, or a Unit row with Eventunittype NONE such as
    JUD's TMRY), "bout" (any other Unit row) or "ceremony" (a Medals row)."""
    code: str
    level: str
    kind: str
    status: str
    event_key: tuple[str, str]
    phase: str
    order: int
    unit_seq: int
    medal: str
    name: str
    covered_bouts: int = 0


def plan_sort_key(row: PlannedRow) -> tuple:
    """Event, then codes Order, prelims before finals, unit sequence, code.
    A ceremony sorts after everything else in its event."""
    order = 999 if row.kind == "ceremony" else row.order
    return (row.event_key, order, _phase_rank(row.phase), row.unit_seq,
            row.code)


def _plan_kind(f: dict) -> str:
    if f.get("Level") == "Medals":
        return "ceremony"
    if f.get("Level") == "Phase" or f.get("Eventunittype") == "NONE":
        return "block"
    return "bout"


def schedule_plan(refdata, discipline: str) -> list[PlannedRow]:
    """Every row the discipline's DT_SCHEDULE lists, with its status.

    Rows: EVENT_UNIT rows with Schedule=Y at Level Unit, Phase or Medals,
    outside the GEN events -- exactly what the real SYOG26 schedule lists.

    Status, in this order (spec §1):
    1. ceremonies are SCHEDULED;
    2. a Phase row covering two or more bouts of its event (bouts whose phase
       starts with the Phase row's phase, so GP-- covers GPA-..GPH-) is a
       SCHEDULED block and those bouts are UNSCHEDULED; covering fewer, the
       Phase row is UNSCHEDULED;
    3. in an event with Unit-level blocks (JUD's TMRY), the blocks are
       SCHEDULED and every bout not yet decided is UNSCHEDULED;
    4. every remaining bout is SCHEDULED.
    """
    table = refdata.pack.codes.table("EVENT_UNIT")
    if table is None:
        return []
    rows: list[PlannedRow] = []
    for code, row in table._rows.items():
        f = row.fields
        if (f.get("Discipline") != discipline
                or f.get("Level") not in _PLAN_LEVELS
                or f.get("Schedule") != "Y"
                or f.get("Event") in GEN_EVENTS):
            continue
        u = _row_to_unit(code, f)
        rows.append(PlannedRow(
            code=code, level=f["Level"], kind=_plan_kind(f), status=SCHEDULED,
            event_key=u.event_key, phase=u.phase, order=u.order,
            unit_seq=u.unit_seq, medal=u.medal, name=u.name))

    bouts: dict[tuple[str, str], list[PlannedRow]] = {}
    for r in rows:
        if r.kind == "bout":
            bouts.setdefault(r.event_key, []).append(r)

    decided: set[str] = set()
    for r in rows:
        if r.level != "Phase":
            continue
        tag = r.phase.rstrip("-")
        covered = [b for b in bouts.get(r.event_key, [])
                   if tag and b.phase.startswith(tag)]
        if len(covered) >= 2:
            r.covered_bouts = len(covered)
            for b in covered:
                b.status = UNSCHEDULED
                decided.add(b.code)
        else:
            r.status = UNSCHEDULED

    unit_blocks = {r.event_key for r in rows
                   if r.kind == "block" and r.level == "Unit"}
    for r in rows:
        if r.kind == "block" and r.level == "Unit":
            r.covered_bouts = len(bouts.get(r.event_key, []))
        elif (r.kind == "bout" and r.code not in decided
              and r.event_key in unit_blocks):
            r.status = UNSCHEDULED

    rows.sort(key=plan_sort_key)
    return rows
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `/home/claude/venv/bin/python -m pytest -q -p no:cacheprovider tests/unit/test_schedule_plan.py`
Expected: 7 passed. If `test_plan_sizes_are_pinned` differs, **stop**. Print
`got` and compare it against the spec's measured rule. Do not edit
`EXPECTED` to match.

- [ ] **Step 5: Full suite, then commit**

Run the full suite (expected 309 passed), then:

```bash
git add generator/eventstructure.py tests/unit/test_schedule_plan.py
git commit -m "Plan the schedule the way the real SYOG26 feed lists it" \
  -m "Every Schedule=Y row at Unit, Phase and Medals level; blocks scheduled, the bouts they cover unscheduled; ceremonies always. Not yet used." \
  --trailer "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
  --trailer "Claude-Session: https://claude.ai/code/session_01KaJ7FXU5PU2Vn9C8Rprnei"
```

---

### Task 2: `schedule_layout.lay_out()` — plan to sessions

**Files:**
- Create: `generator/schedule_layout.py`
- Modify: `generator/model.py` (defaults on `ScheduleUnit` and `Session`;
  `Dataset.unscheduled`)
- Create: `tests/unit/test_schedule_layout.py`

**Interfaces:**
- Consumes: `PlannedRow`, `SCHEDULED` and `schedule_plan` (Task 1).
- Produces:
  - `schedule_layout.lay_out(plan, discipline, venue, venue_name, location="",
    location_name="") -> tuple[list[Session], list[ScheduleUnit]]`, returning
    SCHEDULED rows in sessions and the UNSCHEDULED ones in plan order.
  - Constants `MINUTES`, `SESSION_MINUTES`, `SCHEDULE_BASE`,
    `PHASE_TYPE_COMPETITION` and `PHASE_TYPE_MEDAL_CEREMONY`.
  - `Dataset.unscheduled: list[ScheduleUnit]`.

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_schedule_layout.py`:

```python
"""lay_out: SCHEDULED plan rows into sessions, UNSCHEDULED rows aside.
Spec §2: bout 13, block 30, ceremony 5 minutes; sessions at most 150 minutes,
09:30 and 14:00, from 2026-11-01."""
from __future__ import annotations

from datetime import datetime, timedelta

from generator.eventstructure import SCHEDULED, UNSCHEDULED, schedule_plan
from generator.refdata import RefData
from generator.schedule_layout import MINUTES, SESSION_MINUTES, lay_out
from tests.conftest import PACK

RD = RefData(PACK)


def _layout(disc):
    return lay_out(schedule_plan(RD, disc), disc, "V", "Venue", "L", "Loc")


def test_unscheduled_rows_are_set_aside_without_time_or_session():
    plan = schedule_plan(RD, "FEN")
    sessions, unscheduled = lay_out(plan, "FEN", "V", "Venue")
    assert [u.code for u in unscheduled] == \
        [r.code for r in plan if r.status == UNSCHEDULED]
    for u in unscheduled:
        assert u.schedule_status == UNSCHEDULED
        assert not (u.start_date or u.end_date or u.session_code)


def test_every_scheduled_row_gets_a_slot_of_its_kind_length():
    plan = schedule_plan(RD, "SWM")
    sessions, _ = lay_out(plan, "SWM", "V", "Venue")
    laid = [u for s in sessions for u in s.units]
    sched = [r for r in plan if r.status == SCHEDULED]
    assert [u.code for u in laid] == [r.code for r in sched]
    for u, r in zip(laid, sched):
        start = datetime.fromisoformat(u.start_date)
        end = datetime.fromisoformat(u.end_date)
        assert end - start == timedelta(minutes=MINUTES[r.kind]), r.code


def test_sessions_hold_at_most_150_minutes_and_follow_the_day_pattern():
    sessions, _ = _layout("TKW")
    assert len(sessions) > 2
    for i, s in enumerate(sessions):
        start = datetime.fromisoformat(s.start_date)
        end = datetime.fromisoformat(s.end_date)
        assert (end - start) <= timedelta(minutes=SESSION_MINUTES)
        day, half = divmod(i, 2)
        assert start.date().isoformat() == f"2026-11-{1 + day:02d}"
        assert (start.hour, start.minute) == ((9, 30), (14, 0))[half]
        assert s.session_code == f"TKW{i + 1:02d}"
        assert s.units and s.units[-1].end_date == s.end_date


def test_phase_type_and_medal_come_from_the_row():
    sessions, unscheduled = _layout("ATH")
    units = unscheduled + [u for s in sessions for u in s.units]
    cer = [u for u in units if "VICT" in u.code]
    assert cer and {u.phase_type for u in cer} == {"6"}
    assert {u.phase_type for u in units if "VICT" not in u.code} == {"3"}
    assert {u.medal for u in units} <= {"0", "1", "3"}
    assert {u.medal for u in cer} == {"0"}


def test_judo_fits_in_two_days():
    sessions, _ = _layout("JUD")
    days = {s.start_date[:10] for s in sessions}
    assert len(days) <= 2
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/home/claude/venv/bin/python -m pytest -q -p no:cacheprovider tests/unit/test_schedule_layout.py`
Expected: ERROR, `ModuleNotFoundError: No module named 'generator.schedule_layout'`.

- [ ] **Step 3: Make the model accept the slimmer rows**

In `generator/model.py`, replace the `ScheduleUnit` and `Session` dataclasses
and add `unscheduled` to `Dataset`. The old fields stay for now with
defaults, because `dataset.py` still sets them until Task 4:

```python
@dataclass
class ScheduleUnit:
    code: str
    phase_type: str
    schedule_status: str
    medal: str | None = "0"
    start_date: str = ""
    end_date: str = ""
    session_code: str = ""
    item_name: str = "Round"
    sort_order: int = 0          # removed in Task 5
    unit_num: str = ""           # removed in Task 5


@dataclass
class Session:
    venue: str
    venue_name: str
    session_code: str
    start_date: str
    end_date: str
    name: str = ""               # removed in Task 5
    units: list[ScheduleUnit] = field(default_factory=list)
    session_type: str = ""       # removed in Task 5
    location: str = ""
    location_name: str = ""
```

In `Dataset`, add after `entries`:

```python
    unscheduled: list[ScheduleUnit] = field(default_factory=list)
```

- [ ] **Step 4: Create `generator/schedule_layout.py`**

```python
"""Lay a schedule plan out into sessions (spec §2).

Only SCHEDULED rows get a slot. Each takes a fixed length by kind -- a bout
13 minutes, a block 30 (the real SYOG26 median), a ceremony 5 -- and runs
after the previous one. A session holds at most 150 minutes (the real median
span); there are two a day, at 09:30 and 14:00, from 2026-11-01. There are no
parallel lanes: the real feed runs some events side by side (two WRB rings),
so a few disciplines come out longer here than there.

UNSCHEDULED rows are returned separately, in plan order, with no time, venue
or session: that is how the real feed lists them.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .eventstructure import SCHEDULED, PlannedRow
from .model import ScheduleUnit, Session

SCHEDULE_BASE = datetime(2026, 11, 1, tzinfo=timezone.utc)
SESSION_MINUTES = 150
MINUTES = {"bout": 13, "block": 30, "ceremony": 5}
_SESSION_STARTS = ((9, 30), (14, 0))

# CC@PHASE_TYPE: "3" Competition, "6" Medal/Flower Ceremony -- the only two
# the real SYOG26 schedule uses for these rows.
PHASE_TYPE_COMPETITION = "3"
PHASE_TYPE_MEDAL_CEREMONY = "6"


def _session_start(index: int) -> datetime:
    day, half = divmod(index, 2)
    hour, minute = _SESSION_STARTS[half]
    return SCHEDULE_BASE + timedelta(days=day, hours=hour, minutes=minute)


def _unit(row: PlannedRow, start: datetime | None = None,
          end: datetime | None = None, session_code: str = "") -> ScheduleUnit:
    return ScheduleUnit(
        code=row.code,
        phase_type=(PHASE_TYPE_MEDAL_CEREMONY if row.kind == "ceremony"
                    else PHASE_TYPE_COMPETITION),
        schedule_status=row.status,
        medal=row.medal or "0",
        start_date=start.isoformat() if start else "",
        end_date=end.isoformat() if end else "",
        session_code=session_code,
        item_name=row.name,
    )


def lay_out(plan: list[PlannedRow], discipline: str, venue: str,
            venue_name: str, location: str = "", location_name: str = ""
            ) -> tuple[list[Session], list[ScheduleUnit]]:
    unscheduled = [_unit(r) for r in plan if r.status != SCHEDULED]
    sessions: list[Session] = []
    current: Session | None = None
    cursor = SCHEDULE_BASE
    used = 0
    for r in plan:
        if r.status != SCHEDULED:
            continue
        minutes = MINUTES[r.kind]
        if current is None or used + minutes > SESSION_MINUTES:
            start = _session_start(len(sessions))
            current = Session(
                venue=venue, venue_name=venue_name,
                session_code=f"{discipline}{len(sessions) + 1:02d}",
                start_date=start.isoformat(), end_date=start.isoformat(),
                location=location, location_name=location_name)
            sessions.append(current)
            cursor, used = start, 0
        end = cursor + timedelta(minutes=minutes)
        current.units.append(_unit(r, cursor, end, current.session_code))
        current.end_date = end.isoformat()
        cursor, used = end, used + minutes
    return sessions, unscheduled
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `/home/claude/venv/bin/python -m pytest -q -p no:cacheprovider tests/unit/test_schedule_layout.py`
Expected: 5 passed.

- [ ] **Step 6: Full suite, then commit**

Full suite: expected 314 passed. Then:

```bash
git add generator/schedule_layout.py generator/model.py tests/unit/test_schedule_layout.py
git commit -m "Lay a schedule plan out into 150-minute sessions" \
  -m "Bout 13, block 30, ceremony 5 minutes; unscheduled rows set aside. Not yet used." \
  --trailer "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
  --trailer "Claude-Session: https://claude.ai/code/session_01KaJ7FXU5PU2Vn9C8Rprnei"
```

---

### Task 3: DT_SCHEDULE attributes as the real feed has them

This task is independent of the model switch. It changes only how the
builder serialises the dataset, so it can be judged on its own.

**Files:**
- Modify: `generator/builders/schedule.py` (whole file)
- Modify: `tests/unit/test_real_feed_conformance.py` (append a B section)
- Modify: `tests/unit/test_build_schedule.py` (delete
  `test_schedule_unit_sort_orders_unique_within_session`)
- Modify: `tests/unit/test_dataset.py` (delete
  `test_unit_sort_orders_unique_within_session`)

**Interfaces:**
- Consumes: `Dataset.unscheduled`, `ScheduleUnit`, and `Session` (Task 2).

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_real_feed_conformance.py`:

```python
# --- B. Schedule attributes ------------------------------------------------

def _schedules():
    for disc in _disciplines():
        yield disc, _messages(disc)["DT_SCHEDULE"]


def test_every_unit_carries_medal_and_no_order_or_unitnum():
    """Real feed: Medal on all 3,077 units ("0" when none); no Order and no
    UnitNum anywhere."""
    bad = []
    for disc, root in _schedules():
        for u in root.iter("Unit"):
            if u.get("Medal") not in ("0", "1", "3"):
                bad.append((disc, u.get("Code"), "Medal", u.get("Medal")))
            for attr in ("Order", "UnitNum"):
                if u.get(attr) is not None:
                    bad.append((disc, u.get("Code"), attr, u.get(attr)))
    assert not bad, bad[:5]


def test_sessions_are_named_by_code_and_count_their_gold_medals():
    """Real feed: SessionName@Value = SessionCode; no SessionType;
    Session@Medal = number of Medal="1" units in it, omitted when zero -- true
    for all 186 real sessions."""
    for disc, root in _schedules():
        golds = {}
        for u in root.iter("Unit"):
            if u.get("Medal") == "1" and u.get("SessionCode"):
                golds[u.get("SessionCode")] = golds.get(u.get("SessionCode"), 0) + 1
        for s in root.iter("Session"):
            code = s.get("SessionCode")
            assert s.find("SessionName").get("Value") == code, disc
            assert s.get("SessionType") is None, disc
            n = golds.get(code, 0)
            assert s.get("Medal") == (str(n) if n else None), (disc, code)


def test_scheduled_units_carry_time_venue_and_session_and_unscheduled_none():
    for disc, root in _schedules():
        for u in root.iter("Unit"):
            placed = [u.get(a) for a in ("StartDate", "EndDate", "Venue",
                                          "SessionCode")]
            if u.get("ScheduleStatus") == "SCHEDULED":
                assert all(placed), (disc, u.get("Code"))
                assert u.find("VenueDescription") is not None
            else:
                assert u.get("ScheduleStatus") == "UNSCHEDULED"
                assert not any(placed) and u.get("Location") is None
                assert u.find("VenueDescription") is None


def test_unscheduled_units_come_before_scheduled_ones():
    for disc, root in _schedules():
        statuses = [u.get("ScheduleStatus") for u in root.iter("Unit")]
        assert statuses == sorted(statuses, key=lambda s: s != "UNSCHEDULED"), disc
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/home/claude/venv/bin/python -m pytest -q -p no:cacheprovider tests/unit/test_real_feed_conformance.py -k "medal or named or unscheduled"`
Expected:
- `test_every_unit_carries_medal…` fails on missing Medal and on Order.
- `test_sessions_are_named…` fails on SessionName.
- The two unscheduled tests pass, because there are no UNSCHEDULED units yet.
  They start biting in Task 4.

- [ ] **Step 3: Rewrite `generator/builders/schedule.py`**

```python
"""DT_SCHEDULE, shaped as the real SYOG26 schedule (spec §3).

Sessions first (the XSD's competitionType sequence requires Session before
Unit), then UNSCHEDULED units bare, then SCHEDULED units in time order."""
from __future__ import annotations
import random
from ..dataset import build_dataset
from ..envelope import build_odfbody, competition_code
from ..serialize import el, to_xml


def _session_el(s):
    golds = sum(1 for u in s.units if u.medal == "1")
    name = el("SessionName", {"Value": s.session_code, "Language": "ENG"})
    return el("Session", {
        "SessionCode": s.session_code,
        "StartDate": s.start_date,
        "EndDate": s.end_date,
        "Medal": str(golds) if golds else None,
        "Venue": s.venue,
        "VenueName": s.venue_name,
    }, name)


def _unit_el(u, s=None):
    item = el("ItemName", {"Language": "ENG", "Value": u.item_name})
    if s is None:
        return el("Unit", {
            "Code": u.code,
            "PhaseType": u.phase_type,
            "ScheduleStatus": u.schedule_status,
            "Medal": u.medal or "0",
        }, item)
    venue_desc = None
    if s.venue_name:
        venue_desc = el("VenueDescription", {
            "VenueName": s.venue_name,
            "LocationName": s.location_name or s.venue_name,
        })
    return el("Unit", {
        "Code": u.code,
        "PhaseType": u.phase_type,
        "ScheduleStatus": u.schedule_status,
        "StartDate": u.start_date,
        "EndDate": u.end_date,
        "Medal": u.medal or "0",
        "Venue": s.venue,
        "Location": s.location,         # dropped by el() when empty
        "SessionCode": u.session_code or s.session_code,
    }, item, venue_desc)


def build(refdata, discipline: str, seed: int, overrides=None) -> bytes:
    rng = random.Random(seed)
    ds = build_dataset(refdata, discipline, seed, overrides)
    root, comp = build_odfbody(rng, refdata, discipline, "DT_SCHEDULE",
                               competition_code(refdata), overrides=overrides)
    for s in ds.sessions:
        comp.append(_session_el(s))
    for u in ds.unscheduled:
        comp.append(_unit_el(u))
    for s in ds.sessions:
        for u in s.units:
            comp.append(_unit_el(u, s))
    return to_xml(root)
```

Delete `test_schedule_unit_sort_orders_unique_within_session` from
`tests/unit/test_build_schedule.py`, and
`test_unit_sort_orders_unique_within_session` from `tests/unit/test_dataset.py`.
They pinned `@Order`, which the real feed does not carry. Unit overlap within
a session stays covered by `test_schedule_times_are_coherent.py`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `/home/claude/venv/bin/python -m pytest -q -p no:cacheprovider tests/unit/test_real_feed_conformance.py tests/unit/test_build_schedule.py tests/unit/test_dataset.py`
Expected: all pass.

- [ ] **Step 5: Full suite, then commit**

Full suite: expected 316 passed (314 + 4 new − 2 deleted). Then:

```bash
git add generator/builders/schedule.py tests/unit/test_real_feed_conformance.py tests/unit/test_build_schedule.py tests/unit/test_dataset.py
git commit -m "Write DT_SCHEDULE attributes the way the real feed does" \
  -m "Medal on every unit, no Order/UnitNum/SessionType, SessionName = code, Session@Medal = gold units." \
  --trailer "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
  --trailer "Claude-Session: https://claude.ai/code/session_01KaJ7FXU5PU2Vn9C8Rprnei"
```

---

### Task 4: Switch the datasets to plan + layout

**Files:**
- Modify: `generator/dataset.py`:
  - `_build_arc_dataset` schedule part (ll. 240–256);
  - `_build_codes_dataset` schedule part (ll. 425–531);
  - `build_dataset` (ll. 725–747);
  - constants and helpers at ll. 15–33 and 277–294.
- Modify: `tests/unit/test_options.py`:
  - `_scheduled_unit_codes`;
  - `test_defaults_unchanged_without_options`;
  - `test_seeded_heats_follow_entry_counts`;
  - `test_victory_ceremonies_added_for_any_discipline`.
- Modify: `tests/unit/test_dataset_codes_driven.py` (`_expected_units` and the
  two WST schedule tests).
- Modify: `tests/unit/test_build_schedule.py`
  (`test_schedule_arc_matches_real_life_profile`).
- Modify: `tests/unit/test_arc_profile_is_pack_scoped.py` (all three tests).
- Modify: `tests/unit/test_real_feed_conformance.py` (ceremonies by default).

**Interfaces:**
- Consumes: `schedule_plan`, `plan_sort_key`, `PlannedRow` and `SCHEDULED`
  (Task 1); `lay_out` and `PHASE_TYPE_COMPETITION` (Task 2).
- Produces: `Dataset.sessions`, holding only SCHEDULED units, and
  `Dataset.unscheduled`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_real_feed_conformance.py`:

```python
def test_ceremonies_are_scheduled_without_any_option():
    """Real feed: 150 VICTMEDAL units, all SCHEDULED, PhaseType 6. They are
    part of the default schedule now, not an option."""
    for disc in ("ATH", "SWM", "JUD"):
        root = _messages(disc)["DT_SCHEDULE"]
        cer = [u for u in root.iter("Unit") if "VICT" in u.get("Code")]
        assert cer, disc
        assert {(u.get("ScheduleStatus"), u.get("PhaseType")) for u in cer} \
            == {("SCHEDULED", "6")}, disc


def test_blocks_are_scheduled_and_the_bouts_under_them_are_not():
    root = _messages("FEN")["DT_SCHEDULE"]
    status = {u.get("Code"): u.get("ScheduleStatus") for u in root.iter("Unit")}
    assert status["FENMEPEE--------------8FNL--------"] == "SCHEDULED"
    assert status["FENMEPEE--------------8FNL000100--"] == "UNSCHEDULED"
```

Replace `_scheduled_unit_codes` and `test_defaults_unchanged_without_options`
in `tests/unit/test_options.py`:

```python
def _scheduled_unit_codes(discipline: str) -> set[str]:
    """The rows Common Codes says belong on a schedule, read from the table
    rather than from eventstructure, so this is a second opinion on the same
    rule and not a restatement of the implementation."""
    table = PACK.codes.table("EVENT_UNIT")
    return {code for code, row in table._rows.items()
            if row.fields.get("Discipline") == discipline
            and row.fields.get("Level") in ("Unit", "Phase", "Medals")
            and row.fields.get("Schedule") == "Y"
            and row.fields.get("Event") not in eventstructure.GEN_EVENTS}


def test_defaults_unchanged_without_options():
    """With every option off, the schedule lists exactly what Common Codes
    marks Schedule=Y at Unit, Phase and Medals level -- no invented rows,
    none dropped -- as the real SYOG26 schedule does.

    Derived rather than hardcoded, and the reason is on the record. This
    assertion read `== 94` until Common Codes v_2_4 retired the
    `Schedule = "S"` flag and SWM went from 94 units to 492 overnight. Since
    2026-09-23 the schedule also lists the Phase-level blocks and the Medals
    rows, so SWM lists 548 rows, of which 106 are scheduled."""
    expected = _scheduled_unit_codes("SWM")
    assert expected, "no scheduled SWM rows in the pack -- check the workbook"
    xml = schedule.build(rd(), "SWM", seed=1)
    emitted = [u.get("Code") for u in etree.fromstring(xml).iter("Unit")]
    assert len(emitted) == len(set(emitted)), "a unit was emitted twice"
    assert set(emitted) == expected
```

In `test_seeded_heats_follow_entry_counts`, count heat *bouts* only. The
`HEAT--------` block is not a heat. Replace

```python
        if code[22:26] == "HEAT":
```

with

```python
        if code[22:26] == "HEAT" and code[26:].strip("-"):
```

Replace `test_victory_ceremonies_added_for_any_discipline` with:

```python
def test_victory_ceremonies_are_in_the_default_schedule():
    for disc, expected in (("SWM", 30), ("WST", 4), ("JUD", 8)):
        root = etree.fromstring(schedule.build(rd(), disc, seed=1))
        vict = [u for u in root.iter("Unit") if u.get("Code")[22:26] == "VICT"]
        assert len(vict) == expected, disc


def test_victory_ceremonies_option_is_a_no_op():
    """Kept so existing API calls and scripts keep working (spec §4)."""
    import re
    strip = lambda b: re.sub(rb' (Date|Time|LogicalDate)="[^"]*"', b"", b)
    plain = schedule.build(rd(), "WST", seed=1)
    flagged = schedule.build(rd(), "WST", seed=1,
                             overrides=Overrides(victory_ceremonies=True))
    assert strip(plain) == strip(flagged)
```

In `tests/unit/test_dataset_codes_driven.py`, replace `_expected_units` and
the two WST schedule tests:

```python
def _expected_units(discipline):
    """Schedule rows for the discipline, per EVENT_UNIT: Schedule=Y at Unit,
    Phase and Medals level, outside the GEN events."""
    table = PACK.codes.table("EVENT_UNIT")
    out = []
    for code, row in table._rows.items():
        f = row.fields
        if (f.get("Discipline") == discipline
                and f.get("Level") in ("Unit", "Phase", "Medals")
                and f.get("Schedule") == "Y"
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


def test_wst_scheduled_units_have_names_sessions_and_times():
    xml = schedule.build(rd(), "WST", seed=1)
    root = etree.fromstring(xml)
    sessions = list(root.iter("Session"))
    assert sessions
    session_codes = {s.get("SessionCode") for s in sessions}
    for u in root.iter("Unit"):
        assert u.find("ItemName").get("Value") not in ("", "Round")
        if u.get("ScheduleStatus") == "SCHEDULED":
            assert u.get("SessionCode") in session_codes
            assert u.get("StartDate") and u.get("EndDate")
```

In `tests/unit/test_build_schedule.py`, replace
`test_schedule_arc_matches_real_life_profile`:

```python
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
```

Replace the three tests in `tests/unit/test_arc_profile_is_pack_scoped.py`
(keep the module docstring, imports and `OTHER`):

```python
from generator import arc_profile


def test_arc_uses_the_embedded_participant_profile_under_syog26():
    ds = build_dataset(RefData(PACK), "ARC", 1)
    assert {t.organisation for t in ds.teams} == set(arc_profile.DUAL_NOCS)


def test_arc_falls_back_to_the_codes_engine_under_another_games():
    ds = build_dataset(RefData(PACK, profile=OTHER), "ARC", 1)
    assert {t.organisation for t in ds.teams} != set(arc_profile.DUAL_NOCS)


def test_arc_schedule_is_the_same_codes_model_under_both():
    # The 2025 embedded calendar is retired: only the participant mix is
    # pack-scoped now.
    syog = build_dataset(RefData(PACK), "ARC", 1)
    other = build_dataset(RefData(PACK, profile=OTHER), "ARC", 1)
    assert [u.code for s in syog.sessions for u in s.units] == \
           [u.code for s in other.sessions for u in s.units]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `/home/claude/venv/bin/python -m pytest -q -p no:cacheprovider tests/unit/test_real_feed_conformance.py tests/unit/test_options.py tests/unit/test_dataset_codes_driven.py tests/unit/test_build_schedule.py tests/unit/test_arc_profile_is_pack_scoped.py`

Expected failures:
- The ceremonies and blocks conformance tests: there are no VICT units or
  blocks yet.
- `test_defaults_unchanged…`: the set lacks Phase and Medals rows.
- `test_victory_ceremonies_are_in_the_default…`.
- `test_victory_ceremonies_option_is_a_no_op`: the option still adds units.
- The WST set test.
- The ARC shape test (83 units).
- `test_arc_schedule_is_the_same…`.

- [ ] **Step 3: Implement in `generator/dataset.py`**

a) Imports: add `from . import schedule_layout` to the existing
`from . import fields, names, arc_profile, eventstructure` line, making it
`from . import fields, names, arc_profile, eventstructure, schedule_layout`.
Add `import math` at the top, after `import random`.

b) Delete these from the top block: `_UNITS_PER_SESSION`, `_UNIT_MINUTES`,
the `PHASE_TYPE_*` constants with their comment, and `_phase_type()`. Replace
`_SCHEDULE_STATUS = "SCHEDULED"  # fallback …` with:

```python
_SCHEDULE_STATUS = eventstructure.SCHEDULED
```

c) Delete `_SCHEDULE_BASE`, `_dt()` and `_fmt_dt()` (ll. 277–294) with their
comment block. They now live in `schedule_layout`. Also delete the stale
comment line `# First day of the synthetic competition window. Only the
codes-driven engine`.

d) Add these helpers above `_build_codes_dataset`:

```python
def _discipline_venue(rng, refdata, discipline: str):
    """(venue, venue_name, location, location_name) from LOCATION, with the
    fallback the codes engine always had for a discipline LOCATION omits."""
    venue, venue_name, location, location_name = \
        eventstructure.discipline_venue(refdata, discipline)
    if not venue:
        venue = fields.pick_code(rng, refdata, "VENUE") or "ALL"
        venue_name = (refdata.description("VENUE", venue, "ENG_Description")
                      or venue)
        location, location_name = "", ""
    return venue, venue_name, location, location_name


def _seed_heats(plan, refdata, discipline: str, evs, entries_by_event):
    """seeded_heats: a SWM event's heat bouts become ceil(entries / 8) real
    heat RSCs from the codes' full heat pool. They keep the status the plan
    gave the heats they replace (UNSCHEDULED under a HEAT block)."""
    pool = eventstructure.heat_pool(refdata, discipline)
    out = list(plan)
    for ev in evs:
        key = (ev.gender, ev.event)
        if key not in pool:
            continue
        e_list = entries_by_event.get(
            _event_rsc(discipline, ev.gender, ev.event))
        n_entries = len(e_list.athlete_codes) if e_list else ev.entrants
        need = max(1, math.ceil(n_entries / 8))
        old = [r for r in out if r.event_key == key and r.kind == "bout"
               and r.phase == "HEAT"]
        status = old[0].status if old else eventstructure.SCHEDULED
        keep_order = min((r.order for r in old), default=0)
        out = [r for r in out if r not in old]
        kept = pool[key][:min(need, len(pool[key]))]
        for h in kept:
            out.append(eventstructure.PlannedRow(
                code=h.code, level="Unit", kind="bout", status=status,
                event_key=h.event_key, phase=h.phase,
                order=keep_order or h.order, unit_seq=h.unit_seq,
                medal=h.medal, name=h.name))
        for r in out:
            if (r.event_key == key and r.level == "Phase"
                    and r.phase.rstrip("-") and "HEAT".startswith(r.phase.rstrip("-"))):
                r.covered_bouts = len(kept)
    out.sort(key=eventstructure.plan_sort_key)
    return out
```

e) In `_build_codes_dataset`, replace everything from
`    # Schedule: chunk the codes-defined units into morning/afternoon sessions.`
through the end of the function (the `return Dataset(...)`) with:

```python
    # Schedule: the codes' schedule plan (spec §1), laid out into sessions.
    entries_by_event = {e.event_rsc: e for e in event_entries}
    plan = eventstructure.schedule_plan(refdata, discipline)
    if ov and ov.seeded_heats:
        plan = _seed_heats(plan, refdata, discipline, evs, entries_by_event)
    venue, venue_name, location, location_name = \
        _discipline_venue(rng, refdata, discipline)
    sessions, unscheduled = schedule_layout.lay_out(
        plan, discipline, venue, venue_name, location, location_name)

    return Dataset(discipline=discipline, organisations=used_nocs,
                   participants=participants, teams=teams, sessions=sessions,
                   entries=event_entries, unscheduled=unscheduled)
```

Also update that function's docstring. Replace the paragraph
`` ``ov`` (normalized Overrides) can enable live-operations realism: …``
with:

```
    ``ov`` (normalized Overrides) can enable live-operations realism:
    qualification-scale entry lists, seeded heats and historical athletes.
    Victory ceremonies are always in the plan; the old option is a no-op.
```

f) In `_build_arc_dataset`, replace the block from `    sessions: list[Session] = []`
through the `item_name=item_name))` of the `arc_profile.UNITS` loop with:

```python
    # The 2025 embedded calendar is retired: ARC schedules through the same
    # codes plan as every discipline (its plan matches the real SYOG26 ARC
    # schedule row for row). The profile still supplies the participant mix.
    venue, venue_name, location, location_name = \
        _discipline_venue(rng, refdata, "ARC")
    sessions, unscheduled = schedule_layout.lay_out(
        eventstructure.schedule_plan(refdata, "ARC"), "ARC",
        venue, venue_name, location, location_name)
```

and change its `return Dataset(...)` to pass `unscheduled=unscheduled`. In its
docstring, replace `and the\n    real 9-session / 83-unit schedule` with
`and the\n    codes-derived schedule`.

g) In `_build_fallback_dataset`, change
`phase_type=PHASE_TYPE_COMPETITION,` to
`phase_type=schedule_layout.PHASE_TYPE_COMPETITION,`. Its
`sort_order=k + 1, medal=rng.choice([None, "0", "1"]),` becomes
`medal=rng.choice(["0", "0", "1"]),`, which keeps one rng draw. Drop
`unit_num=str(k + 1), `. In its `Session(...)`, drop `name="Session 1", ` and
change the `session_type=...` line to a bare
`fields.pick_code(rng, refdata, "SESSION_TYPE")` statement placed just before
`sessions = [...]`, so the rng draws are unchanged:

```python
    fields.pick_code(rng, refdata, "SESSION_TYPE")  # keep the rng sequence
    sessions = [Session(
        venue=venue, venue_name=venue_name, session_code=session_code,
        start_date=start, end_date=end, units=units)]
```

h) In `build_dataset`, the ARC branch: change

```python
        schedule_opts = bool(ov and (ov.realistic_entries or ov.seeded_heats
                                     or ov.victory_ceremonies))
```

to

```python
        schedule_opts = bool(ov and (ov.realistic_entries or ov.seeded_heats))
```

and replace the two comment lines above it with:

```python
        # ARC uses the embedded participant profile. Entry-shaping options
        # switch it to the codes engine so they apply there too.
```

- [ ] **Step 4: Run the tests to verify they pass**

Run the Step 2 command. Expected: all pass. Then run
`tests/unit/test_schedule_times_are_coherent.py`,
`tests/unit/test_bundle_all_disciplines.py` and
`tests/unit/test_obligation_coverage.py`. Expected: all pass, and all 24
disciplines are clean.

If `test_obligation_coverage.py` fails on changed counts, read the failure
before touching it. The pins cover DT_ENTRIES Description ambiguity, which
this task must not change.

- [ ] **Step 5: Full suite, then commit**

Full suite: expected 319 passed. That is 316, plus 2 conformance tests, plus
1 because the victory test becomes two; the other rewrites replace tests one
for one. Then:

```bash
git add generator/dataset.py tests/unit/test_real_feed_conformance.py tests/unit/test_options.py tests/unit/test_dataset_codes_driven.py tests/unit/test_build_schedule.py tests/unit/test_arc_profile_is_pack_scoped.py
git commit -m "Schedule blocks, not bouts, and always include ceremonies" \
  -m "Datasets now use schedule_plan + lay_out. ARC's 2025 calendar retires; victory_ceremonies becomes a no-op." \
  --trailer "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
  --trailer "Claude-Session: https://claude.ai/code/session_01KaJ7FXU5PU2Vn9C8Rprnei"
```

---

### Task 5: Remove what the switch left dead, and the UI checkbox

**Files:**
- Modify: `generator/model.py`: drop `sort_order` and `unit_num` from
  `ScheduleUnit`, and `name` and `session_type` from `Session`.
- Modify: `generator/eventstructure.py`: delete `victory_units()`.
- Modify: `generator/arc_profile.py`: delete `VENUE`, `VENUE_NAME`,
  `LOCATION`, `LOCATION_NAME`, `SESSIONS`, `UNITS` and their comments; rewrite
  the docstring.
- Modify: `generator/overrides.py`, `generator/export.py`, `api/app.py`:
  document the no-op.
- Modify: `web/templates/index.html`, `web/static/app.js`: remove the
  checkbox.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_web_template.py`:

```python
def test_victory_ceremonies_checkbox_is_gone():
    """Ceremonies are always scheduled (spec §4); a checkbox that does nothing
    would mislead."""
    html = TEMPLATE.read_text(encoding="utf-8")
    assert 'id="victory_ceremonies"' not in html
    js = (WEB / "static" / "app.js").read_text(encoding="utf-8")
    assert '"victory_ceremonies"' not in js
```

(`TEMPLATE` and `WEB` are already defined in that module.)

- [ ] **Step 2: Run the test to verify it fails**

Run: `/home/claude/venv/bin/python -m pytest -q -p no:cacheprovider tests/unit/test_web_template.py -k victory`
Expected: FAIL on the `id=` assertion.

- [ ] **Step 3: Implement**

`web/templates/index.html`: delete the line
`            <label><input type="checkbox" id="victory_ceremonies"> Victory ceremony units</label>`.

`web/static/app.js`: delete the line `  "victory_ceremonies",` from `FLAGS`.

`generator/model.py`: remove the four fields marked `# removed in Task 5`.

`generator/eventstructure.py`: delete the whole `victory_units` function.

`generator/arc_profile.py`: delete everything except the NOC lists. The file
becomes:

```python
"""ARC (Archery) participant profile for SYOG2026.

The NOC mix of the real AWAARC1 initial-download test feed (2025-10-17):
17 NOCs entering one man and one woman (who also form the mixed teams),
15 men-only and 15 women-only NOCs -> 32 M + 32 W athletes. FRG and URS,
historical NOCs, were replaced by GER and KAZ on 2026-09-23.

Its 2025 schedule calendar was retired on 2026-09-23: ARC schedules through
the codes plan like every discipline (generator/eventstructure.schedule_plan).
"""
from __future__ import annotations

DUAL_NOCS = ["ASA","BAH","BDI","CRC","CZE","EGY","GER","GHA","ITA","JOR","KAZ","KOR","LAO","PLE","PUR","SWE","USA"]
MEN_NOCS = ["BAR","BEL","CAM","COD","CRO","ETH","GUM","INA","ISL","LCA","MOZ","NCA","NOR","OMA","TKM"]
WOMEN_NOCS = ["ALB","AND","AZE","BAN","BEN","CHI","CIV","COL","HUN","IRL","ISV","KGZ","KSA","SEN","SOM"]
```

These three lines are unchanged from the current file. Only the docstring and
the deleted constants change, and the old FRG/URS comment above `DUAL_NOCS`
goes because the docstring now carries it.

`generator/overrides.py`: change the `victory_ceremonies` line to:

```python
    victory_ceremonies: bool = False   # no-op: ceremonies are always scheduled
```

`generator/export.py`: change the help text to
`help="no-op, kept for compatibility: ceremonies are always scheduled"`.

`api/app.py`: above `victory_ceremonies: bool = False` in the request model,
add `    # Accepted for compatibility; a no-op (ceremonies are always scheduled).`

- [ ] **Step 4: Verify**

- Run `grep -rn "sort_order\|unit_num\|session_type\|victory_units\|arc_profile\.\(VENUE\|LOCATION\|SESSIONS\|UNITS\)" generator api tests --include=*.py`.
  Expected: no output.
- Run the full suite. Expected: 320 passed.
- Run `npm test` if `node_modules` exists: `app.test.mjs` must still pass
  without the flag.

- [ ] **Step 5: Commit**

```bash
git add generator/model.py generator/eventstructure.py generator/arc_profile.py generator/overrides.py generator/export.py api/app.py web/templates/index.html web/static/app.js tests/unit/test_web_template.py
git commit -m "Drop what the schedule switch left dead, and the ceremonies checkbox" \
  --trailer "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
  --trailer "Claude-Session: https://claude.ai/code/session_01KaJ7FXU5PU2Vn9C8Rprnei"
```

---

### Task 6: README, samples, verification, delivery

**Files:**
- Modify: `README.md`: the Realism model section (ARC bullet and schedule
  bullet) and the Live-operations options section.
- Regenerate: `samples/`

- [ ] **Step 1: Update the README**

- **ARC bullet.** Replace the whole bullet, from `- **ARC** uses an embedded
  real-life profile` through `Common Codes).`, with:

  ```markdown
  - **ARC** keeps an embedded participant profile (`generator/arc_profile.py`):
    32 M + 32 W athletes across 47 NOCs, one coach per NOC plus the codes'
    judges, 17 mixed teams. Its schedule comes from the codes like every
    discipline's, and matches the real SYOG26 ARC schedule row for row.
  ```

- **Schedule bullet.** After the "Every other discipline" bullet, add:

  ```markdown
  - **Schedule model** (as in the real SYOG26 feed). DT_SCHEDULE lists every
    EVENT_UNIT row with `Schedule=Y` at Unit, Phase and Medals level. A phase
    with several bouts is scheduled as one block and its bouts are listed
    `UNSCHEDULED` with no time or venue; JUD schedules its preliminary and
    final blocks the same way. Victory ceremonies are always scheduled
    (`PhaseType="6"`). Every unit carries `Medal` (`0` when none); a session's
    `Medal` counts its gold-medal units and its name is its code. Slots are
    13 minutes a bout, 30 a block and 5 a ceremony, in sessions of at most
    150 minutes at 09:30 and 14:00. SWM lists 548 rows and schedules 106.
  ```

- **Live-operations options.**
  - Replace the `victory_ceremonies` bullet with:

    ```markdown
    - `victory_ceremonies` (`--victory-ceremonies`): no longer does anything.
      Ceremonies are always scheduled; the option is still accepted so
      existing calls keep working.
    ```

  - Replace the first sentence of the "Notes:" paragraph
    (`Notes: ARC uses its embedded real-life schedule profile; …too.`) with
    `Notes: realistic entries or seeded heats switch ARC from its participant
    profile to the codes engine, so those options apply there too.`
  - Change "Four options (off by default" to "Three options (off by
    default", plus a no-op fourth.

- **`@UnitNum` mentions.** README (the line saying consumers key on `@Code`
  and `@UnitNum`) and the `lengths.py` module docstring (same sentence) both
  change to say consumers key on `@Code`, which stays distinct. `UnitNum` is
  no longer emitted.

- [ ] **Step 2: Regenerate the samples**

```bash
cd /home/claude/gen && /home/claude/venv/bin/python -m generator.export --all --seed 1 --no-manifest --out-dir samples
```

Expected: 24 disciplines written; `SKIP GAR` (the designed refusal).

- [ ] **Step 3: Verify**

- Full suite: 0 failures.
- `python -m generator.obligations`: exit 0.
- Regenerate into `/tmp/claude-0/regen`. It must be identical to `samples/`
  apart from Date, Time and LogicalDate (same check as the A commit).
- Re-run `/home/claude/cmp/profile.py`, and check the DT_SCHEDULE section
  against the real feed:
  - `PhaseType` is 3 or 6 only;
  - `ScheduleStatus` has both values;
  - `Medal` appears on every unit;
  - there is no `Order`, `UnitNum` or `SessionType`.

- [ ] **Step 4: Commit, then create and verify the patch**

```bash
git add README.md samples
git commit -m "Regenerate samples with the real feed's schedule model" \
  --trailer "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
  --trailer "Claude-Session: https://claude.ai/code/session_01KaJ7FXU5PU2Vn9C8Rprnei"
git format-patch 19b7a41..HEAD -o /mnt/user-data/outputs/real-feed-patches
```

Verify the series applies to `19b7a41` in a scratch clone and reproduces
HEAD's tree. Then write the patch folder into the laptop repo root, replacing
the single A patch. Finally, update the project doc
`claude/real-feed-comparison-2026-09-23.md`: mark B done and list what
remains out of scope.
