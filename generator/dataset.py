from __future__ import annotations
import random
from datetime import datetime, timedelta, timezone
from itertools import cycle
from . import fields, names, arc_profile, eventstructure
from .model import (Participant, Team, ScheduleUnit, Session, Dataset,
                    EventEntries)


def _event_rsc(discipline: str, gender: str, event: str) -> str:
    """Event RSC per CC@EVENT: discipline(3) + gender(1) + event(18) + '-'x12."""
    return f"{discipline}{gender}{event}"[:34].ljust(34, "-")

_SCHEDULE_STATUS = "SCHEDULED"  # fallback when SCHEDULESTATUS code table is absent
_PARTICIPANT_STATUS = "ENT"  # Entered — default sport-entry status for an initial download
_ID_BASE = 9000000  # 7-digit participant IDs, as in the real-life feed
_MAX_NOCS = 60       # delegations to draw from per discipline
_UNITS_PER_SESSION = 16
_UNIT_MINUTES = 13   # slot length within a session, as in the real ARC feed


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


def _team_type(refdata, discipline: str, gender: str = "",
               team_size: int = 0) -> str:
    """@TeamType for a squad: an SC@TeamType code chosen by what the squad is.

    GEN 2.1.3.5 defines Team@TeamType as an SCGEN@TeamType code -- ORG
    ("Organisation"), CPLM ("Couple, male first"), CPLW, CPLP, CUSTOM. The
    attribute is required by the XSD, so it always has to carry one of them.

    Two things were wrong before. Disciplines with no SC@TeamType@<disc> table
    (TKW is the only one in SYOG26) fell back to DISCIPLINE_GENDER and emitted
    a 34-character RSC, "TKWX------...", where the spec wants a short code --
    invisible because TKW is also the one discipline with no code_membership
    rule to catch it. And the value was drawn once per discipline with
    rng.choice, so a discipline publishing both ORG and CPLM got whichever the
    seed happened to pick, for every event.

    Now: the discipline's own table where it has one, SC@TeamType@GEN
    otherwise, and the choice is semantic rather than random -- a two-person
    mixed squad is a couple, anything else is an organisation. Deterministic,
    so it consumes no rng.
    """
    codes = (refdata.codes(f"SC@TeamType@{discipline}")
             or refdata.codes("SC@TeamType@GEN") or [])
    if not codes:
        return "ORG"
    # A mixed pair. _athlete_gender alternates from M for an X event, so the
    # squad really is male-first, which is what CPLM asserts.
    if gender == "X" and team_size == 2 and "CPLM" in codes:
        return "CPLM"
    return "ORG" if "ORG" in codes else codes[0]


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


