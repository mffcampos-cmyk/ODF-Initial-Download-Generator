"""Generated output against the Data Dictionaries' M/O obligations.

The validator resolves obligations across DD -> GEN DD -> XSD and exposes two
sets: everything a DD marks mandatory, and the subset it is willing to ENFORCE
(`enforceable_only=True`), which is the pairs the schema proves unambiguous
minus the ones the schema already requires.

Those two sets are very far apart here, and the gap is not a gap in the output:

- The enforceable set is EMPTY for every message this project builds, so
  CORE_DD_MANDATORY_ATTR cannot fire on generated output at all. That is why
  the stricter engine cost this project nothing.
- The wider set asks for 63 pairs, and every attribute it finds absent sits on
  an element called <Description> -- which the schema maps to 13 different
  complexTypes. A DT_ENTRIES message contains two of them: Entry/Description
  (a team entry: @TeamName) and Athlete/Description (a person: @FamilyName,
  @Gender, @Organisation, ...). The DD's obligations for both arrive under the
  one name, so the wide set simultaneously demands @TeamName of every athlete
  and @FamilyName of every team.

So obligations are read here as a CHECK, never as a filler. Emitting the wide
set would put a team name on 2,458 athletes and a family name on 193 teams --
output that looks plausible and is wrong, which is the failure mode both
projects have already paid for once.
"""
from __future__ import annotations

from lxml import etree

from generator.bundle import build_bundle
from generator.obligations import Omission, message_omissions
from generator.refdata import RefData
from odf_validator.dispatch import dispatch
from tests.conftest import PACK, REFUSED_DISCIPLINES

RD = RefData(PACK)

# Every (parent, element, attribute) the wide DD set reports absent from
# generated output, asserted exactly. Each one is the <Description> ambiguity
# described above, not a missing attribute: a new entry here means either the
# builders stopped emitting something, or a re-ingested DD started attributing
# a row to a different element.
KNOWN_AMBIGUOUS = {
    ("Athlete", "Description", "Nationality"),
    ("Athlete", "Description", "TeamName"),
    ("Entry", "Description", "FamilyName"),
    ("Entry", "Description", "Gender"),
    ("Entry", "Description", "Nationality"),
    ("Entry", "Description", "Organisation"),
}


def _sweep():
    """(enforceable, ambiguous) omissions across every buildable discipline."""
    enforceable: list[Omission] = []
    ambiguous: set[tuple[str, str, str]] = set()
    for disc in sorted(PACK.disciplines):
        if disc in REFUSED_DISCIPLINES:
            continue
        for _key, (xml, _errs) in build_bundle(RD, disc, seed=1).items():
            for om in message_omissions(xml, PACK):
                if om.enforceable:
                    enforceable.append(om)
                else:
                    ambiguous.add((om.parent, om.element, om.attribute))
    return enforceable, ambiguous


ENFORCEABLE, AMBIGUOUS = _sweep()


def test_no_enforceable_obligation_is_omitted():
    """The set the validator will actually report on must stay empty.

    This is the guard the pin in the README rests on: it fails the moment a
    builder stops emitting an attribute a DD requires and the schema does not.
    """
    assert ENFORCEABLE == [], \
        f"builders omit attributes the engine would report: {ENFORCEABLE[:5]}"


def test_the_wide_set_finds_only_the_known_description_ambiguity():
    assert AMBIGUOUS == KNOWN_AMBIGUOUS, (
        "the wide DD set reports something new as absent; check whether the "
        "builders changed or a re-ingested DD moved a row.\n"
        f"unexpected: {sorted(AMBIGUOUS - KNOWN_AMBIGUOUS)}\n"
        f"no longer seen: {sorted(KNOWN_AMBIGUOUS - AMBIGUOUS)}")


def test_an_omission_is_reported_with_the_parent_that_disambiguates_it():
    """Element name alone cannot identify which <Description> is meant, so the
    report carries the parent tag. Without it the two rows above are one line."""
    parents = {p for p, _e, _a in AMBIGUOUS}
    assert parents == {"Athlete", "Entry"}, \
        "the ambiguity is between these two parents; the report must show which"


def test_a_real_omission_is_detected():
    """Strip an attribute the DD requires and check the sweep would catch it.

    Guards the check itself: a checker that never reports anything would pass
    both tests above.
    """
    xml = next(iter(build_bundle(RD, "ARC", seed=1).values()))[0]
    root = etree.fromstring(xml)
    info = dispatch(root)
    wide = PACK.obligations.mandatory_attrs(info.discipline, info.doc_type,
                                            enforceable_only=False)
    victim = None
    for element, attribute in sorted(wide):
        for node in root.iter(element):
            if node.get(attribute) is not None:
                del node.attrib[attribute]
                victim = (element, attribute)
                break
        if victim:
            break
    assert victim, "no DD-mandatory attribute was present to remove"

    found = message_omissions(etree.tostring(root), PACK)
    assert any((om.element, om.attribute) == victim for om in found), \
        f"removing {victim} was not reported"
