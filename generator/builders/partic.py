from __future__ import annotations
import random
from ..dataset import build_dataset
from ..envelope import build_odfbody, competition_code
from ..names import name_fields
from ..serialize import el, to_xml


def _participant_el(p, discipline_rsc):
    disc = el("Discipline", {"Code": discipline_rsc})
    nf = name_fields(p.given_name, p.family_name)
    attrs = {
        "Code": p.code,
        "Parent": p.parent,
        "Status": p.status,
        "GivenName": nf["GivenName"],
        "FamilyName": nf["FamilyName"],
        "PassportGivenName": nf["PassportGivenName"],
        "PassportFamilyName": nf["PassportFamilyName"],
        "PrintName": nf["PrintName"],
        "PrintInitialName": nf["PrintInitialName"],
        "TVName": nf["TVName"],
        "TVInitialName": nf["TVInitialName"],
        "TVFamilyName": nf["TVFamilyName"],
        "Gender": p.gender,
        "Organisation": p.organisation,
        "BirthDate": p.birth_date,
        "Nationality": p.nationality,       # dropped by el() when empty
        "MainFunctionId": p.main_function,  # mandatory for current participants
    }
    # PSCB names appear on athletes only in the real-life feed (created by OVR).
    if not p.is_official:
        attrs["PSCBName"] = nf["PSCBName"]
        attrs["PSCBShortName"] = nf["PSCBShortName"]
        attrs["PSCBLongName"] = nf["PSCBLongName"]
    return el("Participant", attrs, disc)


def build(refdata, discipline: str, seed: int, overrides=None) -> bytes:
    rng = random.Random(seed)
    ds = build_dataset(refdata, discipline, seed, overrides)
    root, comp = build_odfbody(rng, refdata, discipline, "DT_PARTIC",
                               competition_code(refdata), overrides=overrides)
    # Discipline@Code carries the same full discipline RSC as @DocumentCode.
    disc_rsc = root.get("DocumentCode")
    for p in ds.participants:
        comp.append(_participant_el(p, disc_rsc))
    return to_xml(root)
