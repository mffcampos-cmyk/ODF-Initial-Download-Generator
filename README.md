# ODF Message Generator

Generates DT_PARTIC, DT_PARTIC_TEAMS, DT_ENTRIES and DT_SCHEDULE messages for
a chosen discipline, built from the validator's own rule pack and verified
against the `odf_validator` engine before anything is written.

## What this repository ships

The application, the generator, the tests, a 206-file corpus of generated
sample output under `samples/`, and the SYOG26 rule pack at `Rules/SYOG26` —
authored rules plus the SYOG2026 schema, copied from
[ODF-Validator](https://github.com/mffcampos-cmyk/ODF-Validator) at the commit
named in `Rules/SYOG26/PROVENANCE.md`. The schema carries two deliberate
changes from the IOC's published copy, both explained there.
The schema files are the IOC's, redistributed with those corrections and
outside this repository's MIT grant — see `LICENSE`.

It does not ship the IOC's Common Codes workbook or the 25 Data Dictionaries.
They are published by the IOC, they are revised, and they are fetched on
demand — the first run converts one PDF per discipline, so give it a few
minutes:

```bash
python -m generator.sources
```

A clone that has not run that command is not broken; it is un-imported, and it
says so.

### What "verified" covers, and what it does not

Every generated message is run through the real validator pipeline and the
exporter refuses to write one that still has findings. That covers the envelope,
XSD conformance, code membership, and the core conventions.

It does **not** cover four things the engine has no way to check — it has no
length, cardinality, sort-order or datetime-coherence primitive, and the bundled
XSDs carry no `maxLength` facet. Messages violating all four once validated
clean and shipped into `samples/`: sessions whose `EndDate` preceded their
`StartDate`, `DT_ENTRIES` with zero `Entry` elements, unsorted
`DT_PARTIC_TEAMS`, and 19 over-length `TVTeamName` values. The generator now
enforces these itself:

- **Lengths** — `generator/lengths.py`, keyed on (element, attribute) because
  `Value`, `Name` and `Code` each have several limits depending on the element.
  Description-matched attributes (`VenueName`, `LocationName`,
  `Unit/ItemName`) are deliberately excluded: they must equal the code's
  ENG_Description exactly, so truncating one would either *break* a rule that
  does exist or hand the reader a wrong name.
- **Datetime coherence** — real `datetime` arithmetic, asserted by
  `tests/unit/test_schedule_times_are_coherent.py`.
- **Sort order** — `DT_PARTIC_TEAMS` sorts by `Team@Code` per GEN 2.1.3.6.

One conflict in the source is resolved deliberately, and it is worth
understanding before trusting the output. The DD specifies
`Unit/ItemName@Value` as both `S(40)` *and* the Common Codes ENG description,
and Common Codes ships descriptions longer than 40 characters. The generator
keeps the description whole and leaves the width unenforced;
`Rules/SYOG26/pack.yaml` records that as a `length_exempt` entry, so the
decision is visible from the pack rather than buried in code.

Measurement decided it. 149 of the 4,709 `EVENT_UNIT` descriptions exceed 40
characters (TTE 56, JUD 36, WST 27, RCB 26, SWM 3, PCO 1), and cutting them
does two things:

- It changes the meaning. `"Women -44 kg Repechage Second Round of 16"` (41)
  becomes `"...Second Round of 1"` — a different round, stated confidently.
- Worse, it **merges units that were distinct**. Truncation collapses 16
  description groups covering 124 unit codes. The clearest case is rowing:
  `"Mixed Double Sculls Last 16 - Knockout 1"` and
  `"Mixed Double Sculls Last 16 - Knockout 1 - Re-Row"` truncate to the same
  string, so a race and its re-row become indistinguishable by name.

Against that, the `S(40)` violation is the lesser fault. A consumer keys on
`@Code` and `@UnitNum`, which stay distinct either way; the name is what a
human reads, and a name that is wrong reads as authoritative in a way a name
that is long does not. `tests/unit/test_lengths.py` asserts that every
generated `ItemName` equals its code's description in full, so the output
cannot drift back into truncation unnoticed.

If your consumer enforces the width, shorten these descriptions deliberately
rather than mechanically — the generator will not do it for you.

### Data Dictionary obligations

`generator/obligations.py` checks generated output against the M/O obligations
the validator derives from the Data Dictionaries (`pack.obligations`). It
**reports** and never fills, for a reason worth reading before anyone is
tempted to make it fill:

obligations are keyed on (doc_type, element, attribute), and an element name is
not an element. `<Description>` maps to 13 complexTypes in the schema, two of
which appear in one DT_ENTRIES message — `Entry/Description` (a team entry:
`@TeamName`) and `Athlete/Description` (a person: `@FamilyName`, `@Gender`,
`@Organisation`). Both arrive under the one key, so the unrestricted set
demands `@TeamName` of every athlete and `@FamilyName` of every team at once.
Emitting it across the 24 buildable disciplines would put a team name on 2,458
athletes and a family name on 193 teams — plausible-looking, wrong, and
invisible to the validator, since no rule checks whether an attribute belongs
on the element carrying it.

The subset the validator will enforce (`enforceable_only=True`) is, measured on
this project's four message types, **empty**: nothing the DDs require that the
schema declares unambiguously and does not already require itself. So there is
nothing an emitter could safely add — and nothing for `CORE_DD_MANDATORY_ATTR`
to report on this output either.

```
python -m generator.obligations [DISCIPLINE ...]
```

Exit 1 on an enforceable omission; the ambiguous residue is printed with the
parent tag that tells the two `<Description>`s apart. Both halves are pinned by
`tests/unit/test_obligation_coverage.py`, so a builder that stops emitting a
required attribute is caught rather than absorbed into the noise.

A bundle is validated as a batch, not as a pile of separate files: the messages
of one attempt share a validator `ValidationContext`, which is what lets the
engine's `cross_message` rules compare them (each retry gets a fresh one, so a
seed that was thrown away leaves nothing behind). No rule in the shipped
SYOG26 pack uses that primitive yet, so today this changes no finding — it
means a bundle-level rule starts working the moment one is written, instead of
silently returning nothing.

