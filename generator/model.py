from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Participant:
    code: str
    parent: str
    family_name: str
    given_name: str
    gender: str
    organisation: str
    birth_date: str
    status: str = "ENT"
    is_official: bool = False
    nationality: str = ""          # CC@COUNTRY; usually same as organisation
    main_function: str = "AA01"    # CC@DISCIPLINE_FUNCTION; AA01=Athlete


@dataclass
class Team:
    code: str
    organisation: str
    short_name: str
    tv_team_name: str
    gender: str
    team_type: str
    status: str = "ENT"
    member_codes: list[str] = field(default_factory=list)
    name: str = ""                 # full team name (e.g. country long name)


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


@dataclass
class EventEntries:
    """Entries for one event: DT_ENTRIES is a per-event message whose
    DocumentCode is the Event RSC (CC@EVENT)."""
    event_rsc: str
    athlete_codes: list[str] = field(default_factory=list)
    team_codes: list[str] = field(default_factory=list)


@dataclass
class Dataset:
    discipline: str
    organisations: list[str]
    participants: list[Participant]
    teams: list[Team]
    sessions: list[Session]
    entries: list[EventEntries] = field(default_factory=list)
    unscheduled: list[ScheduleUnit] = field(default_factory=list)
