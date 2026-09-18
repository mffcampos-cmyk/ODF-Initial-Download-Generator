import re
import random
from generator.fields import (
    rsc, gender_participant, gender_team, odf_date, odf_datetime,
    feed_flag, name_token, pos_int, pick, pick_code,
)
from generator.refdata import RefData
from tests.conftest import PACK

RSC_RE = re.compile(r"[A-Z0-9]{3}[A-Z0-9-]{31}")
DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
DT_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}")


def rng():
    return random.Random(42)


def test_rsc_is_34_chars_and_matches_pattern():
    v = rsc(rng(), "ARC")
    assert len(v) == 34 and RSC_RE.fullmatch(v)


def test_rsc_prefix_over_three_chars_is_truncated():
    v = rsc(rng(), "ARCHERY")
    assert len(v) == 34 and v[:3] == "ARC"


def test_genders_in_domain():
    assert gender_participant(rng()) in {"M", "F", "X"}
    assert gender_team(rng()) in {"M", "W", "X", "G", "O"}


def test_dates_match_patterns():
    assert DATE_RE.fullmatch(odf_date(rng()))
    assert DT_RE.fullmatch(odf_datetime(rng()))


def test_feed_flag_and_names_and_ints():
    assert feed_flag(rng()) in {"P", "T"}
    assert name_token(rng()).isalpha() and len(name_token(rng())) == 8
    n = pos_int(rng(), 1, 10)
    assert 1 <= n <= 10


def test_pick_code_returns_valid_member():
    r = rng()
    rd = RefData(PACK)
    code = pick_code(r, rd, "DISCIPLINE")
    assert code in set(rd.codes("DISCIPLINE"))
    assert pick_code(r, rd, "NO_SUCH") is None
