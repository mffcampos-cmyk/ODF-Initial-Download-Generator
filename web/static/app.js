// Operator page behaviour.
//
// Everything here is exported and side-effect free until `init()` runs, so
// tests/web/app.test.mjs can drive it against a jsdom document with a stubbed
// fetch. The browser entry point is the guarded bootstrap at the bottom.
//
// DOM is always built with createElement + textContent, never from strings:
// pack readiness reasons legitimately contain angle brackets (they tell the
// operator to create `Rules/<PACK>/Disciplines/<CODE>/`) and innerHTML would
// silently swallow them. That rule covers generated XML too, for the same
// reason with more force.

/** Text override fields, keyed by element id -> request key. */
const TEXT_FIELDS = {
  competition_code: "competition_code",
  source: "source",
  gen: "gen",
  sport: "sport",
  codes: "codes",
  status_ov: "status",
};

const COUNT_FIELDS = ["athletes", "teams", "coaches"];

const FLAGS = [
  "realistic_entries",
  "seeded_heats",
  "victory_ceremonies",
  "historical_athletes",
];

/**
 * Lines above which the output pane drops its number gutter.
 *
 * The gutter is one element per line. That is cheap for the ~1,800 lines a
 * discipline bundle usually runs to, and not cheap at all for a Games-wide
 * one. Past the budget the pane renders plain text and the manifest says so,
 * rather than either freezing or silently dropping the numbers.
 */
export const GUTTER_LINE_BUDGET = 12000;

/**
 * Read a count field.
 *
 * `<input type="number">` accepts more than plain integers: "1e3" and "2.7"
 * are both valid values the browser will hand back as strings. parseInt would
 * turn them into 1 and 2 respectively, silently generating the wrong number of
 * entries, so anything that is not a non-negative integer is rejected outright.
 *
 * @returns {{state:"blank"}|{state:"invalid"}|{state:"ok", value:number}}
 */
export function parseCount(raw) {
  const s = String(raw ?? "").trim();
  if (s === "") return { state: "blank" };
  const n = Number(s);
  if (!Number.isInteger(n) || n < 0) return { state: "invalid" };
  return { state: "ok", value: n };
}

/** Replace `ul`'s children with one <li> per item, as literal text. */
export function renderList(ul, items) {
  const doc = ul.ownerDocument;
  ul.replaceChildren(
    ...items.map((text) => {
      const li = doc.createElement("li");
      li.textContent = text;
      return li;
    }),
  );
}

/** Replace `select`'s options. `items` is [{value, label}]. */
export function renderOptions(select, items) {
  const doc = select.ownerDocument;
  select.replaceChildren(
    ...items.map(({ value, label }) => {
      const opt = doc.createElement("option");
      opt.value = value;
      opt.textContent = label;
      return opt;
    }),
  );
}

/**
 * Build the request body from the form.
 * @throws {Error} naming the offending field if a count is not a whole number.
 */
export function collectPayload(doc) {
  const value = (id) => doc.getElementById(id).value.trim();
  const payload = {
    discipline: value("discipline"),
    pack: value("pack"),
    seed: 1,
  };
  for (const id of FLAGS) payload[id] = doc.getElementById(id).checked;

  for (const [id, key] of Object.entries(TEXT_FIELDS)) {
    const v = value(id);
    if (v) payload[key] = v;
  }
  for (const id of COUNT_FIELDS) {
    const count = parseCount(value(id));
    if (count.state === "invalid") {
      throw new Error(`${id} must be a whole number of 0 or more.`);
    }
    if (count.state === "ok") payload[id] = count.value;
  }
  return payload;
}

/** English plural for a count of `noun`, so status copy never says "1 errors". */
function plural(n, noun, many = `${noun}s`) {
  return `${n} ${n === 1 ? noun : many}`;
}

/**
 * One entry per document type in a generated bundle.
 *
 * `lines` is what the manifest counts. Message *count* would be the obvious
 * numeral, but the API returns exactly one document per type, so it would read
 * "1" on every row and tell the operator nothing. Lines is both true and the
 * thing the gutter below is numbering.
 *
 * @returns {{docType:string, xml:string, errors:string[], lines:string[]}[]}
 */
export function summarise(messages) {
  return Object.entries(messages ?? {}).map(([docType, m]) => {
    const xml = m?.xml ?? "";
    const lines = xml.split("\n");
    // A file ending in a newline is not a file with a trailing blank line.
    if (lines.length > 1 && lines[lines.length - 1] === "") lines.pop();
    return { docType, xml, errors: m?.errors ?? [], lines };
  });
}

