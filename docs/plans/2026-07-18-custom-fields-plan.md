# Custom Message Fields & Entry Counts — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the webapp UI override ODF header fields, participant status, and athlete/team/coach counts, with blank fields falling back to existing defaults; drive officials from each discipline's Common Codes and stamp Date/Time from the real generation clock.

**Architecture:** A single optional `Overrides` object is threaded from the three API endpoints through `build_bundle` → each builder → `build_odfbody` (header fields, real timestamp) and `build_dataset` (status, counts, code-driven officials). A new discipline-aware DISCIPLINE_FUNCTION reader supplies per-discipline function codes and categories that the collapsed pack code-table cannot.

**Tech Stack:** Python 3.11, FastAPI + Pydantic, openpyxl (already a dependency), lxml, vanilla JS/HTML template.

## Global Constraints

- Any override left blank (empty string / null / absent) MUST fall back to the exact behavior already programmed. Verbatim: "If the information is blank then use the default attributes already programmed in the logic."
- `Date`, `Time`, `LogicalDate` are NOT user-editable; they reflect the real generation moment: `Date`/`LogicalDate` = today `YYYY-MM-DD`, `Time` = `HHMMSSmmm` (9 digits).
- Count overrides are a HARD override, applied per-discipline at generation time.
- Officials other than coaches (categories J/T/S) are generated from the selected discipline's DISCIPLINE_FUNCTION rows where `Partic = Y`. No invented roles. This replaces the current fixed 4 judges.
- DISCIPLINE_FUNCTION categories: `A`=Athlete, `C`=Coach, `T`=Team official, `J`=Judge, `S`=Other/technical official.
- Must degrade gracefully: when the DISCIPLINE_FUNCTION sheet or pack workbook is absent, fall back to today's behavior (`AA01`/`COACH`/`JU`, 4 judges) so existing packs and tests never regress.
- Existing selfcheck retry loop in `build_bundle` MUST still guard output; overrides must not bypass it.
- Test runner in this environment: `python -m tests.minirunner` (pytest is not installable offline; the project ships a minirunner that imports and runs `tests/unit/test_*` functions). Set `PYTHONPATH="<generator-root>:<validator-root>"` and `ODF_PACK_DIR="<validator-root>/Rules/SYOG26"` when running.
- Integration tests under `tests/integration/` use `fastapi.testclient.TestClient` and are NOT collected by minirunner; run them by importing directly (`python -c "import tests.integration.test_api as t; t.test_x()"`) when a pytest-capable environment is unavailable.
- No git repository is initialized in this project. Where a step says "Commit", run `git init` once first if `.git` is absent, or skip the commit if the team does not want version control here. Commits are optional and never block a task's completion.

---

## File Structure

- `generator/overrides.py` — **new**. Plain dataclass `Overrides` + a `normalize()` helper that coerces blank strings to `None` and clamps counts to non-negative ints. Framework-free so both the API layer and the generator import it without a FastAPI dependency.
- `generator/functions.py` — **new**. Discipline-aware DISCIPLINE_FUNCTION reader over the pack workbook; returns `list[FunctionInfo]` per discipline.
- `generator/refdata.py` — **modify**. Store optional `pack_dir`; add `discipline_functions(discipline)` delegating to `functions.py` with caching.
- `generator/packload.py` — **modify**. Pass the resolved pack dir into `RefData(pack, pack_dir=resolved)`.
- `generator/envelope.py` — **modify**. `build_odfbody(..., overrides=None)`: apply header overrides; stamp real Date/Time/LogicalDate.
- `generator/dataset.py` — **modify**. `build_dataset(..., overrides=None)`: status override; code-driven officials; hard-override counts.
- `generator/bundle.py` — **modify**. `build_bundle(..., overrides=None)`; pass to each builder.
- `generator/builders/partic.py`, `partic_teams.py`, `entries.py`, `schedule.py` — **modify**. `build(refdata, discipline, seed, overrides=None)`; pass through to `build_odfbody` and `build_dataset`.
- `generator/export.py` — **modify**. `export_bundle(..., overrides=None)` passed to `build_bundle`.
- `api/app.py` — **modify**. Add `Overrides` Pydantic model; `overrides` field on `GenerateRequest`; wire all three endpoints; add per-field query params to `/api/generate.zip`.
- `web/templates/index.html` — **modify**. Add optional "Custom fields" section and include values in fetch/query.
- `tests/unit/test_overrides.py`, `test_functions.py`, and additions to `test_envelope.py`, `test_dataset.py` — **new/modify**. Unit coverage.
- `tests/integration/test_api_overrides.py` — **new**. Endpoint coverage.

---

## Task 1: `Overrides` value object

**Files:**
- Create: `generator/overrides.py`
- Test: `tests/unit/test_overrides.py`

