# SOLG28 (LA 2028) Generator Scaffold — Design

**Date:** 2026-07-25
**Status:** approved, ready for planning

## Goal

Make the ODF Message Generator able to target more than one Games, and add
SOLG28 (LA 2028) as a discoverable target that is **wired but inert** until
official LA2028 source documents exist.

The day those documents are dropped into `Rules/SOLG28/`, SOLG28 must start
working with **no code change**. One configuration step remains, and it is
unavoidable: three version strings (`gen`, `codes`, `sport_template`) are
published in the LA2028 GEN document and cannot be derived from the pack, so
they must be copied into `generator/games/SOLG28.yaml`. The app names that step
explicitly in its readiness reasons, so it cannot be forgotten or guessed at.

## Background

The generator is currently welded to SYOG2026 in three places:

1. `generator/packload.py` resolves one pack, defaulting to `Rules/SYOG26`.
2. `generator/envelope.py` hardcodes `GEN_VERSION = "OWG-2026-GEN-V4.5"`,
   `CODES_VERSION = "SYOG-2026-CC-V0.04"`, the `Sport="SYOG-2026-{disc}-1.0"`
   template, and the per-discipline `SOURCES` map.
3. `api/app.py` binds a single module-level `REFDATA = load_refdata()` at
   import time.

Everything else — competition code, discipline list, event structure, venues,
entry counts — is already derived from the pack, so it is Games-agnostic for
free.

On the validator side, `Rules/SOLG28/` already exists as an empty scaffold:
`pack.yaml` with no version set, a `_reference/README.md` documenting the
drop-in workflow, and nothing else. No XSD, no Common Codes, no Data
Dictionaries. No LA2028 source material is available yet.

## Decisions

| Question | Decision |
| --- | --- |
| What does SOLG28 do with no documents? | Wired but inert: selectable, but generation fails with actionable instructions. |
| How is the Games chosen? | Dropdown in the UI; both packs discovered and loaded at startup. |
| Where does Games-specific knowledge live? | A profile file in the generator repo (`generator/games/<PACK>.yaml`). |
| How is readiness determined? | Computed from the loaded pack, never a hand-maintained flag. |

The last two together are the core of the design. The profile file carries only
what cannot be derived — the four constants above. Readiness is derived, so
nobody has to remember to flip a switch when LA2028 lands.

## Components

### New: `generator/games.py`

A `GamesProfile` dataclass holding the Games-specific constants:

- `pack_name` — e.g. `SYOG26`
- `label` — display name, e.g. `Youth Olympic Games 2026`
- `gen` — the `Competition/@Gen` string
- `codes` — the `Competition/@Codes` string
- `sport_template` — e.g. `SYOG-2026-{disc}-1.0`, rendered per discipline
- `sources` — discipline → `@Source` code map
- `default_source` — fallback `@Source`

Loaded from `generator/games/<PACK>.yaml`. Two files ship:

- `SYOG26.yaml` reproduces today's constants byte-for-byte.
- `SOLG28.yaml` carries only what is honestly known: the label and
  `default_source: OGEN`. `gen`, `codes`, and `sport_template` are null,
  meaning "unknown until the documents arrive". A null in any of those three
  is itself a readiness failure (see below).

A pack with no matching profile file is a load error, not a silent default.

### New: `generator/packs.py`

Pack discovery and a `PackRegistry`.

Discovery scans the validator's `Rules/` directory for subfolders containing a
`pack.yaml`, builds each pack once, and pairs it with its profile.

```
PackRegistry.names() -> list[str]
PackRegistry.get(name) -> RefData            # raises if not ready
PackRegistry.status(name) -> PackStatus
PackRegistry.default_name() -> str
```

`PackStatus` is `ready: bool` plus `reasons: list[str]`. Readiness is computed
by inspecting the loaded pack and its profile:

| Condition | Reason emitted when it fails |
| --- | --- |
| An XSD compiles | "No XSD compiles — drop the LA2028 schema file(s) under `Rules/SOLG28/` and set `root_xsd` in `pack.yaml` if the entry point is not `odf2.xsd`." |
| At least one code table loaded | "No Common Codes loaded — drop the LA2028 Common Codes workbook under `Rules/SOLG28/codes/`." |
| At least one discipline | "No disciplines — create `Rules/SOLG28/Disciplines/<CODE>/` per sport and drop each Data Dictionary in." |
| Profile `gen`/`codes`/`sport_template` all non-null | "Games profile incomplete — set `gen`, `codes` and `sport_template` in `generator/games/SOLG28.yaml` once the LA2028 GEN document is available." |

Reason text mirrors the numbered drop-in steps in
`Rules/SOLG28/_reference/README.md`, so an operator who has never read that
README still learns exactly what to do.

**Deliberate behaviour change.** `load_refdata` today *raises* `PackDirError`
when a pack loads empty. That is correct for "you pointed me at a decoy
directory" and wrong for "SOLG28 is legitimately empty and should be listed".
Discovery must therefore tolerate an empty pack and record it as not-ready,
while `PackRegistry.get()` still raises when generation is attempted against
one. `tests/unit/test_packload.py` guards the old behaviour and is updated
deliberately as part of this work.

Discovering **zero** packs remains a hard startup failure — this preserves the
existing property that the app refuses to boot into an empty discipline
dropdown.

### Changed: `generator/envelope.py`

