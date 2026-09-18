from __future__ import annotations
import random
import string

_RSC_TAIL = string.ascii_uppercase + string.digits + "-"
_ALNUM = string.ascii_uppercase + string.digits


def rsc(rng: random.Random, prefix: str) -> str:
    """Full RSC at the discipline level: 3-char discipline code padded with
    dashes to 34 chars (e.g. ``ARC-------------------------------``), per
    CC@DISCIPLINE. The rng argument is kept for signature compatibility and is
    only used to repair a non-alphanumeric prefix."""
    head = (prefix.upper() + "XXX")[:3]
    head = "".join(c if c in _ALNUM else rng.choice(_ALNUM) for c in head)
    return head + "-" * 31


def unit_rsc(rng: random.Random, prefix: str) -> str:
    """A synthetic 34-char event-unit RSC (discipline prefix + random tail).
    Used for disciplines without an embedded real-life schedule profile, where
    unit codes must be unique but the event structure is not modelled."""
    head = (prefix.upper() + "XXX")[:3]
    head = "".join(c if c in _ALNUM else rng.choice(_ALNUM) for c in head)
    tail = "".join(rng.choice(_RSC_TAIL) for _ in range(31))
    return head + tail


def gender_participant(rng: random.Random) -> str:
    # Real-life feeds only use M/F for people; X exists in CC@PERSON_GENDER
    # but is not used for athletes/officials.
    return rng.choice(["M", "F"])


def gender_team(rng: random.Random) -> str:
    return rng.choice(["M", "W", "X", "G", "O"])


def odf_date(rng: random.Random) -> str:
    y = rng.randint(2024, 2026)
    m = rng.randint(1, 12)
    d = rng.randint(1, 28)
    return f"{y:04d}-{m:02d}-{d:02d}"


def athlete_birth_date(rng: random.Random) -> str:
    """YOG athlete age group (born 2009-2011 for Dakar 2026)."""
    return f"{rng.randint(2009, 2011):04d}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"


def official_birth_date(rng: random.Random) -> str:
    """Realistic adult birth date for coaches/judges/officials."""
    return f"{rng.randint(1961, 1996):04d}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"


def odf_datetime(rng: random.Random) -> str:
    return f"{odf_date(rng)}T{rng.randint(0,23):02d}:{rng.randint(0,59):02d}:{rng.randint(0,59):02d}"


def feed_flag(rng: random.Random) -> str:
    return rng.choice(["P", "T"])


def name_token(rng: random.Random, n: int = 8) -> str:
    return "".join(rng.choice(string.ascii_letters) for _ in range(n))


def pos_int(rng: random.Random, lo: int = 1, hi: int = 999) -> int:
    return rng.randint(lo, hi)


def pick(rng: random.Random, seq: list[str]) -> str:
    if not seq:
        raise ValueError("pick() from empty sequence")
    return rng.choice(seq)


def pick_code(rng: random.Random, refdata, codeset: str):
    codes = refdata.codes(codeset)
    return rng.choice(codes) if codes else None
