// Front-end behaviour tests for web/static/app.js.
//
// Run with: npm test   (node --test tests/web/)
//
// These are deliberately pack-free: they never touch the Python side or the
// validator's Rules/ folder, so they run anywhere node does. The API is faked
// through the injected `fetch`, which is the only external dependency app.js
// has.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { JSDOM } from "jsdom";

import {
  parseCount,
  renderList,
  renderOptions,
  collectPayload,
  init,
} from "../../web/static/app.js";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const TEMPLATE = readFileSync(join(ROOT, "web", "templates", "index.html"), "utf8");

/** A document built from the real template, so tests fail if markup drifts. */
function page() {
  const dom = new JSDOM(TEMPLATE, { runScripts: "outside-only" });
  return dom.window.document;
}

/** A fetch stub. `routes` maps path -> {status, body} or a thrower. */
function fakeFetch(routes) {
  const calls = [];
  const fn = async (path, opts) => {
    calls.push({ path, opts });
    const route = routes[path];
    if (route === undefined) throw new Error(`unexpected fetch: ${path}`);
    if (typeof route === "function") return route();
    return {
      ok: route.status === undefined || route.status < 400,
      status: route.status ?? 200,
      statusText: route.statusText ?? "OK",
      json: async () => route.body,
    };
  };
  fn.calls = calls;
  return fn;
}

const READY_PACKS = {
  default: "SYOG26",
  packs: [
    { name: "SYOG26", label: "Singapore 2026", ready: true, reasons: [], disciplines: ["ARC", "SWM"] },
  ],
};

// ---------------------------------------------------------------------------
// Finding #1 - reason strings must survive to the DOM verbatim
// ---------------------------------------------------------------------------

test("renderList keeps angle brackets in reason text as literal text", () => {
  const doc = page();
  const ul = doc.getElementById("reasons");

  renderList(ul, [
    "No disciplines - create Rules/SOLG28/Disciplines/<CODE>/ per sport.",
    "No Common Codes loaded - drop the .xml with <Codeset> elements.",
  ]);

  const items = [...ul.querySelectorAll("li")];
  assert.equal(items.length, 2);
  assert.match(items[0].textContent, /Disciplines\/<CODE>\/ per sport/);
  assert.match(items[1].textContent, /<Codeset> elements/);
});

test("renderList does not let reason text create elements", () => {
  const doc = page();
  const ul = doc.getElementById("reasons");

  renderList(ul, ["drop it under Rules/<CODE>/ and set <b>root_xsd</b>"]);

  assert.equal(ul.querySelectorAll("code, b").length, 0);
  assert.equal(ul.querySelectorAll("li").length, 1);
});

test("renderList replaces previous content rather than appending", () => {
  const doc = page();
  const ul = doc.getElementById("reasons");
  renderList(ul, ["first"]);
  renderList(ul, ["second"]);
  assert.equal(ul.querySelectorAll("li").length, 1);
  assert.equal(ul.textContent, "second");
});

test("renderOptions writes option labels as text, not markup", () => {
  const doc = page();
  const select = doc.getElementById("pack");

  renderOptions(select, [{ value: "P<1>", label: "Pack <not ready>" }]);

  const opt = select.querySelector("option");
  assert.equal(select.querySelectorAll("option").length, 1);
  assert.equal(opt.value, "P<1>");
  assert.equal(opt.textContent, "Pack <not ready>");
});

// ---------------------------------------------------------------------------
// Finding #4 - count fields must not be silently truncated
// ---------------------------------------------------------------------------

test("parseCount reports a blank field as blank", () => {
  assert.deepEqual(parseCount(""), { state: "blank" });
  assert.deepEqual(parseCount("   "), { state: "blank" });
});

test("parseCount reads plain integers", () => {
  assert.deepEqual(parseCount("5"), { state: "ok", value: 5 });
  assert.deepEqual(parseCount("0"), { state: "ok", value: 0 });
  assert.deepEqual(parseCount(" 12 "), { state: "ok", value: 12 });
});

