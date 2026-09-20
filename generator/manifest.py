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


def _direct_url() -> dict | None:
    """What pip recorded about where odf-validator was installed from.

    A `name @ git+https://...@<sha>` install -- the one pyproject.toml declares
    and the README documents -- makes pip write direct_url.json with the
    resolved commit. That is authoritative: it is the revision that WAS
    installed, not an inference from the filesystem.
    """
    try:
        from importlib.metadata import Distribution
        dist = Distribution.from_name("odf-validator")
        raw = dist.read_text("direct_url.json")
    except Exception:
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def _checkout_root(module_file=None) -> Path | None:
    """The validator's own git checkout, or None.

    The package directory's parent counts only when IT is a repository. The
    previous version resolved a root and let `git -C` answer, but git
    discovers a repository by walking UP: after the documented install the root
    is `site-packages`, and the documented layout puts `.venv/` inside the
    project, so git cheerfully returned the GENERATOR clone's HEAD and the
    manifest recorded it as the validator's. An enclosing repository is not
    this package's repository, and only a `.git` directly at the root proves
    the difference.
    """
    if module_file is None:
        try:
            import odf_validator
        except ImportError:
            return None
        module_file = odf_validator.__file__
    root = Path(module_file).resolve().parent.parent
    return root if (root / ".git").exists() else None


def validator_revision() -> dict:
    """Which validator engine ran, and how we know.

    Three answers, in descending order of authority: the commit pip recorded
    for a VCS install, the HEAD of a real validator checkout, or None with a
    reason. Never a guess -- a manifest asserting a revision it did not read
    is worse than one admitting it does not know, and this one spent a while
    asserting a revision it had read from the wrong repository entirely.
    """
    try:
        import odf_validator  # noqa: F401
    except ImportError as exc:                              # pragma: no cover
        return {"revision": None, "reason": f"odf_validator not importable: {exc}"}

    direct = _direct_url()
    if direct:
        commit = (direct.get("vcs_info") or {}).get("commit_id")
        if commit:
            return {"revision": commit, "source": "installed distribution",
                    "url": direct.get("url")}

    root = _checkout_root()
    if root is not None:
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
        dirty = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            capture_output=True, text=True, timeout=10, check=False)
        return {
            "revision": out.stdout.strip(),
            "source": "checkout",
            "path": str(root),
            # An uncommitted change means the revision does not fully describe
            # the engine that ran. Say so rather than letting the SHA imply
            # more than it can.
            "dirty": bool(dirty.stdout.strip()) if dirty.returncode == 0 else None,
        }

    version = None
    try:
        from importlib.metadata import version as _version
        version = _version("odf-validator")
    except Exception:
        pass
    return {"revision": None, "version": version,
            "reason": ("odf-validator was not installed from a VCS reference "
                       "and is not a git checkout, so no commit is recorded")}


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
