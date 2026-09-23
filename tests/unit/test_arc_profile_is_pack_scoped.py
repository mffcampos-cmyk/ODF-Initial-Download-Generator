"""The embedded archery profile is real SYOG2026 data and must never appear in
another Games' messages."""
from generator import arc_profile
from generator.dataset import build_dataset
from generator.games import GamesProfile
from generator.refdata import RefData
from tests.conftest import PACK

OTHER = GamesProfile(pack_name="OTHER", label="Other Games",
                     gen="X-GEN-V1.0", codes="X-CC-V1.0",
                     sport_template="X-{disc}-1.0")


def test_arc_uses_the_embedded_participant_profile_under_syog26():
    ds = build_dataset(RefData(PACK), "ARC", 1)
    assert {t.organisation for t in ds.teams} == set(arc_profile.DUAL_NOCS)


def test_arc_falls_back_to_the_codes_engine_under_another_games():
    ds = build_dataset(RefData(PACK, profile=OTHER), "ARC", 1)
    assert {t.organisation for t in ds.teams} != set(arc_profile.DUAL_NOCS)


def test_arc_schedule_is_the_same_codes_model_under_both():
    # The 2025 embedded calendar is retired: only the participant mix is
    # pack-scoped now.
    syog = build_dataset(RefData(PACK), "ARC", 1)
    other = build_dataset(RefData(PACK, profile=OTHER), "ARC", 1)
    assert [u.code for s in syog.sessions for u in s.units] == \
           [u.code for s in other.sessions for u in s.units]