test("parseCount reads scientific notation at full value, not truncated", () => {
  // <input type="number"> accepts "1e3"; parseInt("1e3", 10) would give 1.
  assert.deepEqual(parseCount("1e3"), { state: "ok", value: 1000 });
});

test("parseCount rejects decimals instead of silently flooring them", () => {
  assert.deepEqual(parseCount("2.7"), { state: "invalid" });
});

test("parseCount rejects negative counts", () => {
  assert.deepEqual(parseCount("-1"), { state: "invalid" });
});

test("parseCount rejects non-numeric text", () => {
  assert.deepEqual(parseCount("abc"), { state: "invalid" });
});

// ---------------------------------------------------------------------------
// collectPayload - blank overrides omitted, counts sent as numbers
// ---------------------------------------------------------------------------

test("collectPayload omits blank text overrides", () => {
  const doc = page();
  doc.getElementById("discipline").innerHTML = '<option value="ARC">ARC</option>';
  doc.getElementById("pack").innerHTML = '<option value="SYOG26">SYOG26</option>';

  const p = collectPayload(doc);

  assert.equal(p.discipline, "ARC");
  assert.equal(p.pack, "SYOG26");
  assert.ok(!("competition_code" in p));
  assert.ok(!("athletes" in p));
});

test("collectPayload maps the status field onto the status key", () => {
  const doc = page();
  doc.getElementById("discipline").innerHTML = '<option value="ARC">ARC</option>';
  doc.getElementById("pack").innerHTML = '<option value="SYOG26">SYOG26</option>';
  doc.getElementById("status_ov").value = "HIS";
  doc.getElementById("athletes").value = "1e3";

  const p = collectPayload(doc);

  assert.equal(p.status, "HIS");
  assert.equal(p.athletes, 1000);
});

test("collectPayload reports invalid counts instead of sending a wrong number", () => {
  const doc = page();
  doc.getElementById("discipline").innerHTML = '<option value="ARC">ARC</option>';
  doc.getElementById("pack").innerHTML = '<option value="SYOG26">SYOG26</option>';
  doc.getElementById("athletes").value = "2.7";

  assert.throws(() => collectPayload(doc), /athletes/i);
});

// ---------------------------------------------------------------------------
// Finding #3 - a failing API call must be visible on the page
// ---------------------------------------------------------------------------

test("a failed pack load shows a message instead of failing silently", async () => {
  const doc = page();
  const fetch = fakeFetch({
    "/api/packs": () => {
      throw new TypeError("fetch failed");
    },
  });

  await init(doc, { fetch });

  const status = doc.getElementById("status").textContent;
  assert.notEqual(status.trim(), "");
  assert.match(status, /could not reach|service|fetch failed/i);
});

test("a 500 from /api/packs is surfaced to the user", async () => {
  const doc = page();
  const fetch = fakeFetch({
    "/api/packs": { status: 500, statusText: "Internal Server Error", body: {} },
  });

  await init(doc, { fetch });

  assert.match(doc.getElementById("status").textContent, /500|internal server error/i);
});

test("an error response from /api/generate is shown as an error, not dumped as output", async () => {
  const doc = page();
  const fetch = fakeFetch({
    "/api/packs": { body: READY_PACKS },
    "/api/generate": { status: 409, body: { error: "pack not ready" } },
  });
  await init(doc, { fetch });

  doc.getElementById("go").click();
  await new Promise((r) => setTimeout(r, 0));

  assert.match(doc.getElementById("status").textContent, /pack not ready/);
  assert.equal(doc.getElementById("out").textContent, "");
});

