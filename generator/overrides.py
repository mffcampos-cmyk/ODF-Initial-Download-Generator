from __future__ import annotations
from dataclasses import dataclass, replace


@dataclass
class Overrides:
    competition_code: str | None = None
    source: str | None = None
    gen: str | None = None
    sport: str | None = None
    codes: str | None = None
    status: str | None = None
    athletes: int | None = None
    teams: int | None = None
    coaches: int | None = None
    # Live-operations realism options (modeled on the real-life feeds; all
    # default to off so the baseline stays strictly Common-Codes-driven):
    realistic_entries: bool = False    # qualification-scale entry lists
    seeded_heats: bool = False         # heats = ceil(entries/8), real RSCs
    victory_ceremonies: bool = False   # include VICT units in the schedule
    historical_athletes: bool = False  # Status=HIS athletes with A-prefix IDs

    def normalize(self) -> "Overrides":
        def s(v):
            return v if (v is not None and str(v).strip() != "") else None
        def n(v):
            return v if (v is not None and int(v) >= 0) else None
        return replace(
            self,
            competition_code=s(self.competition_code),
            source=s(self.source),
            gen=s(self.gen),
            sport=s(self.sport),
            codes=s(self.codes),
            status=s(self.status),
            athletes=n(self.athletes),
            teams=n(self.teams),
            coaches=n(self.coaches),
        )

    def is_empty(self) -> bool:
        return all(getattr(self, f) is None for f in (
            "competition_code", "source", "gen", "sport", "codes", "status",
            "athletes", "teams", "coaches")) and not (
            self.realistic_entries or self.seeded_heats
            or self.victory_ceremonies or self.historical_athletes)
