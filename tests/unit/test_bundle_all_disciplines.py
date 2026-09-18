from generator.bundle import build_bundle, DOC_TYPES
from generator.eventstructure import UnknownSquadSize
from generator.refdata import RefData
from tests.conftest import PACK, REFUSED_DISCIPLINES


def test_bundle_covers_four_doc_types():
    assert set(DOC_TYPES) == {"DT_PARTIC", "DT_PARTIC_TEAMS", "DT_ENTRIES", "DT_SCHEDULE"}


def test_bundle_is_clean_for_every_discipline():
    rd = RefData(PACK)
    failures = []
    for disc in rd.disciplines():
        if disc in REFUSED_DISCIPLINES:
            continue
        bundle = build_bundle(rd, disc, seed=1)
        for doc_type, (xml, errs) in bundle.items():
            if errs:
                failures.append(f"{disc}/{doc_type}: {errs[:3]}")
    assert not failures, "un-clean messages:\n" + "\n".join(failures)


def test_refused_disciplines_are_exactly_the_known_set():
    """Pins the skip list above, in both directions.

    A discipline that starts refusing would otherwise be silently skipped by
    every sweeping test; one that stops refusing should drop off the list
    rather than linger as a permanent exemption.
    """
    rd = RefData(PACK)
    refused = set()
    for disc in rd.disciplines():
        try:
            build_bundle(rd, disc, seed=1)
        except UnknownSquadSize:
            refused.add(disc)
    assert refused == REFUSED_DISCIPLINES, (
        f"refusal set changed: now {sorted(refused)}, "
        f"expected {sorted(REFUSED_DISCIPLINES)}")
