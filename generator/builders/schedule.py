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
