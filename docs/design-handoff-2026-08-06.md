# Design handoff — applying the ODF Validator's visual system

Written 2026-08-06, alongside the validator redesign (`ODF Validator Webapp 2`,
commit `606d271`). The target for this document is `odf-message-generator`, but
Parts 1 and 2 are project-agnostic.

Read this in three passes:

| Part | What it gives you | Portable? |
|---|---|---|
| 1. Method | How to arrive at a direction that isn't templated | Anywhere |
| 2. Rules | The specific rules that made the validator work, and *why* | Mostly |
| 3. Application | What to do to this repo, file by file | This repo |

The single most important idea: **do not copy the validator's tally rail into
this app.** It is an answer to a question the generator does not ask. Part 3
explains what the generator's equivalent question is.

---

## Part 1 — Method

### 1.1 Ground the direction in the subject, not in "good design"

Before choosing a colour, name three things: the concrete subject, its audience,
and the page's single job. Then look for the direction inside the subject's own
world — its materials, instruments, artifacts and vocabulary.

For the validator that was: *Olympic Data Feed conformance · a broadcast timing
integration engineer · does this message obey the spec?* The world of that
subject is timing equipment, transport signage, fixed-width positional codes and
technical drawings. DIN type and a recessed readout came from there. They were
not chosen because they look nice in the abstract.

The test: **could this design be lifted onto an unrelated product without
anything looking wrong?** If yes, it is templated. A design that fits its subject
should look slightly odd anywhere else.

### 1.2 Choose one signature, and let everything else be quiet

Pick the single element the interface will be remembered by, make it the thing
the page is built around, and then keep everything else disciplined. Boldness
spent in two places cancels out.

The signature should answer the page's core question. Ask: *what is this tool's
verdict?* Then make the verdict the largest thing on the screen. For the
validator the verdict is a count of violations by severity, so the severity
readout became the hero — and, because the same element also filters the list,
the biggest thing on the page is also its main control. Nothing decorative.

### 1.3 Structural devices must encode something true

Numbering, eyebrows, dividers, tick marks — each has to carry information the
reader needs, or it is decoration.

`01 / 02 / 03` step markers are the classic offender: they are correct only when
the content genuinely is a sequence. The validator earns its numbering exactly
once, in the source gutter, because findings cite line numbers — the number is
the thing that gets you to the fix. Everything else is unnumbered.

### 1.4 The three defaults to avoid

Machine-generated design currently clusters hard around three looks. All are
legitimate for some briefs; none should be reached for by default:

1. Warm cream background (~`#F4F1EA`), high-contrast serif display, terracotta accent.
2. Near-black background with one bright acid-green or vermilion accent.
3. Broadsheet layout — hairline rules, zero border-radius, dense newspaper columns.

The validator deliberately avoids all three: the ground is a cool blue-grey
(drafting paper, not cream), there is no single accent colour at all, and the
radius is 2px — machined rather than either razor-sharp or SaaS-soft.

Where a brief specifies one of these looks, follow the brief. Where the brief is
silent, don't spend the freedom on a default.

### 1.5 Copy is design material

Words exist to make the interface easier to use, not to set a mood.

- Name things by what the person controls, never by how the system is built.
- Active voice; a control says what happens. An action keeps the same name
  through the whole flow — the button that says "Generate" produces a status
  that says "Generated."
- Errors state what happened and what to do. They don't apologise and they are
  never vague.
- An empty screen is an invitation to act, not an apology.
- One job per element. A label labels; an example demonstrates. Nothing does
  double duty.

---

## Part 2 — The rules, with their reasoning

Each of these is followed by *why*, so you can break it knowingly.

### 2.1 The only saturated colour in the interface is a verdict

If something is red, amber or blue, it is stating a fact about the user's data.
There is no brand accent, no decorative colour, no coloured hero.

**Why:** in a tool whose entire output is a judgement, colour is the loudest
available signal. Spending it on chrome — a teal button, a gradient header —
means the judgement has to compete with decoration for the same channel.
Withholding colour everywhere else makes a single red bar unmissable.

**Transferring it:** the rule is "reserve saturation for whatever this tool is
actually telling you." That is not always severity. In the generator it is
*what got produced and whether it self-checked*.

### 2.2 Three type roles, chosen for the subject

| Role | Face | Used for |
|---|---|---|
| Display | Bahnschrift → DIN Alternate → Roboto Condensed → Segoe UI | Headings, labels, buttons, eyebrows, numerals |
| Data | Consolas → Cascadia Mono → ui-monospace | Rule IDs, XPaths, codes, filenames, XML, line numbers |
| Prose | Segoe UI Variable Text → Segoe UI → system-ui | Messages, help text, empty states |