Module-level constants are removed. `build_odfbody` takes the resolved
`GamesProfile` and reads `gen`, `codes`, `sport_template.format(disc=disc)`,
and `sources.get(disc, default_source)` from it. Override precedence is
unchanged: an explicit `Overrides` field still wins over the profile.

### Changed: `api/app.py`

`REFDATA` becomes `REGISTRY`, built at startup. New endpoint:

```
GET /api/packs -> {"default": "SYOG26", "packs": [
  {"name": "SYOG26", "label": "...", "ready": true,  "reasons": [], "disciplines": [...]},
  {"name": "SOLG28", "label": "LA 2028", "ready": false, "reasons": [...], "disciplines": []}
]}
```

`GenerateRequest` gains an optional `pack` field; `/api/generate.zip` gains a
`pack` query parameter. `/api/disciplines` gains the same. Resolution:

- pack omitted → `REGISTRY.default_name()`
- unknown pack → **400** `{"error": "unknown pack: X", "known": [...]}`
- known but not ready → **409** `{"error": ..., "pack": ..., "reasons": [...]}`
- ready → existing code path, unchanged

### Changed: `web/templates/index.html`

A Games dropdown sits above the discipline picker, populated from
`/api/packs`. Selecting a not-ready pack replaces the generate form with the
readiness reasons rendered as a checklist. The discipline dropdown repopulates
on Games change.

### Changed: `generator/export.py`

Adds `--pack SOLG28` alongside the existing `--pack-dir`. `--pack` selects by
name from the registry; `--pack-dir` keeps working as an explicit path escape
hatch. Exporting a not-ready pack exits non-zero with the readiness reasons.
The `--pack-dir` help text stops naming `Rules/SYOG26` specifically.

### Changed: `generator/arc_profile.py`

The embedded archery profile is real SYOG2026 data — 32 M + 32 W athletes
across 47 NOCs, the real 9-session schedule. It is selected only when the
active pack is `SYOG26`. Under any other Games the codes-driven engine is used,
so SYOG2026 archery data can never leak into an LA2028 message.

## Data flow

```
startup
  discover Rules/*/pack.yaml
    -> build pack (tolerant: failures become not-ready + reason)
    -> load generator/games/<name>.yaml
    -> compute PackStatus
  zero packs discovered -> hard failure
  resolve default, first match wins:
    1. ODF_GAMES (error if it names an unknown pack)
    2. the pack ODF_PACK_DIR points at
    3. the alphabetically first ready pack
    4. the alphabetically first pack, ready or not

request
  pack name (or default)
    unknown -> 400
    not ready -> 409 + reasons
    ready -> build_bundle(refdata, discipline, seed, profile, overrides)
               -> self-check against the same pack
               -> emit
```

## Testing

**Regression gate (the important one).** After the refactor, regenerating
SYOG26 at seed 1 must produce output byte-identical to the committed
`samples/`. If a single byte moves, the refactor changed behaviour and is
wrong. The existing all-discipline clean-bundle acceptance test stays green
unchanged.

**Unit**

- `test_games_profile.py` — SYOG26 profile reproduces today's four constants
  exactly; `sport_template` renders per discipline; SOLG28 profile has null
  version strings; a pack with no profile file raises.
- `test_pack_registry.py` — discovery finds SYOG26 and SOLG28; SYOG26 is ready;
  SOLG28 is not ready with reasons naming the XSD, the codes and the
  disciplines; a decoy directory holding only `.ingestion_state.json` is
  discovered as not-ready rather than raising; zero packs raises.
- `test_packload.py` — updated for the tolerant-discovery change.
- `test_envelope.py` — parameterised by profile rather than asserting the
  SYOG2026 literals.

**The drop-in proof.** A test builds a throwaway minimal pack in a temp
directory — a trivial compiling XSD, a one-table codes file, one discipline
folder — plus a complete temp profile, and asserts the registry flips it to
ready and generation proceeds. The whole promise of this design is "it works
the day the documents land"; this is the only way to verify that promise
before the documents exist.

**Integration**

- `GET /api/packs` returns both packs with correct readiness.
- `POST /api/generate` with `pack=SOLG28` returns 409 and reasons.
- `POST /api/generate` with `pack=SYOG26` returns the same bundle as before.
- Unknown pack returns 400.

**Sandbox.** `pytest` and `fastapi` are not guaranteed present; every unit test
above is mirrored in `tests/minirunner.py`, consistent with existing practice.

## Out of scope

- Guessing at LA2028 codes, discipline lists, venue codes, or version strings.
  Nothing fabricated reaches an LA2028 message.
- LA2028 realism profiles equivalent to `arc_profile.py`.
- Per-Games name/culture data in `names.py` — the existing NOC-driven data is
  Games-agnostic.
- The `*_UPDATE` message variants, still out of scope as in v1.
- Changes to the validator repo. `Rules/SOLG28/` is already scaffolded and
  needs nothing further from this work.

## Acceptance criteria

1. `GET /api/packs` lists SYOG26 (ready) and SOLG28 (not ready, with reasons).
2. Selecting SOLG28 in the UI shows the drop-in checklist, not a broken form.
3. Generating against SOLG28 returns 409 with actionable reasons; the CLI exits
   non-zero with the same.
4. SYOG26 output is byte-identical to the committed `samples/` at seed 1.
5. A synthetic minimal pack is reported ready and generates successfully,
   proving the drop-in path.
6. No SYOG2026 constant remains in `envelope.py` or reachable under a non-
   SYOG26 pack.
