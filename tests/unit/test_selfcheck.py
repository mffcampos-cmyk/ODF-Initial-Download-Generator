from generator import selfcheck
from generator.selfcheck import errors
from tests.conftest import PACK

CLEAN = (b'<?xml version="1.0" encoding="UTF-8"?>'
         b'<OdfBody CompetitionCode="X" DocumentCode="D" DocumentType="DT_PARTIC" '
         b'Version="1" FeedFlag="P" Date="2026-01-01" Time="000000000" '
         b'LogicalDate="2026-01-01" Source="S"><Competition Gen="G" Codes="C">'
         b'<Discipline Code="ARC"/></Competition></OdfBody>')


def test_errors_returns_list_of_strings():
    result = errors(CLEAN, PACK)
    assert isinstance(result, list)
    assert all(isinstance(s, str) for s in result)


def test_generate_clean_returns_first_clean(monkeypatch):
    """It stops at the first seed that validates clean.

    `errors` is stubbed rather than run for real. This test used to carry a
    hand-written "clean" DT_PARTIC and assert the real engine accepted it --
    which held until the engine learned to check child cardinalities, at which
    point the fixture was rejected for having no <Participant> and the test
    failed for a reason that had nothing to do with what it was testing. The
    control flow here is independent of any rule set, so it should not be
    re-broken by every rule the validator gains.

    `test_errors_returns_list_of_strings` still exercises the real pack.
    """
    calls = []

    def make(seed):
        calls.append(seed)
        return f"<seed-{seed}/>".encode()

    def fake_errors(xml, pack):
        return [] if xml == b"<seed-2/>" else ["not clean"]

    monkeypatch.setattr(selfcheck, "errors", fake_errors)

    xml, findings = selfcheck.generate_clean(make, PACK, seeds=[1, 2, 3])

    assert calls == [1, 2], "it must stop at the first clean seed"
    assert xml == b"<seed-2/>"
    assert findings == []


def test_generate_clean_reports_the_last_failure_when_nothing_is_clean(monkeypatch):
    calls = []

    def make(seed):
        calls.append(seed)
        return f"<seed-{seed}/>".encode()

    monkeypatch.setattr(selfcheck, "errors", lambda xml, pack: [f"bad {xml!r}"])

    xml, findings = selfcheck.generate_clean(make, PACK, seeds=[1, 2, 3])

    assert calls == [1, 2, 3], "every seed must be tried before giving up"
    assert xml == b"<seed-3/>"
    assert findings == ["bad b'<seed-3/>'"]
