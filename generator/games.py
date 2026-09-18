"""Games-specific message conventions.

Everything else the generator needs -- competition code, disciplines, event
structure, venues, entry counts -- is derived from the validator rule pack and
is therefore Games-agnostic for free. Four values are not derivable: they are
published in a Games' GEN document. They live here, one YAML file per pack, in
``generator/games/<PACK>.yaml``.

A profile whose ``gen`` / ``codes`` / ``sport_template`` are still null is
*incomplete*: the pack it belongs to is reported not-ready and generation is
refused, rather than emitting an invented version string.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .packload import PackDirError

PROFILE_DIR = Path(__file__).resolve().parent / "games"

# Fields published in the Games' GEN document; all three are required before a
# pack can generate. Order is the order they are reported to the operator.
REQUIRED_FIELDS = ("gen", "codes", "sport_template")


class GamesProfileError(PackDirError):
    """No profile file exists for a pack, or the file cannot be read.

    A subclass of ``PackDirError`` (not just ``RuntimeError``): both mean "the
    thing the operator pointed us at is not fully usable", and any caller that
    already does ``except PackDirError`` around pack resolution/loading (e.g.
    a --pack-dir CLI entry point) should not be surprised by an uncaught
    sibling exception type when the pack it selected turns out to have no
    matching Games profile."""


@dataclass(frozen=True)
class GamesProfile:
    """The Games-specific half of an ODF message header."""

    pack_name: str
    label: str
    gen: str | None = None
    codes: str | None = None
    sport_template: str | None = None
    sources: dict[str, str] = field(default_factory=dict)
    default_source: str = "OGEN"

    @property
    def complete(self) -> bool:
        """True when every GEN-document value is known."""
        return not self.missing_fields()

    def missing_fields(self) -> list[str]:
        missing = [name for name in REQUIRED_FIELDS if not getattr(self, name)]
        # A sport_template that is present but lacks the {disc} placeholder
        # is not usable -- format() would silently return the same literal
        # string for every discipline. Treat it as incomplete (surfaced as a
        # readiness reason) rather than complete (surfaced as a bug at
        # generate time).
        if ("sport_template" not in missing and self.sport_template
                and "{disc}" not in self.sport_template):
            missing.append("sport_template")
        return missing

    def sport(self, discipline: str) -> str | None:
        """``Competition/@Sport`` for a discipline, or None if unknown."""
        if not self.sport_template:
            return None
        return self.sport_template.format(disc=discipline)

    def source(self, discipline: str) -> str:
        """``OdfBody/@Source``: the system generating the message."""
        return self.sources.get(discipline, self.default_source)


def load_profile(pack_name: str,
                 profile_dir: Path | str | None = None) -> GamesProfile:
    directory = Path(profile_dir) if profile_dir is not None else PROFILE_DIR
    path = directory / f"{pack_name}.yaml"
    if not path.exists():
        raise GamesProfileError(
            f"No Games profile for pack '{pack_name}': expected {path}. "
            f"Create it with the pack's label and, once that Games' GEN "
            f"document is available, its gen / codes / sport_template.")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        raise GamesProfileError(f"Games profile {path} is unreadable: {e}") from e
    if not isinstance(raw, dict):
        raise GamesProfileError(f"Games profile {path} must be a YAML mapping")

    sport_template = raw.get("sport_template")
    if sport_template:
        try:
            sport_template.format(disc="ARC")
        except Exception as e:
            raise GamesProfileError(
                f"Games profile {path} has an invalid sport_template "
                f"{sport_template!r}: {e}. The placeholder must be exactly "
                f"'{{disc}}', e.g. 'LA28-{{disc}}-1.0'.") from e

    raw_sources = raw.get("sources")
    if raw_sources is not None and not isinstance(raw_sources, dict):
        raise GamesProfileError(
            f"Games profile {path} has a 'sources' value that is not a "
            f"YAML mapping (got {raw_sources!r}). Expected e.g. "
            f"'sources: {{ARC: AWAARC1}}'.")

    return GamesProfile(
        pack_name=pack_name,
        label=raw.get("label") or pack_name,
        gen=raw.get("gen"),
        codes=raw.get("codes"),
        sport_template=sport_template,
        sources=dict(raw_sources or {}),
        default_source=raw.get("default_source") or "OGEN",
    )
