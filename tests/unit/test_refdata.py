from generator.refdata import RefData
from tests.conftest import PACK


def test_disciplines_nonempty_and_sorted():
    rd = RefData(PACK)
    ds = rd.disciplines()
    assert ds == sorted(ds) and len(ds) > 0


def test_codes_returns_sorted_ids():
    rd = RefData(PACK)
    disc = rd.codes("DISCIPLINE")
    assert disc == sorted(disc) and len(disc) > 0


def test_missing_codeset_is_empty_not_error():
    rd = RefData(PACK)
    assert rd.codes("NO_SUCH_CODESET") == []
    assert rd.has_codeset("NO_SUCH_CODESET") is False
