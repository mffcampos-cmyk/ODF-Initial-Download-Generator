"""DD S(n) maximum lengths are enforced on generated output.

Nothing else enforces them: the validator has no length primitive and the
bundled XSDs carry no maxLength facet, so over-length attributes validate
clean. 19 Team/@TVTeamName values in the corpus exceeded S(21) before this.
"""
from __future__ import annotations

from lxml import etree

from generator import lengths
from generator.bundle import build_bundle
from generator.refdata import RefData
from generator.serialize import el, to_xml
from tests.conftest import PACK, REFUSED_DISCIPLINES


def rd():
    return RefData(PACK)


def test_clamp_truncates_only_the_listed_pair():
    long_name = "Federal Republic of Germany"          # 27 chars
    assert lengths.clamp("Team", "TVTeamName", long_name) == long_name[:21]
    # Same attribute name, different element: not in the table, not touched.
    assert lengths.clamp("Other", "TVTeamName", long_name) == long_name
    # Unlisted attribute on a listed element: untouched.
    assert lengths.clamp("Team", "Name", long_name) == long_name


def test_clamp_leaves_values_within_the_limit_alone():
    for value in ("", "Chile", "x" * 21):
        assert lengths.clamp("Team", "TVTeamName", value) == value


def test_serializer_applies_the_limit():
    node = el("Team", {"TVTeamName": "Federal Republic of Germany"})
    assert node.get("TVTeamName") == "Federal Republic of Ger"[:21]
    assert len(node.get("TVTeamName")) == 21


def test_description_matched_attributes_are_never_truncated():
    """VenueName/LocationName carry no S(n) and must equal the code's
    ENG_Description exactly -- JUD_VENUENAME_CODE and its equivalents check
    that. Truncating them would turn passing output into failing output."""
    for attr in ("VenueName", "LocationName"):
        for element in ("Session", "Unit", "VenueDescription"):
            assert (element, attr) not in lengths.MAX_LENGTHS, (
                f"{element}@{attr} is description-matched: a length limit "
                f"here would break the code_membership rules that check it")
    long_venue = "Iba Mar Diop Stadium, Dakar, Senegal (Main Arena)"
    assert lengths.clamp("Session", "VenueName", long_venue) == long_venue


def test_item_name_is_never_truncated():
    """Unit/ItemName@Value's DD cell states both S(40) and the Common Codes
    ENG description. The description governs: truncating merged 124 unit codes
    into 16 name collisions, and Rules/SYOG26/pack.yaml records the field as
    length-exempt. A limit here would be the repository contradicting its own
    pack."""
    assert ("ItemName", "Value") not in lengths.MAX_LENGTHS, (
        "ItemName carries the Common Codes description; a length limit here "
        "would merge units that Common Codes keeps distinct")
    whole = "Women's Changquan Combined Preliminary Round - Changquan"  # 56
    assert lengths.clamp("ItemName", "Value", whole) == whole


def test_generated_item_names_are_the_whole_description():
    """Every generated Unit/ItemName@Value equals its unit code's EVENT_UNIT
    ENG description character for character -- including the ones past S(40),
    which is the point. Asserted over every generated message rather than a
    sample, because a limit reintroduced anywhere in the serializer would show
    up as a prefix here and nowhere else."""
    refdata = rd()
    table = PACK.codes.table("EVENT_UNIT")
    described = {row.id: (row.fields.get("ENG_Description") or "")
                 for row in table._rows.values()}
    cut, unknown, checked, over_limit = [], [], 0, 0
    for disc in refdata.disciplines():
        if disc in REFUSED_DISCIPLINES:
            continue
        for _key, (xml, _errs) in build_bundle(refdata, disc, seed=1).items():
            for unit in etree.fromstring(xml).iter("Unit"):
                code = unit.get("Code")
                for item in unit.iter("ItemName"):
                    value = item.get("Value") or ""
                    if code not in described:
                        unknown.append(f"{disc} {code}")
                        continue
                    checked += 1
                    if len(value) > 40:
                        over_limit += 1
                    if described[code] != value:
                        cut.append(f"{disc} {code}: {described[code]!r} "
                                   f"-> {value!r}")
    assert not unknown, "units whose code is not in EVENT_UNIT: " + ", ".join(
        unknown[:10])
    assert not cut, "ItemName no longer matches the description:\n" + "\n".join(
        cut[:20])
    assert checked, "no ItemName values were checked -- the loop found nothing"
    assert over_limit, (
        "no generated ItemName exceeds S(40) any more. Either Common Codes "
        "shortened its descriptions or something is truncating again; this "
        "test exists because the long ones must survive.")


def test_no_generated_attribute_exceeds_its_limit():
    refdata = rd()
    over = []
    for disc in refdata.disciplines():
        if disc in REFUSED_DISCIPLINES:
            continue
        for _key, (xml, _errs) in build_bundle(refdata, disc, seed=1).items():
            for node in etree.fromstring(xml).iter():
                for attr, value in node.attrib.items():
                    limit = lengths.MAX_LENGTHS.get((node.tag, attr))
                    if limit is not None and len(value) > limit:
                        over.append(
                            f"{disc} <{node.tag}>@{attr}: {len(value)} > "
                            f"{limit} ({value!r})")
    assert not over, "over-length attributes:\n" + "\n".join(over[:20])
