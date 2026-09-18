"""Session and unit datetimes must be internally coherent.

The validator cannot catch any of this: its rule vocabulary has no
datetime-coherence primitive and the XSD only checks that a value parses as a
dateTime. So DT_SCHEDULE messages with EndDate before StartDate validated
clean for months and shipped into samples/ (ATH03: 09:30 -> 09:22, plus nine
more across eight disciplines).

These assert the invariant directly against the dataset, so a regression
fails here rather than silently passing validation.
"""
from __future__ import annotations

from datetime import datetime

from generator.dataset import build_dataset
from generator.refdata import RefData
from tests.conftest import PACK


def rd():
    return RefData(PACK)


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _check_discipline(refdata, discipline: str, *,
                      sequential: bool = True) -> None:
    """Assert every session/unit datetime relationship that must hold.

    ``sequential`` asserts additionally that units do not overlap. That is an
    invariant of the codes-driven engine, which lays units end-to-end in a
    session, but NOT of ODF in general: ARC's real feed runs three
    qualification units concurrently (men's individual, women's individual and
    mixed team, all 09:30-12:30), which is ordinary for archery.
    """
    ds = build_dataset(refdata, discipline, seed=1)
    assert ds.sessions, f"{discipline}: no sessions built"
    for s in ds.sessions:
        s_start, s_end = _parse(s.start_date), _parse(s.end_date)
        assert s_start <= s_end, (
            f"{discipline} {s.session_code}: session ends before it starts "
            f"({s.start_date} -> {s.end_date})")
        previous_end = None
        for u in s.units:
            u_start, u_end = _parse(u.start_date), _parse(u.end_date)
            assert u_start <= u_end, (
                f"{discipline} {s.session_code} {u.code}: unit ends before it "
                f"starts ({u.start_date} -> {u.end_date})")
            assert s_start <= u_start, (
                f"{discipline} {s.session_code} {u.code}: unit starts "
                f"{u.start_date}, before its session's {s.start_date}")
            assert u_end <= s_end, (
                f"{discipline} {s.session_code} {u.code}: unit ends "
                f"{u.end_date}, after its session's {s.end_date}")
            if sequential and previous_end is not None:
                assert previous_end <= u_start, (
                    f"{discipline} {s.session_code} {u.code}: unit starts "
                    f"{u.start_date}, before the previous unit ended "
                    f"{previous_end.isoformat()}")
            previous_end = u_end


def test_arc_schedule_times_are_coherent():
    """ARC carries the real feed's own dates via the embedded profile.

    Its qualification units are concurrent, so only the containment and
    start<=end relationships apply -- see _check_discipline.
    """
    _check_discipline(rd(), "ARC", sequential=False)


def test_codes_driven_schedule_times_are_coherent():
    """The codes-driven engine, which is where the arithmetic bug lived.

    ATH and CRD are the two disciplines whose session lengths hit the dropped
    carry (a chunk of 3, 4, 7, 8, 9, 12 or 13 units at 13 minutes each). JUD
    is the longest schedule, so it exercises the day rollover.
    """
    refdata = rd()
    for discipline in ("ATH", "CRD", "JUD", "SWM"):
        _check_discipline(refdata, discipline)


def test_schedule_never_emits_an_impossible_calendar_date():
    """The old formatter hardcoded month 11 and would have emitted
    2026-11-31 for any discipline reaching day 31."""
    refdata = rd()
    for discipline in ("JUD", "FEN"):
        ds = build_dataset(refdata, discipline, seed=1)
        for s in ds.sessions:
            # fromisoformat rejects an out-of-range day outright.
            _parse(s.start_date)
            _parse(s.end_date)
