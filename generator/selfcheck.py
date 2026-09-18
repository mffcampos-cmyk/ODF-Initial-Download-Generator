from __future__ import annotations
from odf_validator.pipeline.orchestrator import Pipeline

_PIPELINE = Pipeline()


def errors(xml: bytes, pack, ctx=None) -> list[str]:
    """Error-severity findings for one message.

    `ctx` is a validator ValidationContext shared across the messages of one
    batch. Without it the engine's `cross_message` primitive returns nothing
    at all -- by design, so that validating a single file does not flag every
    value it cannot compare with anything. A generated bundle IS a batch, so
    passing one is what lets those rules see it; see bundle.build_bundle.
    """
    result = _PIPELINE.run(xml, pack, ctx)
    return [f"{f.rule_id}: {f.message}"
            for f in result.findings if f.severity.value == "error"]


def generate_clean(make_xml, pack, seeds: list[int]):
    """Retry `make_xml` across seeds until one message validates clean.

    Deliberately context-free: the candidates here are alternative versions of
    the SAME message, not the members of a batch. Remembering one seed's
    values and comparing the next seed's against them would report a conflict
    between two messages that never ship together.
    """
    last_xml = b""
    last_errs: list[str] = ["no seeds provided"]
    for seed in seeds:
        xml = make_xml(seed)
        errs = errors(xml, pack)
        if not errs:
            return xml, []
        last_xml, last_errs = xml, errs
    return last_xml, last_errs
