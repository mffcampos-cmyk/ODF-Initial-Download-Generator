# Initial Download ODF Message Generator — Design Spec

**Date:** 2026-07-16
**Status:** Approved (design), pending implementation plan
**Related:** `INITIAL_DOWNLOAD_GENERATOR_CONTEXT.md` (project context / compliance model)

## 1. Summary

A standalone webapp that **randomly generates fully ODF-compliant** "initial
download" messages — `DT_PARTIC`, `DT_PARTIC_TEAMS`, `DT_ENTRIES`, `DT_SCHEDULE` —
for a discipline the operator selects. The operator provides no data: the app
synthesizes a coherent, plausible, schema- and rule-valid dataset from the
reference files (XSD, Common/Sport Codes, Data Dictionaries) already used by the
**ODF Validator Webapp 2**, and emits the four messages. Every emitted message
must pass `odf_validator.Pipeline.run` against the same pack with **zero
error-severity findings**.

## 2. Goals / non-goals

**Goals (v1)**
- Operator picks a discipline; app generates all four messages for it as a bundle.
- All disciplines in the SYOG26 pack are supported.
- Compliance guaranteed both **by construction** and by the validator self-check.
- Internally coherent bundle: `DT_ENTRIES` references participants/teams that
  appear in `DT_PARTIC` / `DT_PARTIC_TEAMS`; schedule units use the discipline's
  RSCs.

**Non-goals (v1)**
- No `*_UPDATE` messages, no `DocumentSubtype=SYNC` (plain bulk only).
- No operator-supplied data, no editing of existing messages.
- No persistence/database; generation is stateless per request.

## 3. Chosen approach — A: constraint-driven generation + self-check safety net

Derive each field's constraints from the reference files and generate values that
satisfy them **by construction**:
- Coded attributes ← drawn at random from the pack's `CodeRegistry` tables (valid
  by definition, discipline-partitioned where applicable, e.g. `SC@TeamType@ARC`).
- Typed scalars ← synthesized to match the XSD simple type (patterns/enums/lengths).
- Cardinalities ← required children always present; optional children/attributes
  included with a random subset.

Then run each message through `odf_validator.Pipeline.run` as a safety net; on any
error-severity finding, regenerate the offending message (bounded retries) and
surface any residual findings. Approach B's "validate-and-fix" is retained only as
this bounded safety net, not as the primary mechanism.

## 4. Reuse boundary

Separate repo/app `odf-message-generator`, depending on `odf_validator` as a
packaged library. It imports:
- the pack loader (`build_ruleset_pack`) → `RulePack` (compiled XSD `schema`,
  `codes: CodeRegistry`, `rules`, `disciplines`);
- `Pipeline.run(xml, pack)` for the self-check.

No rule or validation logic is reimplemented. The generator's own responsibility
is *construction* (build the tree, pick codes, format values); *judgment* stays in
the validator.

## 5. Architecture

Web-free `generator/` core package + thin `api/` (FastAPI) + `web/` layer, mirroring
the validator's module hygiene.

```
generator/
  refdata.py       # load pack once; expose code tables + XSD-derived constraints
  fields.py        # value synthesizers (one per XSD type/pattern)
  dataset.py       # build one coherent per-discipline synthetic pool
  envelope.py      # shared message envelope + 34-char DocumentCode/RSC assembly
  serialize.py     # lxml -> XML, enforcing omit-empty (no empty attr/element)
  builders/
    partic.py         # DT_PARTIC
    partic_teams.py   # DT_PARTIC_TEAMS
    entries.py        # DT_ENTRIES
    schedule.py       # DT_SCHEDULE
  selfcheck.py     # wrap Pipeline.run; bounded regenerate-on-error
  model.py         # dataclasses: Noc, Participant, Team, Event, ScheduleUnit, ...
api/               # FastAPI: mirrors the validator's api/
web/               # discipline picker -> Generate -> download (single or zip)
tests/
  unit/            # per-builder clean self-check across all disciplines (seeded)
  integration/     # web layer round trip
```

### 5.1 Data flow

```
pick discipline
  -> load pack (refdata)
  -> build coherent dataset pool (dataset)
  -> for each DocumentType: builder renders lxml tree from the pool
  -> serialize (omit-empty)
  -> selfcheck (Pipeline.run)
       clean  -> offer download (single files or zip bundle)
       errors -> regenerate that message (bounded retries); surface residuals
```

### 5.2 Coherent dataset pool (`dataset.py`)

For the chosen discipline, build one pool reused by all four builders:
- a set of NOC/Organisation codes (from the ORGANISATION/NOC code table);
- N participants (athletes + officials) with stable `Code`s;
- M teams (where the discipline has team events), each referencing participant
  codes in its composition;
- a set of events/RSCs and schedule sessions/units for the discipline.

Builders render *views* over this pool so cross-message references line up.

## 6. Field synthesis rules (from the reference files)

Derived from `Rules/SYOG26/xsd/*` and the code tables. The generator MUST honor:

**Envelope (`bodyType`)** — all required, non-empty:
`CompetitionCode` (∈ `COMPETITION_CODE`), `DocumentCode` (34-char RSC),
`DocumentType` (the target), `Version` (positive int, start 1),
`FeedFlag` ∈ {`P`,`T`}, `Date`/`LogicalDate` = `YYYY-MM-DD` (`odfDateType`
pattern `[0-9]{4}-[0-9]{2}-[0-9]{2}`), `Time` (string), `Source` (string).

**Competition** — `@Gen` required, `@Codes` required, `@Sport` optional; child
`Discipline@Code` ∈ `DISCIPLINE` code table.

