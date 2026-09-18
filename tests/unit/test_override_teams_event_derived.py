"""Teams generated under a count override must come from the discipline's real
team events, not be fabricated from the count alone.

Regression (audit B1 + root cause): _apply_count_overrides built teams from a
scalar count with no EventInfo in scope, so it invented the gender ("X"), the
RSC ("HBBXTEAM----" matches no CC@EVENT row), the squad size (always 2) and the
member genders. Worse, it fabricated teams for disciplines that have no team
events at all, leaving DT_ENTRIES referencing teams that no DT_PARTIC_TEAMS
message declares.
"""
from lxml import etree

from generator import eventstructure
from generator.bundle import build_bundle
from generator.dataset import build_dataset
from generator.overrides import Overrides
from generator.packload import resolve_pack_dir
from generator.refdata import RefData
from tests.conftest import PACK

RD = RefData(PACK, pack_dir=resolve_pack_dir())

# Disciplines whose Common Codes schedule no team event at SYOG2026.
NO_TEAM_DISCIPLINES = ("SWM", "ATH", "JUD", "TRI")


def _athletes(ds):
    return [p for p in ds.participants if not p.is_official]


def _team_events(discipline):
    return [e for e in eventstructure.events(RD, discipline) if e.is_team]


# --- S1: no fabricated teams / no dangling references ---------------------

def test_team_count_ignored_for_disciplines_without_team_events():
    for disc in NO_TEAM_DISCIPLINES:
        ds = build_dataset(RD, disc, 1, Overrides(teams=3))
        assert ds.teams == [], f"{disc} has no team events but produced teams"


def test_entries_never_reference_undeclared_teams():
    # Every Entry@Type='T' code in DT_ENTRIES must be declared by a Team in
    # DT_PARTIC_TEAMS. bundle.py drops DT_PARTIC_TEAMS for disciplines with no
    # team events, so fabricating teams there ships dangling references.
    for disc in NO_TEAM_DISCIPLINES + ("HBB", "TKW"):
        bundle = build_bundle(RD, disc, 1, overrides=Overrides(athletes=12, teams=3))
        referenced = set()
        for key, (xml, _errs) in bundle.items():
            if key.startswith("DT_ENTRIES"):
                referenced |= {e.get("Code") for e in etree.fromstring(xml).iter("Entry")
                               if e.get("Type") == "T"}
        declared = set()
        if "DT_PARTIC_TEAMS" in bundle:
            declared = {t.get("Code") for t in
                        etree.fromstring(bundle["DT_PARTIC_TEAMS"][0]).iter("Team")}
        assert referenced <= declared, \
            f"{disc}: DT_ENTRIES references undeclared teams {referenced - declared}"


# --- S2/S3/S4: teams carry a real event's RSC, squad size and gender -------

def test_override_team_codes_match_a_real_event_rsc():
    # HBB publishes M TEAM4 and W TEAM4; a team code must start with one of
    # those event prefixes, not a fabricated 'HBBXTEAM----'.
    ds = build_dataset(RD, "HBB", 1, Overrides(teams=4))
    prefixes = {f"HBB{e.gender}{e.event}"[:12].ljust(12, "-")
                for e in _team_events("HBB")}
    assert prefixes
    for t in ds.teams:
        assert any(t.code.startswith(p) for p in prefixes), \
            f"{t.code} matches no real HBB event prefix {sorted(prefixes)}"


def test_override_team_squad_size_matches_the_event():
    # RU7 squads are 7 in the codes; the override path used to collapse to 2.
    ds = build_dataset(RD, "RU7", 1, Overrides(teams=2))
    sizes = {e.team_size for e in _team_events("RU7")}
    assert sizes == {7}
    assert all(len(t.member_codes) == 7 for t in ds.teams), \
        [len(t.member_codes) for t in ds.teams]


def test_override_team_gender_is_the_event_gender():
    # The audit's B1: gendered disciplines must not all come out as 'X'.
    ds = build_dataset(RD, "HBB", 1, Overrides(teams=4))
    assert {t.gender for t in ds.teams} <= {"M", "W"}


def test_override_team_members_match_the_team_gender():
    # A team labelled 'M' must not contain a woman.
    ds = build_dataset(RD, "HBB", 1, Overrides(teams=4))
    by_code = {p.code: p.gender for p in _athletes(ds)}
    expected = {"M": {"M"}, "W": {"F"}}
    for t in ds.teams:
        member_genders = {by_code[c] for c in t.member_codes}
        assert member_genders == expected[t.gender], \
            f"{t.code} Gender={t.gender} members={sorted(member_genders)}"


# --- Agreed policy: squad members are additional to the athlete target -----

def test_squad_members_are_additional_to_the_athlete_target():
    # athletes=N governs individual-event athletes; squads are generated on top,
    # so a 2-team HBB override adds 2 x 4 squad members.
    ds = build_dataset(RD, "HBB", 1, Overrides(athletes=10, teams=2))
    assert len(ds.teams) == 2
    squad = sum(len(t.member_codes) for t in ds.teams)
    assert squad == 8
    assert len(_athletes(ds)) == 10 + squad


# --- Independent bug: TeamType must stay inside the discipline -------------

def test_team_type_is_a_teamtype_code_not_a_discipline_rsc():
    """TKW publishes no SC@TeamType@TKW table.

    It first borrowed the whole cross-discipline DISCIPLINE_GENDER table and
    emitted archery codes (ARCW / CERG). The fix for that narrowed the borrow
    to TKW's own codes, which was the right refinement of the wrong idea:
    DISCIPLINE_GENDER is not the TeamType code set, so "TKWX----...", a
    34-character RSC, still is not a TeamType value. GEN 2.1.3.5 wants an
    SCGEN@TeamType code, and SC@TeamType@GEN is where they live.
    """
    valid = set(RD.codes("SC@TeamType@GEN"))
    assert valid, "pack has no SC@TeamType@GEN table"
    for ov in (None, Overrides(teams=4)):
        ds = build_dataset(RD, "TKW", 1, ov)
        assert ds.teams
        for t in ds.teams:
            assert t.team_type in valid, (
                f"{t.code} TeamType={t.team_type!r} is not an "
                f"SC@TeamType@GEN code (overrides={ov})")


def test_team_type_is_chosen_by_what_the_squad_is():
    """Not by rng.choice.

    A discipline publishing both ORG and CPLM used to get whichever the seed
    picked, for every event. TTE's only team event is mixed doubles -- a
    two-person mixed squad, i.e. a couple -- and TTE publishes CPLM
    ("Couple, male first"). TKW's mixed TEAM4 is a squad, not a couple, and
    stays ORG.
    """
    tte = build_dataset(RD, "TTE", 1)
    assert tte.teams
    for t in tte.teams:
        assert t.team_type == "CPLM", (
            f"TTE mixed doubles pair {t.code} is a couple, got {t.team_type!r}")

    tkw = build_dataset(RD, "TKW", 1)
    assert tkw.teams
    for t in tkw.teams:
        assert t.team_type == "ORG", (
            f"TKW 4-person squad {t.code} is an organisation, "
            f"got {t.team_type!r}")


def test_team_type_is_stable_across_seeds():
    """It used to move with the seed; it is a property of the event."""
    seen = {t.code: t.team_type for t in build_dataset(RD, "TTE", 1).teams}
    for seed in (2, 7, 99):
        for t in build_dataset(RD, "TTE", seed).teams:
            if t.code in seen:
                assert t.team_type == seen[t.code], (
                    f"{t.code} TeamType changed with the seed: "
                    f"{seen[t.code]!r} -> {t.team_type!r}")
