"""The README quotes measured figures. This measures them again.

Every number here was true of Common Codes v1.9.1 and quietly stopped being
true at v_2_3: the count of over-length EVENT_UNIT descriptions, the collision
groups truncation creates, and how many disciplines publish a coach role. The
worst of them understated the repository's headline trade-off by 44%, and
nothing would ever have said so -- prose does not fail a test suite.

So these are the numbers, derived from whatever pack is imported, asserted
against the README's own words. When the IOC publishes new Common Codes the
suite goes red with the new figure in the message, and updating the sentence
is a one-line edit rather than an archaeology exercise.

Deliberately NOT a test of the generator: it tests the documentation. A README
that has to stay true is worth more than one that was true once.
"""
import collections
import re
from pathlib import Path

import pytest

from generator.packload import PROJECT_ROOT
from tests.conftest import PACK

# Whitespace-normalised: the README is hard-wrapped, and a sentence that
# happens to break across two lines is still the sentence. Matching the raw
# text would make these tests fail on a reflow, which teaches people to
# distrust them.
README = " ".join((PROJECT_ROOT / "README.md")
                  .read_text(encoding="utf-8").split())
LIMIT = 40  # the S(40) the DD states for Unit/ItemName/@Value


def _descriptions():
    table = PACK.codes.table("EVENT_UNIT")
    return [(row.id, row.fields.get("ENG_Description") or "")
            for row in table._rows.values()]


def _assert_in_readme(needle, what):
    assert needle in README, (
        f"the README no longer states the measured {what}.\n"
        f"  expected to find: {needle!r}\n"
        f"Update the sentence; the measurement is the authority, not the prose.")


def test_over_length_event_unit_descriptions():
    rows = _descriptions()
    over = [(c, d) for c, d in rows if len(d) > LIMIT]
    _assert_in_readme(f"{len(over)} of the {len(rows):,} `EVENT_UNIT` descriptions",
                      "count of over-length EVENT_UNIT descriptions")


def test_over_length_breakdown_by_discipline():
    over = [c for c, d in _descriptions() if len(d) > LIMIT]
    counts = collections.Counter(c[:3] for c in over)
    listed = ", ".join(f"{disc} {n}" for disc, n
                       in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
    _assert_in_readme(f"({listed})", "per-discipline breakdown")


def test_truncation_collisions():
    groups = collections.defaultdict(list)
    for code, d in _descriptions():
        if len(d) > LIMIT:
            groups[d[:LIMIT]].append(code)
    collided = {k: v for k, v in groups.items() if len(v) > 1}
    codes = sum(len(v) for v in collided.values())
    _assert_in_readme(f"Truncation collapses {len(collided)}", "collision-group count")
    _assert_in_readme(f"description groups covering {codes} unit codes",
                      "count of codes merged by truncation")


def _function_categories():
    by_discipline = collections.defaultdict(set)
    for row in PACK.codes.table("DISCIPLINE_FUNCTION")._rows.values():
        disc = (row.fields.get("Discipline") or "").strip()[:3]
        if disc:
            by_discipline[disc].add((row.fields.get("Category") or "").strip())
    return by_discipline


def test_disciplines_publishing_no_coach_role():
    by_discipline = _function_categories()
    known = set(PACK.disciplines)
    with_coach = sorted(d for d in known if "C" in by_discipline.get(d, set()))
    _assert_in_readme(f"{len(known) - len(with_coach)} of the {len(known)}",
                      "count of disciplines with no coach role")
    _assert_in_readme(", ".join(with_coach[:-1]) + f" and {with_coach[-1]} define one",
                      "list of disciplines that do define a coach role")


def test_disciplines_publishing_no_officials_at_all():
    by_discipline = _function_categories()
    none = sorted(d for d in PACK.disciplines if d not in by_discipline)
    _assert_in_readme(", ".join(none[:-1]) + f" and {none[-1]} define no officials",
                      "list of disciplines with no officials")
