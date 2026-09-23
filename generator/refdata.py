from __future__ import annotations

import re

# SYOG2026_ODF_Common_Codes_v_2_4.xlsx -> (2, 4)
_CODES_RELEASE = re.compile(r"_v_(\d+)_(\d+)\.xlsx$", re.IGNORECASE)


def codes_version(loaded_files) -> str | None:
    """The Common Codes release among a pack's loaded files, as "2.4".

    Read from what the pack actually loaded (``LoadReport.loaded_files``), not
    from what happens to sit in the folder, so the stamp names the release the
    messages were built from. The highest release wins if several loaded."""
    found = [(int(m[1]), int(m[2])) for f in loaded_files or ()
             if (m := _CODES_RELEASE.search(str(f)))]
    if not found:
        return None
    major, minor = max(found)
    return f"{major}.{minor}"


class RefData:
    """Read-only accessor over a validator RulePack: code tables + discipline
    list. All generation constraints that come from the reference files are
    reached through here so builders never touch the pack directly."""

    def __init__(self, pack, pack_dir=None, profile=None):
        self.pack = pack
        self.pack_dir = pack_dir
        self._profile = profile
        self._func_cache: dict[str, list] = {}

    @property
    def games(self):
        """The GamesProfile for this pack, resolved lazily by pack name so
        every existing ``RefData(pack)`` call site keeps working."""
        if self._profile is None:
            from .games import load_profile
            self._profile = load_profile(self.pack.name)
        return self._profile

    @property
    def codes_reference(self) -> str | None:
        """``Competition/@Codes`` for this pack's messages."""
        report = getattr(self.pack, "report", None)
        return self.games.codes_reference(
            codes_version(getattr(report, "loaded_files", ())))

    def discipline_functions(self, discipline: str):
        from .functions import read_discipline_functions
        if discipline not in self._func_cache:
            self._func_cache[discipline] = read_discipline_functions(
                self.pack_dir, discipline)
        return self._func_cache[discipline]

    def disciplines(self) -> list[str]:
        return sorted(self.pack.disciplines)

    def has_codeset(self, codeset: str) -> bool:
        return self.pack.codes.table(codeset) is not None

    def has_teams(self, discipline: str) -> bool:
        """Whether a discipline models teams, so a DT_PARTIC_TEAMS message
        applies. Data-driven from the pack: true if it publishes a
        SC@TeamType@<disc> sport-code table, or has any active rule constraining
        a Team element / @TeamType for this discipline (e.g. CRD, validated
        against DISCIPLINE_GENDER without its own SC@TeamType table)."""
        if self.has_codeset(f"SC@TeamType@{discipline}"):
            return True
        for r in getattr(self.pack, "rules", []):
            attr = getattr(r, "attribute", None) or ""
            target = getattr(r, "target", "") or ""
            if attr == "TeamType" or "Team" in target:
                discs = getattr(getattr(r, "applies_to", None), "disciplines", []) or []
                if discipline in discs:
                    return True
        return False

    def codes(self, codeset: str) -> list[str]:
        table = self.pack.codes.table(codeset)
        if table is None:
            return []
        return sorted(table._rows.keys())

    def description(self, codeset: str, code: str, field: str) -> str | None:
        table = self.pack.codes.table(codeset)
        return None if table is None else table.get(code, field)