/** Fetch JSON, turning any non-2xx or unparseable body into a thrown Error. */
async function requestJson(fetchFn, path, init) {
  const res = await fetchFn(path, init);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (data.error) throw new Error(data.error);
    // An unhandled server exception returns a non-JSON body, so there is
    // nothing here to show. The traceback exists, but it is in the "ODF
    // service" console window, which this page cannot see and never used to
    // mention -- the operator got "Error: 500 Internal Server Error" and no
    // next step.
    if (res.status >= 500) {
      throw new Error(
        `The generator service failed (${res.status}). The full error is in ` +
          `the "ODF service" window that opened with the app.`,
      );
    }
    throw new Error(`${res.status} ${res.statusText}`.trim());
  }
  return data;
}

/** Wire the page up. Resolves once the initial pack list has been handled. */
export async function init(doc, { fetch: fetchFn } = {}) {
  const el = (id) => doc.getElementById(id);
  const packEl = el("pack");
  const disciplineEl = el("discipline");
  const statusEl = el("status");
  const outEl = el("out");
  const formEl = el("form");
  const notReadyEl = el("notready");
  const reasonsEl = el("reasons");
  const defaultErrorEl = el("default-error");
  const defaultErrorMessageEl = el("default-error-message");
  const goEl = el("go");
  const saveEl = el("save");
  const downloadEl = el("download");
  const manifestEl = el("manifest");
  const idleEl = el("readout-idle");
  const scopeEl = el("readout-scope");
  const footEl = el("readout-foot");
  const writtenEl = el("written");
  const writtenListEl = el("written-list");
  const outTitleEl = el("out-title");

  let packs = new Map();
  const IDLE_TEXT = idleEl.textContent;

  const make = (tag, className, text) => {
    const node = doc.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };

  /**
   * Announce an outcome. Errors are the operator's verdict on their own run,
   * so they are the one thing on the status line allowed to take colour.
   */
  const say = (text, { error = false } = {}) => {
    statusEl.textContent = text;
    statusEl.classList.toggle("is-error", error);
  };

  /** Put the readout back to unlit, and empty the pane it drives. */
  function resetReadout() {
    manifestEl.replaceChildren();
    manifestEl.hidden = true;
    footEl.hidden = true;
    footEl.replaceChildren();
    scopeEl.textContent = "";
    idleEl.textContent = IDLE_TEXT;
    idleEl.hidden = false;
    outEl.replaceChildren();
    outTitleEl.hidden = true;
    writtenEl.hidden = true;
    writtenListEl.replaceChildren();
  }

  /** One manifest row: a real radio, so arrow keys and screen readers work. */
  function manifestRow({ value, code, codeClass, lines, state, lamp, checked }) {
    const label = make("label", "mrow");
    const input = doc.createElement("input");
    input.type = "radio";
    input.name = "scope";
    input.className = "vh";
    input.value = value;
    input.checked = checked;

    const body = make("span", "mrow-body");
    body.append(
      make("span", `lamp ${lamp}`),
      make("span", codeClass, code),
      make("span", "mnum", lines.toLocaleString()),
      make("span", "munit", "ln"),
      make("span", `mstate${state.error ? " mstate-error" : ""}`, state.text),
    );

    label.append(input, body);
    return label;
  }

  /**
   * The scope line: which pack and discipline this bundle is, plus the seed
   * when it is not the one that was asked for.
   *
   * build_bundle retries with seed+1..+4 when a message has findings, so the
   * data on screen is not always the requested seed's. That used to be
   * invisible; since generation is seed-deterministic, it is the one fact
   * needed to reproduce what you are looking at.
   */
  function scopeText(pack, discipline, data) {
    const parts = [pack, discipline].filter(Boolean);
    const used = data && data.seed;
    const asked = data && data.seed_requested;
    if (used !== undefined && used !== null && used !== asked) {
      parts.push(`seed ${used} (asked ${asked})`);
    }
    return parts.join(" · ");
  }

  /** Draw the manifest and the output pane for a freshly generated bundle. */
  function renderBundle(data) {
    const docs = summarise(data.messages);
    const pack = data.pack || packEl.value;
    const discipline = data.discipline || disciplineEl.value;
    scopeEl.textContent = scopeText(pack, discipline, data);

    if (docs.length === 0) {
      resetReadout();
      scopeEl.textContent = [pack, discipline].filter(Boolean).join(" · ");
      idleEl.textContent = "No documents were produced for this discipline.";
      return;
    }

    idleEl.hidden = true;
    const total = docs.reduce((n, d) => n + d.lines.length, 0);
    const withErrors = docs.filter((d) => d.errors.length);
    const gutter = total <= GUTTER_LINE_BUDGET;

    manifestEl.replaceChildren(
      ...docs.map((d, i) => {
        const row = manifestRow({
          value: d.docType,
          code: d.docType,
          codeClass: "mcode",
          lines: d.lines.length,
          lamp: d.errors.length ? "lamp-error" : "lamp-clean",
          state: d.errors.length
            ? { text: plural(d.errors.length, "error"), error: true }
            : { text: "clean", error: false },
          checked: false,
        });
        row.style.setProperty("--i", String(i));
        return row;
      }),
      (() => {
        const row = manifestRow({
          value: "",
          code: "All documents",
          codeClass: "mall",
          lines: total,
          lamp: withErrors.length ? "lamp-error" : "lamp-clean",
          state: { text: plural(docs.length, "doc"), error: false },
          checked: true,
        });
        row.classList.add("mrow-all");
        row.style.setProperty("--i", String(docs.length));
        return row;
      })(),
    );
    manifestEl.hidden = false;

    // One settle, then stillness. Re-scoping does not redraw the manifest, so
    // the sweep cannot replay on a filter click.
    manifestEl.parentElement.classList.remove("readout-fresh");
    void manifestEl.offsetWidth;
    manifestEl.parentElement.classList.add("readout-fresh");

    // A clean pass is a result, and has to be said. An empty error list is not
    // a sentence.
    footEl.replaceChildren();
    if (withErrors.length === 0) {
      footEl.append(
        make("strong", null, "Self-check clean."),
        doc.createTextNode(
          ` All ${plural(docs.length, "document")}` +
            (pack ? ` pass ${pack}.` : " pass."),
        ),
      );
    } else {
      footEl.append(
        make(
          "strong",
          null,
          `${plural(
            withErrors.reduce((n, d) => n + d.errors.length, 0),
            "self-check error",
          )}.`,
        ),
        doc.createTextNode(` In ${withErrors.map((d) => d.docType).join(", ")}.`),
      );
    }
    if (!gutter) {
      footEl.append(
        doc.createTextNode(
          ` Line numbers are off above ${GUTTER_LINE_BUDGET.toLocaleString()} lines.`,
        ),
      );
    }
    footEl.hidden = false;

    outEl.replaceChildren(
      ...docs.map((d) => {
        const section = make("span", "doc");
        section.dataset.doc = d.docType;
        section.append(make("span", "doc-head", d.docType));
        if (gutter) {
          section.append(...d.lines.map((line) => make("span", "ln", line)));
        } else {
          section.append(doc.createTextNode(`${d.xml}\n`));
        }
        return section;
      }),
    );
    outTitleEl.hidden = false;
  }

  /** Selecting a manifest row scopes the pane to that document. */
  function applyScope() {
    const chosen = manifestEl.querySelector("input[name=scope]:checked");
    const want = chosen ? chosen.value : "";
    for (const section of outEl.querySelectorAll(".doc")) {
      section.hidden = want !== "" && section.dataset.doc !== want;
    }
  }

  function applyPack() {
    const p = packs.get(packEl.value);
    if (!p) return;
    renderList(reasonsEl, p.reasons);
    notReadyEl.hidden = p.ready;
    formEl.hidden = !p.ready;
    renderOptions(
      disciplineEl,
      p.disciplines.map((d) => ({ value: d, label: d })),
    );
    // Anything on screen described the pack we just left.
    resetReadout();
  }

  async function loadPacks() {
    const data = await requestJson(fetchFn, "/api/packs");
    const list = data.packs ?? [];
    if (list.length === 0) {
      formEl.hidden = true;
      say(
        "No Games packs were discovered. Point ODF_PACK_DIR at the validator's " +
          "Rules folder and restart the app.",
        { error: true },
      );
      return;
    }
    packs = new Map(list.map((p) => [p.name, p]));
    renderOptions(
      packEl,
      list.map((p) => ({
        value: p.name,
        label: p.ready ? p.label : `${p.label} (not ready)`,
      })),
    );

    const usable = data.default !== null && packs.has(data.default);
    if (usable) {
      packEl.value = data.default;
    } else {
      packEl.value = list[0].name;
      if (data.default_error) {
        defaultErrorMessageEl.textContent = data.default_error;
        defaultErrorEl.hidden = false;
      }
    }
    applyPack();
  }

  /** Run `work` with the action buttons disabled and a pending message showing. */
  async function busy(message, work) {
    const buttons = [goEl, saveEl, downloadEl].filter(Boolean);
    for (const b of buttons) b.disabled = true;
    say(message);
    try {
      await work();
    } catch (e) {
      say(`Error: ${e.message}`, { error: true });
    } finally {
      for (const b of buttons) b.disabled = false;
    }
  }

  packEl.addEventListener("change", applyPack);
  // Changing the discipline used to leave the previous bundle on screen, so
  // the readout could show ARC's documents while the form said SWM. A control
  // and a result disagreeing is the exact failure a manifest exists to prevent.
  disciplineEl.addEventListener("change", () => {
    resetReadout();
    outEl.replaceChildren();
    outTitleEl.hidden = true;
    writtenEl.hidden = true;
    say("");
  });
  manifestEl.addEventListener("change", applyScope);

  formEl.addEventListener("submit", (e) => {
    e.preventDefault();
    outEl.replaceChildren();
    outTitleEl.hidden = true;
    writtenEl.hidden = true;
    return busy("Generating…", async () => {
      const data = await requestJson(fetchFn, "/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(collectPayload(doc)),
      });
      renderBundle(data);
      const failed = Object.entries(data.messages ?? {})
        .filter(([, m]) => m.errors?.length)
        .map(([name]) => name);
      say(
        failed.length
          ? `Generated with validation errors in: ${failed.join(", ")}`
          : "Generated.",
        { error: failed.length > 0 },
      );
    });
  });

  // Download the bundle as a zip. Until now the page had no exit path at all:
  // /api/generate.zip existed and nothing called it, so the only ways to get
  // the XML out were hand-selecting a scrolling <pre> or finding the files on
  // disk afterwards.
  //
  // Built as a GET navigation rather than fetch+blob so the browser's own
  // download handling applies. The endpoint answers 422 with a JSON body when
  // any message still has findings, which a plain navigation would render as
  // raw JSON in a new tab -- so check cleanliness here and say so instead.
  if (downloadEl) {
    downloadEl.addEventListener("click", () =>
      busy("Preparing download…", async () => {
        const payload = collectPayload(doc);
        const params = new URLSearchParams();
        for (const [key, value] of Object.entries(payload)) {
          if (value === undefined || value === null || value === "") continue;
          params.set(key, String(value));
        }
        const url = `/api/generate.zip?${params.toString()}`;
        const res = await fetchFn(url);
        if (!res.ok) {
          let detail = `${res.status} ${res.statusText}`;
          try {
            const body = await res.json();
            detail = body.error
              ? body.error
              : `validation errors in: ${Object.keys(body).join(", ")}`;
          } catch (_) {
            /* non-JSON body: keep the status line */
          }
          throw new Error(`Nothing downloaded — ${detail}`);
        }
        const blob = await res.blob();
        const href = URL.createObjectURL(blob);
        const a = doc.createElement("a");
        a.href = href;
        a.download = `${payload.discipline || "bundle"}.zip`;
        doc.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(href);
        say(`Downloaded ${payload.discipline}.zip`);
      }),
    );
  }

  saveEl.addEventListener("click", () =>
    busy("Saving…", async () => {
      const data = await requestJson(fetchFn, "/api/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(collectPayload(doc)),
      });
      const saved = data.saved ?? [];
      renderList(writtenListEl, saved);
      writtenEl.hidden = saved.length === 0;
      say(`Saved ${plural(data.count ?? saved.length, "file")}.`);
    }),
  );

  try {
    await loadPacks();
  } catch (e) {
    formEl.hidden = true;
    say(`Could not reach the generator service: ${e.message}`, { error: true });
  }
}

// Browser bootstrap. Guarded so importing this module under node (tests) has
// no side effects.
if (typeof window !== "undefined" && typeof window.document !== "undefined") {
  const start = () => init(window.document, { fetch: window.fetch.bind(window) });
  if (window.document.readyState === "loading") {
    window.document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
}
