from __future__ import annotations
import math
import random
from itertools import cycle
from . import fields, names, arc_profile, eventstructure, schedule_layout
from .model import (Participant, Team, ScheduleUnit, Session, Dataset,
                    EventEntries)


def _event_rsc(discipline: str, gender: str, event: str) -> str:
    """Event RSC per CC@EVENT: discipline(3) + gender(1) + event(18) + '-'x12."""
    return f"{discipline}{gender}{event}"[:34].ljust(34, "-")

_SCHEDULE_STATUS = eventstructure.SCHEDULED
# Default sport-entry status: CNF (Confirmed). The real SYOG26 download uses
# CNF/NPR for athletes and LGL/CNF for teams and never ENT; teams with named
# athletes lean CNF, and every generated team has its full squad.
_PARTICIPANT_STATUS = "CNF"
_ID_BASE = 9000000  # 7-digit participant IDs, as in the real-life feed
_MAX_NOCS = 60       # delegations to draw from per discipline

def _participant_status(rng, refdata) -> str:
    """A valid CC@PARTICIPANT_STATUS code. Prefer 'ENT' (Entered); if the code
    table is present but lacks it, fall back to a random member so output always
    passes code_membership validation."""
    codes = refdata.codes("PARTICIPANT_STATUS")
    if codes:
        return _PARTICIPANT_STATUS if _PARTICIPANT_STATUS in codes else rng.choice(codes)
    return _PARTICIPANT_STATUS


def _athlete_gender(event_gender: str, i: int) -> str:
    """Person gender for the i-th member of a squad in an event of the given
    gender. Mixed (X) events alternate, so a TEAM2 squad is one man and one
    woman, as in the real feeds."""
    if event_gender == "M":
        return "M"
    if event_gender == "W":
        return "F"
    return "M" if i % 2 == 0 else "F"


# Team@TeamType. GEN 2.1.3.5 makes it an SCGEN@TeamType code (ORG, CPLM, CPLW,
# CPLP, CUSTOM). Every team this generator builds is a NOC's team, and the real
# SYOG26 feed uses ORG for all 207 of its teams -- TTE mixed doubles and VBV
# pairs included, although SC@TeamType@VBV lists only CUSTOM and
# SC@TeamType@TTE offers CPLM. The generator used to pick CPLM for a mixed pair
# and fall back to a discipline table's first code (CUSTOM for VBV).
_TEAM_TYPE = "ORG"


def _main_function(refdata, role: str) -> str:
    """CC@DISCIPLINE_FUNCTION id for a role ('athlete'|'coach'|'judge').
    Mandatory for current participants per the data dictionary."""
    preferred = {"athlete": "AA01", "coach": "COACH", "judge": "JU"}[role]
    codes = refdata.codes("DISCIPLINE_FUNCTION")
    if not codes or preferred in codes:
        return preferred
    return codes[0]


def _nationality(refdata, org: str) -> str:
    """Nationality (CC@COUNTRY) — same as the organisation when it is a valid
    country member, else empty (attribute is then omitted)."""
    countries = refdata.codes("COUNTRY")
    if not countries or org in countries:
        return org
    return ""


def _participating_nocs(refdata) -> list[str]:
    """CC@NOC members that can send athletes to these Games.

    The table marks each NOC P (participating), H (historical: EUN, SCG, URS,
    FRG, ...) or NP (not participating: AIN, BOC, ROC). Only P belongs in a
    2026 feed; drawing from the whole table put the Unified Team in 14
    disciplines. A NOC table without a Participation column (another Games'
    workbook) is taken whole rather than emptied."""
    table = refdata.pack.codes.table("NOC")
    if table is None:
        return []
    rows = table._rows
    if not any("Participation" in r.fields for r in rows.values()):
        return sorted(rows)
    return sorted(c for c, r in rows.items()
                  if r.fields.get("Participation") == "P")


