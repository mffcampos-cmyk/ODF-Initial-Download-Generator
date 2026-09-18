"""Check generated messages against the Data Dictionaries' M/O obligations.

A layer in front of the builders, reading `pack.obligations` -- the registry
the validator builds from every discipline Data Dictionary, the GEN DD and the
XSD, cached per ruleset in `.dd_obligations.json`.

## Why this reports and does not fill

The obvious use of an obligation registry in a generator is to emit what it
asks for. That does not survive contact with the data.

Obligations are keyed on (doc_type, element, attribute), and an element NAME is
not an element. `<Description>` maps to 13 complexTypes in odf2-structure.xsd,
and a DT_ENTRIES message contains two of them:

    Entry/Description            @TeamName                  (a team entry)
    Athlete/Description          @FamilyName @Gender ...    (a person)

Both sets of obligations arrive under the single key ("DT_ENTRIES",
"Description", ...), so the wide set demands @TeamName of every athlete and
@FamilyName of every team at the same time. Emitting it across the 24
buildable disciplines would put a team name on 2,458 athletes and a person's
family name on 193 teams -- plausible-looking, wrong, and invisible to the
validator, because no rule checks whether an attribute BELONGS on the element
carrying it.

The validator solves this for enforcement by narrowing to pairs the schema
proves unambiguous (`enforceable_only=True`). Measured on this project's
output that subset is empty: for DT_PARTIC, DT_PARTIC_TEAMS, DT_ENTRIES and
DT_SCHEDULE there is no pair the DDs require, the schema declares
unambiguously, and the schema does not already require. So there is nothing an
emitter could safely add -- and correspondingly nothing for
CORE_DD_MANDATORY_ATTR to report on generated output.

What is left worth doing is the check: keep the enforceable set empty of
omissions (it is the pin the README's known-good claim rests on), and report
the wide set's residue with the parent tag that tells the two Descriptions
apart, so a genuine omission can be recognised among the ambiguity rather than
drowned in it.
"""
from __future__ import annotations

from dataclasses import dataclass

from lxml import etree

from odf_validator.dispatch import dispatch


@dataclass(frozen=True)
class Omission:
    """An attribute a Data Dictionary marks mandatory, absent from a node.

    `parent` is the parent element's tag. It is not decoration: it is the only
    thing in the message that separates two elements sharing a name, and
    without it a report cannot say which <Description> it means.

    `enforceable` mirrors the validator's own restriction -- True when the
    engine would report this as CORE_DD_MANDATORY_ATTR, False when the pair
    survives only in the wider, ambiguity-prone set.

    `code` is set for a conditional obligation, which a DD states only for
    nodes carrying a particular @Code.
    """
    element: str
    attribute: str
    parent: str
    path: str
    enforceable: bool
    code: str | None = None


def _parent_tag(node) -> str:
    parent = node.getparent()
    return parent.tag if parent is not None else "-"


def message_omissions(xml: bytes | str, pack) -> list[Omission]:
    """Every DD-mandatory attribute absent from one message.

    Returns both the enforceable and the wider set; callers separate them on
    `Omission.enforceable`. A pack without an obligation registry, or a message
    that does not parse, yields nothing -- this is a report, never a gate.
    """
    obligations = getattr(pack, "obligations", None)
    if obligations is None:
        return []
    if isinstance(xml, str):
        xml = xml.encode("utf-8")
    try:
        root = etree.fromstring(xml)
    except etree.XMLSyntaxError:
        return []

    info = dispatch(root)
    tree = root.getroottree()
    wide = obligations.mandatory_attrs(info.discipline, info.doc_type,
                                       enforceable_only=False)
    narrow = obligations.mandatory_attrs(info.discipline, info.doc_type,
                                         enforceable_only=True)
    conditional = obligations.conditional_mandatory_attrs(
        info.discipline, info.doc_type, enforceable_only=False)
    conditional_narrow = obligations.conditional_mandatory_attrs(
        info.discipline, info.doc_type, enforceable_only=True)

    out: list[Omission] = []
    for element, attribute in sorted(wide):
        for node in root.iter(element):
            if node.get(attribute) is None:
                out.append(Omission(
                    element=element, attribute=attribute,
                    parent=_parent_tag(node), path=tree.getpath(node),
                    enforceable=(element, attribute) in narrow))

    for (element, attribute), codes in sorted(conditional.items()):
        for node in root.iter(element):
            # A node whose @Code the DD does not name is governed by a
            # different attribute table, or by none: say nothing about it.
            code = node.get("Code")
            if code not in codes or node.get(attribute) is not None:
                continue
            out.append(Omission(
                element=element, attribute=attribute,
                parent=_parent_tag(node), path=tree.getpath(node),
                enforceable=(element, attribute) in conditional_narrow,
                code=code))
    return out


def bundle_omissions(bundle, pack) -> dict[str, list[Omission]]:
    """`{message key: omissions}`, empty entries dropped."""
    found = {key: message_omissions(xml, pack)
             for key, (xml, _errs) in bundle.items()}
    return {key: oms for key, oms in found.items() if oms}


def summarise(omissions) -> list[str]:
    """One line per (parent, element, attribute), most frequent first."""
    counts: dict[tuple[str, str, str, bool], int] = {}
    for om in omissions:
        key = (om.parent, om.element, om.attribute, om.enforceable)
        counts[key] = counts.get(key, 0) + 1
    lines = []
    for (parent, element, attribute, enforceable), n in sorted(
            counts.items(), key=lambda kv: (-kv[1], kv[0])):
        tag = "ENFORCEABLE" if enforceable else "ambiguous  "
        lines.append(f"{tag} {n:6}  <{parent}>/<{element}> @{attribute}")
    return lines


def _main(argv=None) -> int:
    """`python -m generator.obligations [DISCIPLINE ...]`

    Reports what the Data Dictionaries require and the builders do not emit.
    Exits 1 only on an ENFORCEABLE omission -- the ambiguous residue is
    expected and is printed for reading, not for failing a build.
    """
    import argparse

    from .bundle import build_bundle
    from .packload import load_refdata

    parser = argparse.ArgumentParser(description=_main.__doc__)
    parser.add_argument("disciplines", nargs="*",
                        help="default: every buildable discipline")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--pack-dir", default=None)
    args = parser.parse_args(argv)

    refdata = load_refdata(args.pack_dir)
    names = args.disciplines or sorted(refdata.pack.disciplines)
    enforceable = 0
    for name in names:
        try:
            bundle = build_bundle(refdata, name, seed=args.seed)
        except Exception as e:                                  # noqa: BLE001
            print(f"{name}: not built -- {type(e).__name__}: {e}")
            continue
        flat = [om for oms in bundle_omissions(bundle, refdata.pack).values()
                for om in oms]
        enforceable += sum(1 for om in flat if om.enforceable)
        print(f"{name}:")
        for line in (summarise(flat) or ["  none"]):
            print(f"  {line}")
    return 1 if enforceable else 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(_main())
