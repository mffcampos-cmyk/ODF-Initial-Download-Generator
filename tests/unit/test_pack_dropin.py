"""The drop-in proof.

A pack that is not-ready must become ready purely by adding files -- no code
change, no flag to flip. This builds a minimal synthetic pack in a temp
directory, asserts it starts not-ready, adds an XSD, a codes file, a
discipline folder and a complete profile, and asserts it flips to ready.

It also proves each readiness gate is independently load-bearing: dropping
in only *part* of the document set must fail for the specific reason that
part is missing, not just "not ready" in general. Without this, an
individual ``if`` block in ``_readiness()`` could be deleted and no test
would notice, because the only "incomplete" case ever exercised removed the
whole document set at once.
"""
import shutil
import tempfile
from pathlib import Path

from generator.packs import PackRegistry

MINIMAL_XSD = """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="OdfBody">
    <xs:complexType>
      <xs:anyAttribute processContents="skip"/>
    </xs:complexType>
  </xs:element>
</xs:schema>
"""

# The XML codes ingestion (odf_validator/codes/xml.py, load_xml_codes) keys
# each row on Code/@id, not @value -- a fixture using @value loads a
# Codeset with zero rows and still (wrongly) satisfies readiness, since the
# readiness check only counts table *names*. Use @id so this fixture
# actually exercises code ingestion.
MINIMAL_CODES = """<?xml version="1.0" encoding="UTF-8"?>
<Codesets>
  <Codeset name="DISCIPLINE">
    <Code id="ZZZ" description="Test discipline"/>
  </Codeset>
  <Codeset name="COMPETITION_CODE">
    <Code id="TEST0000" description="Test competition"/>
  </Codeset>
</Codesets>
"""

PROFILE = """label: Test Games
gen: TEST-GEN-V1.0
codes: TEST-CC-V1.0
sport_template: TEST-{disc}-1.0
default_source: OGEN
"""


def _fresh(profile_text: str | None = None):
    """A synthetic rules dir + profile dir, both under a temp root."""
    root = Path(tempfile.mkdtemp())
    rules, profiles = root / "Rules", root / "profiles"
    pack = rules / "DROPIN"
    pack.mkdir(parents=True)
    profiles.mkdir()
    (pack / "pack.yaml").write_text("version: ''\n", encoding="utf-8")
    if profile_text is not None:
        (profiles / "DROPIN.yaml").write_text(profile_text, encoding="utf-8")
    return root, rules, profiles, pack


def _add_xsd(pack: Path) -> None:
    """The schema an operator drops under Rules/<PACK>/xsd/."""
    (pack / "xsd").mkdir()
    (pack / "xsd" / "odf2.xsd").write_text(MINIMAL_XSD, encoding="utf-8")


def _add_codes(pack: Path) -> None:
    """The Common Codes workbook an operator drops under Rules/<PACK>/codes/."""
    (pack / "codes").mkdir()
    (pack / "codes" / "codes.xml").write_text(MINIMAL_CODES, encoding="utf-8")


def _add_disciplines(pack: Path) -> None:
    """A discipline folder + Data Dictionary an operator drops under
    Rules/<PACK>/Disciplines/<CODE>/."""
    (pack / "Disciplines" / "ZZZ").mkdir(parents=True)
    (pack / "Disciplines" / "ZZZ" / "ODF_ZZZ_Data_Dictionary.md").write_text(
        "# ZZZ Data Dictionary\n", encoding="utf-8")


def _add_documents(pack: Path) -> None:
    """Everything an operator drops into Rules/<PACK>/ for a real Games."""
    _add_xsd(pack)
    _add_codes(pack)
    _add_disciplines(pack)


