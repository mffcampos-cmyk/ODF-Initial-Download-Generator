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
