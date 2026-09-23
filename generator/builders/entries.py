"""DT_ENTRIES — list of entries by event (GEN dictionary 2.1.5).

One message per event; @DocumentCode is the Event RSC (CC@EVENT). Entries are
sorted within the event by Organisation, Gender and Name. Following the
real-life feeds, every entry (athlete or team) carries its Composition with
Athlete Description; SWM entries also carry the qualification
time as ExtendedEntry Type="ENTRY" Code="QUAL_BEST"."""
from __future__ import annotations
import random
import re
from ..dataset import build_dataset
from ..envelope import build_odfbody, competition_code
from ..serialize import el, to_xml

# Rough qualification-time ranges (seconds) per swim distance, used to
# generate plausible QUAL_BEST values like the real CTO1 feed.
_SWM_TIME_RANGES = {50: (22.5, 33.0), 100: (49.0, 70.0), 200: (108.0, 155.0),
                    400: (235.0, 310.0), 800: (490.0, 640.0)}


def _format_time(seconds: float) -> str:
    if seconds < 100:
        return f"{seconds:.2f}"
    m, s = divmod(seconds, 60.0)
    return f"{int(m)}:{s:05.2f}"


def _qual_best(rng, event_rsc: str) -> str | None:
    m = re.match(r"SWM.(\d+)M", event_rsc)
    if not m:
        return None
    lo, hi = _SWM_TIME_RANGES.get(int(m.group(1)), (60.0, 120.0))
    return _format_time(lo + rng.random() * (hi - lo))


def _athlete_description(p):
    return el("Description", {
        "GivenName": p.given_name,
        "FamilyName": p.family_name,
        "Gender": p.gender,
        "Organisation": p.organisation,
        "BirthDate": p.birth_date,
        # No IFId. It is the International Federation's own identifier; the
        # real feed carries it only when the IF supplied one (11 of 84
        # athletes) and never equal to the ODF code. Copying @Code into it
        # asserted an IF registration that does not exist.
    })


def _athlete_entry(rng, p, order, event_rsc):
    entry = el("Entry", {
        "Code": p.code,
        "Type": "A",
        "Organisation": p.organisation,
        "SortOrder": str(order),
    })
    qual = _qual_best(rng, event_rsc)
    if qual:
        entry.append(el("ExtendedEntry",
                        {"Type": "ENTRY", "Code": "QUAL_BEST", "Value": qual}))
    comp = el("Composition", {})
    athlete = el("Athlete", {"Code": p.code, "Order": "1"})
    athlete.append(_athlete_description(p))
    comp.append(athlete)
    entry.append(comp)
    return entry


def _team_entry(t, people, order):
    entry = el("Entry", {
        "Code": t.code,
        "Type": "T",
        "Organisation": t.organisation,
        "SortOrder": str(order),
    })
    entry.append(el("Description", {"TeamName": t.name or t.short_name}))
    if t.member_codes:
        comp = el("Composition", {})
        for i, code in enumerate(t.member_codes, start=1):
            athlete = el("Athlete", {"Code": code, "Order": str(i)})
            p = people.get(code)
            if p is not None:
                athlete.append(_athlete_description(p))
            comp.append(athlete)
        entry.append(comp)
    return entry


def build_all(refdata, discipline: str, seed: int,
              overrides=None) -> list[tuple[str, bytes]]:
    """Build one DT_ENTRIES message per event; returns [(event_rsc, xml)]."""
    rng = random.Random(seed)
    ds = build_dataset(refdata, discipline, seed, overrides)
    people = {p.code: p for p in ds.participants}
    teams = {t.code: t for t in ds.teams}
    out: list[tuple[str, bytes]] = []
    for ev in ds.entries:
        # GEN 2.1.5.2 gives Entry cardinality (1,N): a DT_ENTRIES with no
        # entrants is not a valid message, so skip the event rather than emit
        # an envelope with nothing in it. Nothing in the validator catches
        # this -- it has no cardinality primitive, and the XSD does not
        # constrain Entry either.
        if not (ev.athlete_codes or ev.team_codes):
            continue
        root, comp = build_odfbody(rng, refdata, discipline, "DT_ENTRIES",
                                   competition_code(refdata),
                                   document_code=ev.event_rsc,
                                   overrides=overrides)
        order = 1
        # Sorted within the event by NOC, gender and name, per the spec.
        athletes = sorted((people[c] for c in ev.athlete_codes if c in people),
                          key=lambda p: (p.organisation, p.gender,
                                         p.family_name, p.given_name))
        for p in athletes:
            comp.append(_athlete_entry(rng, p, order, ev.event_rsc))
            order += 1
        for t in sorted((teams[c] for c in ev.team_codes if c in teams),
                        key=lambda t: t.organisation):
            comp.append(_team_entry(t, people, order))
            order += 1
        out.append((ev.event_rsc, to_xml(root)))
    return out
