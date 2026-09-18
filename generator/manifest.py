"""What produced an exported bundle, written beside it.

A generated ODF message is evidence about a set of documents. Without the
provenance it is just plausible XML, and three facts that make it reproducible
were previously lost the moment the files hit disk:

**The seed that actually produced it.** `build_bundle` walks seed..seed+4
looking for a clean result and returns whichever it got, so the seed you asked
for is not necessarily the seed you have. `Bundle.seed_used` knows; nothing
wrote it down.

**The documents behind it.** The validator records every IOC source it fetched
in the ruleset's `.sources.json` -- url, reference, published date, sha256. The
messages are derived from those documents, so their digests belong with the
messages. "Which Common Codes version produced this sample" then has an answer
that does not depend on anyone remembering.

**The engine that called it clean.** "Validates clean" is a claim about a
specific validator revision (see the README's Setup). Recorded when it can be
read from a git checkout, and explicitly `null` with a reason when it cannot --
a manifest asserting a SHA it never read would be worse than one admitting it
does not know.

Plus the digest of every message written, so a file edited after export stops
matching its own manifest.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path

MANIFEST_NAME = "MANIFEST.json"
SOURCES_FILE = ".sources.json"

# Fields of a SourceRecord worth carrying into the manifest. `sha256` is the
# one that matters -- it identifies the bytes regardless of what the upstream
# reference says -- but the reference and publication date are what a human
# recognises, and `stale` records that the app has seen upstream differ.
_SOURCE_FIELDS = ("sha256", "url", "reference", "published", "fetched_at",
                  "adopted", "stale")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validator_revision() -> dict:
    """The validator checkout's git revision, or why it is unknown.

    Best effort by design. The validator is imported from a sibling checkout on
    PYTHONPATH rather than installed (see the README), so there is no package
    version to read and `git` is the only thing that knows. Every failure path
    returns None with a reason rather than a guess.
    """
    try:
        import odf_validator
    except ImportError as exc:                              # pragma: no cover
        return {"revision": None, "reason": f"odf_validator not importable: {exc}"}

    root = Path(odf_validator.__file__).resolve().parent.parent
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"revision": None, "path": str(root),
                "reason": f"could not run git: {exc}"}
    if out.returncode != 0:
        return {"revision": None, "path": str(root),
                "reason": (out.stderr.strip()
                           or f"git rev-parse exited {out.returncode}")}

    revision = out.stdout.strip()
    dirty = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        capture_output=True, text=True, timeout=10, check=False)
    return {
        "revision": revision,
        "path": str(root),
        # An uncommitted change means the revision does not fully describe the
        # engine that ran. Say so rather than letting the SHA imply more than
        # it can.
        "dirty": bool(dirty.stdout.strip()) if dirty.returncode == 0 else None,
    }


def pack_sources(pack_dir) -> dict:
    """The IOC documents behind this pack, from the validator's `.sources.json`.

    An empty dict means the file is absent -- a pack assembled by hand, or one
    whose documents were adopted rather than fetched. That is a fact about the
    pack, not an error here.
    """
    if not pack_dir:
        return {}
    path = Path(pack_dir) / SOURCES_FILE
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}

    # `.sources.json` is {"entries": {target: record}, "last_checked": ...}.
    # Read the nested shape, but fall back to a flat {target: record} map so a
    # change in the validator's file layout degrades to "no sources recorded"
    # rather than to a manifest full of `{}`.
    entries = raw.get("entries", raw)
    if not isinstance(entries, dict):
        return {}

    out = {}
    for target, record in entries.items():
        if isinstance(record, dict) and "sha256" in record:
            out[target] = {k: record[k] for k in _SOURCE_FIELDS
                           if k in record}
    return out


def _options(overrides) -> dict:
    if overrides is None:
        return {}
    if is_dataclass(overrides):
        return asdict(overrides)
    return dict(getattr(overrides, "__dict__", {}))


def build_manifest(refdata, discipline: str, bundle, *, seed_requested: int,
                   overrides=None) -> dict:
    """The manifest for one built bundle. Pure: touches no output files.

    Message keys are recorded under the filenames `export_bundle` writes, so
    the manifest can be compared against a folder without re-deriving the
    naming.
    """
    pack = refdata.pack
    return {
        "generated_at": _utc_now(),
        "discipline": discipline,
        "seed_requested": seed_requested,
        "seed_used": bundle.seed_used,
        "clean": bundle.clean,
        "options": _options(overrides),
        "pack": {
            "name": pack.name,
            "version": pack.version,
            "dir": str(refdata.pack_dir) if refdata.pack_dir else None,
            "sources": pack_sources(refdata.pack_dir),
        },
        "validator": validator_revision(),
        "messages": {f"{key}.xml": _sha256(xml)
                     for key, (xml, _errs) in bundle.items()},
    }


def write_manifest(manifest: dict, dest: Path) -> Path:
    path = Path(dest) / MANIFEST_NAME
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    return path
