from __future__ import annotations
import random
from ..dataset import build_dataset
from ..envelope import build_odfbody, competition_code
from ..serialize import el, to_xml


def _session_el(s):
    name = el("SessionName", {"Language": "ENG", "Value": s.name})
    return el("Session", {
        "Venue": s.venue,
        "VenueName": s.venue_name,
        "SessionType": s.session_type,  # dropped by el() when empty
        "SessionCode": s.session_code,
        "StartDate": s.start_date,
        "EndDate": s.end_date,
    }, name)


def _unit_el(u, s):
    item = el("ItemName", {"Language": "ENG", "Value": u.item_name})
    venue_desc = None
    if s.venue_name:
        venue_desc = el("VenueDescription", {
            "VenueName": s.venue_name,
            "LocationName": s.location_name or s.venue_name,
        })
    return el("Unit", {
        "Code": u.code,
        "PhaseType": u.phase_type,
        "UnitNum": u.unit_num,          # dropped by el() when empty
        "ScheduleStatus": u.schedule_status,
        "StartDate": u.start_date,
        "EndDate": u.end_date,
        "Medal": u.medal,
        "Order": str(u.sort_order),
        "Venue": s.venue,
        "Location": s.location,         # dropped by el() when empty
        "SessionCode": u.session_code or s.session_code,
    }, item, venue_desc)


def build(refdata, discipline: str, seed: int, overrides=None) -> bytes:
    rng = random.Random(seed)
    ds = build_dataset(refdata, discipline, seed, overrides)
    root, comp = build_odfbody(rng, refdata, discipline, "DT_SCHEDULE",
                               competition_code(refdata), overrides=overrides)
    # In competitionType, Session lives in the outer sequence while Unit is
    # part of the inner choice branch; Session elements must precede Unit
    # elements for the document to validate against the XSD's ordering.
    for s in ds.sessions:
        comp.append(_session_el(s))
    for s in ds.sessions:
        for u in s.units:
            comp.append(_unit_el(u, s))
    return to_xml(root)
