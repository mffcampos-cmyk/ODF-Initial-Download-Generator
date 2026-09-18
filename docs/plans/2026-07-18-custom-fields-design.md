# Custom Message Fields & Entry Counts — Design

**Date:** 2026-07-18
**Status:** Approved (pending spec review)
**Scope:** Add UI-driven customization of ODF header fields, participant status,
and athlete/team/coach counts to the ODF Message Generator webapp.

## 1. Goal

Let the user override, from the webapp UI, a defined set of message header fields
and the number of athletes, teams, and coaches generated. Any field left blank
falls back to the logic already programmed. Officials other than coaches (judges,
team officials, technical officials) are generated from the selected discipline's
Common Codes, replacing the current fixed count of 4 judges.

## 2. Customizable fields

### 2.1 Header fields (optional text inputs, blank = current default)

| UI field | Target attribute | Current default (unchanged when blank) |
|---|---|---|
| CompetitionCode | `OdfBody@CompetitionCode` | `codes("COMPETITION_CODE")[0]` |
| Source | `OdfBody@Source` | `OGEN` (`AWAARC1` for ARC) |
| Gen | `Competition@Gen` | `OWG-2026-GEN-V4.5` |
| Sport | `Competition@Sport` | `SYOG-2026-{disc}-1.0` |
| Codes | `Competition@Codes` | `SYOG-2026-CC-V0.04` |
| Status | participant/team `@Status` | `ENT` (or code-table fallback) |

`Status` is not a header attribute; it is the participant and team status set in
`dataset.py`. A supplied value is applied to every participant and team.

### 2.2 Date / Time — always the real generation timestamp (no input)

`Date`, `Time`, and `LogicalDate` are **not** user-editable. They must reflect the
actual moment the sample is generated, from the system clock:

- `Date` = today, `YYYY-MM-DD`
- `LogicalDate` = same as `Date`
- `Time` = `HHMMSSmmm` (hours, minutes, seconds, milliseconds)

This replaces today's behavior, which fills these with random values.

### 2.3 Count fields (optional integer inputs, hard override, per-discipline)

Blank = the discipline's current default count. A value replaces the default
exactly for the discipline being generated.

