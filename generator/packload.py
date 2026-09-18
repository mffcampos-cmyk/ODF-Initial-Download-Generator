"""Locate and load the validator rule pack, refusing decoy directories.

Why this exists: the pack path used to default to the CWD-relative
``Rules/SYOG26``. When the app or tests were started from this project
without ``ODF_PACK_DIR`` set, the validator's ingestion silently *created*
an empty ``Rules/SYOG26/.ingestion_state.json`` decoy here — a directory
that passed a plain ``is_dir()`` check but produced a pack with no
disciplines and no code tables (symptom: empty discipline dropdown).

This module resolves the pack directory to the copy this repository ships at
``Rules/<ODF_GAMES or SYOG26>`` (an explicit argument or ``ODF_PACK_DIR``
still overrides it), and validates the loaded pack actually has content
before the app is allowed to use it.
"""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PACK_MARKERS = ("codes", "rules", "xsd", "Disciplines")

DEFAULT_PACK_NAME = "SYOG26"

_FETCH_HINT = (
    "The pack ships with its rules and its schema but without the IOC source "
    "documents. Fetch them with:\n"
    "    python -m generator.sources")


class PackDirError(RuntimeError):
    """The pack directory is missing, empty, or not a real rule pack."""


def looks_like_pack(path: Path) -> bool:
    """Cheap structural check: a real pack has at least one recognizable
    ingredient. A decoy dir holding only ``.ingestion_state.json`` does not."""
    if not path.is_dir():
        return False
    for marker in _PACK_MARKERS:
        if (path / marker).is_dir():
            return True
    for pattern in ("*.xsd", "*.xlsx", "**/*.xsd", "**/*.xlsx"):
        if any(path.glob(pattern)):
            return True
    return False


def _describe(path: Path) -> str:
    if not path.exists():
        return f"{path} (does not exist)"
    entries = [p.name for p in path.iterdir()]
    if not entries or entries == [".ingestion_state.json"]:
        return (f"{path} (empty decoy — contains only .ingestion_state.json; "
                f"it was probably created by running the app/tests from the "
                f"wrong directory without ODF_PACK_DIR; delete it)")
    return f"{path} (present but has no codes/rules/xsd content)"


def _default_pack_name() -> str:
    """The pack to look for when nothing points at one explicitly.

    ODF_GAMES names it, matching packs.py, so that setting one variable does
    not require setting the other."""
    return os.environ.get("ODF_GAMES") or DEFAULT_PACK_NAME


def _candidates(name: str) -> list[Path]:
    """Where a pack of that name may live, most specific first.

    The repository ships Rules/<name> (see Rules/SYOG26/PROVENANCE.md), so the
    project root is the answer for an ordinary clone. The CWD-relative entry
    is kept for a checkout run from somewhere else, and comes second so it
    cannot shadow the shipped pack."""
    return [PROJECT_ROOT / "Rules" / name, Path("Rules") / name]


def resolve_pack_dir(explicit: str | os.PathLike | None = None) -> Path:
    """Return a validated pack directory.

    Order: explicit argument, then ``ODF_PACK_DIR``, then the repository's own
    ``Rules/<ODF_GAMES or SYOG26>``, then the same path relative to the
    current directory."""
    env = os.environ.get("ODF_PACK_DIR")
    if explicit is not None or env:
        cand = Path(explicit if explicit is not None else env)
        if looks_like_pack(cand):
            return cand
        raise PackDirError(
            "ODF pack directory is not a usable rule pack:\n"
            f"  {_describe(cand)}\n"
            "Point ODF_PACK_DIR (or --pack-dir) at a rule pack directory, or "
            "unset it to use the pack this repository ships at "
            f"Rules/{_default_pack_name()}.\n"
            + _FETCH_HINT)
    name = _default_pack_name()
    tried: list[Path] = []
    for cand in _candidates(name):
        if looks_like_pack(cand):
            return cand
        tried.append(cand)
    raise PackDirError(
        f"No usable ODF rule pack named {name} found. Tried:\n"
        + "\n".join(f"  - {_describe(p)}" for p in tried)
        + "\n" + _FETCH_HINT)


def load_refdata(pack_dir: str | os.PathLike | None = None):
    """Build the rule pack and wrap it in RefData, failing loudly if the
    resulting pack is empty (no disciplines / no code tables).

    Loading a pack to read its content (list disciplines, look up codes) does
    NOT require a Games profile: the profile publishes GEN-document constants
    (gen / codes / sport_template) that only matter once something actually
    builds a message header. Those are resolved lazily, by pack name, the
    first time ``RefData.games`` is read (see refdata.py) -- so a pack folder
    whose name has no matching ``generator/games/<name>.yaml`` (a dated copy,
    a restored backup, anything not named after a known Games) still loads
    fine here and raises ``GamesProfileError`` only when generation is
    actually attempted against it."""
    from odf_validator.ingestion.builder import build_ruleset_pack
    from .refdata import RefData

    resolved = resolve_pack_dir(pack_dir)
    pack = build_ruleset_pack(Path(resolved))
    missing = []
    if not pack.disciplines:
        missing.append("no disciplines")
    if not pack.codes.names():
        missing.append("no code tables")
    if missing:
        raise PackDirError(
            f"Rule pack at {resolved} loaded but is empty ({', '.join(missing)}) "
            "— the discipline dropdown would be empty.\n" + _FETCH_HINT)
    return RefData(pack, pack_dir=resolved, profile=None)
