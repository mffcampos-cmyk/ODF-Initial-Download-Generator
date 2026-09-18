from __future__ import annotations
import random
from ..dataset import build_dataset
from ..envelope import build_odfbody, competition_code
from ..names import strip_accents
from ..serialize import el, to_xml


def _team_el(t, discipline_rsc):
    disc = el("Discipline", {"Code": discipline_rsc})
    name = t.name or t.short_name
    return el("Team", {
        "Code": t.code,
        "Status": t.status,
        "Organisation": t.organisation,
        "Name": name,
        "ShortName": t.short_name,
        "TVTeamName": t.tv_team_name,
        "PSCBName": strip_accents(name).upper(),
        "PSCBShortName": strip_accents(t.short_name).upper(),
        "PSCBLongName": strip_accents(name).upper(),
        "Gender": t.gender,
        "TeamType": t.team_type,
    }, disc)


def build(refdata, discipline: str, seed: int, overrides=None) -> bytes:
    rng = random.Random(seed)
    ds = build_dataset(refdata, discipline, seed, overrides)
    root, comp = build_odfbody(rng, refdata, discipline, "DT_PARTIC_TEAMS",
                               competition_code(refdata), overrides=overrides)
    disc_rsc = root.get("DocumentCode")
    # GEN 2.1.3.6: "The message is sorted by Team @Code." The dataset builds
    # teams in NOC-cycle order, which is not that -- TTE emitted GER01, YEM01,
    # AND01. Nothing caught it: the validator has no sort-order primitive, and
    # CORE_SORTORDER_UNIQUE checks @SortOrder, which this message does not use.
    for t in sorted(ds.teams, key=lambda t: t.code):
        comp.append(_team_el(t, disc_rsc))
    return to_xml(root)