test("a non-JSON error body still produces a readable message", async () => {
  const doc = page();
  const fetch = fakeFetch({
    "/api/packs": {
      status: 502,
      statusText: "Bad Gateway",
      body: undefined,
      json: null,
    },
  });
  // Force json() to throw the way a proxy's HTML error page would.
  const broken = async () => ({
    ok: false,
    status: 502,
    statusText: "Bad Gateway",
    json: async () => {
      throw new SyntaxError("Unexpected token < in JSON");
    },
  });
  await init(doc, { fetch: fakeFetch({ "/api/packs": broken }) });

  const status = doc.getElementById("status").textContent;
  assert.match(status, /502|bad gateway/i);
  assert.doesNotMatch(status, /undefined/);
});

// ---------------------------------------------------------------------------
// Finding #6 - pending state
// ---------------------------------------------------------------------------

test("generate disables both buttons while the request is in flight", async () => {
  const doc = page();
  let release;
  const pending = new Promise((r) => (release = r));
  const fetch = fakeFetch({
    "/api/packs": { body: READY_PACKS },
    "/api/generate": async () => {
      await pending;
      return { ok: true, status: 200, json: async () => ({ messages: {} }) };
    },
  });
  await init(doc, { fetch });

  doc.getElementById("go").click();
  await new Promise((r) => setTimeout(r, 0));

  assert.equal(doc.getElementById("go").disabled, true);
  assert.equal(doc.getElementById("save").disabled, true);
  assert.match(doc.getElementById("status").textContent, /generating/i);

  release();
  await new Promise((r) => setTimeout(r, 0));

  assert.equal(doc.getElementById("go").disabled, false);
  assert.equal(doc.getElementById("save").disabled, false);
});

test("a successful generate announces completion on the status line", async () => {
  const doc = page();
  const fetch = fakeFetch({
    "/api/packs": { body: READY_PACKS },
    "/api/generate": { body: { messages: { DT_PARTIC: { xml: "<x/>", errors: [] } } } },
  });
  await init(doc, { fetch });

  doc.getElementById("go").click();
  await new Promise((r) => setTimeout(r, 0));

  assert.match(doc.getElementById("status").textContent, /generated/i);
  assert.match(doc.getElementById("out").textContent, /DT_PARTIC/);
});

test("validation errors in the bundle are named on the status line", async () => {
  const doc = page();
  const fetch = fakeFetch({
    "/api/packs": { body: READY_PACKS },
    "/api/generate": {
      body: {
        messages: {
          DT_PARTIC: { xml: "<x/>", errors: [] },
          DT_SCHEDULE: { xml: "<x/>", errors: ["bad element"] },
        },
      },
    },
  });
  await init(doc, { fetch });

  doc.getElementById("go").click();
  await new Promise((r) => setTimeout(r, 0));

  const status = doc.getElementById("status").textContent;
  assert.match(status, /DT_SCHEDULE/);
  assert.doesNotMatch(status, /DT_PARTIC\b/);
});

test("buttons are re-enabled after a failed generate", async () => {
  const doc = page();
  const fetch = fakeFetch({
    "/api/packs": { body: READY_PACKS },
    "/api/generate": () => {
      throw new TypeError("fetch failed");
    },
  });
  await init(doc, { fetch });

  doc.getElementById("go").click();
  await new Promise((r) => setTimeout(r, 0));

  assert.equal(doc.getElementById("go").disabled, false);
  assert.equal(doc.getElementById("save").disabled, false);
});

// ---------------------------------------------------------------------------
// Pack readiness wiring (regression cover for the existing behaviour)
// ---------------------------------------------------------------------------

test("a not-ready pack hides the form and lists its reasons", async () => {
  const doc = page();
  const fetch = fakeFetch({
    "/api/packs": {
      body: {
        default: "SOLG28",
        packs: [
          {
            name: "SOLG28",
            label: "LA 2028",
            ready: false,
            reasons: ["No disciplines - create Rules/SOLG28/Disciplines/<CODE>/ per sport."],
            disciplines: [],
          },
        ],
      },
    },
  });

  await init(doc, { fetch });

  assert.equal(doc.getElementById("notready").hidden, false);
  assert.equal(doc.getElementById("form").hidden, true);
  assert.match(doc.getElementById("reasons").textContent, /<CODE>/);
});

