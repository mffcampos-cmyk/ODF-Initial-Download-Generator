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
