"""Attribute maximum lengths from the Data Dictionary's S(n) column.

Why this exists
---------------
The DD states a maximum length for 90 attributes, and nothing enforces any of
them. The validator has no length primitive (its 13 primitives cover formats,
code membership, presence, uniqueness and emptiness) and the bundled XSDs carry
no ``maxLength`` facet at all. So over-length output validates clean: 19
``Team/@TVTeamName`` values in the committed corpus exceeded S(21), the worst
being "Federal Republic of Germany" at 27 characters against a 21-character
limit.

Why the table is keyed on (element, attribute)
----------------------------------------------
Attribute name alone is not enough. ``Value`` is S(20), S(40) or S(255)
depending on which element carries it, ``Name`` is S(25)/S(35)/S(40)/S(73), and
``Code`` is S(20)/S(34)/S(40). Truncating by attribute name would cut a 34-char
RSC to 20. The validator learned the same lesson from the other direction --
its obligation registry is keyed on (doc_type, element, attribute) because
``Code`` is required on 83 complexTypes.

Why the table is short and hand-written
---------------------------------------
It could be parsed out of the DD Markdown, and an earlier draft of this work
did exactly that. But the DD is converted from PDF, where a nested element's
table can interrupt its parent's, so a parsed row can be attributed to the
wrong element -- the validator drops 279 such rows as provably mis-attributed.
A wrong entry here silently truncates real data. So this lists only pairs that
have been checked against the DD by hand and that the generator actually emits.
Add to it the same way.

What is deliberately NOT here
-----------------------------
``VenueName`` and ``LocationName`` carry no S(n) at all: the DD specifies them
as "CC@VENUE ENG Description (not code)", and active code_membership rules
(JUD_VENUENAME_CODE and its equivalents in HBB, RCB, RU7) require them to equal
the code's description exactly. Truncating one would turn passing output into
failing output. Any attribute whose DD entry names a description rather than a
length belongs in that category -- check before adding.
"""
from __future__ import annotations

# (element, attribute) -> maximum characters, per the SYOG26 GEN DD.
MAX_LENGTHS: dict[tuple[str, str], int] = {
    # GEN DD: "TVTeamName | M | S(21) | TV Team Name".
    ("Team", "TVTeamName"): 21,
    # GEN DD, Competition/Unit/ItemName: "Value | M | S(40) CC@EVENT_UNIT
    # CC@PHASE CC@EVENT ENG Description".
    #
    # This one is a genuine conflict in the source, not an oversight: the same
    # cell demands both a 40-character maximum and the Common Codes
    # description, and Common Codes ships descriptions longer than that
    # ("Women -44 kg Repechage Second Round of 16" is 41). Something has to
    # give. Truncating is safe today because no active rule checks ItemName
    # against the description -- unlike VenueName, which has one. If such a
    # rule ever appears, this entry is the first thing to revisit.
    ("ItemName", "Value"): 40,
}


def clamp(element: str, attribute: str, value: str) -> str:
    """``value`` truncated to the DD limit for this element/attribute pair.

    Plain truncation, no ellipsis: the limit is a field width, and a marker
    would both consume characters and put a character in the data that the
    source never had.
    """
    limit = MAX_LENGTHS.get((element, attribute))
    if limit is None or len(value) <= limit:
        return value
    return value[:limit]
