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