**Why Bahnschrift:** it is Windows' variable DIN, derived from the German
industrial signage standard — the type of timing equipment and instrument faces.
It is on every Windows 10/11 machine, so no webfont is needed.

**Why no webfonts at all:** these tools run locally, launched from a `.bat`, and
may be offline. A Google Fonts link degrades silently to a fallback exactly when
you can't see it happen.

**The inversion worth noticing:** the interface *chrome* is the characterful
face and the *data* is monospace, because the subject is fixed-width machine
data. That is the opposite of the usual "characterful display, neutral body."

### 2.3 Contrast is computed, not eyeballed

Every text/background and control-border pair is checked against WCAG AA before
the design is called done: 4.5:1 for normal text, 3:1 for large text and for
borders that are the only thing defining a control.

**Why this is not just compliance box-ticking:** it caught a genuine design
failure. The tally bar's amber and blue fills, on the original light channel,
landed at **1.04:1 against each other** — three segments that would have read as
a single smear, and been invisible to anyone with a colour vision deficiency.

The fix drove a better design: a dark recessed channel, which gives every fill
3.5:1+ and reframes the empty state as an unlit readout waiting to be driven.
**The dark channel is a contrast fix that turned into the best idea in the
design.** Verification is a design tool, not a chore.

Script in Appendix B. Run it whenever the palette changes.

### 2.4 Motion: one settle, then stillness

The rail sweeps out once, when a result lands (a 0.5s staggered `scaleX`).
Toggling a filter re-proportions it without replaying the sweep — that is what
the `.seg-static` class is for. `prefers-reduced-motion: reduce` collapses all
durations to `0.01ms`.

**Why:** one orchestrated moment reads as an instrument settling. Scattered
hover-and-scroll effects read as generated.

### 2.5 State the states

Three states most internal tools skip, all of which the validator now says out
loud:

- **Idle** — the readout is visibly unlit, not just empty.
- **Clean pass** — "No findings. This message conforms to SYOG26." A pass is a
  result; an empty list is not a sentence.
- **Truncated** — when the server caps a response, the scope line says
  `· N capped` rather than letting the numerals quietly understate.

**Why:** an internal tool's worst failure mode is silent ambiguity. An operator
cannot tell "clean" from "broken" by looking at nothing.

### 2.6 Quality floor, unannounced

Responsive to mobile; visible keyboard focus on every control including custom
ones; reduced motion respected; no `localStorage`. Build to it without making a
feature of it.

Custom controls stay real controls: the validator's severity keys and mode tabs
are visually-hidden `<input type="checkbox">` and `<input type="radio">` inside
wrapping `<label>`s. Space toggles, arrow keys move between radios, screen
readers announce "Errors, checkbox, checked" — all for free, with a
`:focus-visible + .key-body` rule supplying the ring.

---

## Part 3 — Applying this to `odf-message-generator`

### 3.1 Start here: what does this tool actually say?

The validator's verdict is *how wrong is this message.* The generator's is
different, and copying the severity rail would be exactly the templated move
Part 1 warns about — the generator has no severities.

The generator produces a **bundle**: a set of messages for a Games plus a
discipline, optionally with realism switches. After pressing Generate the
operator wants to know:

1. What did I get? (which document types, how many messages of each)
2. Is it sound? (`generator/selfcheck.py` has an opinion)
3. Where is it? (after Save, which paths were written)

Right now the answer to all three is a `<pre>` blob of XML plus a one-line
status. **That gap is the design opportunity, and it is the generator's
signature.**

### 3.2 Proposed signature: the bundle manifest

Not a prescription — the reasoning matters more than the shape:

A manifest strip that appears where the verdict belongs, one row per document
type produced (`DT_SCHEDULE`, `DT_PARTIC`, `DT_ENTRIES`, …), each row carrying
the message count in DIN numerals, the doc-type code in monospace, and its
self-check state. Selecting a row scopes the output pane to that message.

This is recognisably the same device family as the validator — dark recess, DIN
numerals, monospace codes, saturation reserved for the verdict — while answering
the generator's own question rather than borrowing the validator's.

The second state worth designing properly is **not-ready**. A pack that cannot
generate is a pre-flight interlock, not an error: the device declines to arm and
tells you which folder to create. Currently it is a red alert box, which frames
a normal setup step as a failure. An interlock panel in the readout's own idiom
would say it better — and note the audit's finding #1: those reason strings
contain literal `<PACK>` and `<CODE>` placeholders, so whatever renders them must
keep using `textContent` / `replaceChildren`.

### 3.3 What transfers wholesale

