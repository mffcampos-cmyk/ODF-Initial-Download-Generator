# B1 Root Cause — Team generation under count overrides

**Date:** 2026-07-25
**Trigger:** Third-party audit finding B1 ("count-override teams always `gender=X`")
**Status:** Fixed. 109 tests pass (100 baseline + 9 new regression tests); all 25
disciplines generate clean under overrides with no dangling references.

Reproduced against the real SYOG26 pack (`ODF Validator Webapp 2/Rules/SYOG26`),
25 disciplines loaded.

---

## Root cause

`_apply_count_overrides` (`generator/dataset.py:541`) builds teams from a scalar
count with no reference to the discipline's event structure. Every other part of
the system is event-derived:

| Consumer | Source of truth |
|---|---|
| `_build_codes_dataset` team block (`dataset.py:325-351`) | `eventstructure.events()` → `EventInfo` |
| `bundle.py` DT_PARTIC_TEAMS gating | `eventstructure.has_team_events()` |
| Team RSC scheme | `{disc}{ev.gender}{ev.event}` per CC@EVENT |
| `_apply_count_overrides` team block | **the integer the user typed** |

Because there is no `EventInfo` in scope at `dataset.py:581`, every event-derived
property has to be invented:

| Property | Default path | Override path |
|---|---|---|
| Team gender | `ev.gender` (line 345) | literal `"X"` (line 594) |
| RSC prefix | `HBBMTEAM4---` | `HBBXTEAM----` |
| Squad size | `ev.team_size` (4/5/7) | `min(2, len(athletes))` |
| Member genders | `athlete_gender(ev.gender, i)` | alternating M/F by global index |
| Team sequence | `01` | `j:02d` → `00`, `01`, … |

The audit's `gender="X"` is one of five symptoms of the same cause, and it is the
mildest one.

### Observed (HBB, seed 1)

```
DEFAULT            HBBMTEAM4---CAF01  Gender=M  size=4  members=[M,M,M,M]   (16 teams)
teams=4 OVERRIDE   HBBXTEAM----MGL00  Gender=X  size=2  members=[M,F]       (4 teams)
```

Identical shape for FBS (squad 5) and RU7 (squad 7). HBB publishes exactly two
team events in the codes — `M TEAM4` and `W TEAM4`, 8 entrants each — and the
override path matches neither.

### Why the audit's proposed fix makes it worse

The audit suggests `gender = ev.gender if ev.gender in ("M","W","X") else "X"`.
Two problems:

1. `ev` is not in scope — teams there are not event-derived at all.
2. Members really are one man and one woman (`dataset.py:575` alternates M/F;
   `dataset.py:584` takes `athletes[2j]` and `athletes[2j+1]`). Setting
   `Gender="M"` would label a team containing a woman as men's, and the RSC would
   still read `XTEAM`. The output becomes *more* internally contradictory, not
   less.

---

## Symptoms, by severity

### S1 — Dangling team references (worse than B1)

14 of 25 disciplines have no team events: ATH, BDM, BKG, BOX, CRD, EQU, FEN, JUD,
SAL, SKB, SWM, TRI, WRB, WST. For these, `bundle.py` drops DT_PARTIC_TEAMS
(`has_team_events()` is false), but `_apply_count_overrides` still fabricates
teams and enters them in DT_ENTRIES.

Verified — SWM, `athletes=12, teams=3`:

```
bundle keys:            ['DT_PARTIC', 'DT_ENTRIES_SWM', 'DT_SCHEDULE']
DT_PARTIC_TEAMS:        not emitted
DT_ENTRIES Entry@Type=T: SWMXTEAM----AIN02, SWMXTEAM----KOR01, SWMXTEAM----MGL00
validator errors:        0 on every message
```

Three team entries reference teams no message in the bundle declares. The
validator passes because it validates per-message and has no cross-message
referential-integrity check.

### S2 — Fabricated RSC

`HBBXTEAM----` corresponds to no row in CC@EVENT. The `TEAM4` size token is lost
and the gender slot is forced to `X`.

### S3 — Squad size collapse

4/5/7-player squads become 2 regardless of discipline.

### S4 — Team gender (the audit's B1)

`gender="X"` on every override team.

### S5 — Sequence suffix starts at `00`

Default emits `…01`; override emits `…00`, `…01`, `…02`.

---

## Independent bug found during investigation