def _noc_pool(rng, refdata, count: int = _MAX_NOCS) -> list[str]:
    # Prefer the NOC table: CC@ORGANISATION also contains IFs and other
    # non-NOC organisations (e.g. UCI) that never appear on participants.
    for cs in ("NOC", "ORGANISATION", "COUNTRY"):
        codes = (_participating_nocs(refdata) if cs == "NOC"
                 else refdata.codes(cs))
        if codes:
            return rng.sample(codes, min(count, len(codes)))
    # Fallback: synthesize 3-letter org codes if no org table exists.
    return [fields.name_token(rng, 3).upper() for _ in range(4)]


def _person(rng, refdata, code: str, org: str, gender: str, role: str,
            status: str, used: set[str],
            function_code: str | None = None) -> Participant:
    given, family = names.person_name(rng, org, gender, used)
    birth = (fields.athlete_birth_date(rng) if role == "athlete"
             else fields.official_birth_date(rng))
    return Participant(
        code=code,
        parent=code,  # Parent must equal Code for current participants
        family_name=family,
        given_name=given,
        gender=gender,
        organisation=org,
        birth_date=birth,
        status=status,
        is_official=(role != "athlete"),
        nationality=_nationality(refdata, org),
        main_function=function_code or _main_function(refdata, role),
    )


def _generate_officials(add_person, refdata, discipline: str,
                        used_nocs: list[str], rng, coaches_override) -> None:
    """Append officials to the dataset via ``add_person(org, gender, role,
    function_code)``, using the discipline's real CC@DISCIPLINE_FUNCTION roles.

    Categories: C=Coach, J=Judge, T=Team official, S=Other/technical official.
    Coaches (C): ``coaches_override`` if given, else one per delegation.
    Judges/team/technical officials (J/T/S): one participant per published
    function code the discipline defines. When the pack exposes no function
    data for the discipline, fall back to the legacy behaviour (coach per
    delegation + 4 generic judges) so nothing regresses."""
    def rgender():
        return "M" if rng.random() < 0.5 else "F"

    funcs = refdata.discipline_functions(discipline)
    if not funcs:  # no Common-Codes function data available: legacy behaviour
        n = coaches_override if coaches_override is not None else len(used_nocs)
        for i in range(n):
            add_person(used_nocs[i % len(used_nocs)], rgender(), "coach", "COACH")
        for _ in range(4):
            add_person(rng.choice(used_nocs), rgender(), "judge", "JU")
        return

    coach_codes = [f.code for f in funcs if f.category == "C"]
    if coach_codes:  # discipline defines a coach role
        if coaches_override is not None:
            for i in range(coaches_override):
                add_person(rng.choice(used_nocs), rgender(), "coach",
                           coach_codes[i % len(coach_codes)])
        else:  # default: one head coach per delegation
            for noc in used_nocs:
                add_person(noc, rgender(), "coach", coach_codes[0])
    # Disciplines with no coach (C) role generate no coaches; the coaches
    # count then has no effect, since there is no valid code to assign.
    # Judges, team officials and technical officials: one per published code.
    for f in funcs:
        if f.category in ("J", "T", "S"):
            add_person(rng.choice(used_nocs), rgender(), "official", f.code)


# --------------------------------------------------------------------------
# ARC: embedded real-life profile (exact schedule times and delegation mix)
# --------------------------------------------------------------------------

