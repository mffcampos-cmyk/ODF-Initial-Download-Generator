from tests.conftest import PACK


def test_pack_has_active_schema():
    assert PACK.schema is not None, "XSD must compile for guaranteed structural compliance"


def test_pack_lists_disciplines():
    assert isinstance(PACK.disciplines, list) and len(PACK.disciplines) > 0


def test_discipline_and_competition_tables_present():
    assert PACK.codes.table("DISCIPLINE") is not None
    assert PACK.codes.table("COMPETITION_CODE") is not None
