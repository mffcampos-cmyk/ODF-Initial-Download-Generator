from generator.dataset import build_dataset
from generator.refdata import RefData
from tests.conftest import PACK


def rd():
    return RefData(PACK)


def test_dataset_is_deterministic_for_a_seed():
    a = build_dataset(rd(), "ARC", seed=7)
    b = build_dataset(rd(), "ARC", seed=7)
    assert [p.code for p in a.participants] == [p.code for p in b.participants]


def test_dataset_has_participants_and_sessions():
    ds = build_dataset(rd(), "ARC", seed=1)
    assert ds.discipline == "ARC"
    assert len(ds.participants) >= 4
    assert len(ds.sessions) >= 1 and len(ds.sessions[0].units) >= 1


def test_team_members_reference_real_participants():
    ds = build_dataset(rd(), "ARC", seed=1)
    athletes = {p.code for p in ds.participants if not p.is_official}
    for team in ds.teams:
        for code in team.member_codes:
            assert code in athletes
