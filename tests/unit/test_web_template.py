"""Markup guarantees for the operator page.

Deliberately pack-free: these read ``web/templates/index.html`` off disk rather
than importing ``api.app``, so they run without the validator's ``Rules/``
folder present. Behaviour of the page's JavaScript is covered separately by
``tests/web/app.test.mjs`` (``npm test``).
"""
from __future__ import annotations
import re
from html.parser import HTMLParser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"
HTML = TEMPLATE.read_text(encoding="utf-8")


class _Tags(HTMLParser):
    """Every start tag with its attributes, in document order."""

    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def _parsed() -> list[tuple[str, dict[str, str | None]]]:
    p = _Tags()
    p.feed(HTML)
    return p.tags


TAGS = _parsed()


def _by_id(el_id: str) -> dict[str, str | None]:
    for _tag, attrs in TAGS:
        if attrs.get("id") == el_id:
            return attrs
    raise AssertionError(f"no element with id={el_id!r} in {TEMPLATE.name}")


def _names(tag: str) -> list[dict[str, str | None]]:
    return [attrs for name, attrs in TAGS if name == tag]


# --- already-correct behaviour, guarded against regression -----------------

def test_doctype_is_first_line():
    assert HTML.lstrip().lower().startswith("<!doctype html>")


def test_charset_is_the_first_element_in_head():
    metas = [a for t, a in TAGS if t == "meta"]
    assert metas, "no meta elements"
    assert "charset" in metas[0], "charset must be the first meta in <head>"
    assert metas[0]["charset"].lower() == "utf-8"


def test_html_declares_a_language():
    html_attrs = _names("html")[0]
    assert html_attrs.get("lang") == "en"


def test_every_id_is_unique():
    ids = [a["id"] for _t, a in TAGS if a.get("id")]
    assert len(ids) == len(set(ids)), f"duplicate ids: {sorted({i for i in ids if ids.count(i) > 1})}"


def test_every_form_control_has_a_label():
    """Each control is either wrapped in a <label> or referenced by label[for]."""
    labelled_for = {a["for"] for a in _names("label") if a.get("for")}
    control_ids = [
        a["id"] for t, a in TAGS
        if t in {"input", "select", "textarea"} and a.get("id")
    ]
    for cid in control_ids:
        wrapped = re.search(
            rf"<label[^>]*>(?:(?!</label>).)*id=\"{re.escape(cid)}\"",
            HTML, re.S,
        )
        assert wrapped or cid in labelled_for, f"control #{cid} has no label"


# --- finding #2: viewport ---------------------------------------------------

def test_viewport_meta_is_present():
    viewport = [a for t, a in TAGS if t == "meta" and a.get("name") == "viewport"]
    assert viewport, "missing <meta name=viewport>"
    assert "width=device-width" in viewport[0]["content"]


def test_viewport_does_not_block_pinch_zoom():
    viewport = [a for t, a in TAGS if t == "meta" and a.get("name") == "viewport"][0]
    content = viewport["content"].replace(" ", "")
    assert "user-scalable=no" not in content
    assert "maximum-scale=1" not in content


# --- finding #5: live regions ----------------------------------------------

def test_status_line_is_a_live_region():
    status = _by_id("status")
    assert status.get("role") == "status"
    assert status.get("aria-live") == "polite"


def test_output_region_is_named_and_reachable_but_not_announced():
    """The status line announces the outcome; the output itself must not.

    A live region on #out would make a screen reader read an entire generated
    ODF bundle aloud on every click. Instead it is a named, focusable region
    the user can navigate to deliberately.
    """
    out = _by_id("out")
    assert out.get("aria-live") in (None, "off")
    assert out.get("aria-label") or out.get("aria-labelledby")
    assert out.get("tabindex") == "0", "#out scrolls, so it must be keyboard reachable"
    assert out.get("role") == "region"


def test_error_panels_are_alerts():
    for panel in ("default-error", "notready"):
        assert _by_id(panel).get("role") == "alert", f"#{panel} is not an alert"


def test_hidden_panels_use_the_hidden_attribute_not_inline_display():
    for panel in ("default-error", "notready"):
        attrs = _by_id(panel)
        assert "hidden" in attrs, f"#{panel} should start hidden via the hidden attribute"
        assert "display:none" not in (attrs.get("style") or "").replace(" ", "")


# --- finding #7: semantics --------------------------------------------------

def test_there_is_exactly_one_main_landmark():
    assert len(_names("main")) == 1


def test_controls_live_in_a_real_form():
    assert _names("form"), "controls should be wrapped in a <form>"


def test_generate_submits_the_form_and_save_does_not():
    assert _by_id("go").get("type") == "submit"
    assert _by_id("save").get("type") == "button"


def test_count_inputs_are_numeric_and_non_negative():
    for field in ("athletes", "teams", "coaches"):
        attrs = _by_id(field)
        assert attrs.get("type") == "number"
        assert attrs.get("min") == "0"
        assert attrs.get("step") == "1"


def test_code_fields_opt_out_of_autofill_and_spellcheck():
    for field in ("competition_code", "source", "gen", "sport", "codes", "status_ov"):
        attrs = _by_id(field)
        assert attrs.get("autocomplete") == "off", f"#{field} should disable autofill"
        assert attrs.get("spellcheck") == "false", f"#{field} should disable spellcheck"


# --- finding #9: no inline script or style ---------------------------------

def test_no_inline_style_attributes():
    styled = [(t, a["style"]) for t, a in TAGS if a.get("style")]
    assert not styled, f"inline style attributes remain: {styled}"


def test_stylesheet_is_external():
    links = [a for t, a in TAGS if t == "link" and (a.get("rel") or "") == "stylesheet"]
    assert links, "no external stylesheet linked"
    assert links[0]["href"].endswith("app.css")


def test_script_is_external_and_deferred():
    scripts = _names("script")
    assert scripts, "no script tag"
    for s in scripts:
        assert s.get("src"), "inline <script> blocks should live in web/static/app.js"
    assert any(
        s["src"].endswith("app.js") and (s.get("type") == "module" or "defer" in s)
        for s in scripts
    ), "app.js must not block parsing (type=module or defer)"


def test_template_contains_no_inline_javascript_body():
    body = re.search(r"<script[^>]*>(.*?)</script>", HTML, re.S)
    assert body is None or not body.group(1).strip(), "script tags must be empty"


def test_template_never_builds_dom_from_strings():
    assert "innerHTML" not in HTML


# --- finding #10: noscript --------------------------------------------------

def test_a_noscript_fallback_explains_the_page_needs_javascript():
    assert _names("noscript"), "no <noscript> fallback"
    text = re.search(r"<noscript>(.*?)</noscript>", HTML, re.S).group(1)
    assert re.search(r"javascript", text, re.I)


# --- finding #8: output must not force horizontal page scroll --------------

def test_stylesheet_wraps_the_output_block():
    css = (PROJECT_ROOT / "web" / "static" / "app.css").read_text(encoding="utf-8")
    rule = re.search(r"#out\s*\{([^}]*)\}", css, re.S)
    assert rule, "no #out rule in app.css"
    assert "pre-wrap" in rule.group(1), "#out must wrap long XML lines"


def test_victory_ceremonies_checkbox_is_gone():
    """Ceremonies are always scheduled (spec §4); a checkbox that does nothing
    would mislead."""
    html = TEMPLATE.read_text(encoding="utf-8")
    assert 'id="victory_ceremonies"' not in html
    js = (PROJECT_ROOT / "web" / "static" / "app.js").read_text(encoding="utf-8")
    assert '"victory_ceremonies"' not in js
