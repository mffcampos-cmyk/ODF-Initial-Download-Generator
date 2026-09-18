"""DT_ENTRIES @DocumentCode is an Event RSC, on every path.

GEN 2.1.5.2 requires @DocumentCode to be a CC@EVENT code. The count-override
path used to collapse all entries into one message whose DocumentCode was the
*discipline* RSC ("SKB------------..."), and could emit a message with zero
Entry elements against a stated cardinality of (1,N).

Neither was caught: the validator has no rule checking DocumentCode against
CC@EVENT for this message type, and no cardinality primitive at all.
"""
from __future__ import annotations

from lxml import etree

from generator.bundle import build_bundle
from generator.overrides import Overrides
from generator.refdata import RefData
from tests.conftest import PACK

RD = RefData(PACK)


def _event_codes():
    return {c for c in RD.codes("EVENT")}


def _entries_docs(bundle):
    return [(k, etree.fromstring(x)) for k, (x, _e) in bundle.items()
            if k.startswith("DT_ENTRIES")]


def test_document_code_is_an_event_code_with_count_overrides():
    events = _event_codes()
    assert events, "pack has no EVENT code table"
    for ov in (Overrides(athletes=40), Overrides(teams=6),
               Overrides(athletes=25, teams=4)):
        bundle = build_bundle(RD, "TKW", seed=1, overrides=ov)
        docs = _entries_docs(bundle)
        assert docs, f"no DT_ENTRIES produced for {ov}"
        for key, root in docs:
            code = root.get("DocumentCode")
            assert code in events, (
                f"{key}: DocumentCode {code!r} is not a CC@EVENT code "
                f"(overrides={ov})")


def test_document_code_is_never_the_discipline_rsc():
    """The specific regression: 'SKB' padded to 34 dashes."""
    disc_rsc = "SKB".ljust(34, "-")
    bundle = build_bundle(RD, "SKB", seed=1, overrides=Overrides(athletes=30))
    for key, root in _entries_docs(bundle):
        assert root.get("DocumentCode") != disc_rsc, (
            f"{key}: DocumentCode collapsed to the discipline RSC")


def test_no_entries_message_is_emitted_without_entrants():
    """athletes=0 & teams=0 used to emit a DT_ENTRIES holding only
    <Competition>, violating Entry (1,N)."""
    bundle = build_bundle(RD, "TKW", seed=1,
                          overrides=Overrides(athletes=0, teams=0))
    for key, root in _entries_docs(bundle):
        assert list(root.iter("Entry")), f"{key}: DT_ENTRIES with zero entries"


def test_every_emitted_entries_message_has_at_least_one_entry():
    for ov in (None, Overrides(athletes=12), Overrides(athletes=0, teams=3)):
        for key, root in _entries_docs(build_bundle(RD, "TKW", 1, overrides=ov)):
            assert list(root.iter("Entry")), f"{key} empty (overrides={ov})"
