from generator.selfcheck import errors, generate_clean
from tests.conftest import PACK

CLEAN = (b'<?xml version="1.0" encoding="UTF-8"?>'
         b'<OdfBody CompetitionCode="X" DocumentCode="D" DocumentType="DT_PARTIC" '
         b'Version="1" FeedFlag="P" Date="2026-01-01" Time="000000000" '
         b'LogicalDate="2026-01-01" Source="S"><Competition Gen="G" Codes="C">'
         b'<Discipline Code="ARC"/></Competition></OdfBody>')


def test_errors_returns_list_of_strings():
    result = errors(CLEAN, PACK)
    assert isinstance(result, list)
    assert all(isinstance(s, str) for s in result)


def test_generate_clean_returns_first_clean():
    calls = []

    def make(seed):
        calls.append(seed)
        # Only seed 2 yields a message with valid codes.
        good = seed == 2
        if good:
            return (b'<?xml version="1.0"?><OdfBody CompetitionCode="SYOG2026" '
                    b'DocumentCode="ARC0000000000000000000000000000000" '
                    b'DocumentType="DT_PARTIC" Version="1" FeedFlag="P" '
                    b'Date="2026-01-01" Time="000000000" LogicalDate="2026-01-01" '
                    b'Source="S"><Competition Gen="G" Codes="C">'
                    b'<Discipline Code="ARC-------------------------------">'
                    b'<Event Code="ARCG------------------------------"><Medal Code="ME_GOLD"/></Event>'
                    b'</Discipline></Competition></OdfBody>')
        else:
            # Bad: empty CompetitionCode
            return (b'<?xml version="1.0"?><OdfBody CompetitionCode="" '
                    b'DocumentCode="ARC0000000000000000000000000000000" '
                    b'DocumentType="DT_PARTIC" Version="1" FeedFlag="P" '
                    b'Date="2026-01-01" Time="000000000" LogicalDate="2026-01-01" '
                    b'Source="S"><Competition Gen="G" Codes="C"><Discipline Code="ARC"/>'
                    b'</Competition></OdfBody>')

    xml, findings = generate_clean(make, PACK, seeds=[1, 2, 3])
    # It should stop at the first clean seed and not try seed 3.
    assert 3 not in calls
