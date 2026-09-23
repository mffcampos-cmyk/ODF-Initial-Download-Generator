# Schedule model: blocks, unscheduled bouts, ceremonies — design

Date: 2026-09-23. Status: approved by Marcos in conversation, 2026-09-23.
Source: section B of the real-feed comparison
(`claude/real-feed-comparison-2026-09-23.md` in the project), against the real
SYOG26 initial download's DT_SCHEDULE (publish history, 2026-09-23).

## Decisions taken with Marcos

1. **Derived by rules, nothing vendored.** No part of the real schedule
   (sessions, times, statuses, per-unit venues) goes into either repository.
   Everything below is derived from Common Codes.
2. **The new model is the default.** No option switches back to the old
   all-SCHEDULED schedule.
3. **Approach 1:** one pure planning function owns the status rule; the
   dataset lays out only what it schedules. A per-Games "blocks" list
   (approach 3) was rejected, because it would encode organiser knowledge.

## What the real schedule is

Measured against Common Codes v_2_4:

- **Rows.** It lists every EVENT_UNIT row with `Schedule=Y` at `Level` Unit
  (2,804), Phase (103) and Medals (155), plus 15 Phase rows flagged `N` (BOX
  8FNL, RCB SFNL, TTE 8FNL). Nothing else. 1,250 of the 3,077 rows are
  SCHEDULED.
- **Blocks.** Where a scheduled row covers bouts, the bouts are UNSCHEDULED.
  The covering row is one of:
  - a phase placeholder, `FENMEPEE--------------8FNL--------`;
  - a group parent, `TTEMSINGLES-----------GP----------` over `GPA-`…`GPH-`;
  - JUD's `TMRY000100/000200` Unit rows (`Eventunittype` NONE);
  - SWM's `HEAT--------`.
- **Sessions.** They span a median of 150 minutes and hold a median of 4
  rows. Blocks last a median of 30 minutes and bouts 25. 39% of consecutive
  rows in a session overlap (parallel events).

## §1 Unit set and status

New pure function in `generator/eventstructure.py`:

```python
schedule_plan(refdata, discipline) -> list[PlannedRow]

@dataclass
class PlannedRow:
    code: str
    kind: str            # "block" | "bout" | "ceremony"
    status: str          # "SCHEDULED" | "UNSCHEDULED"
    event_key: tuple[str, str]
    phase: str
    order: int
    unit_seq: int
    medal: str           # "", "1" or "3"
    name: str
    covered_bouts: int   # blocks only: how many bouts it stands for
```

**Rows:** EVENT_UNIT rows of the discipline with `Schedule == "Y"` and `Level`
in {Unit, Phase, Medals}, excluding GEN events (`GEN_EVENTS`, as today).

**Kinds:**
- *ceremony:* `Level == "Medals"`: 153 `VICTMEDAL` rows plus 2 `BRONZE`
  rows. The Phase-level `VICT` rows are all `Schedule=N`, so they never
  enter the plan.
- *block:* `Level == "Phase"`, or a Unit row with `Eventunittype == "NONE"`.
- *bout:* every other Unit row.

**Status, applied in this order:**
1. **Ceremonies** are SCHEDULED.
2. **Phase rows.** For a Phase row, its bouts are the bouts of the same event
   whose 4-character phase code starts with the Phase row's phase code
   stripped of `-`. So `GP--` covers `GPA-`…`GPH-` and `8FNL` covers `8FNL`.
   - With 2 or more bouts, the Phase row is SCHEDULED and those bouts are
     UNSCHEDULED.
   - Otherwise the Phase row is UNSCHEDULED and its single bout keeps the
     next rule.
