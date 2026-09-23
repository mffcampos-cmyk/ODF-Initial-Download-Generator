from generator.names import TV_SWITCH_NOCS
from generator.builders import partic
from generator.refdata import RefData
from generator.selfcheck import errors
from tests.conftest import PACK


def test_partic_validates_clean_for_arc():
    rd = RefData(PACK)
    xml = partic.build(rd, "ARC", seed=1)
    assert errors(xml, PACK) == []


def test_partic_is_document_type_partic():
    rd = RefData(PACK)
    xml = partic.build(rd, "ARC", seed=1)
    assert b'DocumentType="DT_PARTIC"' in xml
    assert b"<Participant" in xml


def test_partic_arc_matches_real_life_profile():
    # 32 M + 32 W athletes (R32 bracket size), 47 coaches, 4 judges = 115,
    # mirroring the real-life SYOG2026 archery feed.
    from lxml import etree
    rd = RefData(PACK)
    root = etree.fromstring(partic.build(rd, "ARC", seed=1))
    ps = list(root.iter("Participant"))
    assert len(ps) == 115
    athletes = [p for p in ps if p.get("MainFunctionId") == "AA01"]
    assert len(athletes) == 64
    assert sum(1 for a in athletes if a.get("Gender") == "M") == 32
    assert sum(1 for a in athletes if a.get("Gender") == "F") == 32
    disc_rsc = "ARC" + "-" * 31
    assert root.get("DocumentCode") == disc_rsc
    for p in ps:
        assert p.get("Parent") == p.get("Code")
        assert p.get("MainFunctionId")
        assert p.find("Discipline").get("Code") == disc_rsc
        year = int(p.get("BirthDate")[:4])
        if p.get("MainFunctionId") == "AA01":
            assert 2009 <= year <= 2011
        else:
            assert 1961 <= year <= 1996
        assert p.get("PSCBName") is None  # C4: no scoreboard names
        # TV conventions (Naming Guidelines 5.5 / 5.9): "Given FAMILY" and
        # "I. FAMILY", family first for the listed East Asian NOCs.
        fam_upper = p.get("TVFamilyName")
        if p.get("Organisation") in TV_SWITCH_NOCS:
            assert p.get("TVName").startswith(fam_upper)
            assert p.get("TVInitialName").startswith(fam_upper)
        else:
            assert p.get("TVName").endswith(fam_upper)
            assert p.get("TVInitialName")[1:3] == ". "
