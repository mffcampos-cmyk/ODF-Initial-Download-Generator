"""Fetch the IOC source documents a vendored pack needs, and ingest them.

This repository ships Rules/<pack> with its authored rules and its schema and
deliberately none of the IOC documents: the Common Codes workbook and the 25
Data Dictionaries are the IOC's to publish, and they change. This module
fetches them through the validator's own source-sync code and rebuilds the
pack, so a fresh clone becomes usable with one command rather than by
installing and operating the validator web application.

Both kinds of document are required, and the Data Dictionaries are the less
obvious half: a pack's disciplines are derived from the DD files found under
Disciplines/<CODE>/ and from nothing else -- builder.build_ruleset_pack reads
them out of scan.dd_files, and scan_ruleset skips rules/ as a managed
directory. The authored rule files this repository ships therefore contribute
no disciplines at all, and a codes-only import leaves a pack that
load_refdata refuses. Hence --codes-only is the narrow option, not the
default.

The validator's three sync functions and its pack builder are bound to
module-level names below rather than imported at each call site, so tests can
replace them without touching the validator's own modules.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

from odf_validator.ingestion.builder import build_ruleset_pack as _build_ruleset_pack
from odf_validator.sources.sync import apply_targets as _apply_targets
from odf_validator.sources.sync import check as _check
from odf_validator.sources.sync import fetch_targets as _fetch_targets

from .packload import PROJECT_ROOT, PackDirError, resolve_pack_dir

CODES_KIND = "codes"
# States meaning "upstream has something this pack does not hold". Anything
# else -- current, unverified, missing-upstream, unknown -- is either already
# here or not downloadable, and fetching it would be a no-op or an error.
OUTSTANDING = ("new", "update")


@dataclass
class ImportReport:
    pack_dir: Path
    selected: list[str] = field(default_factory=list)
    fetched: list[str] = field(default_factory=list)
    applied: list[str] = field(default_factory=list)
    disciplines: int = 0
    code_tables: int = 0
    error: str | None = None


def select_entries(sync_report, *, codes_only: bool = False):
    """The entries worth downloading, in the order the index lists them."""
    outstanding = [s for s in sync_report.entries if s.state in OUTSTANDING]
    if codes_only:
        outstanding = [s for s in outstanding if s.entry.kind == CODES_KIND]
    return [s.entry for s in outstanding]


def import_sources(pack=None, *, codes_only: bool = False,
                   client=None) -> ImportReport:
    """Fetch, apply and re-ingest. Returns what happened rather than printing.

    A sync error stops before fetching: if the index page could not be read
    there is nothing to fetch, and continuing would report an empty download
    as a successful one."""
    resolved = resolve_pack_dir(pack)
    report = ImportReport(pack_dir=resolved)

    sync_report = _check(resolved, client=client)
    if getattr(sync_report, "error", None):
        report.error = sync_report.error
        return report

    entries = select_entries(sync_report, codes_only=codes_only)
    report.selected = [e.reference for e in entries]
    if entries:
        report.fetched = _fetch_targets(resolved, entries, client=client)
        report.applied = _apply_targets(resolved, entries)

    pack_obj = _build_ruleset_pack(resolved)
    report.disciplines = len(pack_obj.disciplines)
    report.code_tables = len(pack_obj.codes.names())
    return report


def _pack_argument(value: str | None):
    """Accept a path or a bare pack name.

    `--pack SYOG26` is what a reader will try first, and it should not have to
    be spelled Rules/SYOG26."""
    if value is None:
        return None
    candidate = Path(value)
    if candidate.is_dir():
        return candidate
    named = PROJECT_ROOT / "Rules" / value
    if named.is_dir():
        return named
    return candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m generator.sources",
        description="Fetch the IOC source documents this repository does not "
                    "ship, and ingest them into a rule pack. The first run "
                    "converts one PDF per discipline and takes a while.")
    parser.add_argument(
        "--pack", default=None,
        help="pack directory, or a pack name under Rules/ (default: the pack "
             "resolve_pack_dir() finds -- ODF_PACK_DIR, else "
             "Rules/<ODF_GAMES or SYOG26>)")
    parser.add_argument(
        "--codes-only", dest="codes_only", action="store_true",
        help="fetch only the Common Codes workbook. Refreshes code membership "
             "without reconverting the Data Dictionaries -- but note that a "
             "pack with no Data Dictionaries has no disciplines, so this is "
             "for refreshing an already-imported pack, not for setting one up.")
    args = parser.parse_args(argv)

    try:
        report = import_sources(_pack_argument(args.pack),
                               codes_only=args.codes_only)
    except PackDirError as exc:
        print(exc, file=sys.stderr)
        return 1

    print(f"pack: {report.pack_dir}")
    if report.error:
        print(f"could not read the upstream index: {report.error}",
              file=sys.stderr)
        return 1
    if not report.selected:
        print("nothing outstanding upstream")
    else:
        print(f"selected {len(report.selected)}: {', '.join(report.selected)}")
        print(f"applied {len(report.applied)}: {', '.join(report.applied)}")
    print(f"disciplines: {report.disciplines}, code tables: {report.code_tables}")

    missing = []
    if not report.disciplines:
        missing.append("no disciplines (they come from the Data Dictionaries; "
                       "--codes-only will not produce any)")
    if not report.code_tables:
        missing.append("no code tables (they come from the Common Codes "
                       "workbook)")
    if missing:
        print("ABORT: the pack is still unusable and the application will not "
              "start:\n  " + "\n  ".join(missing)
              + f"\nCheck {report.pack_dir}/.incoming/ for anything fetched "
                "but not applied.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