def test_empty_pack_starts_not_ready():
    root, rules, profiles, _pack = _fresh(PROFILE)
    try:
        st = PackRegistry.discover(rules, profiles).status("DROPIN")
        assert not st.ready
        assert any("No XSD compiles" in r for r in st.reasons)
        assert any("No Common Codes loaded" in r for r in st.reasons)
        assert any("No disciplines" in r for r in st.reasons)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dropping_in_documents_flips_the_pack_to_ready():
    root, rules, profiles, pack = _fresh(PROFILE)
    try:
        _add_documents(pack)
        st = PackRegistry.discover(rules, profiles).status("DROPIN")
        assert st.ready, f"still not ready: {st.reasons}"
        assert st.disciplines == ("ZZZ",)
        assert st.label == "Test Games"

        rd = PackRegistry.discover(rules, profiles).get("DROPIN")
        assert rd.games.sport("ZZZ") == "TEST-ZZZ-1.0"
        assert rd.games.source("ZZZ") == "OGEN"

        # A code must actually resolve, not just a Codeset name be detected --
        # otherwise MINIMAL_CODES could silently degrade back to an
        # unparseable/empty table (e.g. reverting @id to @value) and this
        # test would keep passing on table names alone.
        assert rd.description("DISCIPLINE", "ZZZ", "description") == "Test discipline"

        # Finding E: readiness alone is not the spec's acceptance criterion --
        # a ready pack must actually generate. Build the full bundle and check
        # every message that comes back is well-formed, parseable XML.
        #
        # NOTE: MINIMAL_XSD above is a deliberately trivial stub schema (an
        # OdfBody with only anyAttribute, no real content model), so every
        # generated message here fails its self-check with XSD_INVALID
        # findings -- that is an artifact of the stub schema, not a generator
        # fault. Do NOT "fix" this by trying to make these messages validate
        # cleanly; assert only that they are produced and are well-formed
        # XML, matching what a real (non-stub) XSD would actually validate.
        import xml.etree.ElementTree as ET

        from generator.bundle import build_bundle

        bundle = build_bundle(rd, "ZZZ", 1)
        assert bundle, "build_bundle returned no messages at all"
        # DT_PARTIC_TEAMS is correctly absent: MINIMAL_CODES models no team
        # event for ZZZ (eventstructure.has_team_events is data-driven from
        # the codes, and bundle.py itself drops that key when it's False) --
        # not a bug, just this fixture not exercising that path.
        assert "DT_PARTIC" in bundle
        assert "DT_SCHEDULE" in bundle
        assert any(k.startswith("DT_ENTRIES") for k in bundle)
        for doc_type, (xml_bytes, errs) in bundle.items():
            root_el = ET.fromstring(xml_bytes)  # raises if not well-formed
            assert root_el.tag == "OdfBody"
            # The stub schema means every message is expected to carry
            # XSD_INVALID self-check findings (see NOTE above) -- confirm
            # that's the only kind of finding, i.e. nothing generator-side
            # (a real crash or a non-XSD finding) is being masked by it.
            assert all("XSD_INVALID" in e for e in errs), (
                f"{doc_type} has unexpected non-XSD_INVALID findings: {errs}")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_missing_xsd_alone_keeps_the_pack_not_ready():
    """Codes and disciplines present, XSD absent -- only the XSD gate should
    fire. Pins the ``if getattr(pack, "schema", None) is None`` check in
    ``_readiness()``."""
    root, rules, profiles, pack = _fresh(PROFILE)
    try:
        _add_codes(pack)
        _add_disciplines(pack)
        st = PackRegistry.discover(rules, profiles).status("DROPIN")
        assert not st.ready
        assert any("No XSD compiles" in r for r in st.reasons)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_missing_codes_alone_keeps_the_pack_not_ready():
    """XSD and disciplines present, codes absent -- only the codes gate
    should fire. Pins the ``if not pack.codes.names()`` check in
    ``_readiness()``."""
    root, rules, profiles, pack = _fresh(PROFILE)
    try:
        _add_xsd(pack)
        _add_disciplines(pack)
        st = PackRegistry.discover(rules, profiles).status("DROPIN")
        assert not st.ready
        assert any("No Common Codes loaded" in r for r in st.reasons)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_missing_disciplines_alone_keeps_the_pack_not_ready():
    """XSD and codes present, disciplines absent -- only the disciplines gate
    should fire. Pins the ``if not pack.disciplines`` check in
    ``_readiness()``."""
    root, rules, profiles, pack = _fresh(PROFILE)
    try:
        _add_xsd(pack)
        _add_codes(pack)
        st = PackRegistry.discover(rules, profiles).status("DROPIN")
        assert not st.ready
        assert any("No disciplines" in r for r in st.reasons)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_incomplete_profile_alone_keeps_the_pack_not_ready():
    """Documents present but version strings unknown -- exactly SOLG28's state
    once the XSD and codes arrive but before the GEN document is read."""
    root, rules, profiles, pack = _fresh(
        "label: Test Games\ndefault_source: OGEN\n")
    try:
        _add_documents(pack)
        st = PackRegistry.discover(rules, profiles).status("DROPIN")
        assert not st.ready
        assert len(st.reasons) == 1
        assert "Games profile incomplete" in st.reasons[0]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_missing_profile_is_a_reason_not_a_crash():
    root, rules, profiles, pack = _fresh(None)
    try:
        _add_documents(pack)
        st = PackRegistry.discover(rules, profiles).status("DROPIN")
        assert not st.ready
        assert any("Games profile missing" in r for r in st.reasons)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_pack_load_failure_reason_names_the_exception_type():
    """Finding D: _load_one used to record only str(e), discarding the
    exception type -- the one message an operator sees when an LA2028
    document is malformed, and it couldn't distinguish "empty pack" from
    "ingestion crashed". Monkeypatch build_ruleset_pack (module-level
    function; PackRegistry._load_one re-imports it by name on every call, so
    reassigning the module attribute is enough) to raise a distinctive
    exception and assert its type name reaches the reason string."""
    import odf_validator.ingestion.builder as builder_mod

    root, rules, profiles, _pack = _fresh(PROFILE)
    original = builder_mod.build_ruleset_pack

    def _boom(pack_dir):
        raise ValueError("synthetic ingestion failure")

    builder_mod.build_ruleset_pack = _boom
    try:
        st = PackRegistry.discover(rules, profiles).status("DROPIN")
        assert not st.ready
        assert len(st.reasons) == 1
        assert "ValueError" in st.reasons[0]
        assert "synthetic ingestion failure" in st.reasons[0]
    finally:
        builder_mod.build_ruleset_pack = original
        shutil.rmtree(root, ignore_errors=True)
