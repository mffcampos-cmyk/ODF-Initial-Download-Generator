"""The embedded archery profile is real SYOG2026 data and must never appear in
another Games' messages."""
from generator.dataset import build_dataset
from generator.games import GamesProfile
from generator.refdata import RefData
from tests.conftest import PACK

OTHER = GamesProfile(pack_name="OTHER", label="Other Games",
                     gen="X-GEN-V1.0", codes="X-CC-V1.0",
                     sport_template="X-{disc}-1.0")


def test_arc_uses_the_embedded_profile_under_syog26():
    ds = build_dataset(RefData(PACK), "ARC", 1)
    # The embedded profile's real schedule: 9 sessions.
    assert len(ds.sessions) == 9


def test_arc_falls_back_to_the_codes_engine_under_another_games():
    ds = build_dataset(RefData(PACK, profile=OTHER), "ARC", 1)
    assert len(ds.sessions) != 9


def test_the_two_paths_produce_different_schedules():
    syog = build_dataset(RefData(PACK), "ARC", 1)
    other = build_dataset(RefData(PACK, profile=OTHER), "ARC", 1)
    assert [s.session_code for s in syog.sessions] != \
           [s.session_code for s in other.sessions]
