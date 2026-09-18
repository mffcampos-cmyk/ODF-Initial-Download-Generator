"""Export generated ODF message bundles to files inside the project.

Generated messages are written under ``output/`` in the project root, which
is gitignored. Layout::

    output/<DISCIPLINE>/DT_PARTIC.xml
    output/<DISCIPLINE>/DT_PARTIC_TEAMS.xml
    output/<DISCIPLINE>/DT_ENTRIES_<EVENT>.xml   (one per event)
    output/<DISCIPLINE>/DT_SCHEDULE.xml

Not ``samples/``: that folder is the committed reference corpus, checked
against by hand when a change alters generated output. Writing generated
files there on every Save made the baseline move with the thing it was
supposed to be a baseline for, and a stray click could rewrite a
compliance reference with no signal in the UI. Regenerating the corpus is
now a deliberate ``--out-dir samples`` rather than the default.

CLI::

    python -m generator.export --discipline ARC
    python -m generator.export --all
"""
from __future__ import annotations

from pathlib import Path

from .bundle import build_bundle

# Anchor the default output at the project root so exports land in the
# project's output/ folder regardless of the current working directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = PROJECT_ROOT / "output"


def export_bundle(refdata, discipline: str, seed: int = 1,
                  out_dir: Path | str = DEFAULT_OUT_DIR,
                  *, require_clean: bool = True,
                  overrides=None, manifest: bool = True) -> list[Path]:
    """Build a bundle for ``discipline`` and write each message to disk.

    Files go to ``<out_dir>/<discipline>/<DOC_TYPE>.xml``. Returns the list of
    written paths. If ``require_clean`` is true (default) and any message still
    carries validation errors, nothing is written and ``ValueError`` is raised.

    A ``MANIFEST.json`` is written alongside recording what produced the
    output -- the seed actually used, the rule pack and the digests of the IOC
    documents behind it, the validator revision, and a digest per message. It
    is not in the returned list: that is the messages, and callers count it.
    Pass ``manifest=False`` when regenerating the committed ``samples/``
    corpus, where a timestamp changing on every run is diff noise.
    """
    bundle = build_bundle(refdata, discipline, seed, overrides=overrides)
    residual = bundle.errors
    if require_clean and residual:
        summary = "; ".join(f"{dt}: {errs[:3]}" for dt, errs in residual.items())
        raise ValueError(f"refusing to export un-clean messages for {discipline}: {summary}")

    dest = Path(out_dir) / discipline
    dest.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for doc_type, (xml, _errs) in bundle.items():
        path = dest / f"{doc_type}.xml"
        path.write_bytes(xml)
        written.append(path)

    if manifest:
        from .manifest import build_manifest, write_manifest
        write_manifest(
            build_manifest(refdata, discipline, bundle,
                           seed_requested=seed, overrides=overrides),
            dest)
    return written


def main(argv: list[str] | None = None) -> int:
    import argparse
    from .eventstructure import UnknownSquadSize
    from .games import GamesProfileError
    from .packload import PackDirError, load_refdata

    parser = argparse.ArgumentParser(
        prog="python -m generator.export",
        description="Export generated ODF message bundles into the project's output/ folder.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--discipline", help="discipline code to export, e.g. ARC")
    group.add_argument("--all", action="store_true", help="export every known discipline")
    parser.add_argument("--seed", type=int, default=1, help="generation seed (default: 1)")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR),
                        help=f"output folder (default: {DEFAULT_OUT_DIR})")
    pack_group = parser.add_mutually_exclusive_group()
    pack_group.add_argument("--pack", default=None,
                            help="pack name to generate for, e.g. SOLG28 "
                                 "(default: ODF_GAMES, else the pack "
                                 "ODF_PACK_DIR points at)")
    pack_group.add_argument("--pack-dir", default=None,
                            help="explicit path to a validator rule pack "
                                 "(default: ODF_PACK_DIR or known fallbacks)")
    parser.add_argument("--allow-unclean", action="store_true",
                        help="export even if messages still have validation errors")
    parser.add_argument("--no-manifest", action="store_true",
                        help="skip MANIFEST.json (use when regenerating "
                             "samples/, where its timestamp is diff noise)")
    parser.add_argument("--realistic-entries", action="store_true",
                        help="qualification-scale entry lists (like the real feeds)")
    parser.add_argument("--seeded-heats", action="store_true",
                        help="schedule heats = ceil(entries/8) using the codes' heat units")
    parser.add_argument("--victory-ceremonies", action="store_true",
                        help="include VICT units in the schedule")
    parser.add_argument("--historical-athletes", action="store_true",
                        help="add Status=HIS athletes with A-prefixed IDs")
    args = parser.parse_args(argv)

    if args.pack_dir:
        try:
            refdata = load_refdata(args.pack_dir)
        except (PackDirError, GamesProfileError) as exc:
            parser.error(str(exc))
    else:
        from .packs import PackNotReady, PackRegistry, UnknownPack
        try:
            registry = PackRegistry.discover()
            refdata = registry.get(args.pack or registry.default_name())
        except (PackDirError, PackNotReady, UnknownPack) as exc:
            parser.error(str(exc))

    if args.all:
        disciplines = refdata.disciplines()
    else:
        if args.discipline not in refdata.disciplines():
            parser.error(f"unknown discipline: {args.discipline}")
        disciplines = [args.discipline]

    from .overrides import Overrides
    overrides = Overrides(
        realistic_entries=args.realistic_entries,
        seeded_heats=args.seeded_heats,
        victory_ceremonies=args.victory_ceremonies,
        historical_athletes=args.historical_athletes)

    failures: list[str] = []
    for disc in disciplines:
        try:
            written = export_bundle(refdata, disc, args.seed, args.out_dir,
                                    require_clean=not args.allow_unclean,
                                    overrides=overrides,
                                    manifest=not args.no_manifest)
        except ValueError as exc:
            failures.append(str(exc))
            print(f"SKIP {disc}: {exc}")
            continue
        except UnknownSquadSize as exc:
            # A team event whose squad size nothing states. Skip the
            # discipline with the reason rather than aborting --all, so one
            # unmapped event does not cost the other 24 disciplines.
            failures.append(str(exc))
            print(f"SKIP {disc}: {exc}")
            continue
        except GamesProfileError as exc:
            # load_refdata() (the --pack-dir path) no longer requires a
            # profile just to load the pack and list its disciplines -- it
            # resolves the profile lazily, the first time a message header
            # actually needs the GEN-document constants, which happens here.
            # A pack folder with no matching generator/games/<name>.yaml
            # still can't generate; report that the same way every other
            # --pack-dir failure is reported (exit 2, actionable message)
            # instead of an uncaught traceback.
            parser.error(str(exc))
        print(f"OK   {disc}: wrote {len(written)} files to {written[0].parent}")

    if failures:
        print(f"\n{len(failures)} discipline(s) skipped due to validation errors.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