def _build_arc_dataset(refdata, seed: int) -> Dataset:
    """Real-life-scale ARC dataset: 32 M + 32 W athletes across 47 NOCs,
    one coach per NOC, 4 judges (115 participants), 17 mixed teams, and the
    codes-derived schedule (counts match Common Codes EVENT_UNIT:
    a 16-match R32 bracket per individual event => 32 entrants)."""
    rng = random.Random(seed)
    status = _participant_status(rng, refdata)
    used: set[str] = set()
    known = set(_participating_nocs(refdata)) or None

    def keep(noc_list):
        return [n for n in noc_list if known is None or n in known]

    dual = keep(arc_profile.DUAL_NOCS)
    men = sorted(dual + keep(arc_profile.MEN_NOCS))
    women = sorted(dual + keep(arc_profile.WOMEN_NOCS))
    all_nocs = sorted(set(men) | set(women))

    participants: list[Participant] = []
    next_id = _ID_BASE
    men_codes: dict[str, str] = {}
    women_codes: dict[str, str] = {}
    for noc in men:
        next_id += 1
        p = _person(rng, refdata, str(next_id), noc, "M", "athlete", status, used)
        men_codes[noc] = p.code
        participants.append(p)
    for noc in women:
        next_id += 1
        p = _person(rng, refdata, str(next_id), noc, "F", "athlete", status, used)
        women_codes[noc] = p.code
        participants.append(p)
    # Officials from ARC's Common-Codes roles (coach per delegation, plus the
    # judges/team officials the codes define) instead of a fixed 4 judges.
    _next = [next_id]

    def _add_official(org, gender, role, function_code=None):
        _next[0] += 1
        participants.append(_person(rng, refdata, str(_next[0]), org, gender,
                                    role, status, used, function_code))

    _generate_officials(_add_official, refdata, "ARC", all_nocs, rng, None)
    next_id = _next[0]

    tt = _TEAM_TYPE
    teams: list[Team] = []
    for noc in dual:  # NOCs with one man + one woman form the mixed teams
        long_name = (refdata.description("NOC", noc, "ENG_longDescription")
                     or refdata.description("NOC", noc, "ENG_Description") or noc)
        short_name = refdata.description("NOC", noc, "ENG_Description") or noc
        teams.append(Team(
            code=f"ARCXTEAM2---{noc}01",
            organisation=noc,
            short_name=short_name,
            tv_team_name=long_name,
            gender="X",
            team_type=tt,
            status=status,
            member_codes=[men_codes[noc], women_codes[noc]],
            name=long_name,
        ))

    # The 2025 embedded calendar is retired: ARC schedules through the same
    # codes plan as every discipline (its plan matches the real SYOG26 ARC
    # schedule row for row). The profile still supplies the participant mix.
    venue, venue_name, location, location_name = \
        _discipline_venue(rng, refdata, "ARC")
    sessions, unscheduled = schedule_layout.lay_out(
        eventstructure.schedule_plan(refdata, "ARC"), "ARC",
        venue, venue_name, location, location_name)

    entries = [
        EventEntries(_event_rsc("ARC", "M", "INDIVID-----------"),
                     athlete_codes=[men_codes[n] for n in men]),
        EventEntries(_event_rsc("ARC", "W", "INDIVID-----------"),
                     athlete_codes=[women_codes[n] for n in women]),
        EventEntries(_event_rsc("ARC", "X", "TEAM2-------------"),
                     team_codes=[t.code for t in teams]),
    ]
    return Dataset(discipline="ARC", organisations=all_nocs,
                   participants=participants, teams=teams, sessions=sessions,
                   entries=entries, unscheduled=unscheduled)


# --------------------------------------------------------------------------
# All other disciplines: derived from the Common Codes tables
# --------------------------------------------------------------------------

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


