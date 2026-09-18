from __future__ import annotations
from lxml import etree

from .lengths import clamp


def el(tag: str, attrs: dict, *children):
    node = etree.Element(tag)
    for k, v in attrs.items():
        if v is None:
            continue
        s = str(v)
        if s.strip() == "":
            continue
        # Enforce the DD's S(n) maximum here, at the single place every
        # attribute in every message is set. Doing it at each call site would
        # mean remembering it at each call site.
        node.set(k, clamp(tag, k, s))
    for child in children:
        if child is None:
            continue
        node.append(child)
    return node


def _is_empty(node) -> bool:
    has_text = node.text is not None and node.text.strip() != ""
    return not node.attrib and len(node) == 0 and not has_text


def to_xml(root) -> bytes:
    for node in root.iter("*"):
        if _is_empty(node):
            raise ValueError(f"empty element <{node.tag}> would be serialized")
        for k, v in node.attrib.items():
            if v is None or str(v).strip() == "":
                raise ValueError(f"empty attribute @{k} on <{node.tag}>")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
