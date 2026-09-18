# Generator restyle — decisions

Applies `docs/design-handoff-2026-08-06.md` to `web/`. This file records the
choices the handoff asked to be made deliberately, so the next pass can break
them knowingly.

## The signature: a bundle manifest, not a tally rail

The validator's verdict is *how wrong is this message*, so its hero is a
severity rail. The generator has no severities. Its verdict is *what came out
and did it self-check*, so the hero is a manifest: a dark recessed readout with
one row per document type, and — per §1.2 — the biggest thing on the page is
also its main control. Selecting a row scopes `#out` to that document.

Three decisions inside it:

- **The row numeral is lines, not messages.** `/api/generate` returns exactly
  one document per type, so a message count would read `1` on every row and
  tell the operator nothing. Lines is true, varies meaningfully between
  disciplines, and is the same number the gutter below is printing.
- **The last row is the total *and* the "all documents" scope.** One element,
  because the total and the unscoped view are the same idea.
- **Colour is never the only channel.** Every lamp has its state in words
  beside it (`clean` / `2 errors`), so the readout survives a colour vision
  deficiency and a monochrome screenshot.

## Dark mode: kept

Handoff §3.4 required this to be a choice. It is kept, and dark values are
authored for `--ground`, `--panel`, `--panel-sunk`, `--ink*`, `--rule*` and the
readout. Two things do not survive as-is:

- The bare signal colours move to lighter siblings (`--error: #ef6a5c`). `#c0261b`
  on a dark ground is a smudge, not a verdict.
- The tints are re-authored dark; the `-fill` values are unchanged, because they
  were always designed to sit on a dark readout.

`--readout` stays the darkest surface on the page in both modes, so it still
reads as recessed rather than as just another panel.

## Not-ready is an interlock, not an error

A pack that cannot generate is a normal setup step. It renders in the readout's
own idiom — dark recess, amber eyebrow, the reasons in monospace because they
are paths. It keeps `role="alert"`, because it does appear in response to the
operator's choice of Games.

Those reason strings contain literal `<PACK>` and `<CODE>`, so they are still
built with `createElement` + `textContent` (audit finding #1).

## States said out loud (§2.5)

| State | What it says |
|---|---|
| Idle | "Not run yet. Choose a Games and a discipline, then Generate." The readout is visibly unlit rather than absent. |
| Clean pass | "Self-check clean. All 4 documents pass SYOG26." |
| Errors | "2 self-check errors. In DT_ENTRIES_ARCMINDIVID." |
| Gutter capped | Above `GUTTER_LINE_BUDGET` (12,000 lines) the pane drops line numbers and the manifest foot says so, rather than freezing. |
| Saved | The written paths render under the pane; `#status` says how many. |

`#status` answers "what did my last action do"; the manifest foot answers "is
the bundle sound". Two sentences, two jobs.

## Trade-offs taken

- **The gutter is one `<span class="ln">` per line.** That is what keeps the
  numbers attached to wrapped lines — a two-column layout desyncs the moment a
  line wraps, and `#out` must wrap (audit finding #8). The cost is that copying
  a selection relies on the browser inserting newlines between block elements,
  which Chromium and Firefox both do. `GUTTER_LINE_BUDGET` bounds the node count.
- **Focus rings are desaturated** (`--ink` on paper, `--readout-ink` inside the
  readout) rather than the usual blue, so §2.1 holds without exception: no
  saturated colour on this page that isn't a verdict.
- **The DOM-light constraint was not inherited.** It exists in the validator only
  to satisfy a hand-rolled `document` stub. This repo has a real jsdom suite, so
  `classList`, `dataset` and `addEventListener` are used freely.

## One accessory removed (checklist, last item)

The interlock panel first had a 3px amber left edge alongside its amber
eyebrow — the same signal twice. The edge is gone.

## Verification

- `python scripts/check_contrast.py` — 21 pairs × 2 modes, 0 failures. It reads
  the tokens out of the stylesheet, and treats decorative hairlines (`--rule`,
  `--readout-line`) as exempt while holding `--rule-strong` — the only thing
  outlining a real control — to 3:1.
- `npm test` — 25 jsdom tests.
- `python -m pytest tests/unit/test_web_template.py` — 23 markup assertions.