**DocumentCode / RSC** — `[A-Z0-9]{3}[A-Z0-9-]{31}`, **exactly 34 chars**
(`CORE_DOCCODE_RSC_FORMAT` + XSD `rscType` length 34 for Unit `@Code`). Compose as
discipline(3) + random `[A-Z0-9-]` padded/truncated to length 34.

**`participantType`** (DT_PARTIC) — required attrs: `Code`, `Parent`, `Status`,
`FamilyName`, `PrintName`, `PrintInitialName`, `TVName`, `TVInitialName`,
`TVFamilyName`, `Gender` (∈ `[MFX]`), `Organisation`. Required child
`Discipline` (`registeredDisciplineType`, `@Code` required). `BirthDate` optional
`odfDateType`. Optional attrs included at random.

**`teamType`** (DT_PARTIC_TEAMS) — required attrs: `Code`, `Status`,
`Organisation`, `ShortName`, `TVTeamName`, `Gender` (∈ `[MWXGO]`), `TeamType`
(∈ `SC@TeamType@<DISC>` where defined). Required child `Discipline`; optional
`Composition` with `Team`/athlete references drawn from the pool.

**`EntriesEntry`** (DT_ENTRIES) — required attrs: `Code`, `Type` (∈ {`A`,`T`,`H`}),
`Organisation`, `SortOrder` (integer, **unique among sibling Entries**). Entry
`Code`s reference pool participants/teams. Optional children (Description, Coaches,
ExtendedEntry, Composition) at random.

**Schedule (`SessionType` + `scheduleUnitType`)** (DT_SCHEDULE) —
`Session` required attrs: `Venue`, `VenueName`, `SessionCode`, `StartDate`,
`EndDate` (`xs:dateTime`); required child `SessionName@Language`.
`Unit` (`scheduleUnitType`) required attrs: `Code` (34-char `rscType`),
`PhaseType`, `ScheduleStatus` (∈ scheduleStatusType enum); required child
`ItemName@Language`. `Medal` optional ∈ {0,1,2,3}; `SortOrder`/`Order` integer.

**Core conventions (immutable, apply to every message)** —
- Never emit an attribute/element with an empty value (omit it) —
  `CORE_NO_EMPTY_ATTRS` / `CORE_NO_EMPTY_ELEMENTS`. Enforced in `serialize.py` so
  it is structurally impossible.
- `@SortOrder` integer ≥ 1 and unique among siblings — `CORE_SORTORDER_POSINT` /
  `CORE_SORTORDER_UNIQUE`.
- `@ItemNum` non-negative integer; `RankEqual` only `Y`; `IFRANK` no `-` (N/A for
  these four but the serializer/synthesizers must not violate them).

## 7. Error handling

- **Self-check gate:** a message is releasable only when `Pipeline.run` returns
  zero `error`-severity findings. Warnings/info are surfaced but do not block.
- **Bounded regeneration:** on an error finding, regenerate that single message up
  to K times (K configurable, default 5). If still failing, return the message
  plus its findings to the operator rather than a false "clean" — never claim
  compliance without a clean run.
- **Pack load failure / XSD inactive:** if the pack's XSD does not compile
  (`CORE_XSD_INACTIVE`), generation is refused with a clear message — we cannot
  guarantee structural compliance without an active schema.
- **Determinism:** all synthesis goes through a single seeded RNG; the API accepts
  an optional seed so a bundle is reproducible for debugging and tests.

## 8. Testing strategy (TDD)

- **Per builder, per discipline (property-style):** for every discipline in the
  pack, generate N messages with a fixed seed and assert `Pipeline.run` returns
  zero error-severity findings. This is the primary acceptance test and the direct
  encoding of "compliant the same way the validator enforces."
- **Invariants:** RSC/DocumentCode length == 34; serializer never emits an empty
  attribute or element; sibling `SortOrder` values are unique; envelope attrs all
  present and non-empty; dates match `odfDateType`.
- **Referential consistency:** every `DT_ENTRIES` competitor `Code` exists in the
  same bundle's `DT_PARTIC`/`DT_PARTIC_TEAMS`.
- **Field synthesizers:** unit tests that each `fields.py` synthesizer's output
  matches its XSD type (gender pattern, date pattern, enum membership, code-table
  membership).
- **Web/API integration:** pick discipline → generate → download bundle; response
  contains four well-formed messages and a zero-error self-check summary.
- **Sandbox note:** `pytest`/`fastapi` may be unavailable in the sandbox and git
  can corrupt on `NUL` paths (carried over from the validator project). The plan
  provides a dependency-light "minirunner" fallback and side-effect cleanup, as the
  validator repo does.

## 9. Acceptance criteria (v1)

1. Operator selects any pack discipline and generates all four messages.
2. Every emitted message passes `odf_validator.Pipeline.run` with zero
   error-severity findings (structural + code + semantic).
3. All coded values come from the pack's code registry; no hand-invented codes.
4. The serializer provably never emits empty attributes or elements.
5. The four messages in a bundle are internally consistent (shared pool).
6. Each builder has a per-discipline seeded self-check test; the web layer has a
   generate→download integration test.

## 10. Resolved decisions

- Input: app-generated random data; operator picks discipline only.
- Coverage: all disciplines in the SYOG26 pack; all four message types.
- Architecture: separate repo/app depending on `odf_validator`.
- Bulk only (no SYNC subtype); no message editing; one discipline → four-message
  bundle per action; RSC = discipline(3) + random `[A-Z0-9-]` to length 34;
  single seeded RNG with optional API seed.