test("an empty pack list is reported rather than throwing", async () => {
  const doc = page();
  const fetch = fakeFetch({ "/api/packs": { body: { default: null, packs: [] } } });

  await init(doc, { fetch });

  assert.match(doc.getElementById("status").textContent, /no .*pack/i);
});

test("a null default with an explanation shows that explanation", async () => {
  const doc = page();
  const fetch = fakeFetch({
    "/api/packs": {
      body: {
        default: null,
        default_error: "unknown pack in ODF_GAMES: NOPE",
        packs: [{ name: "SYOG26", label: "Singapore 2026", ready: true, reasons: [], disciplines: ["ARC"] }],
      },
    },
  });

  await init(doc, { fetch });

  const box = doc.getElementById("default-error");
  assert.equal(box.hidden, false);
  assert.match(box.textContent, /unknown pack in ODF_GAMES: NOPE/);
  assert.equal(doc.getElementById("pack").value, "SYOG26");
});

test("a missing default_error does not render the string undefined", async () => {
  const doc = page();
  const fetch = fakeFetch({
    "/api/packs": {
      body: {
        default: null,
        packs: [{ name: "SYOG26", label: "Singapore 2026", ready: true, reasons: [], disciplines: ["ARC"] }],
      },
    },
  });

  await init(doc, { fetch });

  assert.doesNotMatch(doc.getElementById("default-error").textContent, /undefined/);
});

// ---------------------------------------------------------------------------
// The output had no exit path: /api/generate.zip existed and nothing called it
// ---------------------------------------------------------------------------

/** Fire a click and let the handler's promise chain settle. */
async function click(doc, id) {
  doc.getElementById(id).dispatchEvent(
    new doc.defaultView.Event("click", { bubbles: true }),
  );
  await new Promise((r) => setTimeout(r, 0));
}

test("the page offers a download control", async () => {
  const doc = page();
  await init(doc, { fetch: fakeFetch({ "/api/packs": { body: READY_PACKS } }) });
  assert.ok(doc.getElementById("download"), "no download button in the template");
});

test("download requests the zip endpoint with the chosen discipline", async () => {
  const doc = page();
  const base = fakeFetch({ "/api/packs": { body: READY_PACKS } });
  const seen = [];
  // The zip URL carries a query string, so it is matched by prefix rather
  // than by the exact-path table fakeFetch uses.
  const wrapped = async (path, opts) => {
    if (path.startsWith("/api/generate.zip")) {
      seen.push(path);
      return { ok: true, status: 200, blob: async () => new doc.defaultView.Blob(["x"]) };
    }
    return base(path, opts);
  };
  await init(doc, { fetch: wrapped });
  doc.getElementById("discipline").value = "SWM";
  await click(doc, "download");

  assert.equal(seen.length, 1, `expected one zip request, got ${seen.length}`);
  assert.match(seen[0], /discipline=SWM/);
});

test("a 422 from the zip endpoint explains itself instead of downloading", async () => {
  const doc = page();
  const base = fakeFetch({ "/api/packs": { body: READY_PACKS } });
  const wrapped = async (path, opts) => {
    if (path.startsWith("/api/generate.zip")) {
      return {
        ok: false,
        status: 422,
        statusText: "Unprocessable Entity",
        json: async () => ({ DT_PARTIC: ["some finding"] }),
      };
    }
    return base(path, opts);
  };
  await init(doc, { fetch: wrapped });
  await click(doc, "download");

  const status = doc.getElementById("status").textContent;
  assert.match(status, /nothing downloaded/i);
  assert.match(status, /DT_PARTIC/);
});

// ---------------------------------------------------------------------------
// A 500 has its traceback in the service window, which the page cannot see
// ---------------------------------------------------------------------------