`_team_type` (`dataset.py:31`) falls back to the **entire cross-discipline**
`DISCIPLINE_GENDER` table when a discipline publishes no `SC@TeamType@<disc>`
table. TKW is the only discipline in this pack without one, and it draws archery
codes:

```
committed samples/TKW/DT_PARTIC_TEAMS.xml   @TeamType = CERG
TKW + teams=4 override                       @TeamType = ARCW
TKW's own DISCIPLINE_GENDER codes            TKWG, TKWM, TKWW, TKWX
```

This affects the **default** path, not just overrides. Checked all 11 committed
DT_PARTIC_TEAMS samples — VBV's `CUSTOM` is legitimate (it comes from VBV's own
`SC@TeamType@VBV` table); TKW is the only genuine case.

---

## Verified fix shape

Distribute the requested team count round-robin across the discipline's real team
events, so each team carries a real event's gender, RSC, and squad size.
Prototyped out-of-tree and run against the pack:

```
HBB teams=4   HBBMTEAM4---MGL01  Gender=M  TeamType=ORG   size=4  members=[M,M,M,M]
              HBBWTEAM4---KOR01  Gender=W  TeamType=ORG   size=4  members=[F,F,F,F]
              HBBMTEAM4---AIN01  Gender=M  TeamType=ORG   size=4  members=[M,M,M,M]
              HBBWTEAM4---ALB01  Gender=W  TeamType=ORG   size=4  members=[F,F,F,F]

RU7 teams=4   RU7MTEAM7---MGL01  Gender=M  size=7  members=[M×7]
              RU7WTEAM7---KOR01  Gender=W  size=7  members=[F×7]

TKW teams=4   TKWXTEAM4---MGL01  Gender=X  TeamType=TKWX  size=4  members=[M,F,M,F]
```

All five properties become consistent, and TeamType stays inside the discipline.

### Agreed policy

- **athletes vs teams conflict** — teams add on top. `athletes=N` governs
  individual-event athletes; squad members are generated in addition, so total
  participants exceeds N. (RU7 `teams=4` generates 28 squad athletes.)
- **Disciplines with no team events** — ignore the count, generate zero teams.
  Matches `bundle.py`'s existing gating and fixes S1.
- **`_team_type`** — fix alongside; restrict the DISCIPLINE_GENDER fallback to the
  discipline's own codes.

---

## What was changed

`generator/dataset.py`

- `_apply_count_overrides` — the team block now distributes `team_target`
  round-robin across `eventstructure.events()`, taking each team's gender, RSC
  prefix, squad size and member genders from the event. Disciplines with no team
  events produce no teams. Squad members are generated on top of
  `athlete_target` and are entered via their team, not individually.
- `_athlete_gender` — promoted to module level so the override path uses the same
  rule as the default path.
- `_team_type` — the DISCIPLINE_GENDER fallback is restricted to the discipline's
  own codes.
- `_team_type_for_gender` — new. For disciplines with no SC@TeamType table, picks
  the DISCIPLINE_GENDER code matching the team's gender (TKW mixed → `TKWX`, not
  `TKWM`). Deterministic, so it consumes no rng: output for every other
  discipline is byte-identical.

`tests/unit/test_override_teams_event_derived.py` — new, 9 regression tests, each
watched failing before the corresponding fix.

`tests/unit/test_customization.py` — `test_entries_match_participants_on_override`
moved from SWM to HBB. SWM schedules no team event, so after the fix a `teams=`
override there yields no teams and the team half of the assertion would have
silently stopped testing anything.

`samples/` — regenerated. Only `samples/TKW/DT_PARTIC_TEAMS.xml` changed content
(`TeamType` `CERG` → `TKWX`).

## Verification

- 109 tests pass (100 baseline + 9 new). No test was weakened to accommodate the
  change; the one edit strengthened an assertion that had gone vacuous.
- All 25 disciplines with `athletes=12, teams=3, coaches=5, status=ENT`: zero
  validator errors, zero DT_ENTRIES team references undeclared by
  DT_PARTIC_TEAMS.

## Correction to the audit's R5

R5 ("committed samples are stale") was filed for the wrong reason — the officials
logic it cited was already reflected in the samples. But `samples/BDM/` genuinely
was stale: regenerating it with the *pre-fix* generator produced different
participant names and `Status` (`CNF` → `ENT`). BDM was the only affected
discipline. The regeneration above fixes it.
