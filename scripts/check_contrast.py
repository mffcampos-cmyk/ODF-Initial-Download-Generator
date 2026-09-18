"""WCAG AA contrast check for web/static/app.css, both colour modes.

Run after any palette change::

    python scripts/check_contrast.py

It reads the tokens straight out of the stylesheet, so it cannot drift from
what ships. Two habits make it worth having:

* **Check fills against each other, not only against the background.** On the
  validator this caught amber and blue landing at 1.04:1 against one another --
  three bar segments that would have read as a single smear. This page never
  places two signal fills in contact (each manifest lamp is separated by the
  readout ground and labelled in words beside it), so those pairs are checked
  as ``CONTACT_PAIRS`` only where contact is actually possible.
* **Verify your verifier.** Decorative hairlines are deliberately excluded:
  ``--rule`` and ``--readout-line`` never carry meaning on their own, and
  holding them to 3:1 would force a palette that looks like a wireframe. Only
  ``--rule-strong``, which is the sole thing outlining a real control, is held
  to it.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "web" / "static" / "app.css"
TEXT = CSS.read_text(encoding="utf-8")

HEX = re.compile(r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})")
DARK = re.compile(
    r"@media\s*\(prefers-color-scheme:\s*dark\)\s*\{(.*?\n\s*\}\s*)\n\}", re.S
)


def tokens() -> tuple[dict[str, str], dict[str, str]]:
    """The light palette, and the dark palette as an overlay on it."""
    dark_block = DARK.search(TEXT)
    if dark_block is None:
        raise SystemExit("no prefers-color-scheme: dark block in app.css")
    light_text = TEXT[: dark_block.start()] + TEXT[dark_block.end():]
    light = dict(HEX.findall(light_text))
    dark = dict(light)
    dark.update(dict(HEX.findall(dark_block.group(1))))
    return light, dark


def lum(h: str) -> float:
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(palette: dict[str, str], a: str, b: str) -> float:
    l1, l2 = sorted([lum(palette[a]), lum(palette[b])], reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


# (minimum, foreground, background, label) -- 4.5 for normal text, 3.0 for
# large text and for a border that is the only thing defining a control.
CHECKS = [
    (4.5, "--ink", "--ground", "body / ground"),
    (4.5, "--ink", "--panel", "body / panel"),
    (4.5, "--ink", "--panel-sunk", "body / sunk card"),
    (4.5, "--ink-mid", "--panel", "secondary / panel"),
    (4.5, "--ink-mid", "--panel-sunk", "field labels / sunk card"),
    (4.5, "--ink-soft", "--ground", "small-caps labels / ground"),
    (4.5, "--ink-soft", "--panel-sunk", "small-caps labels / sunk card"),
    (4.5, "--ink-soft", "--panel", "gutter numerals / editor"),
    (4.5, "--readout-text", "--readout", "idle text / readout"),
    (4.5, "--readout-ink", "--readout", "driven text / readout"),
    (4.5, "--error", "--ground", "error text / ground"),
    (4.5, "--error", "--panel", "error text / panel"),
    (4.5, "--ink", "--error-tint", "notice body / error tint"),
    (4.5, "--error", "--error-tint", "notice heading / error tint"),
    (4.5, "--panel", "--ink", "primary button label / fill"),
    (3.0, "--rule-strong", "--panel", "control border / panel"),
    (3.0, "--rule-strong", "--panel-sunk", "control border / sunk card"),
    (3.0, "--rule-strong", "--ground", "control border / ground"),
    (3.0, "--error-fill", "--readout", "lamp: error"),
    # --error-fill also paints .mstate-error, the 12px uppercase state text
    # beside that lamp. One token, two jobs, and only the 3:1 lamp job was
    # being checked -- so #e0483a at 3.55:1 passed this suite while failing AA
    # as text for months. Text needs 4.5:1; check the same pair twice rather
    # than trusting the looser threshold to cover both.
    (4.5, "--error-fill", "--readout", "state text: error"),
    (3.0, "--warning-fill", "--readout", "interlock text"),
    (3.0, "--readout-text", "--readout", "lamp: clean"),
    # The selected manifest row. Its indicator is a --readout-ink left edge;
    # WCAG 1.4.11 wants 3:1 for the state of a UI component, and the real
    # radio is visually hidden so there is no native indicator behind it.
    (3.0, "--readout-ink", "--select-wash", "selected row: edge"),
    (4.5, "--readout-ink", "--select-wash", "selected row: text"),
    (4.5, "--readout-ink", "--hover-wash", "hovered row: text"),
]

# Pairs that actually touch. Nothing on this page places two signal fills in
# contact, so this list stays empty by design -- it exists so that adding an
# adjacent-segment device later cannot skip the check.
CONTACT_PAIRS: list[tuple[float, str, str, str]] = []


def main() -> int:
    light, dark = tokens()
    bad = 0
    for mode, palette in (("light", light), ("dark", dark)):
        print(f"--- {mode} ---")
        for need, fg, bg, label in CHECKS + CONTACT_PAIRS:
            missing = [t for t in (fg, bg) if t not in palette]
            if missing:
                print(f"MISS   {'  '.join(missing)}  ({label})")
                bad += 1
                continue
            r = ratio(palette, fg, bg)
            ok = r >= need
            bad += not ok
            print(f"{'PASS' if ok else 'FAIL'}  {r:5.2f} / {need}  {label}")
        print()
    print("FAILURES:", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