def _noc_pool(rng, refdata, count: int = _MAX_NOCS) -> list[str]:
    # Prefer the NOC table: CC@ORGANISATION also contains IFs and other
    # non-NOC organisations (e.g. UCI) that never appear on participants.
    for cs in ("NOC", "ORGANISATION", "COUNTRY"):
        codes = refdata.codes(cs)
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
    real 9-session / 83-unit schedule (counts match Common Codes EVENT_UNIT:
    a 16-match R32 bracket per individual event => 32 entrants)."""
    rng = random.Random(seed)
    status = _participant_status(rng, refdata)
    used: set[str] = set()
    known = set(refdata.codes("NOC")) or None

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

    tt = _team_type(refdata, "ARC", gender="X", team_size=2)
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

    sessions: list[Session] = []
    by_code: dict[str, Session] = {}
    for code, stype, start, end, name in arc_profile.SESSIONS:
        s = Session(
            venue=arc_profile.VENUE, venue_name=arc_profile.VENUE_NAME,
            session_code=code, start_date=start, end_date=end, name=name,
            session_type=stype, location=arc_profile.LOCATION,
            location_name=arc_profile.LOCATION_NAME)
        sessions.append(s)
        by_code[code] = s
    for (code, phase_type, unit_num, start, end, medal, order,
         session_code, item_name) in arc_profile.UNITS:
        by_code[session_code].units.append(ScheduleUnit(
            code=code, phase_type=phase_type, schedule_status=_SCHEDULE_STATUS,
            sort_order=int(order), medal=medal or None, unit_num=unit_num,
            start_date=start, end_date=end, session_code=session_code,
            item_name=item_name))

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
                   entries=entries)


# --------------------------------------------------------------------------
# All other disciplines: derived from the Common Codes tables
# --------------------------------------------------------------------------

# First day of the synthetic competition window. Only the codes-driven engine
# uses it; ARC carries the real feed's own dates (see arc_profile).
_SCHEDULE_BASE = datetime(2026, 11, 1, tzinfo=timezone.utc)


def _dt(day: int, hour: int = 0, minute: int = 0) -> datetime:
    """An instant in the competition window, ``day`` counted from 1.

    Real ``datetime`` arithmetic, not f-string formatting. The previous
    version built the string from hand-rolled divmod and dropped the carry
    when ``start_m + total % 60`` crossed the hour, emitting sessions whose
    EndDate preceded their StartDate (ATH03: 09:30 -> 09:22). It also
    hardcoded month 11, so a discipline long enough to reach day 31 would
    have produced 2026-11-31. Both are structurally impossible here."""
    return _SCHEDULE_BASE + timedelta(days=day - 1, hours=hour, minutes=minute)


def _fmt_dt(moment: datetime) -> str:
    """ODF datetime: ``2026-11-01T09:30:00+00:00``."""
    return moment.isoformat()


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
    qualification-scale entry lists, seeded heats, victory ceremonies and
    historical athletes — modeled on the real CTO1/AWAARC1 feeds."""
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
        tt = _team_type(refdata, discipline, ev.gender, ev.team_size)
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

    # Schedule: chunk the codes-defined units into morning/afternoon sessions.
    sched_units = list(units)
    entries_by_event = {e.event_rsc: e for e in event_entries}
    if ov and ov.seeded_heats:
        # Heats follow the entry lists (ceil(entries/8) lanes of 8), drawing
        # real RSCs from the codes' full heat pool — as in the real feed.
        import math
        pool = eventstructure.heat_pool(refdata, discipline)
        for ev in evs:
            key = (ev.gender, ev.event)
            if key not in pool:
                continue
            e_list = entries_by_event.get(
                _event_rsc(discipline, ev.gender, ev.event))
            n_entries = len(e_list.athlete_codes) if e_list else ev.entrants
            need = max(1, math.ceil(n_entries / 8))
            old_heats = [u for u in sched_units
                         if u.event_key == key and u.phase == "HEAT"]
            keep_order = min((u.order for u in old_heats), default=0)
            sched_units = [u for u in sched_units
                           if not (u.event_key == key and u.phase == "HEAT")]
            for h in pool[key][:min(need, len(pool[key]))]:
                h.order = keep_order or h.order
                sched_units.append(h)
    if ov and ov.victory_ceremonies:
        for v in eventstructure.victory_units(refdata, discipline):
            v.order = 999  # after the finals of its event
            sched_units.append(v)
    sched_units.sort(key=lambda u: (u.event_key, u.order,
                                    eventstructure._phase_rank(u.phase),
                                    u.unit_seq, u.code))

    venue, venue_name, location, location_name = \
        eventstructure.discipline_venue(refdata, discipline)
    if not venue:
        venue = fields.pick_code(rng, refdata, "VENUE") or "ALL"
        venue_name = (refdata.description("VENUE", venue, "ENG_Description")
                      or venue)
        location, location_name = "", ""
    session_types = refdata.codes("SESSION_TYPE")
    phase_counts: dict[tuple, dict[str, int]] = {}
    for u in sched_units:
        phase_counts.setdefault(u.event_key, {})
        phase_counts[u.event_key][u.phase] = \
            phase_counts[u.event_key].get(u.phase, 0) + 1

    sessions: list[Session] = []
    schedule_status = _SCHEDULE_STATUS
    codes = refdata.codes("SCHEDULESTATUS")
    if codes and schedule_status not in codes:
        schedule_status = rng.choice(codes)
    chunks = [sched_units[i:i + _UNITS_PER_SESSION]
              for i in range(0, len(sched_units), _UNITS_PER_SESSION)]
    for idx, chunk in enumerate(chunks):
        day = 1 + idx // 2
        morning = idx % 2 == 0
        start_h = 9 if morning else 14
        start_m = 30 if morning else 0
        stype = ("MOR" if morning else "AFT")
        if session_types and stype not in session_types:
            stype = session_types[0]
        session_code = f"{discipline}{idx + 1:02d}"
        session_start = _dt(day, start_h, start_m)
        session_end = session_start + timedelta(
            minutes=len(chunk) * _UNIT_MINUTES)
        s = Session(
            venue=venue, venue_name=venue_name, session_code=session_code,
            start_date=_fmt_dt(session_start),
            end_date=_fmt_dt(session_end),
            name=f"Session {idx + 1}", session_type=stype,
            location=location, location_name=location_name)
        cursor = session_start
        for order, u in enumerate(chunk, start=1):
            u_start = _fmt_dt(cursor)
            cursor += timedelta(minutes=_UNIT_MINUTES)
            u_end = _fmt_dt(cursor)
            multi = phase_counts[u.event_key].get(u.phase, 0) > 1
            s.units.append(ScheduleUnit(
                code=u.code,
                phase_type=fields.pick_code(rng, refdata, "PHASE_TYPE") or "3",
                schedule_status=schedule_status,
                sort_order=order,
                medal=u.medal or None,
                unit_num=str(u.unit_seq) if multi and u.unit_seq else "",
                start_date=u_start,
                end_date=u_end,
                session_code=session_code,
                item_name=u.name,
            ))
        sessions.append(s)

    return Dataset(discipline=discipline, organisations=used_nocs,
                   participants=participants, teams=teams, sessions=sessions,
                   entries=event_entries)


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
    tt = _team_type(refdata, discipline)
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
        phase_type=fields.pick_code(rng, refdata, "PHASE_TYPE") or "1",
        schedule_status=_SCHEDULE_STATUS,
        sort_order=k + 1, medal=rng.choice([None, "0", "1"]),
        unit_num=str(k + 1), start_date=start, end_date=end,
        session_code=session_code, item_name="Round") for k in range(3)]
    sessions = [Session(
        venue=venue, venue_name=venue_name, session_code=session_code,
        start_date=start, end_date=end, name="Session 1", units=units,
        session_type=fields.pick_code(rng, refdata, "SESSION_TYPE") or "")]

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
            team_type=_team_type(refdata, discipline, ev.gender, ev.team_size),
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
    for i, a in enumerate(athletes):
        if not indiv_evs:
            break
        ev = indiv_evs[i % len(indiv_evs)]
        bucket(ev.gender, ev.event).athlete_codes.append(a.code)
    for t in teams:
        gender, event = team_event_of[t.code]
        bucket(gender, event).team_codes.append(t.code)

    # Only events that actually have entrants. Emitting an EventEntries with
    # neither athletes nor teams produced a DT_ENTRIES with zero <Entry>
    # elements, violating Entry (1,N) -- reachable with athletes=0&teams=0.
    entries = [e for _key, e in sorted(by_event.items())
               if e.athlete_codes or e.team_codes]
    out = Dataset(discipline=discipline, organisations=used_nocs,
                  participants=participants, teams=teams,
                  sessions=ds.sessions, entries=entries)
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
        # ARC uses the embedded real-life profile (exact schedule times).
        # Schedule-affecting options switch it to the codes-driven engine so
        # the options apply there too.
        schedule_opts = bool(ov and (ov.realistic_entries or ov.seeded_heats
                                     or ov.victory_ceremonies))
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