test("a 500 with no JSON body points at the service window", async () => {
  const doc = page();
  const base = fakeFetch({ "/api/packs": { body: READY_PACKS } });
  const wrapped = async (path, opts) => {
    if (path === "/api/generate") {
      return {
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        json: async () => { throw new Error("not json"); },
      };
    }
    return base(path, opts);
  };
  await init(doc, { fetch: wrapped });
  doc.getElementById("form").dispatchEvent(
    new doc.defaultView.Event("submit", { bubbles: true, cancelable: true }),
  );
  await new Promise((r) => setTimeout(r, 0));

  const status = doc.getElementById("status").textContent;
  assert.match(status, /ODF service/i, `status was: ${status}`);
});

// ---------------------------------------------------------------------------
// A control and a result must not disagree
// ---------------------------------------------------------------------------

test("changing the discipline clears the previous bundle", async () => {
  const doc = page();
  const base = fakeFetch({ "/api/packs": { body: READY_PACKS } });
  const wrapped = async (path, opts) => {
    if (path === "/api/generate") {
      return {
        ok: true, status: 200,
        json: async () => ({
          pack: "SYOG26", discipline: "ARC", seed: 1, seed_requested: 1,
          clean: true,
          messages: { DT_PARTIC: { xml: "<OdfBody/>\n", errors: [] } },
        }),
      };
    }
    return base(path, opts);
  };
  await init(doc, { fetch: wrapped });
  doc.getElementById("form").dispatchEvent(
    new doc.defaultView.Event("submit", { bubbles: true, cancelable: true }),
  );
  await new Promise((r) => setTimeout(r, 0));
  assert.notEqual(doc.getElementById("manifest").hidden, true,
    "precondition: a bundle should be on screen");

  const discipline = doc.getElementById("discipline");
  discipline.value = "SWM";
  discipline.dispatchEvent(new doc.defaultView.Event("change", { bubbles: true }));

  assert.equal(doc.getElementById("manifest").hidden, true,
    "stale ARC manifest still showing after switching to SWM");
  assert.equal(doc.getElementById("out").textContent, "");
});

// ---------------------------------------------------------------------------
// The retried seed is the one that made the data on screen
// ---------------------------------------------------------------------------

test("the scope line names the seed when it is not the one asked for", async () => {
  const doc = page();
  const base = fakeFetch({ "/api/packs": { body: READY_PACKS } });
  const wrapped = async (path, opts) => {
    if (path === "/api/generate") {
      return {
        ok: true, status: 200,
        json: async () => ({
          pack: "SYOG26", discipline: "ARC", seed: 4, seed_requested: 1,
          clean: true,
          messages: { DT_PARTIC: { xml: "<OdfBody/>\n", errors: [] } },
        }),
      };
    }
    return base(path, opts);
  };
  await init(doc, { fetch: wrapped });
  doc.getElementById("form").dispatchEvent(
    new doc.defaultView.Event("submit", { bubbles: true, cancelable: true }),
  );
  await new Promise((r) => setTimeout(r, 0));

  const scope = doc.getElementById("readout-scope").textContent;
  assert.match(scope, /seed 4/, `scope was: ${scope}`);
  assert.match(scope, /asked 1/);
});

test("the scope line stays quiet when the seed matches", async () => {
  const doc = page();
  const base = fakeFetch({ "/api/packs": { body: READY_PACKS } });
  const wrapped = async (path, opts) => {
    if (path === "/api/generate") {
      return {
        ok: true, status: 200,
        json: async () => ({
          pack: "SYOG26", discipline: "ARC", seed: 1, seed_requested: 1,
          clean: true,
          messages: { DT_PARTIC: { xml: "<OdfBody/>\n", errors: [] } },
        }),
      };
    }
    return base(path, opts);
  };
  await init(doc, { fetch: wrapped });
  doc.getElementById("form").dispatchEvent(
    new doc.defaultView.Event("submit", { bubbles: true, cancelable: true }),
  );
  await new Promise((r) => setTimeout(r, 0));

  assert.doesNotMatch(doc.getElementById("readout-scope").textContent, /seed/);
});
