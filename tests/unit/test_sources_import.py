"""The one command a fresh clone runs before anything works.

Every test here stubs the network. The real fetch is a manual check: it
depends on an IOC page this project does not control, and a test that fails
when that page is slow teaches people to ignore failures."""
from datetime import date

import pytest

from generator import sources
from generator.sources import ImportReport, import_sources, select_entries


class _Entry:
    """Stand-in for odf_validator.sources.catalogue.CatalogueEntry.

    Deliberately a local stub rather than the real class: these tests are
    about which entries get picked, and constructing the real frozen
    dataclass ties them to a field list that is none of their business."""

    def __init__(self, reference, kind):
        self.reference = reference
        self.kind = kind
        self.title = reference
        self.published = date(2026, 1, 1)
        self.url = f"https://example.invalid/{reference}"
        self.target = f"{kind}/{reference}"
        self.discipline = None


class _Status:
    def __init__(self, entry, state):
        self.entry = entry
        self.state = state


class _Report:
    def __init__(self, entries, error=None):
        self.entries = entries
        self.error = error


CODES = _Status(_Entry("CC_v2_2", "codes"), "new")
DD = _Status(_Entry("ODF_ARC_DD", "dd"), "new")
SCHEMA = _Status(_Entry("odf-schema", "schema"), "update")
HELD = _Status(_Entry("CC_v2_1", "codes"), "current")


def test_default_selects_every_outstanding_entry_in_catalogue_order():
    """The Data Dictionaries are not optional: disciplines come from them and
    nothing else, so a default that skipped them would leave a pack the
    application refuses to start against.

    The input is deliberately NOT in alphabetical order of kind. With codes,
    dd, schema listed alphabetically, an implementation that grouped by kind
    would produce the same list as one that preserved the catalogue's order,
    and this assertion would hold for both."""
    chosen = select_entries(_Report([SCHEMA, CODES, DD, HELD]))
    assert [e.reference for e in chosen] == ["odf-schema", "CC_v2_2", "ODF_ARC_DD"]


def test_codes_only_narrows_to_the_workbook():
    chosen = select_entries(_Report([CODES, DD, SCHEMA, HELD]), codes_only=True)
    assert [e.reference for e in chosen] == ["CC_v2_2"]


def test_entries_already_held_are_not_refetched():
    assert select_entries(_Report([HELD])) == []


def test_import_fetches_applies_then_rebuilds(monkeypatch, tmp_path):
    pack = tmp_path / "SYOG26"
    (pack / "rules").mkdir(parents=True)
    calls = []

    class _Pack:
        disciplines = ["ARC", "ATH"]

        class codes:
            @staticmethod
            def names():
                return ["EVENT_UNIT", "LOCATION", "DISCIPLINE_FUNCTION"]

    monkeypatch.setattr(sources, "_check", lambda d, client=None: (
        calls.append(("check", d)) or _Report([CODES, DD])))
    monkeypatch.setattr(sources, "_fetch_targets", lambda d, entries, client=None: (
        calls.append(("fetch", [e.reference for e in entries]))
        or [".incoming/codes/CC_v2_2.xlsx", ".incoming/Disciplines/ARC/ODF_ARC_DD.pdf"]))
    monkeypatch.setattr(sources, "_apply_targets", lambda d, entries: (
        calls.append(("apply", [e.reference for e in entries]))
        or ["codes/CC_v2_2.xlsx", "Disciplines/ARC/ODF_ARC_DD.pdf"]))
    monkeypatch.setattr(sources, "_build_ruleset_pack", lambda d: (
        calls.append(("build", d)) or _Pack()))

    report = import_sources(pack)

    assert [c[0] for c in calls] == ["check", "fetch", "apply", "build"]
    assert calls[1][1] == ["CC_v2_2", "ODF_ARC_DD"]
    assert report.code_tables == 3
    assert report.disciplines == 2
    assert report.error is None


def test_a_sync_error_stops_before_fetching(monkeypatch, tmp_path):
    pack = tmp_path / "SYOG26"
    (pack / "rules").mkdir(parents=True)

    def _explode(*args, **kwargs):
        raise AssertionError("must not fetch when the index could not be read")

    monkeypatch.setattr(sources, "_check",
                        lambda d, client=None: _Report([], error="403 Forbidden"))
    monkeypatch.setattr(sources, "_fetch_targets", _explode)
    monkeypatch.setattr(sources, "_apply_targets", _explode)

    report = import_sources(pack)

    assert report.error == "403 Forbidden"
    assert report.fetched == []


@pytest.mark.parametrize("disciplines,code_tables", [(0, 5), (25, 0), (0, 0)])
def test_main_reports_failure_when_the_pack_is_still_unusable(
        monkeypatch, tmp_path, disciplines, code_tables):
    """Both halves are load-bearing. load_refdata refuses a pack missing
    either, so reporting success on one of them is reporting success on a
    pack that cannot start the application."""
    pack = tmp_path / "SYOG26"
    (pack / "rules").mkdir(parents=True)
    monkeypatch.setattr(sources, "import_sources",
                        lambda *a, **k: ImportReport(pack_dir=pack,
                                                    disciplines=disciplines,
                                                    code_tables=code_tables))
    assert sources.main(["--pack", str(pack)]) == 2


def test_main_succeeds_when_both_arrived(monkeypatch, tmp_path):
    pack = tmp_path / "SYOG26"
    (pack / "rules").mkdir(parents=True)
    monkeypatch.setattr(sources, "import_sources",
                        lambda *a, **k: ImportReport(pack_dir=pack, disciplines=25,
                                                    code_tables=570))
    assert sources.main(["--pack", str(pack)]) == 0