3. **Events with NONE-type block units** (JUD's TMRY): the block units are
   SCHEDULED and every bout of the event not already decided is UNSCHEDULED.
4. **Every remaining bout** is SCHEDULED.

**Measured:** this reproduces 2,847 of the 3,077 real statuses. The 230
misses fall into three groups:

- *Entry-dependent spares:* TKW and BOX 8FNL, ATH's third semi, SWM
  swim-offs, and a few others. The real feed leaves these unscheduled because
  of entry counts.
- *The 15 `Schedule=N` blocks:* the organiser's choice.
- *GAR:* it is not generated.

These misses are accepted; §5 lists them as out of scope.

**Seeded heats.** `seeded_heats` keeps trimming a SWM event's heat bouts to
`ceil(entries / 8)` from the heat pool. The kept heats are bouts under the
`HEAT` block, so they are UNSCHEDULED.

## §2 Calendar

Only SCHEDULED rows are laid out.

**Durations:**

| Kind | Minutes |
|---|---|
| bout | 13 (as today) |
| block | 30 |
| ceremony | 5 |

**Ordering:** the existing sort (event, order, phase rank, unit sequence, code).
A ceremony sorts after the last row of its event, as the old
`victory_ceremonies` did with `order = 999`.

**Sessions:**
- A new session starts when adding the next row would take the session past
  150 minutes.
- Two sessions a day, starting at 09:30 and 14:00, from day 1 = 2026-11-01 as
  today.
- The session code keeps its current form, `<DISC><NN>`.
- Rows run sequentially. There are no parallel lanes (YAGNI).

**Simulated days per discipline** (real in brackets):

| Discipline | Days | Discipline | Days | Discipline | Days |
|---|---|---|---|---|---|
| FEN | 4 (6) | SWM | 6 (6) | JUD | 2 (3) |
| TTE | 3 (6) | ARC | 4 (5) | TKW | 8 (5) |
| WRB | 9 (2) | | | | |

WRB is long because the real feed runs two rings in parallel. Accepted.

**ARC.** ARC's embedded 2025 calendar (`arc_profile.SESSIONS` and `UNITS`)
retires, and ARC schedules through this model. Its participant, NOC and team
profile is unchanged.

## §3 Attributes

**Unit, every row:**
- `Code`, `PhaseType` (ceremony `6`, otherwise `3`), `ScheduleStatus`,
  `Medal` (always present; `0` when no medal) and `ItemName`.
- `Order` and `UnitNum` are no longer emitted.

**Unit, SCHEDULED rows add:** `StartDate`, `EndDate`, `Venue`, `Location`,
`SessionCode` and `VenueDescription`.

**Unit, UNSCHEDULED rows:** none of the SCHEDULED-only attributes, and no
`VenueDescription`.

**Order in the message:** Sessions, then UNSCHEDULED units in plan order, then
SCHEDULED units chronologically.

**Session:**
- `SessionCode`, `StartDate`, `EndDate`, `Venue`, `VenueName`, and
  `SessionName@Value` = the session code.
- No `SessionType`.
- `Medal` = the number of `Medal="1"` units in the session, omitted when 0.
  This holds for all 186 real sessions.

## §4 Options

- **`victory_ceremonies`:** ceremonies are always scheduled now. The checkbox
  is removed from the web UI. `/api/generate`, `/api/save`,
  `/api/generate.zip` and `--victory-ceremonies` still accept the option as a
  documented no-op, so existing calls keep working.
- **`seeded_heats`:** as in §1.
- **Other options:** `realistic_entries` and `historical_athletes` are
  unaffected.
- **ARC with a schedule option:** the note that "enabling a schedule-affecting
  option switches ARC to the codes-driven engine" becomes moot, since ARC is
  always codes-driven for its schedule.

## §5 Out of scope

- **Location codes.** Every real Location is a valid LOCATION member, and so
  is every generated one. No codes-only rule matched the real choice better
  than 685 of 1,250 units.
- **Not modelled:** `StartList` (group-stage pairings), `StartText`,
  `HideStartDate` and `HideEndDate`.
- **Status misses:** entry-dependent spares, and the 15 `Schedule=N` blocks.
- **Calendar:** the real calendar and parallel lanes.

## §6 Tests

New `tests/unit/test_schedule_plan.py`, pure over the plan (no XML):

- Every row is a `Schedule=Y` EVENT_UNIT row of the discipline. Every such row
  (Unit, Phase or Medals, non-GEN) appears exactly once.
- A Phase row with 2 or more bouts is a SCHEDULED block and its bouts are
  UNSCHEDULED. A single-bout phase is UNSCHEDULED and its bout is SCHEDULED.
  Fixtures: FEN 8FNL, TTE GP, ARC QUAL.
- JUD: TMRY blocks SCHEDULED, all JUD bouts UNSCHEDULED.
- Ceremonies are SCHEDULED, with kind `ceremony`.
- Aggregate: the plan's statuses agree with a pinned per-discipline count of
  SCHEDULED rows. The counts come from the plan itself at the time of writing.
  That makes it a regression pin, not a claim about the real feed.

`tests/unit/test_real_feed_conformance.py`, over the built XML:

- SCHEDULED units have dates, a venue and a session code; UNSCHEDULED units
  have none of these.
- Every unit carries `Medal`; no unit carries `Order` or `UnitNum`.
- `Session@Medal` equals the count of `Medal="1"` units in the session.
  `SessionName@Value` equals `SessionCode`, and there is no `SessionType`.
- Ceremony units are present by default, with no option set.

**Existing tests that still hold:** `test_schedule_times_are_coherent.py`, now
over SCHEDULED rows only; the clean-bundle test for all 24 disciplines; and
the obligations sweep.

**Tests to revise:**
- Those that pin all-SCHEDULED output or unit counts: `test_options.py`,
  `test_readme_numbers.py`, `test_build_schedule.py`, and ARC profile schedule
  tests.
- Revise each by what it was protecting, not by deleting it.

**Numbers to update:** README figures such as "SWM's schedule went from 94
units to 492" gain the scheduled/unscheduled split. `samples/` is regenerated.