- The full token block — colour, type, metrics (Appendix A).
- The three type roles and their fallback stacks.
- The contrast script (Appendix B), run against your final palette.
- `.btn` / `.btn-run`, `.eyebrow`, `.empty` / `.clear`, `.stack`, `.item-head`,
  `.chips`, `.field-label`, `.notice` and the focus-ring rules — all
  generic and directly liftable from `web/static/styles.css`.
- The `.mode` segmented-control pattern, if you ever add mutually exclusive
  modes.

### 3.4 What must NOT be copied

**The DOM-light constraint.** The validator's `app.js` avoids `classList`,
`dataset`, `addEventListener` and `element.style` on any path reachable from
`validate()`. That is *not* a design principle — it exists solely because
`tests/js/export_filter.test.js` evals the file against a hand-rolled `document`
stub. This repo has a real jsdom suite (`tests/web/app.test.mjs`, 25 tests) and
already uses `replaceChildren`, `hidden` and ES modules idiomatically. **Use the
full DOM API here.** Inheriting the constraint would be cargo-culting.

**The tally rail itself.** See 3.1.

**Light-only tokens, without a decision.** `web/static/app.css` currently
supports `prefers-color-scheme: dark`; the validator's palette is light-only.
Pick one deliberately:

- *Keep dark mode* — you must author dark values for all of `--ground`,
  `--panel`, `--panel-sunk`, `--ink*`, `--rule*` and re-run the contrast script
  for both modes. The signal colours and `--readout` mostly survive as-is.
- *Drop it* — defensible for a launched-from-`.bat` operator tool used in bursts,
  and it is what the validator does. But it is a removal of working behaviour,
  so make it a choice rather than an accident of copying.

### 3.5 File-by-file

| File | Action |
|---|---|
| `web/static/app.css` | Replace `:root` with the Appendix A token block; keep the existing layout rules and re-express them in the new tokens. Resolve the dark-mode question (3.4). |
| `web/templates/index.html` | Add the nameplate header (`.rig` / `.wordmark`) so the two tools read as one family. Keep `<main>`, the `<form>`, every `<label>` association, `role="alert"`, `role="status"`, `aria-live` and the `<noscript>` block exactly as they are. |
| `web/templates/index.html` | The three `<fieldset>`s are good structure — restyle, don't remove. `<legend>` becomes `.eyebrow`. |
| `web/static/app.js` | Manifest rendering, if you take 3.2. Keep `textContent`/`replaceChildren`, the `api()` error wrapper, the pending/disabled state and the `#status` announcement. |
| `#out` | Keep `pre-wrap`, `max-height: 60vh` and `role="region"`. Restyle as the validator's `.editor` pane; a line-number gutter is genuinely useful here too, since generated XML is what you are reading. |
| `docs/` | Record whatever you decide, the way this repo already does. |

### 3.6 Guardrails — do not regress the 2026-08-06 audit

That audit fixed 11 findings and is covered by 25 jsdom tests plus 23 markup
assertions. A visual pass can quietly undo several of them. Before calling the
restyle done:

- `npm test` and the Python markup suite both still pass.
- Still no `innerHTML` on any operator-facing string (finding #1 — the reason
  strings contain literal `<CODE>` placeholders that HTML parsing eats).
