import datetime
import random
import re
from generator.envelope import build_odfbody, competition_code
from generator.overrides import Overrides
from generator.refdata import RefData
from tests.conftest import PACK

REQUIRED = ["CompetitionCode", "DocumentCode", "DocumentType", "Version",
            "FeedFlag", "Date", "Time", "LogicalDate", "Source"]


def test_header_overrides_applied():
    rd = RefData(PACK)
    ov = Overrides(competition_code="SYOG2026", source="OGEN",
                   gen="OWG-2026-GEN-V4.5", sport="SYOG-2026-SWM-1.0",
                   codes="SYOG-2026-CC-V0.04")
    root, comp = build_odfbody(random.Random(1), rd, "SWM", "DT_PARTIC",
                               competition_code(rd), overrides=ov)
    assert root.get("CompetitionCode") == "SYOG2026"
    assert root.get("Source") == "OGEN"
    assert comp.get("Gen") == "OWG-2026-GEN-V4.5"
    assert comp.get("Sport") == "SYOG-2026-SWM-1.0"
    assert comp.get("Codes") == "SYOG-2026-CC-V0.04"


def test_blank_overrides_keep_defaults():
    rd = RefData(PACK)
    root, comp = build_odfbody(random.Random(1), rd, "ARC", "DT_PARTIC",
                               competition_code(rd), overrides=Overrides())
    assert root.get("Source") == "SEQ"                # message-type default
    assert comp.get("Sport") == "SYOG-2026-ARC-1.2"  # ARC DD reference


def test_date_and_time_are_real_generation_clock():
    rd = RefData(PACK)
    root, _ = build_odfbody(random.Random(1), rd, "ARC", "DT_PARTIC",
                            competition_code(rd))
    today = datetime.date.today().isoformat()
    assert root.get("Date") == today
    assert root.get("LogicalDate") == today
    assert re.fullmatch(r"\d{9}", root.get("Time"))


def test_document_code_param_still_honoured():
    rd = RefData(PACK)
    root, _ = build_odfbody(random.Random(1), rd, "ARC", "DT_ENTRIES",
                            competition_code(rd), document_code="ARCMEVENT" + "-" * 25)
    assert root.get("DocumentCode") == "ARCMEVENT" + "-" * 25


def test_competition_code_is_valid_member():
    rd = RefData(PACK)
    assert competition_code(rd) in set(rd.codes("COMPETITION_CODE"))


def test_envelope_has_all_required_attrs_nonempty():
    rd = RefData(PACK)
    root, comp = build_odfbody(random.Random(1), rd, "ARC", "DT_PARTIC",
                               competition_code(rd))
    for a in REQUIRED:
        assert root.get(a) and root.get(a).strip()
    assert len(root.get("DocumentCode")) == 34
    assert int(root.get("Version")) >= 1
    assert root.get("FeedFlag") == "P"


def test_competition_child_has_gen_codes_and_no_discipline_element():
    rd = RefData(PACK)
    root, comp = build_odfbody(random.Random(1), rd, "ARC", "DT_PARTIC",
                               competition_code(rd))
    assert comp.get("Gen") and comp.get("Codes")
    assert comp.find("Discipline") is None  # XSD: Discipline can't coexist with content


def test_document_code_prefix_is_resolved_discipline():
    rd = RefData(PACK)
    root, _ = build_odfbody(random.Random(1), rd, "ATH", "DT_PARTIC",
                            competition_code(rd))
    assert root.get("DocumentCode")[:3] == "ATH"


def test_invalid_discipline_falls_back_to_pack_member():
    rd = RefData(PACK)
    root, _ = build_odfbody(random.Random(1), rd, "ZZZ", "DT_PARTIC",
                            competition_code(rd))
    assert root.get("DocumentCode")[:3] in set(rd.pack.disciplines)


def test_envelope_takes_versions_from_the_games_profile():
    rd = RefData(PACK)
    root, comp = build_odfbody(random.Random(1), rd, "SWM", "DT_PARTIC",
                               competition_code(rd))
    assert comp.get("Gen") == rd.games.gen
    assert comp.get("Codes") == rd.codes_reference == "YOG-2026-2.4"
    assert comp.get("Sport") == rd.games.sport("SWM")
    assert root.get("Source") == rd.games.source("DT_PARTIC")


def test_envelope_refuses_an_incomplete_profile():
    from generator.games import GamesProfile
    rd = RefData(PACK, profile=GamesProfile(pack_name="SOLG28", label="LA 2028"))
    try:
        build_odfbody(random.Random(1), rd, "ARC", "DT_PARTIC",
                      competition_code(rd))
        raise AssertionError("expected ValueError for an incomplete profile")
    except ValueError as e:
        assert "SOLG28" in str(e)
        assert "gen" in str(e)


def test_no_syog_literal_remains_in_envelope():
    import pathlib
    src = pathlib.Path("generator/envelope.py").read_text(encoding="utf-8")
    assert "SYOG-2026" not in src
    assert "OWG-2026" not in src
    assert "AWAARC1" not in src