**Interfaces:**
- Produces:
  - `@dataclass Overrides` with fields (all defaulting to `None`):
    `competition_code: str | None`, `source: str | None`, `gen: str | None`,
    `sport: str | None`, `codes: str | None`, `status: str | None`,
    `athletes: int | None`, `teams: int | None`, `coaches: int | None`.
  - `Overrides.normalize() -> Overrides` — returns a copy where blank/whitespace-only
    strings become `None` and any negative count becomes `None`.
  - `Overrides.is_empty() -> bool` — True when every field is `None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_overrides.py
from generator.overrides import Overrides


def test_blank_strings_normalize_to_none():
    o = Overrides(competition_code="  ", source="", gen="OWG").normalize()
    assert o.competition_code is None
    assert o.source is None
    assert o.gen == "OWG"


def test_negative_counts_drop_to_none():
    o = Overrides(athletes=-1, teams=0, coaches=5).normalize()
    assert o.athletes is None
    assert o.teams == 0
    assert o.coaches == 5


def test_is_empty_true_when_all_none():
    assert Overrides().is_empty() is True
    assert Overrides(status="ENT").is_empty() is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m tests.minirunner test_overrides`
Expected: FAIL — `ModuleNotFoundError: No module named 'generator.overrides'`

- [ ] **Step 3: Write minimal implementation**

```python
# generator/overrides.py
from __future__ import annotations
from dataclasses import dataclass, replace


@dataclass
class Overrides:
    competition_code: str | None = None
    source: str | None = None
    gen: str | None = None
    sport: str | None = None
    codes: str | None = None
    status: str | None = None
    athletes: int | None = None
    teams: int | None = None
    coaches: int | None = None

    def normalize(self) -> "Overrides":
        def s(v):
            return v if (v is not None and str(v).strip() != "") else None
        def n(v):
            return v if (v is not None and int(v) >= 0) else None
        return replace(
            self,
            competition_code=s(self.competition_code),
            source=s(self.source),
            gen=s(self.gen),
            sport=s(self.sport),
            codes=s(self.codes),
            status=s(self.status),
            athletes=n(self.athletes),
            teams=n(self.teams),
            coaches=n(self.coaches),
        )

    def is_empty(self) -> bool:
        return all(getattr(self, f) is None for f in (
            "competition_code", "source", "gen", "sport", "codes", "status",
            "athletes", "teams", "coaches"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m tests.minirunner test_overrides`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add generator/overrides.py tests/unit/test_overrides.py
git commit -m "feat: add Overrides value object for message customization"
```

---

## Task 2: Discipline-aware DISCIPLINE_FUNCTION reader

**Files:**
- Create: `generator/functions.py`
- Modify: `generator/refdata.py`, `generator/packload.py`
- Test: `tests/unit/test_functions.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `@dataclass FunctionInfo` with `code: str`, `category: str`, `order: int` (in `generator/functions.py`).
  - `read_discipline_functions(pack_dir, discipline) -> list[FunctionInfo]` — reads the
    DISCIPLINE_FUNCTION sheet from the first `*.xlsx` under `pack_dir` that contains it,
    returns rows for `discipline` where `Partic == "Y"`, sorted by `order`. Returns `[]`
    when `pack_dir` is None, no workbook is found, or the sheet is absent.
  - `RefData.discipline_functions(discipline) -> list[FunctionInfo]` — cached delegate;
    returns `[]` when the RefData has no `pack_dir`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_functions.py
from generator.refdata import RefData
from generator.packload import resolve_pack_dir
from tests.conftest import PACK

PACK_DIR = resolve_pack_dir()


def _cats(funcs):
    from collections import Counter
    return dict(Counter(f.category for f in funcs))


def test_hbb_has_expected_categories():
    rd = RefData(PACK, pack_dir=PACK_DIR)
    cats = _cats(rd.discipline_functions("HBB"))
    # HBB publishes coach, team, technical and judge officials plus athletes.
    assert cats.get("A", 0) >= 1
    assert cats.get("C", 0) >= 1
    assert cats.get("J", 0) >= 1
    assert cats.get("T", 0) >= 1


def test_swm_has_no_coach_or_judge():
    rd = RefData(PACK, pack_dir=PACK_DIR)
    cats = _cats(rd.discipline_functions("SWM"))
    assert cats.get("C", 0) == 0
    assert cats.get("J", 0) == 0
    assert cats.get("A", 0) >= 1


def test_athlete_function_code_present_for_arc():
    rd = RefData(PACK, pack_dir=PACK_DIR)
    codes = {f.code for f in rd.discipline_functions("ARC") if f.category == "A"}
    assert "AA01" in codes


def test_missing_pack_dir_returns_empty():
    rd = RefData(PACK)  # no pack_dir
    assert rd.discipline_functions("ARC") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m tests.minirunner test_functions`
Expected: FAIL — `RefData.__init__() got an unexpected keyword argument 'pack_dir'` (or `AttributeError: discipline_functions`).

- [ ] **Step 3a: Create the reader**

```python
# generator/functions.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import openpyxl

_SHEET = "DISCIPLINE_FUNCTION"


@dataclass(frozen=True)
class FunctionInfo:
    code: str
    category: str
    order: int


