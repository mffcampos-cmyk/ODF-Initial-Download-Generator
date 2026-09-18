# tests/unit/test_functions.py
from generator.refdata import RefData
from generator.packload import resolve_pack_dir
from tests.conftest import PACK

PACK_DIR = resolve_pack_dir()


def _cats(funcs):
    from collections import Counter
    return dict(Counter(f.category for f in funcs))


def test_hbb_has_expected_categories():
    rd = RefData(PACK, pack_dir=PACK_DIR)
    cats = _cats(rd.discipline_functions("HBB"))
    # HBB publishes coach, team, technical and judge officials plus athletes.
    assert cats.get("A", 0) >= 1
    assert cats.get("C", 0) >= 1
    assert cats.get("J", 0) >= 1
    assert cats.get("T", 0) >= 1


def test_swm_has_no_coach_or_judge():
    rd = RefData(PACK, pack_dir=PACK_DIR)
    cats = _cats(rd.discipline_functions("SWM"))
    assert cats.get("C", 0) == 0
    assert cats.get("J", 0) == 0
    assert cats.get("A", 0) >= 1


def test_athlete_function_code_present_for_arc():
    rd = RefData(PACK, pack_dir=PACK_DIR)
    codes = {f.code for f in rd.discipline_functions("ARC") if f.category == "A"}
    assert "AA01" in codes


def test_missing_pack_dir_returns_empty():
    rd = RefData(PACK)  # no pack_dir
    assert rd.discipline_functions("ARC") == []