- `role="status"` / `role="alert"` / `aria-live` regions intact (#5).
- Buttons still disable during work (#6).
- `<main>` and the real `<form>` still present (#7).
- `#out` still wraps and does not force horizontal scroll (#8).
- Focus rings still visible on every control, including any custom ones you add
  (§2.6).

The audit's one deliberate deviation is worth preserving too: `#out` is a named
focusable region rather than a live region, because announcing a whole generated
bundle on every click would be hostile. Outcomes are announced on `#status`.

---

## Appendix A — token block

Drop-in replacement for `:root`. Values are the shipped validator palette; every
pair passes AA (Appendix B).

```css
:root {
  /* ground & ink — cool blue-grey, drafting paper rather than cream */
  --ground:      #e4e9ef;
  --panel:       #fbfcfd;
  --panel-sunk:  #edf1f6;
  --ink:         #10151c;
  --ink-mid:     #56606e;
  --ink-soft:    #5f6775;   /* 4.67:1 on ground — small-caps labels are text */
  --rule:        #c6ceda;   /* decorative hairlines */
  --rule-strong: #738296;   /* outlines real controls, so >=3:1 */

  /* the readout is unlit until driven; dark is what lets fills clear 3:1 */
  --readout:      #232a34;
  --readout-line: #3b4553;
  --readout-text: #98a2b0;

  /* signals — the only saturated colour. -fill paints on the dark readout,
     -tint backs a chip on paper, bare states a verdict in text. */
  --error:        #c0261b;  --error-fill:   #e0483a;  --error-tint:   #f9e6e4;
  --warning:      #96580b;  --warning-fill: #e8a11c;  --warning-tint: #fbefdb;
  --info:         #1f5ea8;  --info-fill:    #5e9bdd;  --info-tint:    #e5eefa;

  /* type */
  --font-display: "Bahnschrift", "DIN Alternate", "DIN Condensed",
                  "Roboto Condensed", "Segoe UI", system-ui, sans-serif;
  --font-data:    "Consolas", "Cascadia Mono", ui-monospace, "SF Mono",
                  "Liberation Mono", Menlo, monospace;
  --font-prose:   "Segoe UI Variable Text", "Segoe UI", system-ui,
                  -apple-system, Roboto, sans-serif;
  --code-lh: 1.55;

  /* metrics */
  --s1: .25rem; --s2: .5rem; --s3: .75rem; --s4: 1rem;
  --s5: 1.5rem; --s6: 2rem;  --s7: 3rem;
  --radius: 2px;            /* machined: neither 0 nor the SaaS 8-12px */
  --measure: 1180px;
  --ease: cubic-bezier(.2, .8, .2, 1);
}
```

Two details that are easy to lose:

- `font-feature-settings: "tnum" 1` on `body`. Tabular figures stop numerals
  jittering as counts change. It is an instrument.
- Condensed numerals via `font-variation-settings: "wdth" 85, "wght" 700` on the
  large readout figures. Harmless on non-variable fallbacks.

---

## Appendix B — contrast verification

Run after any palette change. Reads the tokens straight out of the stylesheet,
so it cannot drift from what ships.

```python
import re, pathlib, sys

CSS = pathlib.Path("web/static/app.css").read_text()
V = dict(re.findall(r'(--[\w-]+):\s*(#[0-9a-fA-F]{6});', CSS))

def lum(h):
    h = h.lstrip('#')
    c = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    c = [x/12.92 if x <= 0.03928 else ((x+0.055)/1.055)**2.4 for x in c]
    return 0.2126*c[0] + 0.7152*c[1] + 0.0722*c[2]

def cr(a, b):
    l1, l2 = sorted([lum(V.get(a, a)), lum(V.get(b, b))], reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)

# (minimum, foreground, background, label) — 4.5 for text, 3.0 for large
# text and for borders that are the only thing defining a control.
CHECKS = [
    (4.5, '--ink',          '--ground',      'body / ground'),
    (4.5, '--ink',          '--panel',       'body / panel'),
    (4.5, '--ink-mid',      '--panel',       'secondary / panel'),
    (4.5, '--ink-soft',     '--ground',      'small-caps labels / ground'),
    (4.5, '--readout-text', '--readout',     'idle text / readout'),
    (4.5, '--error',        '--ground',      'error numeral'),
    (4.5, '--warning',      '--ground',      'warning numeral'),
    (4.5, '--info',         '--ground',      'info numeral'),
    (4.5, '--error',        '--error-tint',  'error chip'),
    (3.0, '--rule-strong',  '--panel',       'control border / panel'),
    (3.0, '--rule-strong',  '--ground',      'control border / ground'),
    (3.0, '--error-fill',   '--readout',     'bar: error'),
    (3.0, '--warning-fill', '--readout',     'bar: warning'),
    (3.0, '--info-fill',    '--readout',     'bar: info'),
]

bad = 0
for need, fg, bg, label in CHECKS:
    r = cr(fg, bg)
    ok = r >= need
    bad += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {r:5.2f} / {need}  {label}")
print("\nFAILURES:", bad)
sys.exit(1 if bad else 0)
```

Two habits that make it worth having:

- **Check fills against each other, not only against the background.** The
  amber/blue collision (§2.3) passed every background check and still would have
  shipped a broken bar.
- **Watch the escaping.** An earlier run of a NUL-byte check used `$'\x00'` in
  bash, which collapses to an empty pattern and matches every line — it reported
  864 corrupt lines in a perfectly clean file. Verify your verifier.

---

## Checklist

Before calling a design pass done:

- [ ] The direction came from the subject's own world, and would look faintly
      wrong on an unrelated product.
- [ ] There is exactly one signature element, and it answers the tool's core
      question.
- [ ] It is none of the three defaults (§1.4).
- [ ] Every structural device encodes something true (§1.3).
- [ ] Saturation is reserved for the tool's verdict (§2.1).
- [ ] Contrast script passes, including fills against each other (§2.3).
- [ ] Idle, clean-pass and truncated states all say something (§2.5).
- [ ] Responsive; focus visible on every control including custom ones; reduced
      motion respected (§2.6).
- [ ] The existing test suites still pass (§3.6).
- [ ] One accessory removed. Something in the first draft was decoration — in
      the validator it was a hairline divider in the wordmark. Find yours and
      cut it.