| UI field | Meaning | Default when blank |
|---|---|---|
| Athletes | Number of Category-A participants | Event-structure-derived count (incl. ARC's real-life profile) |
| Teams | Number of teams | Discipline default |
| Coaches | Number of Category-C participants | One coach per participating NOC |

Counts apply only to the discipline generated in that request. If a discipline
defines no coach (Category C) function (e.g. SWM), the Coaches field has no effect
for it.

## 3. Officials driven by Common Codes

Currently `dataset.py` hardcodes 4 judges and uses non-discipline-aware function
codes (`AA01` / `COACH` / `JU`). This changes so that **every non-athlete
participant is generated from the selected discipline's DISCIPLINE_FUNCTION rows**.

### 3.1 Data source problem

The rule pack loads DISCIPLINE_FUNCTION through the generic code-table loader,
which keys rows by the `Function` column only. Because `AA01` (and others) recur
across disciplines, rows collapse (last-wins) and the `Discipline` / `Category`
columns are effectively lost. `refdata.codes("DISCIPLINE_FUNCTION")` therefore
cannot answer "which function codes belong to discipline X, in which category".

### 3.2 Solution — discipline-aware function accessor

Add a discipline-aware reader that yields, per discipline, the list of
`(function_code, category, order)` where `Partic = Y`. Categories:

- `A` — Athlete
- `C` — Coach
- `T` — Team official
- `J` — Judge
- `S` — Other / technical official

Preferred implementation: read the DISCIPLINE_FUNCTION sheet directly from the
pack's Common Codes workbook (keyed by `(Discipline, Function)`), exposed via a new
`RefData` method, e.g. `discipline_functions(discipline) -> list[FunctionInfo]`.
The reader must degrade gracefully (empty list) when the sheet or pack is absent,
so existing tests and packs without the workbook still run.

### 3.3 Generation rule

For the selected discipline:

- **Athletes** use the Category-A function code as `MainFunctionId` (typically
  `AA01`); count per Section 2.3.
- **Coaches** use Category-C function code(s); count per Section 2.3. When count
  exceeds the number of distinct C codes, cycle through them.
- **Judges, team officials, technical officials** (Categories J / T / S) are
  auto-generated: one participant per applicable function code the discipline
  publishes. This replaces the fixed 4 judges. Each uses its own function code as
  `MainFunctionId`.

When a discipline publishes no function codes at all (pack lacks the sheet), fall
back to today's behavior (`AA01` / `COACH` / `JU`, 4 judges) so nothing regresses.

## 4. Data flow / threading

A single optional `overrides` object is threaded through the existing call chain;
no global state, each request self-contained.

```
POST /api/generate | /api/save | GET /api/generate.zip
  -> GenerateRequest.overrides: Overrides | None
    -> build_bundle(refdata, discipline, seed, overrides)
      -> build_fn(refdata, discipline, seed, overrides)   # each builder
        -> build_odfbody(rng, refdata, ..., overrides)    # header fields + real timestamp
        -> build_dataset(refdata, discipline, seed, overrides)  # counts, status, officials
```

### 4.1 `Overrides` shape (Pydantic model + plain dataclass)

```
competition_code: str | None
source:           str | None
gen:              str | None
sport:            str | None
codes:            str | None
status:           str | None
athletes:         int | None
teams:            int | None
coaches:          int | None
```

All fields optional; blank string / null / absent = default. The API model
coerces empty strings to `None` and validates integers are non-negative.

## 5. Component changes

- `api/schemas.py` (new or existing) / `api/app.py` — add `Overrides` model;
  add `overrides` to `GenerateRequest`; pass to `build_bundle` in all three
  endpoints. `generate` and `save` carry `overrides` in the JSON body. The
  `generate.zip` endpoint (a GET download link) gains one optional query parameter
  per override field (`competition_code`, `source`, `gen`, `sport`, `codes`,
  `status`, `athletes`, `teams`, `coaches`), assembled into an `Overrides` object
  server-side; the UI builds the query string from the same form inputs.
- `generator/envelope.py` — `build_odfbody(..., overrides=None)`: apply header
  overrides where non-blank; set `Date` / `LogicalDate` / `Time` from the real
  clock; apply `Sport` default relative to discipline.
- `generator/refdata.py` (+ small loader) — `discipline_functions(discipline)`
  discipline-aware DISCIPLINE_FUNCTION accessor.
- `generator/dataset.py` — accept `overrides`; apply status override; use
  discipline-aware officials generation; apply hard-override counts for athletes,
  teams, coaches; keep event-structure schedule unchanged.
- `generator/bundle.py` + `generator/builders/*.py` — thread `overrides` through
  `build_bundle` and each `build()`.
- `generator/export.py` — thread `overrides` through `export_bundle` (used by
  `/api/save`).
- `web/templates/index.html` — add a collapsible "Custom fields" section: 6 text
  inputs + 3 number inputs, all optional with `placeholder="default"`; include
  values in the fetch bodies for generate/save/zip.

## 6. Design for isolation

- Header customization lives entirely in `envelope.build_odfbody`.
- Count / status / officials logic lives entirely in `dataset.py`, reading the new
  `RefData.discipline_functions`.
- `Overrides` is a single, well-defined interface passed by value; builders remain
  thin pass-throughs.
- The discipline-function reader is independent and testable in isolation.

## 7. Validity / invariants

- DT_ENTRIES simply enumerates generated athletes + teams, so count overrides stay
  self-consistent.
- DT_SCHEDULE remains event-structure-driven and independent of participant counts.
- Teams always reference member codes drawn from generated athletes, so
  DT_PARTIC_TEAMS cross-references remain valid.
- The existing `selfcheck` residual-error retry in `build_bundle` still guards
  output; overrides must not bypass it.

## 8. Testing

- Unit: header override applied / blank falls back; real timestamp shape
  (`Date` = today, `Time` matches `^\d{9}$`); `discipline_functions` returns
  correct per-discipline categories (HBB has C/T/S/J; SWM has only A/S); hard
  counts produce exactly N athletes / M teams / K coaches; officials generated one
  per J/T/S code; graceful fallback when the sheet is absent.
- Integration: `/api/generate` and `/api/save` with and without `overrides`;
  overrides reach the XML; status override reflected on participants and teams.
- Regression: existing tests pass unchanged when no overrides are supplied.

## 9. Out of scope

- Cap/limit count semantics (hard override only).
- Persisting overrides between sessions.
- Customizing Date/Time to arbitrary values (they are the real generation time).
- Adding new disciplines or editing the Common Codes.
