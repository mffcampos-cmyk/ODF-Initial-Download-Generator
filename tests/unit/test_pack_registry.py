"""Pack discovery must tolerate an empty pack (SOLG28 today) while still
refusing to generate against one."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from generator.packs import (PackNotReady, PackRegistry, PackStatus,
                             UnknownPack, rules_dir_from_env)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class _env:
    """Temporarily set (value) or clear (None) environment variables."""

    def __init__(self, **values):
        self._values = values
        self._old: dict[str, str | None] = {}

    def __enter__(self):
        for key, value in self._values.items():
            self._old[key] = os.environ.get(key)
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        return self

    def __exit__(self, *exc):
        for key, value in self._old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

# The same resolution every other consumer uses (tests/conftest.py, api.app,
# generator.export): ODF_RULES_DIR, else the parent of resolve_pack_dir(),
# which falls back to the pack this repository ships and then to the
# CWD-relative one. Reading
# os.environ["ODF_PACK_DIR"] directly here used to abort collection of the
# entire suite -- see test_module_imports_without_odf_pack_dir_being_set.
RULES_DIR = rules_dir_from_env()


def test_module_imports_without_odf_pack_dir_being_set():
    """Regression: ``RULES_DIR`` was computed as
    ``Path(os.environ["ODF_PACK_DIR"]).parent`` at *import* time, so a shell
    that had not set that variable raised ``KeyError`` during pytest
    **collection** and aborted the whole suite -- 181 tests taken down by one
    module, none of which had anything to do with pack discovery.

    Nothing else in the project resolves the pack directory that way:
    ``resolve_pack_dir()`` documents a fallback chain (explicit ->
    ``ODF_PACK_DIR`` -> the repository's own ``Rules/<ODF_GAMES or SYOG26>``
    -> the same path relative to the current directory) and
    ``tests/conftest.py`` goes through it, which is why collection got as far
    as this module at all. This module must use the same resolution as
    everyone else.
    """
    env = {k: v for k, v in os.environ.items() if k != "ODF_PACK_DIR"}
    proc = subprocess.run(
        [sys.executable, "-c", "import tests.unit.test_pack_registry"],
        cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True)
    assert "KeyError" not in proc.stderr, (
        "importing this module still hard-requires ODF_PACK_DIR:\n"
        + proc.stderr)


def _registry():
    return PackRegistry.discover(RULES_DIR)


_MINIMAL_XSD = """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="OdfBody">
    <xs:complexType>
      <xs:anyAttribute processContents="skip"/>
    </xs:complexType>
  </xs:element>
</xs:schema>
"""

_MINIMAL_CODES = """<?xml version="1.0" encoding="UTF-8"?>
<Codesets>
  <Codeset name="DISCIPLINE"><Code id="ZZZ" description="Test discipline"/></Codeset>
  <Codeset name="COMPETITION_CODE"><Code id="TEST0000" description="Test competition"/></Codeset>
