from lxml import etree
from generator.serialize import el, to_xml


def test_el_drops_empty_and_none_attrs():
    node = el("Team", {"Code": "T1", "Name": "", "TeamType": None, "Org": "  "})
    assert node.get("Code") == "T1"
    assert node.get("Name") is None
    assert node.get("TeamType") is None
    assert node.get("Org") is None


def test_el_drops_none_children_keeps_real_ones():
    parent = el("Competition", {"Gen": "G"}, el("Discipline", {"Code": "ARC"}), None)
    assert len(parent) == 1 and parent[0].tag == "Discipline"


def test_to_xml_has_declaration_and_content():
    root = el("OdfBody", {"DocumentType": "DT_PARTIC"}, el("Competition", {"Gen": "G", "Codes": "C"},
              el("Discipline", {"Code": "ARC"})))
    xml = to_xml(root)
    assert xml.startswith(b"<?xml")
    assert b'DocumentType="DT_PARTIC"' in xml


def test_to_xml_rejects_empty_element():
    root = el("OdfBody", {"DocumentType": "DT_PARTIC"})
    # Manually attach an empty child that el() would normally never create.
    etree.SubElement(root, "Empty")
    try:
        to_xml(root)
        assert False, "expected ValueError for empty element"
    except ValueError:
        pass


def test_to_xml_rejects_empty_attr_on_root():
    root = el("OdfBody", {"DocumentType": "DT_PARTIC"})
    root.set("CompetitionCode", "")  # bypasses el()'s filtering
    try:
        to_xml(root)
        assert False, "expected ValueError for empty attribute on root"
    except ValueError:
        pass