A "clean" result is only meaningful against a specific validator revision; see
Setup for the known-good one and why it matters.

## Realism model

Output follows the conventions of the real SYOG26 initial download (received
2026-09-23) and the ODF data dictionaries:

- Full 34-char discipline RSC in `@DocumentCode` and `Discipline@Code`
  (e.g. `ARC-------------------------------`).
- `Participant@Parent` = `@Code`; 7-digit IDs from 9000001; `MainFunctionId`,
  `Nationality`, passport names, and PSCB names (athletes only) included.
- Name conventions: `PrintName` = "FAMILY Given", `PrintInitialName` =
  "FAMILY EB" (one initial per given-name part, no dots), `TVName` = "Given
  FAMILY", `TVInitialName` = "E.B. FAMILY"; cut to the GEN DD widths
  (PrintName/TVName 35, PrintInitialName/TVInitialName/TVFamilyName 18).
- Delegations are drawn only from NOCs the Common Codes mark as participating
  (`Participation = P`), never historical ones such as EUN or URS.
- Realistic, culture-aware names per NOC (`generator/names.py`) and plausible
  birth dates (athletes 2009–2011, officials 1961–1996).
- Header, from `generator/games/SYOG26.yaml`: `Gen="OWG2026-GEN-4.6"` (the
  GEN DD reference); `Sport` = each discipline DD's own reference
  (`SYOG-2026-ARC-1.2`, `SYOG-2026-EQU-EJP-1.0`, ...); `Codes="YOG-2026-2.4"`,
  the release read from the loaded workbook's file name. `FeedFlag="P"`.
  `Source` is per message type: `SEQ` for DT_PARTIC, DT_PARTIC_TEAMS and
  DT_ENTRIES, `OSM` for DT_SCHEDULE.
- Every team is `TeamType="ORG"`; schedule units are `PhaseType="3"`
  (competition) and victory ceremonies `"6"`. DT_ENTRIES carries no `IFId`:
  that is the federation's identifier, which the generator does not have.
- **ARC** uses an embedded real-life profile (`generator/arc_profile.py`):
  32 M + 32 W athletes across 47 NOCs, one coach per NOC + 4 judges
  (115 participants), 17 mixed teams, and the real 9-session / 83-unit
  schedule — counts match the Common Codes EVENT_UNIT tables. Venue/Location
  use the Common Codes members `SAW` / `AR1` (the real feed's `AWA` is not in
  Common Codes).
- **Every other discipline** is derived from the Common Codes tables
  (`generator/eventstructure.py`): the schedule contains exactly the
  scheduled competitive units from EVENT_UNIT (real unit RSCs, item names,
  medal flags, prelims-before-finals ordering), venue/location come from the
  LOCATION table, and athlete/team counts follow the event structure —
  bracket events get 2 x the matches of the largest elimination round (JUD
  R32 -> 32 entrants per weight class), heats get 8 x lanes, group phases 4
  per group, direct finals 8; multi-event disciplines (SWM/ATH) share a
  per-gender athlete pool. Team squads are sized from the event code
  (TEAM2/TEAM5). One coach per delegation plus judges are added on top.

## Live-operations realism options

Four options (off by default — the baseline stays strictly Common-Codes-
driven) reproduce what the real venue feeds look like, for every discipline.
They are available as checkboxes in the web UI, fields on `/api/generate` and
`/api/save`, query params on `/api/generate.zip`, and CLI flags on
`python -m generator.export`:

- `realistic_entries` (`--realistic-entries`): qualification-scale entry
  lists (24–120 entries per non-bracket event, varying per event, with a
  correspondingly larger athlete pool). Bracket events keep their bracket
  size; team events keep their codes-derived slots.
- `seeded_heats` (`--seeded-heats`): schedule heats become
  `ceil(entries / 8 lanes)` per event, drawing real unit RSCs from the codes'
  full heat pool (e.g. 18 defined per SWM event). Timed-final events
  (400m/800m freestyle) correctly keep no heats.
- `victory_ceremonies` (`--victory-ceremonies`): VICT units from the codes
  are scheduled after each event's final.
- `historical_athletes` (`--historical-athletes`): adds Status=HIS athletes
  with A-prefixed IDs (per spec) and adult birth dates; they appear in
  DT_PARTIC but are never entered in events.

Notes: ARC uses its embedded real-life schedule profile; enabling a
schedule-affecting option switches ARC to the codes-driven engine so the
options apply there too. Header overrides (competition code, source,
Gen/Sport/Codes versions, status, coach count) are also honoured end-to-end.

### Where the count overrides have less effect than you'd expect

Both cases are properties of the discipline's codes, not bugs — but neither is
visible in the UI, so they are worth knowing:

- **`athletes` in a team-only discipline.** BK3, BS5, FBS, HBB, RU7 and VBV
  schedule only team events, so there is no individual event to enter a loose
  athlete into. They are still generated and still listed in DT_PARTIC — an
  athlete list is not an entry list — but they appear in no DT_ENTRIES. (This
  previously looked like it worked, because every entry went into one
  discipline-level message whose `@DocumentCode` was the discipline RSC, which
  GEN 2.1.5.2 does not permit.)
- **`coaches` in a discipline that defines no coach role.** 21 of the 25
  disciplines publish no `Category="C"` row in CC@DISCIPLINE_FUNCTION, so there
  is no valid function code to assign and the field does nothing — only BS5,
  FBS, RU7 and TTE define one. ATH, CRD, JUD, RCB and SKB define no officials
  at all.

## Multiple Games

The generator discovers every rule pack under `Rules/`
and offers them in a **Games** dropdown. Two ship today:

- **SYOG26** — Youth Olympic Games 2026. Ready; this is the default.
- **SOLG28** — LA 2028. Discovered but **not ready**: no official LA2028
  documents exist yet, so generating against it returns HTTP 409 (and the CLI
  exits 2) listing exactly what is missing.

Games-specific message conventions live in `generator/games/<PACK>.yaml`:
`gen`, `codes`, `sport_template` and the per-discipline `sources` map. Every
other constraint is derived from the pack itself.

To bring SOLG28 online:

1. Drop the LA2028 XSD, Common Codes workbook, and per-discipline Data
   Dictionaries into `Rules/SOLG28/`, laid out as `Rules/SYOG26/` already is:
   the workbook under `codes/`, each discipline's Data Dictionary under
   `Disciplines/<CODE>/`, the schema under `xsd/`. Authored rules go under
   `rules/` and `Disciplines/<CODE>/rules/`; `Rules/SYOG26/` is the worked
   example to copy the shape from.
2. Copy `Gen`, `Codes` and the `Sport` template from the LA2028 GEN document
   into `generator/games/SOLG28.yaml`. These cannot be derived — do not guess
   them. The `sport_template` value must contain the literal placeholder
   `{disc}` (not `{discipline}` or any other name) — e.g. `LA28-{disc}-1.0` —
   which the generator substitutes with each discipline code; a template that
   doesn't render with `{disc}` fails to load, and one without the
   placeholder at all is treated as incomplete rather than silently reused
   for every discipline.
3. Restart the app. Readiness is recomputed from what is actually present;
   there is no flag to flip.

Select a Games from the CLI with `--pack SOLG28`, or set `ODF_GAMES=SOLG28` to
change the startup default. `ODF_PACK_DIR` keeps working and determines the
default when `ODF_GAMES` is unset.

## Setup

```bash
pip install -e ".[dev]"
python -m generator.sources
uvicorn api.app:app
```

That is the whole of it. What each step does, and why the middle one exists:

1. **Install.** This brings the validation engine with it, pinned to one
   commit (see `pyproject.toml`). The generator does not merely use the
   validator — every message it emits is run through the real pipeline and
   the exporter refuses to write one with findings — so the engine is a hard
   dependency, and "validates clean" is a claim about that revision.