def _find_workbook(pack_dir: Path) -> Path | None:
    for xlsx in sorted(pack_dir.rglob("*.xlsx")):
        try:
            wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
        except Exception:
            continue
        try:
            if _SHEET in wb.sheetnames:
                return xlsx
        finally:
            wb.close()
    return None


def read_discipline_functions(pack_dir, discipline: str) -> list[FunctionInfo]:
    if pack_dir is None:
        return []
    pack_dir = Path(pack_dir)
    wb_path = _find_workbook(pack_dir)
    if wb_path is None:
        return []
    wb = openpyxl.load_workbook(wb_path, read_only=True, data_only=True)
    try:
        ws = wb[_SHEET]
        rows = ws.iter_rows(values_only=True)
        header = next(rows, None)
        if not header:
            return []
        idx = {str(h).strip(): i for i, h in enumerate(header) if h is not None}
        need = ("Function", "Discipline", "Order", "Category", "Partic")
        if not all(k in idx for k in need):
            return []
        out: list[FunctionInfo] = []
        for raw in rows:
            if raw is None:
                continue
            def cell(name):
                i = idx[name]
                return "" if i >= len(raw) or raw[i] is None else str(raw[i]).strip()
            if cell("Discipline") != discipline or cell("Partic").upper() != "Y":
                continue
            try:
                order = int(float(cell("Order"))) if cell("Order") else 0
            except ValueError:
                order = 0
            out.append(FunctionInfo(code=cell("Function"),
                                    category=cell("Category").upper(),
                                    order=order))
        out.sort(key=lambda f: f.order)
        return out
    finally:
        wb.close()
```

- [ ] **Step 3b: Wire `pack_dir` into RefData**

In `generator/refdata.py`, replace the constructor and add the accessor:

```python
    def __init__(self, pack, pack_dir=None):
        self.pack = pack
        self.pack_dir = pack_dir
        self._func_cache: dict[str, list] = {}

    def discipline_functions(self, discipline: str):
        from .functions import read_discipline_functions
        if discipline not in self._func_cache:
            self._func_cache[discipline] = read_discipline_functions(
                self.pack_dir, discipline)
        return self._func_cache[discipline]
```

- [ ] **Step 3c: Pass the resolved pack dir from packload**

In `generator/packload.py`, inside `load_refdata`, change the return to carry the dir:

```python
    return RefData(pack, pack_dir=resolved)
```

(`resolved` is already computed earlier in the function as `resolve_pack_dir(pack_dir)`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m tests.minirunner test_functions test_refdata`
Expected: PASS (existing `test_refdata` still green; new function tests pass)

- [ ] **Step 5: Commit**

```bash
git add generator/functions.py generator/refdata.py generator/packload.py tests/unit/test_functions.py
git commit -m "feat: discipline-aware DISCIPLINE_FUNCTION reader"
```

---

## Task 3: Header overrides + real generation timestamp in `build_odfbody`

**Files:**
- Modify: `generator/envelope.py`
- Test: `tests/unit/test_envelope.py`

**Interfaces:**
- Consumes: `Overrides` (Task 1).
- Produces: `build_odfbody(rng, refdata, discipline, document_type, competition_code, overrides=None) -> (root, comp)` — signature gains a trailing optional `overrides`. When `overrides` is None or a field is None, behavior is unchanged except Date/Time/LogicalDate now come from the real clock.

- [ ] **Step 1: Write the failing tests**

```python
# add to tests/unit/test_envelope.py
import re
import datetime
from generator.overrides import Overrides


def test_header_overrides_applied():
    rd = RefData(PACK)
    ov = Overrides(competition_code="SYOG2026", source="OGEN",
                   gen="OWG-2026-GEN-V4.5", sport="SYOG-2026-SWM-1.0",
                   codes="SYOG-2026-CC-V0.04")
    root, comp = build_odfbody(random.Random(1), rd, "SWM", "DT_PARTIC",
                               competition_code(rd), ov)
    assert root.get("CompetitionCode") == "SYOG2026"
    assert root.get("Source") == "OGEN"
    assert comp.get("Gen") == "OWG-2026-GEN-V4.5"
    assert comp.get("Sport") == "SYOG-2026-SWM-1.0"
    assert comp.get("Codes") == "SYOG-2026-CC-V0.04"


def test_blank_overrides_keep_defaults():
    rd = RefData(PACK)
    root, comp = build_odfbody(random.Random(1), rd, "ARC", "DT_PARTIC",
                               competition_code(rd), Overrides())
    assert root.get("Source") == "AWAARC1"          # ARC default preserved
    assert comp.get("Sport") == "SYOG-2026-ARC-1.0"  # discipline default


def test_date_and_time_are_real_generation_clock():
    rd = RefData(PACK)
    root, _ = build_odfbody(random.Random(1), rd, "ARC", "DT_PARTIC",
                            competition_code(rd))
    today = datetime.date.today().isoformat()
    assert root.get("Date") == today
    assert root.get("LogicalDate") == today
    assert re.fullmatch(r"\d{9}", root.get("Time"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m tests.minirunner test_envelope`
Expected: FAIL — `build_odfbody()` takes no `overrides` arg / Date is random not today.