def _build_codes_dataset(refdata, discipline: str, seed: int,
                         ov=None) -> Dataset:
    """Participants and schedule derived from EVENT / EVENT_UNIT / LOCATION.

    Unit list = every scheduled competitive event unit in the codes.
    Entrant counts per event come from the phase structure (see
    eventstructure._entrants). Individual bracket events get unique athletes
    per event (weight classes etc. are disjoint); non-bracket individual
    events share a per-gender pool (athletes enter several events, as in
    swimming/athletics); team events get one full squad per entrant slot.

    ``ov`` (normalized Overrides) can enable live-operations realism:
    qualification-scale entry lists, seeded heats and historical athletes.
    Victory ceremonies are always in the plan; the old option is a no-op."""
    rng = random.Random(seed)
    evs = eventstructure.events(refdata, discipline)
    units = eventstructure.competitive_units(refdata, discipline)
    if not units:
        return _build_fallback_dataset(refdata, discipline, seed)

    status = _participant_status(rng, refdata)
    if ov and ov.status and (not refdata.codes("PARTICIPANT_STATUS")
                             or ov.status in refdata.codes("PARTICIPANT_STATUS")):
        status = ov.status
    used: set[str] = set()
    nocs = _noc_pool(rng, refdata)
    noc_iter = cycle(nocs)
    participants: list[Participant] = []
    teams: list[Team] = []
    next_id = [_ID_BASE]

    def add_person(org, gender, role, function_code=None):
        next_id[0] += 1
        p = _person(rng, refdata, str(next_id[0]), org, gender, role, status,
                    used, function_code)
        participants.append(p)
        return p

    def athlete_gender(event_gender, i):
        if event_gender == "M":
            return "M"
        if event_gender == "W":
            return "F"
        return "M" if i % 2 == 0 else "F"

    # Individual events: bracket events are disjoint (unique athletes per
    # event); non-bracket events share a per-gender pool sized
    # min(sum(entrants), 2 * max(entrants)).
    event_entries: list[EventEntries] = []
    individual = [e for e in evs if not e.is_team]
    bracket = [e for e in individual
               if any(p in e.phases for p in ("R64-", "R32-", "R16-", "8FNL"))]
    pooled = [e for e in individual if e not in bracket]
    for ev in bracket:
        codes_for_event = [
            add_person(next(noc_iter), athlete_gender(ev.gender, i),
                       "athlete").code
            for i in range(ev.entrants)]
        event_entries.append(EventEntries(
            _event_rsc(discipline, ev.gender, ev.event),
            athlete_codes=codes_for_event))
    by_gender: dict[str, list] = {}
    for ev in pooled:
        by_gender.setdefault(ev.gender, []).append(ev)
    realistic = bool(ov and ov.realistic_entries)
    for gender, gender_events in sorted(by_gender.items()):
        if realistic:
            # Qualification-scale entry lists, as in the real feeds
            # (25-119 entries per SWM event, varying with popularity).
            targets = {id(e): rng.randint(24, 120) for e in gender_events}
            pool = min(200, max(int(max(targets.values()) * 1.3), 24))
        else:
            targets = {id(e): e.entrants for e in gender_events}
            total = sum(e.entrants for e in gender_events)
            pool = min(total, 2 * max(e.entrants for e in gender_events))
        pool_people = [add_person(next(noc_iter), athlete_gender(gender, i),
                                  "athlete") for i in range(pool)]
        for ev in gender_events:  # athletes enter several events, as in SWM/ATH
            want = targets[id(ev)]
            picked = (pool_people if want >= len(pool_people)
                      else rng.sample(pool_people, want))
            event_entries.append(EventEntries(
                _event_rsc(discipline, ev.gender, ev.event),
                athlete_codes=[p.code for p in picked]))

    # Team events: one squad per entrant slot, all members from the team NOC.
    for ev in (e for e in evs if e.is_team):
        tt = _TEAM_TYPE
        ev_entry = EventEntries(_event_rsc(discipline, ev.gender, ev.event))
        event_entries.append(ev_entry)
        prefix = f"{discipline}{ev.gender}{ev.event}"[:12].ljust(12, "-")
        team_nocs = [next(noc_iter) for _ in range(ev.entrants)]
        for noc in team_nocs:
            members = []
            for i in range(ev.team_size):
                members.append(add_person(noc, athlete_gender(ev.gender, i),
                                          "athlete").code)
            long_name = (refdata.description("NOC", noc, "ENG_longDescription")
                         or refdata.description("NOC", noc, "ENG_Description")
                         or noc)
            teams.append(Team(
                code=f"{prefix}{noc}01",
                organisation=noc,
                short_name=refdata.description("NOC", noc, "ENG_Description") or noc,
                tv_team_name=long_name,
                gender=ev.gender if ev.gender in ("M", "W", "X") else "X",
                team_type=tt,
                status=status,
                member_codes=members,
                name=long_name,
            ))
            ev_entry.team_codes.append(f"{prefix}{noc}01")

    # Officials: coaches (override count or one per delegation) plus judges,
    # team and technical officials taken from the discipline's Common Codes
    # (CC@DISCIPLINE_FUNCTION), replacing the former fixed 4 generic judges.
    used_nocs = sorted({p.organisation for p in participants})
    _generate_officials(add_person, refdata, discipline, used_nocs, rng,
                        ov.coaches if ov else None)

    # Historical athletes (real feeds include them in DT_PARTIC with
    # Status=HIS; spec: their IDs start with 'A'). Never entered in events.
    if ov and ov.historical_athletes:
        n_ath = sum(1 for p in participants if not p.is_official)
        for i in range(max(3, n_ath // 20)):
            noc = rng.choice(used_nocs)
            gender = "M" if rng.random() < 0.5 else "F"
            given, family = names.person_name(rng, noc, gender, used)
            participants.append(Participant(
                code=f"A{1000000 + i}", parent=f"A{1000000 + i}",
                family_name=family, given_name=given, gender=gender,
                organisation=noc,
                birth_date=(f"{rng.randint(1955, 1998):04d}-"
                            f"{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"),
                status="HIS", is_official=False,
                nationality=_nationality(refdata, noc),
                main_function=_main_function(refdata, "athlete")))

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


# --------------------------------------------------------------------------
# Fallback for packs without EVENT_UNIT data for the discipline
# --------------------------------------------------------------------------

def _build_fallback_dataset(refdata, discipline: str, seed: int) -> Dataset:
    rng = random.Random(seed)
    orgs = _noc_pool(rng, refdata, 4)
    status = _participant_status(rng, refdata)
    used: set[str] = set()

    participants: list[Participant] = []
    for i in range(6):
        org = rng.choice(orgs)
        role = "athlete" if i < 4 else "coach"  # last two are officials
        given, family = names.person_name(rng, org,
                                          fields.gender_participant(rng), used)
        participants.append(Participant(
            code=str(_ID_BASE + 1 + i), parent=str(_ID_BASE + 1 + i),
            family_name=family, given_name=given,
            gender=fields.gender_participant(rng), organisation=org,
            birth_date=(fields.athlete_birth_date(rng) if role == "athlete"
                        else fields.official_birth_date(rng)),
            status=status, is_official=(role != "athlete"),
            nationality=_nationality(refdata, org),
            main_function=_main_function(refdata, role)))

    athletes = [p for p in participants if not p.is_official]
    teams: list[Team] = []
    tt = _TEAM_TYPE
    for j in range(2):
        org = rng.choice(orgs)
        long_name = (refdata.description("NOC", org, "ENG_longDescription")
                     or refdata.description("NOC", org, "ENG_Description") or org)
        members = [a.code for a in rng.sample(athletes, min(2, len(athletes)))]
        teams.append(Team(
            code=f"{discipline}T{j:02d}", organisation=org,
            short_name=refdata.description("NOC", org, "ENG_Description") or org,
            tv_team_name=long_name, gender=fields.gender_team(rng),
            team_type=tt, status=status, member_codes=members, name=long_name))

    venue = fields.pick_code(rng, refdata, "VENUE") or fields.name_token(rng, 3).upper()
    venue_name = (refdata.description("VENUE", venue, "ENG_Description")
                  or fields.name_token(rng, 10).capitalize())
    start = fields.odf_datetime(rng)
    end = fields.odf_datetime(rng)
    session_code = f"{discipline}01"
    units = [ScheduleUnit(
        code=fields.unit_rsc(rng, discipline),
        phase_type=schedule_layout.PHASE_TYPE_COMPETITION,
        schedule_status=_SCHEDULE_STATUS,
        medal=rng.choice(["0", "0", "1"]),
        start_date=start, end_date=end,
        session_code=session_code, item_name="Round") for k in range(3)]
    fields.pick_code(rng, refdata, "SESSION_TYPE")  # keep the rng sequence
    sessions = [Session(
        venue=venue, venue_name=venue_name, session_code=session_code,
        start_date=start, end_date=end, units=units)]

    # No event structure in the pack for this discipline: single entries
    # message at discipline level (best effort).
    entries = [EventEntries(
        f"{discipline}"[:34].ljust(34, "-"),
        athlete_codes=[p.code for p in athletes],
        team_codes=[t.code for t in teams])]
    return Dataset(discipline=discipline, organisations=orgs,
                   participants=participants, teams=teams, sessions=sessions,
                   entries=entries)


def _apply_count_overrides(ds: Dataset, refdata, discipline: str, seed: int,
                           ov) -> Dataset:
    """Hard-override the exact number of athletes and/or teams.

    Blank counts keep the discipline's default (the count already in ``ds``);
    a supplied count is honoured exactly. Because arbitrary counts cannot map
    onto the real per-event entrant structure, DT_ENTRIES collapses to a single
    discipline-level message listing every individual athlete and every team.
    The baseline schedule is reused unchanged.

    ``athletes`` governs individual-event athletes; squad members are generated
    on top of it, because squad size is fixed by the event (an HBB squad is 4,
    an RU7 squad 7). ``teams`` is distributed round-robin across the
    discipline's real team events and is ignored for disciplines whose codes
    schedule none."""
    rng = random.Random(seed + 4242)
    base_athletes = [p for p in ds.participants if not p.is_official]
    status = (base_athletes[0].status if base_athletes
              else (ds.participants[0].status if ds.participants
                    else _participant_status(rng, refdata)))
    if ov.status and (not refdata.codes("PARTICIPANT_STATUS")
                      or ov.status in refdata.codes("PARTICIPANT_STATUS")):
        status = ov.status
    athlete_target = ov.athletes if ov.athletes is not None else len(base_athletes)
    team_target = ov.teams if ov.teams is not None else len(ds.teams)

    nocs = _noc_pool(rng, refdata)
    used: set[str] = set()
    next_id = [_ID_BASE]
    participants: list[Participant] = []
    afunc = _main_function(refdata, "athlete")

    def add_person(org, gender, role, function_code=None):
        next_id[0] += 1
        p = _person(rng, refdata, str(next_id[0]), org, gender, role, status,
                    used, function_code)
        participants.append(p)
        return p

    athletes = [add_person(nocs[i % len(nocs)], "M" if i % 2 == 0 else "F",
                           "athlete", afunc) for i in range(athlete_target)]

    # Teams come from the discipline's real team events, distributed round-robin
    # across them, so each team carries a genuine event's gender, RSC and squad
    # size. Disciplines whose codes schedule no team event get no teams at all —
    # bundle.py drops DT_PARTIC_TEAMS for them, so fabricating teams here would
    # leave DT_ENTRIES referencing teams that no message in the bundle declares.
    all_evs = eventstructure.events(refdata, discipline)
    team_evs = [e for e in all_evs if e.is_team]
    teams: list[Team] = []
    team_event_of: dict[str, tuple[str, str]] = {}   # team code -> (gender, event)
    seq: dict[tuple, int] = {}
    for j in range(team_target if team_evs else 0):
        ev = team_evs[j % len(team_evs)]
        org = nocs[j % len(nocs)]
        # Squad members are generated in addition to ``athlete_target``, which
        # governs individual-event athletes only.
        members = [add_person(org, _athlete_gender(ev.gender, i), "athlete",
                              afunc).code
                   for i in range(ev.team_size)]
        key = (ev.gender, ev.event, org)
        seq[key] = seq.get(key, 0) + 1
        prefix = f"{discipline}{ev.gender}{ev.event}"[:12].ljust(12, "-")
        long_name = (refdata.description("NOC", org, "ENG_longDescription")
                     or refdata.description("NOC", org, "ENG_Description") or org)
        team_code = f"{prefix}{org}{seq[key]:02d}"
        team_event_of[team_code] = (ev.gender, ev.event)
        teams.append(Team(
            code=team_code, organisation=org,
            short_name=refdata.description("NOC", org, "ENG_Description") or org,
            tv_team_name=long_name,
            gender=ev.gender if ev.gender in ("M", "W", "X") else "X",
            team_type=_TEAM_TYPE,
            status=status, member_codes=members, name=long_name))

    used_nocs = sorted({p.organisation for p in participants}) or list(nocs)
    _generate_officials(add_person, refdata, discipline, used_nocs, rng,
                        ov.coaches)

    # Entries are per event, exactly as on the default path. This used to be a
    # single discipline-level message whose @DocumentCode was the discipline
    # RSC ("SKB------...") -- but GEN 2.1.5.2 requires a CC@EVENT code there,
    # so every DT_ENTRIES built with a count override carried an invalid
    # DocumentCode. It validated clean because no rule checks DocumentCode
    # against CC@EVENT for this message type.
    #
    # Athletes are distributed round-robin across the discipline's individual
    # events; teams carry the event they were built for. Squad members are
    # represented by their team's entry, so they are not entered individually.
    indiv_evs = [e for e in all_evs if not e.is_team]
    by_event: dict[tuple[str, str], EventEntries] = {}

    def bucket(gender: str, event: str) -> EventEntries:
        key = (gender, event)
        if key not in by_event:
            by_event[key] = EventEntries(_event_rsc(discipline, gender, event))
        return by_event[key]

    # A discipline whose codes schedule only team events (e.g. FBS) has nowhere
    # to enter loose athletes; they still appear in DT_PARTIC as the
    # delegation's athlete pool, which is what DT_PARTIC is for.
    # Every entry event gets its message, entrants or not (C7).
    for ev in all_evs:
        bucket(ev.gender, ev.event)
    for i, a in enumerate(athletes):
        if not indiv_evs:
            break
        ev = indiv_evs[i % len(indiv_evs)]
        bucket(ev.gender, ev.event).athlete_codes.append(a.code)
    for t in teams:
        gender, event = team_event_of[t.code]
        bucket(gender, event).team_codes.append(t.code)

    # Every entry event, including those left without entrants: the builder
    # sends those in the DD-valid empty form (no <Competition>).
    entries = [e for _key, e in sorted(by_event.items())]
    out = Dataset(discipline=discipline, organisations=used_nocs,
                  participants=participants, teams=teams,
                  sessions=ds.sessions, entries=entries,
                  unscheduled=ds.unscheduled)
    # Preserve the historical-athletes option when combined with count
    # overrides (HIS athletes are added to DT_PARTIC but never entered).
    if ov.historical_athletes:
        _add_historical(refdata, out, seed)
    return out


def build_dataset(refdata, discipline: str, seed: int,
                  overrides=None) -> Dataset:
    ov = overrides.normalize() if overrides is not None else None
    # The embedded profile is real SYOG2026 archery data (exact schedule times,
    # real NOC mix). It must never be emitted under another Games.
    if discipline == "ARC" and refdata.games.pack_name == "SYOG26":
        # ARC uses the embedded participant profile. Entry-shaping options
        # switch it to the codes engine so they apply there too.
        schedule_opts = bool(ov and (ov.realistic_entries or ov.seeded_heats))
        if not schedule_opts:
            ds = _build_arc_dataset(refdata, seed)
            if ov and ov.historical_athletes:
                _add_historical(refdata, ds, seed)
            if ov and (ov.athletes is not None or ov.teams is not None):
                ds = _apply_count_overrides(ds, refdata, discipline, seed, ov)
            return ds
    ds = _build_codes_dataset(refdata, discipline, seed, ov)
    if ov and (ov.athletes is not None or ov.teams is not None):
        ds = _apply_count_overrides(ds, refdata, discipline, seed, ov)
    return ds


def _add_historical(refdata, ds: Dataset, seed: int) -> None:
    rng = random.Random(seed + 777)
    used: set[str] = set()
    n_ath = sum(1 for p in ds.participants if not p.is_official)
    for i in range(max(3, n_ath // 20)):
        noc = rng.choice(ds.organisations)
        gender = "M" if rng.random() < 0.5 else "F"
        given, family = names.person_name(rng, noc, gender, used)
        ds.participants.append(Participant(
            code=f"A{1000000 + i}", parent=f"A{1000000 + i}",
            family_name=family, given_name=given, gender=gender,
            organisation=noc,
            birth_date=(f"{rng.randint(1955, 1998):04d}-"
                        f"{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"),
            status="HIS", is_official=False,
            nationality=_nationality(refdata, noc),
            main_function=_main_function(refdata, "athlete")))
