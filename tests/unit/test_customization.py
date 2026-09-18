"""Message-field and entry-count customization on top of the Overrides system:
per-discipline officials from Common Codes, exact athlete/team counts, and the
'entries match participants' guarantee.
"""
from lxml import etree

from generator.builders import partic
from generator.bundle import build_bundle
from generator.dataset import build_dataset
from generator.overrides import Overrides
from generator.refdata import RefData
from generator.packload import resolve_pack_dir
from tests.conftest import PACK

RD = RefData(PACK, pack_dir=resolve_pack_dir())


def _athletes(ds):
    return [p for p in ds.participants if not p.is_official]


def _officials(ds):
    return [p for p in ds.participants if p.is_official]


def test_officials_use_discipline_function_codes():
    # SWM defines no coach/judge roles (only A and S categories); its officials
    # must use the discipline's own S-category codes, never a generic 'JU'.
    ds = build_dataset(RD, "SWM", 1)
    valid = {f.code for f in RD.discipline_functions("SWM")}
    assert valid
    offs = _officials(ds)
    assert offs
    assert all(p.main_function in valid for p in offs)
    assert "JU" not in {p.main_function for p in offs}


def test_officials_cover_judge_and_team_categories():
    # HBB publishes coach (C), team (T), technical (S) and judge (J) roles.
    ds = build_dataset(RD, "HBB", 1)
    used = {p.main_function for p in _officials(ds)}
    by_cat = {}
    for f in RD.discipline_functions("HBB"):
        by_cat.setdefault(f.category, set()).add(f.code)
    assert used & by_cat.get("J", set())   # at least one judge role
    assert used & by_cat.get("C", set())   # at least one coach role


def test_hard_athlete_count_override():
    ds = build_dataset(RD, "SWM", 1, Overrides(athletes=15))
    assert len(_athletes(ds)) == 15


def test_hard_team_count_override():
    ds = build_dataset(RD, "HBB", 1, Overrides(teams=4))
    assert len(ds.teams) == 4
    athlete_codes = {p.code for p in _athletes(ds)}
    member_codes = {c for t in ds.teams for c in t.member_codes}
    assert member_codes <= athlete_codes  # members reference generated athletes


def test_hard_coach_count_override():
    ds = build_dataset(RD, "HBB", 1, Overrides(coaches=6))
    coach_codes = {f.code for f in RD.discipline_functions("HBB")
                   if f.category == "C"}
    coaches = [p for p in _officials(ds) if p.main_function in coach_codes]
    assert len(coaches) == 6


def test_entries_match_participants_on_override():
    """Everyone entered is a real participant, and every team is entered.

    TKW, not HBB: TKW schedules both individual and team events, so both
    halves of the invariant are exercised. Squad members are represented by
    their team's entry, not entered individually, as on the default path.
    """
    ov = Overrides(athletes=12, teams=3)
    ds = build_dataset(RD, "TKW", 1, ov)
    assert ds.teams, "TKW must produce teams for this invariant to mean anything"
    entered = set()
    for e in ds.entries:
        entered |= set(e.athlete_codes) | set(e.team_codes)
    squad = {c for t in ds.teams for c in t.member_codes}
    individual = {p.code for p in _athletes(ds)} - squad
    expected = individual | {t.code for t in ds.teams}
    assert entered == expected


def test_loose_athletes_are_not_entered_in_a_team_only_discipline():
    """HBB, BK3, BS5, FBS, RU7 and VBV schedule only team events.

    An `athletes=N` override there has no individual event to enter anyone
    into. They are still generated and still appear in DT_PARTIC -- a
    delegation's athlete list is not the same thing as its entry list -- but
    they are entered nowhere.

    This used to look like it worked: all of them went into a single
    discipline-level DT_ENTRIES whose @DocumentCode was the discipline RSC,
    which GEN 2.1.5.2 does not permit. Entering an individual athlete into a
    handball team event would be the wrong fix.
    """
    ds = build_dataset(RD, "HBB", 1, Overrides(athletes=12, teams=3))
    squad = {c for t in ds.teams for c in t.member_codes}
    loose = {p.code for p in _athletes(ds)} - squad
    assert loose, "expected the override to generate loose athletes"

    entered = set()
    for e in ds.entries:
        entered |= set(e.athlete_codes) | set(e.team_codes)
    assert entered == {t.code for t in ds.teams}, \
        "only teams should be entered in a team-only discipline"
    assert not (loose & entered)


def test_status_override_applied_to_participants_and_teams():
    ds = build_dataset(RD, "HBB", 1, Overrides(athletes=8, teams=2, status="ENT"))
    assert all(p.status == "ENT" for p in ds.participants)
    assert all(t.status == "ENT" for t in ds.teams)


def test_header_override_reaches_generated_xml():
    ov = Overrides(competition_code="SYOG2026")
    xml = partic.build(RD, "SWM", 1, overrides=ov)
    root = etree.fromstring(xml)
    assert root.get("CompetitionCode") == "SYOG2026"


def test_blank_counts_keep_discipline_default():
    base = build_dataset(RD, "SWM", 1)
    same = build_dataset(RD, "SWM", 1, Overrides())
    assert len(_athletes(base)) == len(_athletes(same))
    assert len(base.teams) == len(same.teams)


def test_coaches_override_on_coachless_discipline_stays_valid():
    # SWM defines no coach (C) role; a coaches override must not fabricate a
    # 'COACH' code outside the discipline's function set.
    ds = build_dataset(RD, "SWM", 1, Overrides(coaches=5))
    valid = {f.code for f in RD.discipline_functions("SWM")}
    assert all(p.main_function in valid for p in _officials(ds))
    assert "COACH" not in {p.main_function for p in _officials(ds)}


def test_historical_athletes_preserved_with_count_override():
    ds = build_dataset(RD, "SWM", 1,
                       Overrides(athletes=10, historical_athletes=True))
    hist = [p for p in ds.participants if p.status == "HIS"]
    assert hist
    assert all(p.code.startswith("A") for p in hist)
    # historical athletes are never entered
    entered = set()
    for e in ds.entries:
        entered |= set(e.athlete_codes)
    assert not ({p.code for p in hist} & entered)


def test_override_bundle_validates_clean():
    ov = Overrides(athletes=12, teams=3, coaches=5, status="ENT",
                   competition_code="SYOG2026")
    for disc in ("SWM", "HBB", "ARC"):
        bundle = build_bundle(RD, disc, 1, overrides=ov)
        for key, (_xml, errs) in bundle.items():
            assert errs == [], f"{disc}/{key}: {errs[:2]}"
