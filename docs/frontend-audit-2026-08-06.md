# Front-End Audit — `web/templates/index.html`

Audited 2026-08-06 against the [Front-End Checklist](https://frontendchecklist.io)
(385 rules). Scope: the single Flask/FastAPI-served page `web/templates/index.html`
(146 lines, inline CSS + inline JS), plus the response surface of `api/app.py` it
consumes.

**Categories applied:** HTML, CSS, JavaScript, Accessibility, Security (partial).
**Categories skipped:** SEO, Images, Privacy, i18n — the app is a single-operator
tool bound to `127.0.0.1`, has no images, no tracking, no public URL, and is
English-only by design. Most of the Security category (HTTPS, HSTS, CSP, cookie
flags, CAPTCHA) is also N/A for the same reason; the one item that still applies
is noted below.

---

## Critical

### 1. `innerHTML` silently deletes the operator instructions it is meant to show

`applyPack()` renders readiness reasons with `innerHTML` and a template literal:

```js
reasonsEl.innerHTML = p.reasons.map((r) => `<li>${r}</li>`).join("");
```

The reason strings in `generator/packs.py` contain literal angle brackets:

- `"...drop that discipline's Data Dictionary in Rules/<PACK>/Disciplines/<CODE>/"`
- `"...(.xlsx, or .xml with <Codeset> elements)"`

The browser parses `<CODE>` as an HTML `<code>` element and `<Codeset>` as an
unknown element. **The placeholders vanish from the rendered page**, so the
"This Games cannot generate yet" panel — the one screen whose entire job is to
tell an operator which folder to create — tells them to create
`Rules/SOLG28/Disciplines/` with no placeholder, and the rest of the line
silently switches to monospace.

Same pattern at lines 65 (`p.label`) and 86 (discipline codes).

**Fix** — build nodes and assign text, never markup:

```js
reasonsEl.replaceChildren(...p.reasons.map((r) => {
  const li = document.createElement("li");
  li.textContent = r;
  return li;
}));

disciplineEl.replaceChildren(...p.disciplines.map((d) => new Option(d, d)));
packEl.replaceChildren(...data.packs.map((p) =>
  new Option(p.label + (p.ready ? "" : " (not ready)"), p.name)));
```

This also closes the XSS path. It is low-risk today (all strings originate from
local YAML and filesystem paths), but pack `reasons` interpolate raw exception
messages — `f"Pack failed to load: {type(e).__name__}: {e}"` — and an
`XMLSyntaxError` from a malformed XSD will happily quote the offending markup
back into the DOM.

Rule: [avoid-eval](https://frontendchecklist.io/rules/javascript/avoid-eval) (Critical)

### 2. No viewport meta tag

```html
<head><meta charset="utf-8"><title>ODF Message Generator</title></head>
```

Without it, mobile and tablet browsers apply a 980px virtual viewport and scale
the page down. Also blocks the 400%-zoom reflow requirement on desktop.

```html
<meta name="viewport" content="width=device-width, initial-scale=1">
```

Rules: [viewport](https://frontendchecklist.io/rules/html/viewport) (Critical),
[zoom-reflow](https://frontendchecklist.io/rules/accessibility/zoom-reflow) (Critical)

---

## High

### 3. No error handling on any `fetch` — a failed API call is invisible

`loadPacks()` is fired at line 91 with no `.catch()`. If uvicorn isn't up yet, or
`/api/packs` 500s (which `PackRegistry.discover()` will do when *no* packs are
found), the user sees two empty dropdowns, an enabled Generate button, and no
message at all. The rejection lands in the console, which an operator will never
open.

The same applies to `/api/generate`: unlike `/api/save`, it never checks
`res.ok`, so a 400/409 error body is JSON-dumped into `<pre id="out">` looking
exactly like a successful result.

Related latent crash in the same function: `data.packs[0].name` throws if
`packs` is ever empty, and `defaultErrorMessageEl.textContent = data.default_error`
writes the string `"undefined"` when the server omits that key.

**Fix** — wrap each call, surface failures in the status region:

```js
async function api(path, init) {
  const res = await fetch(path, init);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `${res.status} ${res.statusText}`);
  return data;
}

loadPacks().catch((e) => {
  statusEl.textContent = `Could not reach the generator service: ${e.message}`;
});
```

Rules: [error-handling](https://frontendchecklist.io/rules/javascript/error-handling),
[json-safety](https://frontendchecklist.io/rules/javascript/json-safety)

### 4. `parseInt` silently truncates valid `<input type="number">` values

```js
if (v !== "") p[key] = parseInt(v, 10);
```

`type="number"` accepts scientific and decimal notation. A user who types `1e3`
into Athletes sends **1**. `2.7` sends **2**. Both without a word of warning.

```js
const n = Number(v);
if (Number.isInteger(n) && n >= 0) p[key] = n;
else { /* surface a validation message */ }
```

Rules: [type-coercion](https://frontendchecklist.io/rules/javascript/type-coercion),
[form-validation](https://frontendchecklist.io/rules/html/form-validation)

### 5. Status and output updates are never announced to screen readers

`#status`, `#out`, `#notready` and `#default-error` are all written or toggled
from JS, but none is a live region. A screen-reader user presses Generate and
receives silence — no announcement of success, of the saved file list, or of an
error. `#notready` and `#default-error` appear via `style.display` with no
announcement either.

```html
<p id="status" role="status" aria-live="polite"></p>
<pre id="out" aria-live="polite" aria-label="Generated messages"></pre>
<div id="default-error" role="alert" hidden>…</div>
<div id="notready" role="alert" hidden>…</div>
```

(Prefer the `hidden` attribute over `style="display:none"` and toggle
`el.hidden = bool` — it keeps presentation out of the markup and works
identically.)

Rules: [aria-live-regions](https://frontendchecklist.io/rules/accessibility/aria-live-regions),
[accessible-notifications](https://frontendchecklist.io/rules/accessibility/accessible-notifications)

### 6. No pending state — Generate can be fired repeatedly

`#go` clears the status and then does nothing visible until the response lands.
Generation walks an XSD and builds a whole bundle; on a large pack that is not
instant. Nothing disables the button, so impatient double-clicks queue duplicate
requests, and `#save` will happily write the same bundle twice.

`#save` at least sets `"Saving…"`. Mirror that on `#go`, and disable both buttons
for the duration.

Rules: [focus-management](https://frontendchecklist.io/rules/accessibility/focus-management),
[error-handling](https://frontendchecklist.io/rules/javascript/error-handling)

### 7. No semantic structure or `main` landmark

Everything sits as a direct child of `<body>`. There is no `<main>`, no `<form>`,
no heading structure beyond the single `<h1>`.

Wrapping the controls in `<main>` and a real `<form>` fixes three things at once:
the landmark, the missing Enter-to-submit behaviour (right now pressing Enter in
any text field does nothing), and native constraint validation for `min="0"` on
the count fields.

```html
<main>
  <form id="form" novalidate>
    …
    <button id="go" type="submit">Generate</button>
    <button id="save" type="button">Save to samples/</button>
  </form>
</main>
```

Rules: [html5-semantic-elements](https://frontendchecklist.io/rules/html/html5-semantic-elements),
[landmark-one-main](https://frontendchecklist.io/rules/accessibility/landmark-one-main),
[keyboard-navigation](https://frontendchecklist.io/rules/accessibility/keyboard-navigation)

---

## Medium

### 8. `<pre id="out">` forces horizontal page scroll

Generated ODF XML has long lines. `<pre>` does not wrap, so the whole document
grows wider than the viewport and the page scrolls sideways — the form controls
scroll away with it.

```css
#out { white-space: pre-wrap; overflow-x: auto; max-height: 60vh; overflow-y: auto; }
```

Rule: [horizontal-scroll](https://frontendchecklist.io/rules/css/horizontal-scroll)

### 9. Inline CSS and inline JS

Six `style="…"` attributes and a 96-line inline `<script>`. Acceptable for a tool
this size, but moving both to `web/static/app.css` and `web/static/app.js`
(served via `StaticFiles`) would make the script testable, lintable, and
cacheable — and is a precondition for ever adding a CSP.

Rules: [embedded-or-inline-css](https://frontendchecklist.io/rules/css/embedded-or-inline-css),
[javascript-inline](https://frontendchecklist.io/rules/javascript/javascript-inline)

### 10. No `<noscript>` fallback

Every control on the page is inert without JavaScript — the dropdowns are empty
and the buttons do nothing, with no explanation.

```html
<noscript><p>This tool requires JavaScript. Use <code>python -m generator</code> from the command line instead.</p></noscript>
```

Rule: [noscript-tag](https://frontendchecklist.io/rules/html/noscript-tag)

### 11. Only one front-end test exists

`tests/integration/test_api.py:31` asserts `client.get("/")` responds. Nothing
covers the page's behaviour. Finding #1 in particular would have been caught by a
single test asserting that a reason string containing `<CODE>` survives to the
rendered DOM.

Rule: [testing](https://frontendchecklist.io/rules/testing)

---

## Low

- **Text override fields could set `autocomplete="off" spellcheck="false"`.**
  `CompetitionCode`, `Source`, `Gen`, `Sport`, `Codes`, `Status` are all opaque
  identifiers; browser autofill and red squiggles are noise on them.
- **`stack-trace-exposure`** — `_pack_error` and the `PackNotReady` path return
  raw `str(exc)` to the client, and pack load failures embed
  `type(e).__name__: {e}`. That is exactly right for a localhost operator tool
  and exactly wrong if this is ever bound to `0.0.0.0`. Worth a comment in
  `api/app.py` noting the loopback assumption.
  ([rule](https://frontendchecklist.io/rules/security/stack-trace-exposure))

---

## What is already correct

Worth recording so it doesn't get "fixed" later:

- HTML5 doctype first, `charset` first in `<head>`, `lang="en"` on `<html>` — all
  three Critical HTML rules that *are* satisfied.
- **Every form control is labelled.** The `<label>Field <input></label>` wrapping
  pattern is a valid implicit association; no `for`/`id` pairs needed.
- `type="number"` with `min="0"` on the count inputs is the correct input type.
- Output is written with `textContent`, not `innerHTML` — the one place where the
  data really is untrusted (generated XML) is the one place that is safe.
- No duplicate IDs, no `var`, no `eval`, no `console.*` left behind, no
  `localStorage`, `Object.entries`/`fromEntries`/`map` used idiomatically.
- Bound to `127.0.0.1` in `Launch-ODF-Generator.bat`, so the HTTPS/HSTS/CSP/
  cookie-flag family of rules genuinely does not apply.

---

## Suggested order

1. #1 (`innerHTML`) — it is actively corrupting operator-facing instructions.
2. #3 + #6 (error handling, pending state) — currently the app fails silently.
3. #2, #5, #7 (viewport, live regions, landmarks) — one-line-ish each.
4. #4 (`parseInt`) — silent wrong-number bug.
5. The rest as cleanup.

---

## Resolution — 2026-08-06

All 11 findings and both Low items were implemented the same day, test-first.
The page is now `web/templates/index.html` (markup only) plus
`web/static/app.js` and `web/static/app.css`, mounted at `/static`.

New coverage, both pack-free so they run without the validator checkout:

| Suite | Command | Covers |
|---|---|---|
| `tests/web/app.test.mjs` | `npm test` | #1, #3, #4, #6 — 25 tests, jsdom + stubbed fetch |
| `tests/unit/test_web_template.py` | `pytest` / `python -m tests.minirunner` | #2, #5, #7, #8, #9, #10 — 23 markup assertions |

One requirement changed during implementation. The audit proposed
`aria-live="polite"` on `#out`; that would make a screen reader read an entire
generated ODF bundle aloud on every click. `#out` is instead a named, focusable
`role="region"`, and the outcome is announced on the `#status` live region
("Generated." / "Generated with validation errors in: DT_SCHEDULE").
