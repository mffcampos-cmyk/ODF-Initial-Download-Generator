from __future__ import annotations
import datetime
import random
from . import fields
from .serialize import el

FEED_FLAG = "P"


def competition_code(refdata) -> str:
    codes = refdata.codes("COMPETITION_CODE")
    if not codes:
        raise ValueError("COMPETITION_CODE table is empty; cannot build envelope")
    return codes[0]


def _discipline_code(refdata, discipline: str) -> str:
    valid = set(refdata.pack.disciplines)
    return discipline if discipline in valid else sorted(valid)[0]


def build_odfbody(rng: random.Random, refdata, discipline: str,
                  document_type: str, competition_code: str,
                  document_code: str | None = None, overrides=None):
    disc = _discipline_code(refdata, discipline)
    ov = overrides.normalize() if overrides is not None else None
    profile = refdata.games
    if not profile.complete:
        raise ValueError(
            f"Games profile for '{profile.pack_name}' is incomplete: "
            f"{', '.join(profile.missing_fields())} are unknown. Fill them in "
            f"from that Games' GEN document in "
            f"generator/games/{profile.pack_name}.yaml before generating.")

    # Date/Time/LogicalDate always reflect the real moment of generation
    # (not user-customizable), per the ODF header definition.
    now = datetime.datetime.now()
    date = now.date().isoformat()                       # YYYY-MM-DD
    time = now.strftime("%H%M%S") + f"{now.microsecond // 1000:03d}"  # HHMMSSmmm

    comp_code = ov.competition_code if ov and ov.competition_code else competition_code
    source = ov.source if ov and ov.source else profile.source(document_type)

    root = el("OdfBody", {
        "CompetitionCode": comp_code,
        # Full RSC per message spec: discipline level (CC@DISCIPLINE) by
        # default; per-event messages (DT_ENTRIES) pass their Event RSC.
        "DocumentCode": document_code or fields.rsc(rng, disc),
        "DocumentType": document_type,
        "Version": "1",
        # "P" (production): an initial download is a production feed, and the
        # real SYOG26 one is "P" on every message. This was a coin toss per
        # message, so one bundle mixed production and test messages.
        "FeedFlag": FEED_FLAG,
        "Date": date,
        "Time": time,
        "LogicalDate": date,
        "Source": source,
    })
    comp = el("Competition", {
        "Gen": ov.gen if ov and ov.gen else profile.gen,
        "Sport": ov.sport if ov and ov.sport else profile.sport(disc),
        "Codes": ov.codes if ov and ov.codes else refdata.codes_reference,
    })
    root.append(comp)
    return root, comp
