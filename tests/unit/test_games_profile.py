"""The Games profile is the only place Games-specific message conventions live.

SYOG26's profile must reproduce exactly the constants envelope.py shipped
with, or the refactor in Task 2 silently changes SYOG2026 output.
"""
import tempfile
from pathlib import Path

from generator.games import GamesProfile, GamesProfileError, load_profile


def test_syog26_profile_reproduces_the_shipped_constants():
    p = load_profile("SYOG26")
    assert p.gen == "OWG-2026-GEN-V4.5"
    assert p.codes == "SYOG-2026-CC-V0.04"
    assert p.sport_template == "SYOG-2026-{disc}-1.0"
    assert p.sources == {"ARC": "AWAARC1", "SWM": "CTO1"}
    assert p.default_source == "OGEN"


def test_sport_renders_per_discipline():
    p = load_profile("SYOG26")
    assert p.sport("SWM") == "SYOG-2026-SWM-1.0"
    assert p.sport("ARC") == "SYOG-2026-ARC-1.0"


def test_source_falls_back_to_default():
    p = load_profile("SYOG26")
    assert p.source("ARC") == "AWAARC1"
    assert p.source("ATH") == "OGEN"


def test_syog26_profile_is_complete():
    p = load_profile("SYOG26")
    assert p.complete
    assert p.missing_fields() == []


def test_solg28_profile_has_no_invented_versions():
    p = load_profile("SOLG28")
    assert p.label
    assert p.default_source == "OGEN"
    assert p.gen is None and p.codes is None and p.sport_template is None
    assert not p.complete
    assert p.missing_fields() == ["gen", "codes", "sport_template"]
    assert p.sport("ARC") is None


def test_missing_profile_raises_with_the_expected_path():
    d = Path(tempfile.mkdtemp())
    try:
        load_profile("NOPE", profile_dir=d)
        raise AssertionError("expected GamesProfileError")
    except GamesProfileError as e:
        assert "NOPE" in str(e)
        assert str(d / "NOPE.yaml") in str(e)


def test_non_mapping_profile_raises():
    d = Path(tempfile.mkdtemp())
    (d / "BAD.yaml").write_text("- just\n- a\n- list\n", encoding="utf-8")
    try:
        load_profile("BAD", profile_dir=d)
        raise AssertionError("expected GamesProfileError")
    except GamesProfileError as e:
        assert "mapping" in str(e)


def test_profile_is_frozen():
    p = load_profile("SYOG26")
    try:
        p.gen = "x"
        raise AssertionError("expected the dataclass to be frozen")
    except AttributeError:
        pass


def test_label_defaults_to_pack_name_when_absent():
    d = Path(tempfile.mkdtemp())
    (d / "X9.yaml").write_text("default_source: OGEN\n", encoding="utf-8")
    assert load_profile("X9", profile_dir=d).label == "X9"


def test_profile_dataclass_defaults():
    p = GamesProfile(pack_name="T", label="T")
    assert p.sources == {} and p.default_source == "OGEN"
    assert not p.complete


# --- Finding A: a malformed sport_template must be caught at load time, not
# at generate time. The placeholder is literally "{disc}"; a wrong name
# (e.g. "{discipline}") must fail loudly, and a template with no placeholder
# at all must not be treated as "complete" (it would silently emit the same
# Sport value for every discipline).

def test_sport_template_with_wrong_placeholder_name_raises():
    d = Path(tempfile.mkdtemp())
    (d / "BADTPL.yaml").write_text(
        "label: Bad\ngen: G\ncodes: C\nsport_template: LA28-{discipline}-1.0\n",
        encoding="utf-8")
    try:
        load_profile("BADTPL", profile_dir=d)
        raise AssertionError("expected GamesProfileError")
    except GamesProfileError as e:
        msg = str(e)
        assert "BADTPL.yaml" in msg
        assert "{disc}" in msg


def test_sport_template_without_any_placeholder_is_incomplete_not_complete():
    d = Path(tempfile.mkdtemp())
    (d / "NOPLACE.yaml").write_text(
        "label: Bad\ngen: G\ncodes: C\nsport_template: LA28-1.0\n",
        encoding="utf-8")
    p = load_profile("NOPLACE", profile_dir=d)
    # Loads fine (LA28-1.0.format(disc="ARC") does not raise -- the string
    # simply has no substitution to make) but must not count as complete:
    # every discipline would otherwise silently get the same Sport value.
    assert p.sport_template == "LA28-1.0"
    assert not p.complete
    assert p.missing_fields() == ["sport_template"]


def test_sport_template_with_disc_placeholder_is_complete():
    d = Path(tempfile.mkdtemp())
    (d / "GOODTPL.yaml").write_text(
        "label: Good\ngen: G\ncodes: C\nsport_template: LA28-{disc}-1.0\n",
        encoding="utf-8")
    p = load_profile("GOODTPL", profile_dir=d)
    assert p.complete
    assert p.sport("ARC") == "LA28-ARC-1.0"


def test_solg28_null_sport_template_still_means_not_yet_known():
    """A null sport_template (SOLG28's actual current state) must keep
    meaning "not yet known", not be confused with the malformed cases
    above."""
    p = load_profile("SOLG28")
    assert p.sport_template is None
    assert not p.complete
    assert p.missing_fields() == ["gen", "codes", "sport_template"]


# --- Finding B: a non-mapping `sources:` must raise GamesProfileError, not
# a raw ValueError/TypeError from dict(), so it doesn't crash app startup.

def test_non_mapping_sources_list_raises_games_profile_error():
    d = Path(tempfile.mkdtemp())
    (d / "BADSRC.yaml").write_text(
        "label: Bad\nsources:\n  - ARC\n  - SWM\n", encoding="utf-8")
    try:
        load_profile("BADSRC", profile_dir=d)
        raise AssertionError("expected GamesProfileError")
    except GamesProfileError as e:
        assert "sources" in str(e)


def test_non_mapping_sources_string_raises_games_profile_error():
    d = Path(tempfile.mkdtemp())
    (d / "BADSRC2.yaml").write_text(
        "label: Bad\nsources: just-a-string\n", encoding="utf-8")
    try:
        load_profile("BADSRC2", profile_dir=d)
        raise AssertionError("expected GamesProfileError")
    except GamesProfileError as e:
        assert "sources" in str(e)
