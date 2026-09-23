from __future__ import annotations
from odf_validator.context import ValidationContext

from .builders import partic, partic_teams, entries, schedule
from .selfcheck import errors as check_errors

DOC_TYPES = {
    "DT_PARTIC": partic.build,
    "DT_PARTIC_TEAMS": partic_teams.build,
    "DT_ENTRIES": entries.build_all,
    "DT_SCHEDULE": schedule.build,
}


def _entries_key(event_rsc: str) -> str:
    return f"DT_ENTRIES_{event_rsc.rstrip('-')}"


class Bundle(dict):
    """``{key: (xml, errors)}`` plus which seed actually produced it.

    A dict subclass rather than a tuple return, so every existing caller that
    iterates ``.items()`` keeps working.

    ``seed_used`` exists because the retry loop below is free to walk away
    from the seed it was asked for: if seed 1 yields a message with findings
    it tries 2, 3, 4, 5 and returns whichever it got. That is reasonable
    behaviour and it was completely silent -- the caller asked for seed 1, was
    told nothing, and got seed 5's data for every message in the bundle. Since
    generation is seed-deterministic, reproducing a bundle requires knowing
    the seed that made it.
    """

    def __init__(self, *args, seed_used: int, clean: bool, **kwargs):
        super().__init__(*args, **kwargs)
        self.seed_used = seed_used
        self.clean = clean

    @property
    def errors(self) -> dict[str, list]:
        """Residual findings per message key; empty when the bundle is clean."""
        return {k: errs for k, (_xml, errs) in self.items() if errs}


def build_bundle(refdata, discipline: str, seed: int, max_retries: int = 5,
                 overrides=None):
    # Only disciplines whose Common Codes schedule team events get a
    # DT_PARTIC_TEAMS message (ARC's embedded profile also has teams; its
    # codes-scheduled XTEAM2 units make has_team_events true as well).
    doc_types = dict(DOC_TYPES)

    candidate_seeds = [seed + i for i in range(max_retries)]
    last_attempt: dict = {}
    last_seed = seed
    for s in candidate_seeds:
        attempt = {}
        all_clean = True
        # One attempt is one batch. The messages below ship together, so they
        # are validated together: a shared context is what lets the engine's
        # cross_message rules compare them (a participant entered in
        # DT_ENTRIES against DT_PARTIC, an event RSC against DT_SCHEDULE).
        # Without it those rules return nothing and the bundle is only ever
        # checked message by message.
        #
        # Built fresh per seed, inside the loop. The retry below is free to
        # walk away from an attempt; a context outliving that attempt would
        # compare the next seed's messages against values from a bundle
        # nobody will ever see.
        ctx = ValidationContext()
        # DOC_TYPES is ordered so the messages that DEFINE things come before
        # the ones that reference them -- DT_PARTIC before DT_ENTRIES. A
        # cross_message rule remembers the first value it meets and compares
        # the rest against it, so this order decides which message a
        # discrepancy is reported against.
        for doc_type, build_fn in doc_types.items():
            if doc_type == "DT_ENTRIES":
                # DT_ENTRIES is a per-event message (DocumentCode = Event RSC)
                for event_rsc, xml in build_fn(refdata, discipline, s,
                                               overrides=overrides):
                    errs = check_errors(xml, refdata.pack, ctx)
                    attempt[_entries_key(event_rsc)] = (xml, errs)
                    if errs:
                        all_clean = False
                continue
            xml = build_fn(refdata, discipline, s, overrides=overrides)
            errs = check_errors(xml, refdata.pack, ctx)
            attempt[doc_type] = (xml, errs)
            if errs:
                all_clean = False
        last_attempt = attempt
        last_seed = s
        if all_clean:
            return Bundle(attempt, seed_used=s, clean=True)
    # Every candidate seed still had findings. Return the last attempt, but
    # say so: callers that must not ship dirty output (export_bundle, the zip
    # endpoint) check this rather than re-deriving it.
    return Bundle(last_attempt, seed_used=last_seed, clean=False)
