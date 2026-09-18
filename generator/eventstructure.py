"""Derive per-discipline event structure from the Common Codes tables.

Everything here is data-driven from the rule pack's EVENT / EVENT_UNIT /
LOCATION / VENUE tables so that the generated participant counts and schedule
match the Common Codes for every discipline, not just those with an embedded
real-life profile.

Entrant-count heuristics (documented approximations):
- bracket event  (R64/R32/R16/8FNL/QFNL/SFNL/FNL- rounds):
      entrants = 2 x matches of the largest round (e.g. JUD R32: 16 -> 32)
- heats event    (HEAT rounds): entrants = 8 lanes x number of heats
- group event    (GPA-/GPB-/... groups): entrants = 4 per group
- otherwise (direct final / combined events): 8 entrants
Team size comes from the event code where the code states it (TEAM2 -> 2,
SCULL2 -> 2), from _SQUAD_SIZES where it is a sport fact the code omits
(DOUBLES -> 2), and otherwise raises -- see UnknownSquadSize.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

GEN_EVENTS = ("GEN---------------", "------------------")

# Squad size for team events whose code does not carry the number. The codes
# tables have no squad-size column (EVENT holds Discipline, Gender, Event,
# Order, Team_Event, SEQ, Type and descriptions), so this cannot be derived --
# it is a sport fact that has to be stated.
#
# Keyed on the bare event code, matched after the numeric patterns below.
_SQUAD_SIZES = {
    # Table tennis mixed doubles: a doubles pair.
    "DOUBLES": 2,
}

# Event codes that state their own squad size. SCULL2 is a double scull (2
# rowers); the previous regex only looked for TEAM(\d), so RCB's Mixed Double
# Sculls silently became a 4-person crew.
_SIZE_IN_CODE = re.compile(r"(?:TEAM|SCULL)(\d)")


class UnknownSquadSize(RuntimeError):
    """A team event whose squad size is neither in its code nor in _SQUAD_SIZES.

    Raised rather than defaulted. The previous code fell back to 4, which
    produced four-person table-tennis doubles pairs and four-person double
    sculls -- output that looks plausible, validates clean (no rule checks
    squad size), and is wrong. A refusal that names the event is worth more
    than a number nobody chose.
    """


def squad_size(discipline: str, event: str) -> int:
    """Athletes per team for a team event.

    Order matters: the code is authoritative where it carries a number, and
    _SQUAD_SIZES fills in only what the code omits.
    """
    m = _SIZE_IN_CODE.search(event)
    if m:
        return int(m.group(1))
    key = event.rstrip("-")
    if key in _SQUAD_SIZES:
        return _SQUAD_SIZES[key]
    raise UnknownSquadSize(
        f"{discipline} event '{key}' is a team event whose squad size is not "
        f"stated in its event code and is not in _SQUAD_SIZES "
        f"(generator/eventstructure.py). The Common Codes tables carry no "
        f"squad-size column, so it cannot be derived: add the number from "
        f"that discipline's Data Dictionary. Refusing rather than guessing -- "
        f"the previous default of 4 emitted plausible-looking wrong squads.")
# Only a real elimination tree counts as a bracket for entrant sizing; a lone
# FNL-/SFNL (e.g. Wushu combined finals, Athletics direct finals) does not.
_BRACKET_PHASES = ("R64-", "R32-", "R16-", "8FNL")
# Competition-progression rank used as tiebreaker when the codes give equal
# Order values (prelims before finals).
_PHASE_RANK = {"QUAL": 0, "PREL": 0, "HEAT": 1, "R64-": 2, "R32-": 3,
               "R16-": 4, "8FNL": 5, "REP1": 6, "REP2": 6, "QFNL": 7,
               "REP3": 8, "REP4": 8, "SFNL": 9, "REP5": 10, "REPF": 10,
               "TMRY": 11, "FNL-": 12, "VICT": 13}


def _phase_rank(phase: str) -> int:
    if phase in _PHASE_RANK:
        return _PHASE_RANK[phase]
    if phase.startswith("GP"):
        return 1
    return 6


@dataclass
class UnitInfo:
    code: str
    event_key: tuple[str, str]  # (gender, event)
    phase: str
    order: int
    unit_seq: int               # sequence within the phase (from Eventunit)
    medal: str                  # '', '1' or '3'
    name: str


@dataclass
class EventInfo:
    gender: str
    event: str
    is_team: bool
    team_size: int
    entrants: int
    phases: dict[str, int] = field(default_factory=dict)


def _unit_rows(refdata, discipline: str):
    table = refdata.pack.codes.table("EVENT_UNIT")
    if table is None:
        return []
    rows = []
    for code, row in table._rows.items():
        f = row.fields
        if (f.get("Discipline") == discipline and f.get("Level") == "Unit"
                and f.get("Schedule") == "Y" and f.get("Phase") != "VICT"
                and f.get("Event") not in GEN_EVENTS):
            rows.append((code, f))
    return rows


def competitive_units(refdata, discipline: str) -> list[UnitInfo]:
    """All scheduled competitive event units, in a stable, sensible order:
    by event, then phase order (from the codes), then unit sequence."""
    units = []
    for code, f in _unit_rows(refdata, discipline):
        seq_txt = re.sub(r"[^0-9]", "", f.get("Eventunit", "")) or "0"
        try:
            order = int(f.get("Order") or 0)
        except ValueError:
            order = 0
        units.append(UnitInfo(
            code=code,
            event_key=(f.get("Gender", ""), f.get("Event", "")),
            phase=f.get("Phase", ""),
            order=order,
            unit_seq=int(seq_txt) // 100 if len(seq_txt) >= 3 else int(seq_txt),
            medal=f.get("Medalflag", "0") if f.get("Medalflag") in ("1", "3") else "",
            name=f.get("ENG_Description", "") or "Round",
        ))
    units.sort(key=lambda u: (u.event_key, u.order, _phase_rank(u.phase),
                              u.unit_seq, u.code))
    return units


def _event_row(refdata, discipline: str, gender: str, event: str):
    table = refdata.pack.codes.table("EVENT")
    if table is None:
        return None
    code = f"{discipline}{gender}{event}{'-' * 12}"[:34]
    row = table._rows.get(code)
    return row.fields if row is not None else None


def _entrants(phases: dict[str, int]) -> int:
    bracket = [phases[p] for p in _BRACKET_PHASES if p in phases]
    if bracket:
        return 2 * max(bracket)
    heats = [n for p, n in phases.items() if p.startswith("HEAT")]
    if heats:
        return 8 * max(heats)
    groups = [p for p in phases if p.startswith("GP")]
    if groups:
        return 4 * len(groups)
    return 8


def events(refdata, discipline: str) -> list[EventInfo]:
    """Competitive events with entrant counts derived from unit structure."""
    by_event: dict[tuple[str, str], dict[str, int]] = {}
    for u in competitive_units(refdata, discipline):
        by_event.setdefault(u.event_key, {})
        by_event[u.event_key][u.phase] = by_event[u.event_key].get(u.phase, 0) + 1

    out = []
    models_teams = refdata.has_teams(discipline)
    for (gender, event), phases in sorted(by_event.items()):
        row = _event_row(refdata, discipline, gender, event) or {}
        # Some codes rows carry Team_Event='Y' on events that are not squad
        # events in any team message (e.g. WST 'Combined'); only treat an
        # event as a team event when the event code says TEAM<n> or the
        # discipline actually models teams.
        is_team = "TEAM" in event or (row.get("Team_Event") == "Y" and models_teams)
        team_size = squad_size(discipline, event) if is_team else 1
        out.append(EventInfo(
            gender=gender, event=event, is_team=is_team, team_size=team_size,
            entrants=_entrants(phases), phases=phases))
    return out


def _row_to_unit(code: str, f: dict) -> UnitInfo:
    seq_txt = re.sub(r"[^0-9]", "", f.get("Eventunit", "")) or "0"
    try:
        order = int(f.get("Order") or 0)
    except ValueError:
        order = 0
    return UnitInfo(
        code=code,
        event_key=(f.get("Gender", ""), f.get("Event", "")),
        phase=f.get("Phase", ""),
        order=order,
        unit_seq=int(seq_txt) // 100 if len(seq_txt) >= 3 else int(seq_txt),
        medal=f.get("Medalflag", "0") if f.get("Medalflag") in ("1", "3") else "",
        name=f.get("ENG_Description", "") or "Round",
    )


def heat_pool(refdata, discipline: str) -> dict[tuple[str, str], list[UnitInfo]]:
    """All HEAT unit rows per event (scheduled or not), sorted by heat number.
    The codes define more heats than the pre-seeding schedule uses (e.g. 18
    per SWM event); the seeded-heats option draws real RSCs from this pool."""
    table = refdata.pack.codes.table("EVENT_UNIT")
    pool: dict[tuple[str, str], list[UnitInfo]] = {}
    if table is None:
        return pool
    for code, row in table._rows.items():
        f = row.fields
        if (f.get("Discipline") == discipline and f.get("Level") == "Unit"
                and f.get("Phase") == "HEAT"
                and f.get("Event") not in GEN_EVENTS):
            u = _row_to_unit(code, f)
            pool.setdefault(u.event_key, []).append(u)
    for units in pool.values():
        units.sort(key=lambda u: u.unit_seq)
    return pool


def victory_units(refdata, discipline: str) -> list[UnitInfo]:
    """Victory-ceremony units (Phase=VICT; Level 'Medals' in the codes) for
    every competitive event of the discipline."""
    table = refdata.pack.codes.table("EVENT_UNIT")
    out: list[UnitInfo] = []
    if table is None:
        return out
    for code, row in table._rows.items():
        f = row.fields
        if (f.get("Discipline") == discipline and f.get("Phase") == "VICT"
                and f.get("Eventunit", "--------") != "--------"
                and f.get("Event") not in GEN_EVENTS):
            out.append(_row_to_unit(code, f))
    out.sort(key=lambda u: (u.event_key, u.unit_seq, u.code))
    return out


def has_team_events(refdata, discipline: str) -> bool:
    """Whether the Common Codes schedule any team event for the discipline.
    This decides if a DT_PARTIC_TEAMS message applies — the codes are the
    source of truth, not the validator's rule heuristic (which emitted empty
    teams messages for SWM/ATH/JUD and dropped TKW's mixed team event)."""
    return any(e.is_team for e in events(refdata, discipline))


def discipline_venue(refdata, discipline: str) -> tuple[str, str, str, str]:
    """(venue, venue_name, location, location_name) for the discipline from
    the LOCATION table (its Discipline field is a comma-separated list)."""
    table = refdata.pack.codes.table("LOCATION")
    if table is not None:
        for code, row in sorted(table._rows.items()):
            f = row.fields
            discs = [d.strip() for d in (f.get("Discipline") or "").split(",")]
            if discipline in discs and f.get("Venue"):
                venue = f["Venue"]
                venue_name = (refdata.description("VENUE", venue, "ENG_Description")
                              or venue)
                return (venue, venue_name, code,
                        f.get("ENG_Description") or venue_name)
    return ("", "", "", "")