- [ ] **Step 3: Update `build_odfbody`**

Replace the body of `build_odfbody` in `generator/envelope.py` (keep the module's existing imports; add `import datetime` at top):

```python
def build_odfbody(rng: random.Random, refdata, discipline: str,
                  document_type: str, competition_code: str, overrides=None):
    disc = _discipline_code(refdata, discipline)
    ov = overrides.normalize() if overrides is not None else None

    # Date/Time/LogicalDate: the real moment of generation (not customizable).
    now = datetime.datetime.now()
    date = now.date().isoformat()                       # YYYY-MM-DD
    time = now.strftime("%H%M%S") + f"{now.microsecond // 1000:03d}"  # HHMMSSmmm

    comp_code = (ov.competition_code if ov and ov.competition_code
                 else competition_code)
    source = (ov.source if ov and ov.source
              else SOURCES.get(disc, DEFAULT_SOURCE))

    root = el("OdfBody", {
        "CompetitionCode": comp_code,
        "DocumentCode": fields.rsc(rng, disc),
        "DocumentType": document_type,
        "Version": "1",
        "FeedFlag": fields.feed_flag(rng),
        "Date": date,
        "Time": time,
        "LogicalDate": date,
        "Source": source,
    })
    comp = el("Competition", {
        "Gen": (ov.gen if ov and ov.gen else GEN_VERSION),
        "Sport": (ov.sport if ov and ov.sport else f"SYOG-2026-{disc}-1.0"),
        "Codes": (ov.codes if ov and ov.codes else CODES_VERSION),
    })
    root.append(comp)
    return root, comp
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m tests.minirunner test_envelope`
Expected: PASS (all envelope tests green, including the pre-existing ones)

- [ ] **Step 5: Commit**

```bash
git add generator/envelope.py tests/unit/test_envelope.py
git commit -m "feat: header field overrides and real generation timestamp"
```

---

## Task 4: Status override + code-driven officials + hard counts in `build_dataset`

**Files:**
- Modify: `generator/dataset.py`
- Test: `tests/unit/test_dataset.py`

**Interfaces:**
- Consumes: `Overrides` (Task 1); `RefData.discipline_functions` (Task 2).
- Produces: `build_dataset(refdata, discipline, seed, overrides=None) -> Dataset` — signature gains a trailing optional `overrides`. New private helpers:
  - `_function_codes(refdata, discipline, category, fallback) -> list[str]` — the discipline's Partic-Y function codes for a category, else `[fallback]`.
  - `_officials_from_codes(add_person, refdata, discipline, nocs, rng, coaches_override)` — generates judges/team/technical officials (J/T/S) one per code, plus coaches (C) per override-or-default.
  - `_apply_status(status, participants, teams)` — sets `.status` on all when `status` is not None.

This task changes how officials are built for BOTH the ARC profile path and the codes-driven path, and adds hard-count overrides. Because the two dataset builders differ, the override handling is added at their boundaries (see steps).

- [ ] **Step 1: Write the failing tests**

```python
# add to tests/unit/test_dataset.py (create file if absent)
from generator.dataset import build_dataset
from generator.overrides import Overrides
from generator.refdata import RefData
from generator.packload import resolve_pack_dir
from tests.conftest import PACK

RD = RefData(PACK, pack_dir=resolve_pack_dir())


def _athletes(ds):
    return [p for p in ds.participants if not p.is_official]


def _officials(ds):
    return [p for p in ds.participants if p.is_official]


def test_status_override_applied_to_all():
    ds = build_dataset(RD, "ARC", 1, Overrides(status="ACR"))
    assert all(p.status == "ACR" for p in ds.participants)
    assert all(t.status == "ACR" for t in ds.teams)


def test_hard_athlete_count_override():
    ds = build_dataset(RD, "ARC", 1, Overrides(athletes=10))
    assert len(_athletes(ds)) == 10


def test_hard_team_count_override():
    ds = build_dataset(RD, "ARC", 1, Overrides(teams=3))
    assert len(ds.teams) == 3
    member_codes = {c for t in ds.teams for c in t.member_codes}
    athlete_codes = {p.code for p in _athletes(ds)}
    assert member_codes <= athlete_codes  # members reference real athletes


def test_hard_coach_count_override():
    ds = build_dataset(RD, "HBB", 1, Overrides(coaches=5))
    coach_codes = {f.code for f in RD.discipline_functions("HBB")
                   if f.category == "C"}
    coaches = [p for p in _officials(ds) if p.main_function in coach_codes]
    assert len(coaches) == 5


def test_officials_use_discipline_function_codes():
    ds = build_dataset(RD, "HBB", 1, Overrides())
    valid = {f.code for f in RD.discipline_functions("HBB")}
    assert valid  # sanity
    assert all(p.main_function in valid for p in _officials(ds))


def test_defaults_unchanged_when_overrides_empty():
    base = build_dataset(RD, "ARC", 1)
    same = build_dataset(RD, "ARC", 1, Overrides())
    assert len(_athletes(base)) == len(_athletes(same))
    assert len(base.teams) == len(same.teams)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m tests.minirunner test_dataset`
Expected: FAIL — `build_dataset()` takes 3 positional args / officials use `JU` not discipline codes.

- [ ] **Step 3a: Add shared helpers to `generator/dataset.py`**

Add near the top-level helpers (after `_main_function`):

```python
def _function_codes(refdata, discipline: str, category: str,
                    fallback: str) -> list[str]:
    """Partic-Y DISCIPLINE_FUNCTION codes for a category, or [fallback]."""
    codes = [f.code for f in refdata.discipline_functions(discipline)
             if f.category == category]
    return codes or [fallback]


def _athlete_function(refdata, discipline: str) -> str:
    return _function_codes(refdata, discipline, "A", "AA01")[0]


def _apply_status(status, participants, teams) -> None:
    if not status:
        return
    for p in participants:
        p.status = status
    for t in teams:
        t.status = status
```

- [ ] **Step 3b: Make `_person` accept an explicit function code**

Change `_person` so athletes/coaches/officials get the right code. Replace its
`main_function=_main_function(refdata, role)` argument with a passed-in code:

```python
def _person(rng, refdata, code: str, org: str, gender: str, role: str,
            status: str, used: set[str], function_code: str) -> Participant:
    given, family = names.person_name(rng, org, gender, used)
    birth = (fields.athlete_birth_date(rng) if role == "athlete"
             else fields.official_birth_date(rng))
    return Participant(
        code=code, parent=code, family_name=family, given_name=given,
        gender=gender, organisation=org, birth_date=birth, status=status,
        is_official=(role != "athlete"),
        nationality=_nationality(refdata, org),
        main_function=function_code,
    )
```

Every existing `_person(...)` call must now pass `function_code`. For athletes pass
`_athlete_function(refdata, discipline)`; for the old hardcoded coach/judge calls,
pass the code chosen by the officials helper (Step 3c). `_main_function` may remain
for the fallback dataset (see Step 3e).

- [ ] **Step 3c: Add the officials generator**

```python
def _officials_from_codes(add_person, refdata, discipline: str, nocs: list[str],
                          rng, coaches_override) -> None:
    """Generate officials from the discipline's Common Codes.

    Coaches (category C): `coaches_override` if not None, else one per NOC.
    Judges/team/technical officials (J/T/S): one participant per published code.
    `add_person(org, gender, role, function_code)` appends a Participant.
    """
    coach_codes = _function_codes(refdata, discipline, "C", "COACH")
    if coaches_override is not None:
        for i in range(coaches_override):
            code = coach_codes[i % len(coach_codes)]
            add_person(rng.choice(nocs), "M" if rng.random() < 0.5 else "F",
                       "coach", code)
    else:
        # default: one coach per NOC (only when the discipline defines coaches)
        has_coach = any(f.category == "C"
                        for f in refdata.discipline_functions(discipline))
        if has_coach or not refdata.discipline_functions(discipline):
            for noc in nocs:
                add_person(noc, "M" if rng.random() < 0.5 else "F",
                           "coach", coach_codes[0])

    for f in refdata.discipline_functions(discipline):
        if f.category in ("J", "T", "S"):
            add_person(rng.choice(nocs), "M" if rng.random() < 0.5 else "F",
                       "judge", f.code)
    # Fallback when the discipline publishes no function codes at all:
    if not refdata.discipline_functions(discipline):
        for _ in range(4):
            add_person(rng.choice(nocs), "M" if rng.random() < 0.5 else "F",
                       "judge", "JU")
```

- [ ] **Step 3d: Apply overrides in `_build_codes_dataset` and `_build_arc_dataset`**

In `_build_codes_dataset(refdata, discipline, seed, overrides=None)`:
1. Add `overrides` param; compute `ov = overrides.normalize() if overrides else None`.
2. `status = ov.status if ov and ov.status else _participant_status(rng, refdata)`.
3. Update the local `add_person` closure to accept `function_code` and forward it to `_person`.
4. Replace the existing athlete generation so that when `ov and ov.athletes is not None`, generate exactly `ov.athletes` athletes across `cycle(nocs)` (alternating M/F) using `_athlete_function`, INSTEAD of the event-structure loop. When `ov.athletes` is None, keep the existing bracket/pooled/team athlete logic (each `add_person(...)` call now passes `_athlete_function(refdata, discipline)`).
5. Replace the team loop so that when `ov and ov.teams is not None`, generate exactly `ov.teams` teams (each drawing 2 members from already-generated athletes, or generating a small squad if none exist yet), INSTEAD of the event-driven team loop. Keep team `team_type=_team_type(...)` and gender `"X"`.
6. Replace the officials block (the `for noc in used_nocs: add_person(... "coach" ...)` and the `for _ in range(4): ... "judge"` lines) with a single call:
   `_officials_from_codes(add_person, refdata, discipline, used_nocs or nocs, rng, ov.coaches if ov else None)`.
7. Before returning, call `_apply_status(status, participants, teams)` (redundant safety; status already set per person).

In `_build_arc_dataset(refdata, seed, overrides=None)`:
1. Add `overrides` param; `ov = overrides.normalize() if overrides else None`.
2. `status = ov.status if ov and ov.status else _participant_status(rng, refdata)`.
3. Wrap the participant/team constructors so athletes use `_athlete_function(refdata, "ARC")` and, when `ov.athletes`/`ov.teams` are set, honor exact counts as above (fall back to the real-life profile when None).
4. Replace the hardcoded coach-per-NOC + 4-judge blocks with
   `_officials_from_codes(add_person_arc, refdata, "ARC", all_nocs, rng, ov.coaches if ov else None)`, where `add_person_arc` is a small closure mirroring the codes-path `add_person`.
5. Call `_apply_status(status, participants, teams)` before constructing the `Dataset`.

- [ ] **Step 3e: Thread `overrides` through `build_dataset`**

```python
def build_dataset(refdata, discipline: str, seed: int, overrides=None) -> Dataset:
    if discipline == "ARC":
        return _build_arc_dataset(refdata, seed, overrides)
    return _build_codes_dataset(refdata, discipline, seed, overrides)
```

The fallback `_build_fallback_dataset` keeps using `_main_function`; give it an
`overrides=None` param and apply `_apply_status` + count overrides only if you reach
it (optional — it triggers only for packs with no EVENT_UNIT data).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m tests.minirunner test_dataset test_build_partic test_build_partic_teams test_build_entries test_bundle_teams_presence test_dataset_codes_driven`
Expected: PASS — new dataset tests green AND existing builder/dataset tests still pass.

- [ ] **Step 5: Commit**

```bash
git add generator/dataset.py tests/unit/test_dataset.py
git commit -m "feat: status override, code-driven officials, hard entry counts"
```

---

## Task 5: Thread `overrides` through bundle, builders, and export

**Files:**
- Modify: `generator/bundle.py`, `generator/builders/partic.py`,
  `generator/builders/partic_teams.py`, `generator/builders/entries.py`,
  `generator/builders/schedule.py`, `generator/export.py`
- Test: `tests/unit/test_pack_smoke.py` (extend) or `tests/unit/test_bundle_all_disciplines.py`

**Interfaces:**
- Consumes: `Overrides` (Task 1); `build_odfbody(..., overrides)` (Task 3); `build_dataset(..., overrides)` (Task 4).
- Produces:
  - `build_bundle(refdata, discipline, seed, overrides=None, max_retries=5)`.
  - Each builder `build(refdata, discipline, seed, overrides=None)`.
  - `export_bundle(refdata, discipline, seed=1, out_dir=..., *, require_clean=True, overrides=None)`.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/unit/test_bundle_all_disciplines.py
from generator.bundle import build_bundle
from generator.overrides import Overrides
from generator.refdata import RefData
from generator.packload import resolve_pack_dir
from tests.conftest import PACK

RD2 = RefData(PACK, pack_dir=resolve_pack_dir())


def test_bundle_accepts_overrides_and_applies_competition_code():
    bundle = build_bundle(RD2, "ARC", 1, Overrides(competition_code="SYOG2026"))
    xml = bundle["DT_PARTIC"][0].decode("utf-8")
    assert 'CompetitionCode="SYOG2026"' in xml
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m tests.minirunner test_bundle_all_disciplines`
Expected: FAIL — `build_bundle()` takes no `overrides` arg.

- [ ] **Step 3a: Update `build_bundle`**

In `generator/bundle.py`, change the signature and the build call:

```python
def build_bundle(refdata, discipline: str, seed: int, overrides=None,
                 max_retries: int = 5):
    ...
        for doc_type, build_fn in doc_types.items():
            xml = build_fn(refdata, discipline, s, overrides)
            errs = check_errors(xml, refdata.pack)
    ...
```

(Only the two lines change: signature adds `overrides=None` before `max_retries`, and `build_fn(...)` passes `overrides`.)

- [ ] **Step 3b: Update each builder**

For `partic.py`, `partic_teams.py`, `entries.py`, `schedule.py`, change `build`:

```python
def build(refdata, discipline: str, seed: int, overrides=None) -> bytes:
    rng = random.Random(seed)
    ds = build_dataset(refdata, discipline, seed, overrides)
    root, comp = build_odfbody(rng, refdata, discipline, "<DOC_TYPE>",
                               competition_code(refdata), overrides)
    ...
```

Keep each file's existing `"<DOC_TYPE>"` string (`DT_PARTIC`, `DT_PARTIC_TEAMS`, `DT_ENTRIES`, `DT_SCHEDULE`) and the rest of its body unchanged.

- [ ] **Step 3c: Update `export_bundle`**

In `generator/export.py`:

```python
def export_bundle(refdata, discipline: str, seed: int = 1,
                  out_dir: Path | str = DEFAULT_OUT_DIR,
                  *, require_clean: bool = True, overrides=None) -> list[Path]:
    bundle = build_bundle(refdata, discipline, seed, overrides)
    ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m tests.minirunner`
Expected: PASS — full unit suite green (previously 58 passed, now higher).

- [ ] **Step 5: Commit**

```bash
git add generator/bundle.py generator/builders/ generator/export.py tests/unit/test_bundle_all_disciplines.py
git commit -m "feat: thread overrides through bundle, builders, and export"
```

---

## Task 6: API endpoints accept overrides

**Files:**
- Modify: `api/app.py`
- Test: `tests/integration/test_api_overrides.py`

**Interfaces:**
- Consumes: `Overrides` (Task 1); `build_bundle`/`export_bundle` (Task 5).
- Produces:
  - Pydantic `OverridesModel` (all optional) → converted to `generator.overrides.Overrides`.
  - `GenerateRequest.overrides: OverridesModel | None = None`.
  - `/api/generate.zip` gains optional query params: `competition_code, source, gen, sport, codes, status, athletes, teams, coaches`.

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_api_overrides.py
from fastapi.testclient import TestClient
from api.app import app

client = TestClient(app)


def test_generate_applies_overrides():
    r = client.post("/api/generate", json={
        "discipline": "ARC", "seed": 1,
        "overrides": {"competition_code": "SYOG2026", "athletes": 8,
                      "status": "ENT"},
    })
    assert r.status_code == 200
    xml = r.json()["messages"]["DT_PARTIC"]["xml"]
    assert 'CompetitionCode="SYOG2026"' in xml


def test_generate_blank_overrides_still_clean():
    r = client.post("/api/generate", json={
        "discipline": "ARC", "seed": 1, "overrides": {},
    })
    assert r.status_code == 200
    for payload in r.json()["messages"].values():
        assert payload["errors"] == []


def test_zip_accepts_override_query_params():
    r = client.get("/api/generate.zip",
                   params={"discipline": "ARC", "seed": 1,
                           "competition_code": "SYOG2026"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
```

Run these directly if pytest is unavailable:
`python -c "import tests.integration.test_api_overrides as t; t.test_generate_applies_overrides(); t.test_generate_blank_overrides_still_clean(); t.test_zip_accepts_override_query_params(); print('ok')"`

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — `overrides` is ignored (extra field) / zip params unknown.

- [ ] **Step 3: Update `api/app.py`**

Add the model and helper near the top (after imports):

```python
from typing import Optional
from generator.overrides import Overrides as GenOverrides


class OverridesModel(BaseModel):
    competition_code: Optional[str] = None
    source: Optional[str] = None
    gen: Optional[str] = None
    sport: Optional[str] = None
    codes: Optional[str] = None
    status: Optional[str] = None
    athletes: Optional[int] = None
    teams: Optional[int] = None
    coaches: Optional[int] = None

    def to_gen(self) -> GenOverrides:
        return GenOverrides(**self.model_dump())


class GenerateRequest(BaseModel):
    discipline: str
    seed: int = 1
    overrides: Optional[OverridesModel] = None
```

In `generate` and `save`, build overrides and pass them:

```python
    ov = req.overrides.to_gen() if req.overrides else None
    bundle = build_bundle(REFDATA, req.discipline, req.seed, ov)   # generate
    ...
    written = export_bundle(REFDATA, req.discipline, req.seed, overrides=ov)  # save
```

Replace `generate_zip` signature and body head:

```python
@app.get("/api/generate.zip")
def generate_zip(discipline: str, seed: int = 1,
                 competition_code: str | None = None, source: str | None = None,
                 gen: str | None = None, sport: str | None = None,
                 codes: str | None = None, status: str | None = None,
                 athletes: int | None = None, teams: int | None = None,
                 coaches: int | None = None):
    if discipline not in REFDATA.disciplines():
        return JSONResponse(status_code=400,
                            content={"error": f"unknown discipline: {discipline}"})
    ov = GenOverrides(competition_code=competition_code, source=source, gen=gen,
                      sport=sport, codes=codes, status=status, athletes=athletes,
                      teams=teams, coaches=coaches)
    bundle = build_bundle(REFDATA, discipline, seed, ov)
    ...
```

(Leave the rest of `generate_zip` — residual check, zip writing — unchanged.)

- [ ] **Step 4: Run tests to verify they pass**

Run (pytest env): `python -m pytest tests/integration/test_api_overrides.py tests/integration/test_api.py -q`
Or offline: the `python -c "..."` one-liner from Step 1, plus re-run the existing
`tests/integration/test_api.py` functions the same way to confirm no regression.
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/app.py tests/integration/test_api_overrides.py
git commit -m "feat: API endpoints accept message field and count overrides"
```

---

## Task 7: UI — Custom fields section

**Files:**
- Modify: `web/templates/index.html`
- Test: `tests/integration/test_api.py` (extend `test_index_page_renders_select`) — assert the new inputs render.

**Interfaces:**
- Consumes: the endpoints from Task 6.
- Produces: no new code interface; adds form inputs and includes them in the fetch bodies / zip query.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/integration/test_api.py
def test_index_page_renders_custom_fields():
    r = client.get("/")
    assert r.status_code == 200
    for ident in ("ov_competition_code", "ov_status", "ov_athletes",
                  "ov_teams", "ov_coaches"):
        assert ident in r.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -c "import tests.integration.test_api as t; t.test_index_page_renders_custom_fields()"`
Expected: FAIL — identifiers absent.

- [ ] **Step 3: Update `web/templates/index.html`**

Add, after the `<button id="save">` line and before `<p id="status">`:

```html
  <details style="margin-top:1rem">
    <summary>Custom fields (optional — blank uses defaults)</summary>
    <fieldset>
      <legend>Message header</legend>
      <label>CompetitionCode <input id="ov_competition_code" placeholder="default"></label>
      <label>Source <input id="ov_source" placeholder="default"></label>
      <label>Gen <input id="ov_gen" placeholder="default"></label>
      <label>Sport <input id="ov_sport" placeholder="default"></label>
      <label>Codes <input id="ov_codes" placeholder="default"></label>
      <label>Status <input id="ov_status" placeholder="default (ENT)"></label>
    </fieldset>
    <fieldset>
      <legend>Entry counts</legend>
      <label>Athletes <input id="ov_athletes" type="number" min="0" placeholder="default"></label>
      <label>Teams <input id="ov_teams" type="number" min="0" placeholder="default"></label>
      <label>Coaches <input id="ov_coaches" type="number" min="0" placeholder="default"></label>
    </fieldset>
  </details>
```

Add this helper inside the `<script>`, above the `go.onclick` handler:

```javascript
    const OV_TEXT = ["competition_code","source","gen","sport","codes","status"];
    const OV_NUM = ["athletes","teams","coaches"];

    function collectOverrides() {
      const ov = {};
      for (const k of OV_TEXT) {
        const v = document.getElementById("ov_" + k).value.trim();
        if (v) ov[k] = v;
      }
      for (const k of OV_NUM) {
        const v = document.getElementById("ov_" + k).value.trim();
        if (v !== "") ov[k] = parseInt(v, 10);
      }
      return ov;
    }
```

Update the two fetch bodies to include overrides:

```javascript
        body: JSON.stringify({discipline, seed: 1, overrides: collectOverrides()}),
```

(Apply to BOTH the `go.onclick` and `save.onclick` fetch calls.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -c "import tests.integration.test_api as t; t.test_index_page_renders_custom_fields(); t.test_index_page_renders_select(); print('ok')"`
Expected: `ok`

- [ ] **Step 5: Manual smoke (optional but recommended)**

Start the app (`python -m uvicorn api.app:app` or the project's `Launch-ODF-Generator.bat`), open `/`, expand "Custom fields", set CompetitionCode=`SYOG2026`, Athletes=`8`, click Generate, confirm the JSON output shows `CompetitionCode="SYOG2026"` and 8 athletes in DT_PARTIC.

- [ ] **Step 6: Commit**

```bash
git add web/templates/index.html tests/integration/test_api.py
git commit -m "feat: UI custom fields for header overrides and entry counts"
```

---

## Task 8: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Run the full unit suite**

Run: `python -m tests.minirunner`
Expected: all pass (>= previous 58, plus new tests).

- [ ] **Step 2: Run integration tests**

In a pytest env: `python -m pytest tests/integration -q`.
Offline: execute each `test_*` function in `tests/integration/test_api.py`,
`test_api_save.py`, `test_api_zip.py`, `test_api_overrides.py` via
`python -c "import <module> as t; [getattr(t,n)() for n in dir(t) if n.startswith('test_')]; print('ok')"`.
Expected: all pass — confirms overrides + defaults + save + zip all clean.

- [ ] **Step 3: Regression sanity — defaults unchanged**

Run: `python -c "from generator.packload import load_refdata; from generator.bundle import build_bundle; rd=load_refdata(); b=build_bundle(rd,'ARC',1); print({k:len(v[1]) for k,v in b.items()})"`
Expected: every doc type has `0` residual errors (clean), matching pre-change behavior.

- [ ] **Step 4: Commit any final fixes**

```bash
git add -A && git commit -m "test: verify full suite green with customization feature"
```

---

## Self-Review Notes

- **Spec coverage:** header fields (Task 3), Status (Task 4), Date/Time/LogicalDate as real clock (Task 3), officials from Common Codes replacing fixed judges (Tasks 2+4), hard athlete/team/coach counts per-discipline (Task 4), threading + endpoints + `.zip` query params (Tasks 5+6), UI (Task 7), blank-falls-back-to-default (Tasks 1,3,4 + tests), graceful fallback without workbook (Task 2). All covered.
- **Type consistency:** `Overrides` field names identical across `overrides.py`, `OverridesModel`, and `collectOverrides()` keys. `discipline_functions` / `FunctionInfo(code, category, order)` used consistently in Tasks 2 and 4. `build_odfbody(..., overrides)`, `build_dataset(..., overrides)`, `build_bundle(..., overrides)`, `build(..., overrides)`, `export_bundle(..., overrides)` signatures match across Tasks 3–6.
- **Fallbacks:** every code-driven path has an explicit non-workbook fallback so the pre-existing 58 tests (which construct `RefData(PACK)` without `pack_dir`) keep passing.
