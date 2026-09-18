from generator.overrides import Overrides


def test_blank_strings_normalize_to_none():
    o = Overrides(competition_code="  ", source="", gen="OWG").normalize()
    assert o.competition_code is None
    assert o.source is None
    assert o.gen == "OWG"


def test_negative_counts_drop_to_none():
    o = Overrides(athletes=-1, teams=0, coaches=5).normalize()
    assert o.athletes is None
    assert o.teams == 0
    assert o.coaches == 5


def test_is_empty_true_when_all_none():
    assert Overrides().is_empty() is True
    assert Overrides(status="ENT").is_empty() is False
