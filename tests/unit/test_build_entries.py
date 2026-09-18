"""DT_ENTRIES is a per-event message (GEN dictionary 2.1.5): DocumentCode is
the Event RSC (CC@EVENT), one message per event, entries sorted within the
event. Team entries carry their composition."""
from lxml import etree

from generator.builders import entries
from generator.dataset import build_dataset
from generator.refdata import RefData
from generator.selfcheck import errors
from tests.conftest import PACK


def rd():
    return RefData(PACK)


def test_entries_are_one_message_per_event_with_event_rsc():
    msgs = entries.build_all(rd(), "ARC", seed=1)
    assert len(msgs) == 3  # M INDIVID, W INDIVID, X TEAM2
    for event_rsc, xml in msgs:
        assert len(event_rsc) == 34
        root = etree.fromstring(xml)
        assert root.get("DocumentCode") == event_rsc
        assert root.get("DocumentType") == "DT_ENTRIES"
    by_event = {rsc: etree.fromstring(xml) for rsc, xml in msgs}
    m = by_event["ARCMINDIVID" + "-" * 23]
    w = by_event["ARCWINDIVID" + "-" * 23]
    x = by_event["ARCXTEAM2" + "-" * 25]
    assert len(list(m.iter("Entry"))) == 32
    assert len(list(w.iter("Entry"))) == 32
    x_entries = list(x.iter("Entry"))
    assert len(x_entries) == 17 and all(e.get("Type") == "T" for e in x_entries)


def test_team_entries_carry_composition():
    msgs = dict(entries.build_all(rd(), "ARC", seed=1))
    x = etree.fromstring(msgs["ARCXTEAM2" + "-" * 25])
    ds = build_dataset(rd(), "ARC", seed=1)
    people = {p.code for p in ds.participants}
    for e in x.iter("Entry"):
        assert e.find("Description") is not None
        assert e.find("Description").get("TeamName")
        athletes = e.findall("Composition/Athlete")
        assert len(athletes) == 2  # mixed team of 2
        for a in athletes:
            assert a.get("Code") in people


def test_all_entries_messages_validate_clean():
    for disc in ("ARC", "WST"):
        for _rsc, xml in entries.build_all(rd(), disc, seed=1):
            assert errors(xml, PACK) == []


def test_wst_entries_split_by_event():
    msgs = entries.build_all(rd(), "WST", seed=1)
    assert len(msgs) == 4  # M/W Changquan & Taijiquan Combined
    for _rsc, xml in msgs:
        es = list(etree.fromstring(xml).iter("Entry"))
        assert len(es) == 8  # entrants per event from the codes
        orders = [int(e.get("SortOrder")) for e in es]
        assert orders == sorted(orders) and len(set(orders)) == len(orders)


def test_entry_codes_reference_dataset_participants():
    ds = build_dataset(rd(), "ARC", seed=1)
    known = {p.code for p in ds.participants} | {t.code for t in ds.teams}
    for _rsc, xml in entries.build_all(rd(), "ARC", seed=1):
        root = etree.fromstring(xml)
        codes = [e.get("Code") for e in root.iter("Entry")]
        assert codes and all(c in known for c in codes)


def test_athlete_entries_carry_composition_with_description():
    # Real-life feeds wrap even Type="A" entries in Composition/Athlete/
    # Description (with IFId), matching the GEN structure.
    for _rsc, xml in entries.build_all(rd(), "SWM", seed=1):
        root = etree.fromstring(xml)
        for e in root.iter("Entry"):
            if e.get("Type") != "A":
                continue
            athletes = e.findall("Composition/Athlete")
            assert len(athletes) == 1
            a = athletes[0]
            assert a.get("Code") == e.get("Code")
            d = a.find("Description")
            assert d is not None
            assert d.get("FamilyName") and d.get("Gender")
            assert d.get("IFId") == e.get("Code")


def test_swm_entries_have_qualification_times():
    # Real-life SWM entries carry ExtendedEntry Type=ENTRY Code=QUAL_BEST.
    import re
    msgs = entries.build_all(rd(), "SWM", seed=1)
    for _rsc, xml in msgs:
        root = etree.fromstring(xml)
        for e in root.iter("Entry"):
            ext = e.find("ExtendedEntry")
            assert ext is not None
            assert ext.get("Type") == "ENTRY" and ext.get("Code") == "QUAL_BEST"
            assert re.fullmatch(r"(\d+:)?\d{1,2}\.\d{2}", ext.get("Value"))
