"""A bundle is one batch, so it must be validated as one.

`cross_message` is a registered validator primitive, and the validator's own
/validate/batch endpoint builds a shared ValidationContext so it can fire.
This project never did: selfcheck.errors() called Pipeline.run(xml, pack) with
no context, so every message of a bundle was checked in isolation -- and a
bundle is exactly the message set (DT_PARTIC + DT_PARTIC_TEAMS + DT_ENTRIES_*
+ DT_SCHEDULE) those rules exist to compare.

The context must be per attempt, not per bundle call: the retry loop is free
to walk away from a seed, and facts remembered from a discarded attempt would
otherwise be compared against the next one's messages -- reporting a conflict
between two messages that never shipped together.
"""
from __future__ import annotations

from odf_validator.context import ValidationContext
from odf_validator.model import Scope, Severity
from odf_validator.rules.defs_model import AppliesTo, RuleDef

from generator import bundle as bundle_mod
from generator.bundle import build_bundle
from generator.refdata import RefData
from generator.selfcheck import errors
from tests.conftest import PACK

RD = RefData(PACK)

CLEAN = (b'<?xml version="1.0" encoding="UTF-8"?>'
         b'<OdfBody CompetitionCode="X" DocumentCode="D" DocumentType="DT_PARTIC" '
         b'Version="1" FeedFlag="P" Date="2026-01-01" Time="000000000" '
         b'LogicalDate="2026-01-01" Source="S"><Competition Gen="G" Codes="C">'
         b'<Discipline Code="ARC"/></Competition></OdfBody>')


def test_errors_accepts_a_context_and_still_works_without_one():
    # Nothing in the shipped pack uses cross_message yet, so the context need
    # not have been written to -- what matters is that the parameter exists
    # and reaches the pipeline rather than being dropped on the floor. The
    # end-to-end proof that it is actually used is the last test below.
    assert isinstance(errors(CLEAN, PACK, ValidationContext()), list)
    assert isinstance(errors(CLEAN, PACK), list)


class _Recorder:
    """Stands in for selfcheck.errors, recording which context it was handed."""

    def __init__(self):
        self.seen: list = []

    def __call__(self, xml, pack, ctx=None):
        self.seen.append(ctx)
        return []


def test_every_message_in_one_attempt_shares_one_context(monkeypatch):
    rec = _Recorder()
    monkeypatch.setattr(bundle_mod, "check_errors", rec)
    b = build_bundle(RD, "ARC", seed=1)
    assert len(b) > 1, "ARC should produce several messages"
    assert all(c is not None for c in rec.seen), \
        "every message must be validated with a context"
    assert len({id(c) for c in rec.seen}) == 1, \
        "one attempt is one batch: all its messages share a context"


def test_a_retry_gets_a_fresh_context(monkeypatch):
    """Seed 1 is rejected, so seed 2 runs. The second attempt must not inherit
    what the first attempt remembered."""
    contexts: list = []

    def failing_first_attempt(xml, pack, ctx=None):
        contexts.append(ctx)
        # Reject every message validated with the first context handed out,
        # and accept everything after it. That is the attempt boundary,
        # whatever number of messages the attempt happens to contain.
        return ["FAKE_RULE: forced"] if ctx is contexts[0] else []

    monkeypatch.setattr(bundle_mod, "check_errors", failing_first_attempt)
    b = build_bundle(RD, "ARC", seed=1)
    assert b.seed_used == 2, "the first attempt was rejected, so seed 2 is used"
    assert b.clean is True
    assert len({id(c) for c in contexts}) == 2, \
        "each attempt gets its own context; a discarded seed leaves no trace"


def test_a_cross_message_rule_fires_across_a_bundle():
    """End to end: a cross_message rule sees a second message's value.

    This is the behaviour the wiring exists for, and the only test here that
    would still pass if `errors` accepted a context and quietly ignored it.
    Both messages carry Competition/@Gen; keyed on @Codes, the second must be
    reported as contradicting the first -- which happens only if the two runs
    share a context.
    """
    rule = RuleDef(
        id="TEST_GEN_CONSISTENT",
        applies_to=AppliesTo(),
        primitive="cross_message",
        target=".//Competition",
        attribute="Gen",
        params={"key_attr": "Codes"},
        severity=Severity.ERROR,
        scope=Scope.CONTEXT,
        source_ref="test",
    )
    first = (b'<?xml version="1.0"?><OdfBody CompetitionCode="X" DocumentCode="D" '
             b'DocumentType="DT_PARTIC" Version="1" FeedFlag="P" Date="2026-01-01" '
             b'Time="000000000" LogicalDate="2026-01-01" Source="S">'
             b'<Competition Gen="V1" Codes="CC"><Discipline Code="ARC"/>'
             b'</Competition></OdfBody>')
    second = first.replace(b'Gen="V1"', b'Gen="V2"')

    ctx = ValidationContext()
    original, PACK.rules = PACK.rules, list(PACK.rules) + [rule]
    try:
        errors(first, PACK, ctx)            # seeds the context
        shared = errors(second, PACK, ctx)
        # Same second message, a context that never saw the first one.
        isolated = errors(second, PACK, ValidationContext())
    finally:
        PACK.rules = original

    assert any("TEST_GEN_CONSISTENT" in f for f in shared), \
        "the second message's Gen contradicts the first; a shared context sees it"
    assert not any("TEST_GEN_CONSISTENT" in f for f in isolated), \
        "with nothing to compare against there is nothing to report"
