"""Discovery of every Games rule pack, and whether each one can generate.

The generator used to bind one pack at import time. It now discovers every
pack under the validator's ``Rules/`` directory so the operator can choose a
Games in the UI, and reports *why* a pack cannot generate rather than either
crashing at startup or silently producing nothing.

Readiness is computed from the loaded pack, never from a hand-maintained flag:
drop the official documents into ``Rules/<PACK>/``, restart, and the pack
becomes ready by itself.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .games import GamesProfile, GamesProfileError, load_profile
from .packload import PackDirError, resolve_pack_dir
from .refdata import RefData

# Top-level-only structural markers for discovery. Deliberately narrower than
# packload.looks_like_pack(), which globs **/*.xsd and **/*.xlsx at unbounded
# depth to answer a different question ("is this one explicitly-configured
# directory an empty decoy?"). Reusing that unbounded glob here would register
# any sibling directory with a stray .xsd/.xlsx anywhere in its subtree (a
# docs/ folder, a _reference/ sample, an old backup) as a phantom pack.
_PACK_TOP_LEVEL_MARKERS = ("codes", "rules", "xsd", "Disciplines")


def _has_pack_structure_at_top_level(directory: Path) -> bool:
    """True if ``directory`` itself (not its subtree) has the structural
    ingredients of a rule pack: one of the marker subdirectories, or a
    schema/workbook file directly inside it."""
    for marker in _PACK_TOP_LEVEL_MARKERS:
        if (directory / marker).is_dir():
            return True
    for pattern in ("*.xsd", "*.xlsx"):
        if any(directory.glob(pattern)):
            return True
    return False


class UnknownPack(RuntimeError):
    """A pack name that was never discovered."""


class PackNotReady(RuntimeError):
    """A discovered pack that cannot generate yet."""


@dataclass(frozen=True)
class PackStatus:
    """Immutable snapshot of one pack's readiness.

    ``reasons`` and ``disciplines`` are stored (and always handed out) as
    tuples, not lists: a ``frozen=True`` dataclass only stops reassigning
    ``st.ready = True``, it does nothing to stop ``st.reasons.append(...)``
    from permanently corrupting the registry's own storage, since a plain
    list is mutable regardless of who holds the reference. Coercing to a
    tuple in ``__post_init__`` closes that hole at the source rather than
    only at ``to_dict()``: every accessor (``status()``, ``statuses()``,
    ``get()`` indirectly) already hands out this same immutable object, so
    there is nothing further to defend at the boundary."""
    name: str
    label: str
    ready: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)
    disciplines: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reasons", tuple(self.reasons))
        object.__setattr__(self, "disciplines", tuple(self.disciplines))

    def to_dict(self) -> dict:
        return {"name": self.name, "label": self.label, "ready": self.ready,
                "reasons": list(self.reasons),
                "disciplines": list(self.disciplines)}


def rules_dir_from_env() -> Path:
    """The directory holding one subfolder per pack.

    ``ODF_RULES_DIR`` wins; otherwise it is the parent of whatever
    ``resolve_pack_dir()`` settles on, which keeps the existing
    ``ODF_PACK_DIR`` setup working untouched."""
    explicit = os.environ.get("ODF_RULES_DIR")
    if explicit:
        return Path(explicit)
    return Path(resolve_pack_dir()).parent


def _readiness(pack, profile: GamesProfile | None,
               profile_error: str | None) -> tuple[list[str], list[str]]:
    """Reasons this pack cannot generate, split into ``(content_reasons,
    profile_reasons)``. Both empty means ready; ``content_reasons`` empty
    (regardless of ``profile_reasons``) means the pack's own content -- its
    disciplines, its code tables -- can be read even though it cannot yet
    generate a message. ``PackStatus.reasons`` is still their concatenation
    in this same order, so every existing reader of ``reasons`` (readiness
    text, count, ordering) sees exactly what it did before; the split is
    purely so callers that only need to *read* a pack (list its disciplines)
    can tell that failure apart from one where there is no content at all.

    The wording mirrors the numbered drop-in steps under "To bring SOLG28
    online" in this repository's README, so an operator who has never read
    that section still learns exactly what to do."""
    name = pack.name
    content_reasons: list[str] = []
    if getattr(pack, "schema", None) is None:
        content_reasons.append(
            f"No XSD compiles - drop the {name} schema file(s) under "
            f"Rules/{name}/ and set root_xsd in pack.yaml if the entry point "
            f"is not odf2.xsd.")
    if not pack.codes.names():
        content_reasons.append(
            f"No Common Codes loaded - drop the {name} Common Codes workbook "
            f"(.xlsx, or .xml with <Codeset> elements) under "
            f"Rules/{name}/codes/.")
    if not pack.disciplines:
        content_reasons.append(
            f"No disciplines - create Rules/{name}/Disciplines/<CODE>/ per "
            f"sport and drop that discipline's Data Dictionary in.")
    profile_reasons: list[str] = []
    if profile is None:
        profile_reasons.append(
            f"Games profile missing - {profile_error} "
            f"See generator/games/{name}.yaml.")
    elif not profile.complete:
        profile_reasons.append(
            f"Games profile incomplete - set "
            f"{', '.join(profile.missing_fields())} in "
            f"generator/games/{name}.yaml from the {name} GEN document "
            f"(sport_template must contain the literal '{{disc}}' "
            f"placeholder, e.g. 'LA28-{{disc}}-1.0').")
    return content_reasons, profile_reasons


class PackRegistry:
    """Every discovered pack, its profile, and its readiness."""

    def __init__(self, entries: dict[str, tuple],
                 profile_dir: Path | str | None = None):
        # name -> (RefData, PackStatus)
        self._entries = entries
        # Kept so default_name() can load a pack discovered only later (see
        # the explicit-selection registration below) with the same profile
        # directory the rest of the registry was built with.
        self._profile_dir = profile_dir

    @classmethod
    def discover(cls, rules_dir: Path | str | None = None,
                 profile_dir: Path | str | None = None) -> "PackRegistry":
        directory = Path(rules_dir) if rules_dir is not None else rules_dir_from_env()
        entries: dict[str, tuple] = {}
        for child in sorted(p for p in directory.iterdir() if p.is_dir()):
            # A candidate pack folder either declares itself with a
            # pack.yaml manifest (the SOLG28-style empty scaffold, which has
            # nothing else yet) or already has the structural ingredients of
            # a pack (codes/rules/xsd/Disciplines, the SYOG26-style fully
            # populated pack, which predates pack.yaml and has none). Either
            # signal alone is enough; requiring both would miss one of them.
            if not (child / "pack.yaml").exists() and not _has_pack_structure_at_top_level(child):
                continue
            entries[child.name] = cls._load_one(child, profile_dir)
        if not entries:
            raise PackDirError(
                f"Found no rule packs under {directory}. A pack is a subfolder "
                f"containing a pack.yaml, or one with top-level codes/, rules/, "
                f"xsd/ or Disciplines/ content. Set ODF_RULES_DIR (or "
                f"ODF_PACK_DIR) to the validator's Rules folder.")
        return cls(entries, profile_dir)

    @staticmethod
    def _load_one(pack_dir: Path, profile_dir: Path | str | None = None) -> tuple:
        from odf_validator.ingestion.builder import build_ruleset_pack

        name = pack_dir.name
        profile: GamesProfile | None = None
        profile_error: str | None = None
        try:
            profile = load_profile(name, profile_dir)
        except GamesProfileError as e:
            profile_error = str(e)

        try:
            pack = build_ruleset_pack(pack_dir)
        except Exception as e:
            status = PackStatus(
                name=name, label=(profile.label if profile else name),
                ready=False,
                reasons=[f"Pack failed to load: {type(e).__name__}: {e}"],
                disciplines=[])
            return (None, status, False)

        content_reasons, profile_reasons = _readiness(pack, profile, profile_error)
        reasons = content_reasons + profile_reasons
        refdata = RefData(pack, pack_dir=pack_dir, profile=profile)
        status = PackStatus(
            name=name, label=(profile.label if profile else name),
            ready=not reasons, reasons=reasons,
            disciplines=sorted(pack.disciplines))
        return (refdata, status, not content_reasons)

    def names(self) -> list[str]:
        return sorted(self._entries)

    def status(self, name: str) -> PackStatus:
        if name not in self._entries:
            raise UnknownPack(
                f"unknown pack: {name}. Known packs: {', '.join(self.names())}")
        return self._entries[name][1]

    def statuses(self) -> list[PackStatus]:
        return [self._entries[n][1] for n in self.names()]

    def get(self, name: str) -> RefData:
        status = self.status(name)
        if not status.ready:
            raise PackNotReady(
                f"pack {name} cannot generate yet:\n"
                + "\n".join(f"  - {r}" for r in status.reasons))
        return self._entries[name][0]

    def peek(self, name: str) -> RefData:
        """RefData for a discovered pack regardless of *generation*
        readiness -- for read-only operations (list disciplines, look up a
        code) that were never supposed to need a complete Games profile in
        the first place, the same lesson ``load_refdata()`` in packload.py
        learned at the --pack-dir layer. ``get()`` remains the gate for
        anything that actually builds a message, since that still must
        refuse a pack with no (or an incomplete) profile.

        Raises ``UnknownPack`` for a name that was never discovered, and
        ``PackNotReady`` if the pack has no usable *content* -- ingestion
        itself failed, or the ruleset is missing its schema/codes/
        disciplines -- since there is nothing to read there regardless of
        the profile."""
        status = self.status(name)
        refdata, _status, content_ready = self._entries[name]
        if refdata is None or not content_ready:
            raise PackNotReady(
                f"pack {name} has no usable content yet:\n"
                + "\n".join(f"  - {r}" for r in status.reasons))
        return refdata

    def default_name(self) -> str:
        chosen = os.environ.get("ODF_GAMES")
        if chosen:
            if chosen not in self._entries:
                raise UnknownPack(
                    f"ODF_GAMES names an unknown pack: {chosen}. "
                    f"Known packs: {', '.join(self.names())}")
            return chosen
        try:
            explicit_dir = resolve_pack_dir()
        except PackDirError:
            explicit_dir = None
        if explicit_dir is not None:
            from_pack_dir = Path(explicit_dir).name
            if from_pack_dir not in self._entries:
                # resolve_pack_dir() already confirmed this is a real,
                # structurally valid pack -- depth-agnostically, via
                # looks_like_pack() -- that top-level-only discovery simply
                # never saw (its content may live one directory deeper than
                # discovery looks, or it may sit outside the discovered
                # Rules/ tree entirely). The operator explicitly pointed us
                # at *this* directory: falling through to "any other
                # discovered pack" below would silently generate messages
                # from a pack the operator never selected. Register it as a
                # pack of its own instead of guessing.
                self._entries[from_pack_dir] = self._load_one(
                    Path(explicit_dir), self._profile_dir)
            return from_pack_dir
        for name in self.names():
            if self._entries[name][1].ready:
                return name
        return self.names()[0]