</Codesets>
"""

_MINIMAL_PROFILE = """label: Test Games
gen: TEST-GEN-V1.0
codes: TEST-CC-V1.0
sport_template: TEST-{disc}-1.0
default_source: OGEN
"""


def _minimal_pack(pack_dir: Path) -> None:
    """A cheap, fast-to-ingest but structurally real pack -- no draft
    extraction, no real Data Dictionary parsing -- for tests that only need
    a pack discovery/readiness can actually load, not a real Games ruleset."""
    (pack_dir / "xsd").mkdir(parents=True)
    (pack_dir / "xsd" / "odf2.xsd").write_text(_MINIMAL_XSD, encoding="utf-8")
    (pack_dir / "codes").mkdir()
    (pack_dir / "codes" / "codes.xml").write_text(_MINIMAL_CODES, encoding="utf-8")
    (pack_dir / "Disciplines" / "ZZZ").mkdir(parents=True)
    (pack_dir / "Disciplines" / "ZZZ" / "dd.md").write_text("# dd\n", encoding="utf-8")


def test_discovery_finds_both_packs():
    reg = _registry()
    assert "SYOG26" in reg.names()
    assert "SOLG28" in reg.names()


def test_syog26_is_ready_with_disciplines():
    st = _registry().status("SYOG26")
    assert st.ready
    assert st.reasons == ()
    assert "ARC" in st.disciplines


def test_solg28_is_not_ready_and_says_why():
    reg = _registry()
    st = reg.status("SOLG28")
    assert not st.ready
    assert st.disciplines == ()
    joined = " ".join(st.reasons)
    assert "No XSD compiles" in joined
    assert "No Common Codes loaded" in joined
    assert "No disciplines" in joined
    # peek() only relaxes the *profile* requirement (see
    # test_peek_lists_disciplines_for_a_pack_with_full_content_but_no_profile);
    # a pack with no content at all must still refuse it the same as get(),
    # since there is nothing for a listing endpoint to return either way.
    try:
        reg.peek("SOLG28")
        raise AssertionError("expected PackNotReady from peek() too")
    except PackNotReady as e:
        assert "SOLG28" in str(e)
    assert "Games profile incomplete" in joined
    # Every reason names the folder the operator has to put something into.
    assert "Rules/SOLG28" in joined
    assert "generator/games/SOLG28.yaml" in joined


def test_get_returns_refdata_for_a_ready_pack():
    rd = _registry().get("SYOG26")
    assert rd.disciplines()
    assert rd.games.complete


def test_get_refuses_a_not_ready_pack_with_the_reasons():
    try:
        _registry().get("SOLG28")
        raise AssertionError("expected PackNotReady")
    except PackNotReady as e:
        assert "SOLG28" in str(e)
        assert "No XSD compiles" in str(e)


def test_get_rejects_an_unknown_pack():
    try:
        _registry().get("NOPE")
        raise AssertionError("expected UnknownPack")
    except UnknownPack as e:
        assert "NOPE" in str(e)
        assert "SYOG26" in str(e)


def test_decoy_directory_is_discovered_not_ready_rather_than_raising():
    d = Path(tempfile.mkdtemp())
    decoy = d / "DECOY"
    decoy.mkdir()
    (decoy / "pack.yaml").write_text("version: ''\n", encoding="utf-8")
    (decoy / ".ingestion_state.json").write_text("{}", encoding="utf-8")
    reg = PackRegistry.discover(d)
    assert reg.names() == ["DECOY"]
    st = reg.status("DECOY")
    assert not st.ready
    # No profile file exists for DECOY; that is a reason, not a crash.
    assert any("Games profile" in r for r in st.reasons)


def test_discovery_finds_structural_pack_with_no_pack_yaml():
    """The SYOG26 shape: no pack.yaml, but top-level codes/rules/xsd content."""
    d = Path(tempfile.mkdtemp())
    pack = d / "STRUCTPACK"
    (pack / "codes").mkdir(parents=True)
    (pack / "rules").mkdir()
    (pack / "xsd").mkdir()
    reg = PackRegistry.discover(d)
    assert reg.names() == ["STRUCTPACK"]


def test_discovery_finds_pack_yaml_only_directory():
    """The SOLG28 shape: only a pack.yaml, no structural content at all."""
    d = Path(tempfile.mkdtemp())
    pack = d / "YAMLONLYPACK"
    pack.mkdir(parents=True)
    (pack / "pack.yaml").write_text("version: ''\n", encoding="utf-8")
    reg = PackRegistry.discover(d)
    assert reg.names() == ["YAMLONLYPACK"]


def test_discovery_ignores_nested_xsd_not_at_top_level():
    """A stray .xsd several levels deep (a docs/ folder, an old backup) must
    not make discovery register the directory as a phantom pack. This is the
    over-admission bug: looks_like_pack() globs **/*.xsd at unbounded depth
    to answer a different question, and reusing it for discovery would let
    any such nested file register a phantom entry."""
    d = Path(tempfile.mkdtemp())
    decoy = d / "NESTEDXSD"
    nested = decoy / "docs" / "old" / "backup"
    nested.mkdir(parents=True)
    (nested / "sample.xsd").write_text("<xsd/>", encoding="utf-8")
    # A real pack sibling so the directory isn't a zero-packs hard failure.
    real = d / "REALPACK"
    (real / "codes").mkdir(parents=True)
    reg = PackRegistry.discover(d)
    assert "NESTEDXSD" not in reg.names()
    assert "REALPACK" in reg.names()


def test_zero_packs_is_a_hard_failure():
    empty = Path(tempfile.mkdtemp())
    try:
        PackRegistry.discover(empty)
        raise AssertionError("expected PackDirError")
    except Exception as e:
        assert "no rule packs" in str(e).lower()


def test_default_name_prefers_odf_games():
    old = os.environ.get("ODF_GAMES")
    os.environ["ODF_GAMES"] = "SOLG28"
    try:
        assert _registry().default_name() == "SOLG28"
    finally:
        if old is None:
            os.environ.pop("ODF_GAMES", None)
        else:
            os.environ["ODF_GAMES"] = old


def test_default_name_rejects_an_unknown_odf_games():
    old = os.environ.get("ODF_GAMES")
    os.environ["ODF_GAMES"] = "NOPE"
    try:
        _registry().default_name()
        raise AssertionError("expected UnknownPack")
    except UnknownPack:
        pass
    finally:
        if old is None:
            os.environ.pop("ODF_GAMES", None)
        else:
            os.environ["ODF_GAMES"] = old


def test_default_name_falls_back_to_the_pack_dir_pack():
    old = os.environ.get("ODF_GAMES")
    os.environ.pop("ODF_GAMES", None)
    try:
        assert _registry().default_name() == "SYOG26"
    finally:
        if old is not None:
            os.environ["ODF_GAMES"] = old


def test_default_name_registers_an_explicit_pack_discovery_could_not_see():
    """Regression 3: a pack laid out one directory deeper than discovery's
    deliberately top-level-only scan (_has_pack_structure_at_top_level) is
    invisible to PackRegistry.discover(), but resolve_pack_dir() validates it
    depth-agnostically (looks_like_pack() globs **/*.xsd) and ODF_PACK_DIR
    points straight at it. Before this fix, default_name() silently fell
    through to "any other ready pack" in exactly this case -- generating
    messages from a pack the operator never selected, with no warning. It
    must instead register the explicitly-selected directory as a pack of its
    own and hand *that* one back, never a substitute.

    This is the pack-identity assertion (``Path(rd.pack_dir) == deep``) that
    would have caught Regression 3: it checks not just the *name* the
    registry resolves to, but that the RefData handed back actually comes
    from the directory the operator selected."""
    import shutil

    root = Path(tempfile.mkdtemp())
    rules = root / "Rules"
    profiles = root / "profiles"
    profiles.mkdir()

    # A sibling that IS discovered and ready -- the pack the old bug would
    # silently substitute for the operator's actual selection.
    sibling = rules / "READYSIBLING"
    _minimal_pack(sibling)
    (profiles / "READYSIBLING.yaml").write_text(_MINIMAL_PROFILE, encoding="utf-8")

    # The operator's actual selection: a valid pack, one directory deeper
    # than discovery's top-level-only scan looks.
    deep = rules / "DEEP1"
    _minimal_pack(deep / "nested" / "deeper")
    (profiles / "DEEP1.yaml").write_text(_MINIMAL_PROFILE, encoding="utf-8")

    old_pack_dir = os.environ.get("ODF_PACK_DIR")
    old_games = os.environ.get("ODF_GAMES")
    os.environ["ODF_PACK_DIR"] = str(deep)
    os.environ.pop("ODF_GAMES", None)
    try:
        reg = PackRegistry.discover(rules, profiles)
        # Confirms the premise: discovery alone still misses DEEP1.
        assert reg.names() == ["READYSIBLING"]

        name = reg.default_name()
        assert name == "DEEP1", (
            f"expected the operator's explicit selection DEEP1, got {name} "
            f"-- a silent substitution of a different pack")
        rd = reg.get(name)
        assert Path(rd.pack_dir) == deep
        assert "DEEP1" in reg.names()
    finally:
        shutil.rmtree(root, ignore_errors=True)
        if old_pack_dir is None:
            os.environ.pop("ODF_PACK_DIR", None)
        else:
            os.environ["ODF_PACK_DIR"] = old_pack_dir
        if old_games is not None:
            os.environ["ODF_GAMES"] = old_games


def test_peek_lists_disciplines_for_a_pack_with_full_content_but_no_profile():
    """Regression 2 (the API side of Regression 1's lesson): reading a
    pack's content -- its discipline list -- never needed a complete Games
    profile. GET /api/disciplines uses PackRegistry.peek() (via
    api.app.resolve(..., require_ready=False)) instead of get() so a pack
    with a full ruleset but no matching generator/games/<name>.yaml still
    lists its disciplines; get() must still refuse it, since generating
    still needs the profile."""
    import shutil

    root = Path(tempfile.mkdtemp())
    rules = root / "Rules"
    pack = rules / "FULLNOPROFILE"
    _minimal_pack(pack)
    # Deliberately no profiles dir / no FULLNOPROFILE.yaml.
    try:
        reg = PackRegistry.discover(rules, root / "profiles")
        st = reg.status("FULLNOPROFILE")
        assert not st.ready
        assert any("Games profile missing" in r for r in st.reasons)

        try:
            reg.get("FULLNOPROFILE")
            raise AssertionError("expected PackNotReady from get()")
        except PackNotReady:
            pass

        rd = reg.peek("FULLNOPROFILE")
        assert rd.disciplines() == ["ZZZ"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_rules_dir_from_env_uses_the_pack_dir_parent():
    """ODF_PACK_DIR names a single pack; the rules dir is the folder holding
    it. Asserted against a fabricated pack rather than against RULES_DIR,
    which is now itself ``rules_dir_from_env()`` -- comparing the two would be
    a tautology that passes no matter what the function does."""
    root = Path(tempfile.mkdtemp())
    pack = root / "Rules" / "SOMEPACK"
    _minimal_pack(pack)
    with _env(ODF_PACK_DIR=str(pack), ODF_RULES_DIR=None):
        assert rules_dir_from_env() == pack.parent


def test_rules_dir_from_env_prefers_an_explicit_rules_dir():
    """ODF_RULES_DIR wins outright: it names the multi-pack folder directly,
    so it must not be second-guessed by ODF_PACK_DIR's parent."""
    root = Path(tempfile.mkdtemp())
    pack = root / "Rules" / "SOMEPACK"
    _minimal_pack(pack)
    other = root / "OtherRules"
    other.mkdir()
    with _env(ODF_PACK_DIR=str(pack), ODF_RULES_DIR=str(other)):
        assert rules_dir_from_env() == other


def test_status_is_frozen():
    st = PackStatus(name="X", label="X", ready=False, reasons=[], disciplines=[])
    try:
        st.ready = True
        raise AssertionError("expected the dataclass to be frozen")
    except AttributeError:
        pass


def test_status_reasons_and_disciplines_reject_in_place_mutation():
    """frozen=True only stops `st.ready = True`; it does nothing to stop
    `st.reasons.append(...)` if reasons is a plain list. Both fields must be
    immutable sequences, not just the dataclass wrapper around them."""
    st = PackStatus(name="X", label="X", ready=False,
                     reasons=["a"], disciplines=["ARC"])
    try:
        st.reasons.append("INJECTED")
        raise AssertionError("expected reasons to reject in-place mutation")
    except AttributeError:
        pass
    try:
        st.disciplines.append("SWM")
        raise AssertionError("expected disciplines to reject in-place mutation")
    except AttributeError:
        pass
    assert st.reasons == ("a",)
    assert st.disciplines == ("ARC",)


def test_mutating_a_returned_status_does_not_corrupt_the_registry():
    """The regression this guards: a caller who gets a PackStatus from the
    registry and mutates what it holds must not permanently corrupt what the
    registry hands back on the next call, for the rest of the process
    lifetime."""
    reg = _registry()
    st = reg.status("SYOG26")
    before = reg.status("SYOG26").reasons
    try:
        st.reasons.append("INJECTED")
    except AttributeError:
        pass
    assert reg.status("SYOG26").reasons == before
    assert "INJECTED" not in reg.status("SYOG26").reasons
    # statuses() and status() must hand out the same isolation guarantee.
    for other in reg.statuses():
        assert "INJECTED" not in other.reasons