2. **Fetch the source documents.** This repository ships the rule pack at
   `Rules/SYOG26`: the authored rules and the SYOG2026 schema. It does not
   ship the Common Codes workbook or the 25 Data Dictionaries, which the IOC
   publishes and revises and which are not ours to redistribute. One command
   fetches both and ingests them. Expect it to take a while the first time: it
   converts one PDF per discipline.

   Both halves are needed, and the Data Dictionaries are the less obvious one.
   A pack's disciplines are derived from the DD files under
   `Disciplines/<CODE>/` and from nothing else, so the authored rules shipped
   here contribute none. Until the import has run, the pack has no disciplines
   and no code tables, and the application refuses to start with an error that
   says which half is missing. `--codes-only` refreshes the workbook of a pack
   that has already been imported.
3. **Run.** Open http://127.0.0.1:8000/.

The package is named `odf-message-generator`; the repository is named for what
it produces.

### Choosing a pack

`ODF_GAMES=SOLG28` selects a different shipped pack by name, and
`ODF_PACK_DIR` points at a pack directory anywhere on disk — a checkout of the
validator, say, if you already keep one. Neither is needed for the default.

## Run
`uvicorn api.app:app`

## Export messages to files

Generated messages are exported to an `output/` folder **inside this project**,
one subfolder per discipline. `output/` is gitignored:

```
output/<DISCIPLINE>/DT_PARTIC.xml
output/<DISCIPLINE>/DT_PARTIC_TEAMS.xml
output/<DISCIPLINE>/DT_ENTRIES_<EVENT>.xml   (one file per event)
output/<DISCIPLINE>/DT_SCHEDULE.xml
output/<DISCIPLINE>/MANIFEST.json
```

`samples/` is a different thing: the committed reference corpus, used to eyeball
what a change did to generated output. It is not written to by Save or by a
default export — regenerating it is a deliberate `--out-dir samples`.

It is generated from whatever Common Codes the pack holds, so a new workbook
dates it. That is not hypothetical: v_2_4 retired the `Schedule = "S"` flag
that 463 unit rows carried, and SWM's schedule went from 94 units to 492 —
every heat it should have been emitting all along. A new `ORGANISATION` row in
the same release reshuffled the NOC pool, so all 206 files changed. Regenerate
after a workbook lands:

```bash
python -m generator.sources
python -m generator.export --all --seed 1 --no-manifest --out-dir samples
```

### MANIFEST.json

Written beside the messages, recording what produced them. Three of those facts
used to be lost the moment the files hit disk:

- **`seed_used`** alongside `seed_requested`. The retry loop walks seed..seed+4
  and returns whichever came clean, so the seed you asked for is not
  necessarily the seed you got — and generation is seed-deterministic, which
  makes it the difference between reproducible output and a guess.
- **`pack.sources`** — the digests, URLs and publication references of the IOC
  documents behind the pack, lifted from the validator's own `.sources.json`.
  "Which Common Codes version produced this sample" then has an answer that
  does not depend on anyone remembering.
- **`validator.revision`** — the commit pip recorded when it installed the
  validator from the pinned VCS reference, with `source` naming where the
  answer came from. Against a validator checkout instead, it is that
  checkout's HEAD, with `dirty` set when its working tree has uncommitted
  changes. When neither applies the value is `null` and `reason` says why; a
  manifest asserting a SHA it never read would be worse than one admitting it
  does not know.

Plus `options` (the overrides in force) and a SHA-256 per message, so a file
edited after export stops matching its own manifest.

`--no-manifest` skips it. Use that when regenerating `samples/`, where a
timestamp changing on every run is diff noise.

Export one discipline, or every discipline:

```powershell
python -m generator.export --discipline ARC
python -m generator.export --all
```

By default the exporter refuses to write messages that still carry validation
errors. Options: `--seed N` (default 1), `--out-dir PATH` (default `output/`),
`--allow-unclean` to write anyway, `--no-manifest` to skip `MANIFEST.json`.

## Test
`pytest -v`

For a dependency-light check that doesn't require `pytest`/`fastapi`
installed, use the bundled unit runner instead:
`python -m tests.minirunner`

It calls each test with no arguments, so tests taking a pytest fixture
(`tmp_path`, `monkeypatch`, `pack`) are reported SKIP and left to `pytest`.
They used to be reported FAIL, which cost the runner its signal: two permanent
red lines meant "2 failed" was the healthy state, and a real regression
arriving as a third looked the same as the noise.

### Front-end tests

The operator page's JavaScript lives in `web/static/app.js` and is covered by
`tests/web/app.test.mjs`, which drives it against a jsdom document with a
stubbed `fetch`:

```
npm install
npm test
```

Both this suite and `tests/unit/test_web_template.py` (which asserts the
page's markup) are **pack-free** — they never load `ODF_PACK_DIR`, so they run
without the validator checkout present. `npm install` is only needed to run
them; the app itself has no JavaScript build step and ships `app.js` as-is.
