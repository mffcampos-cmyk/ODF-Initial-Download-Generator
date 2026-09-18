# Initial Download ODF Message Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone webapp that, given only a discipline choice, randomly generates the four "initial download" ODF messages (`DT_PARTIC`, `DT_PARTIC_TEAMS`, `DT_ENTRIES`, `DT_SCHEDULE`) so each passes the existing `odf_validator` engine with zero error-severity findings.

**Architecture:** A web-free `generator/` core (reference-data loader → field synthesizers → coherent per-discipline dataset → one builder per message → omit-empty serializer → validator self-check with bounded regeneration) plus a thin FastAPI + HTML layer. It depends on the existing `odf_validator` package as a library and never reimplements rule logic — a clean `Pipeline.run` is the acceptance gate.

**Tech Stack:** Python 3.11+, `lxml` (XML build/serialize), `odf_validator` (pack loader + `Pipeline`), FastAPI + Uvicorn + Jinja2 (web), `pytest` (tests, with a dependency-light fallback runner).

## Global Constraints

- Python 3.11+; depend on `odf_validator` as an installed package (editable install of the sibling validator repo is fine); never copy or fork its rule/validation logic.
- The core `generator/` package has **no web dependencies** (no FastAPI/Starlette imports); web code lives only under `api/` and `web/`.
- Acceptance for any generated message = `odf_validator.pipeline.orchestrator.Pipeline().run(xml_bytes, pack)` returns **zero `error`-severity findings**. Warnings/info do not block.
- All randomness flows through a single injected `random.Random` instance; every public generation entry point accepts a `seed: int` for reproducibility.
- Coded attribute values MUST come from the pack's `CodeRegistry` tables; never invent codes.
- Never emit an attribute or element with an empty/whitespace value — omit it (Foundation Principle 6.7; core rules `CORE_NO_EMPTY_ATTRS` / `CORE_NO_EMPTY_ELEMENTS`).
- `DocumentCode` and every schedule `Unit@Code` are RSCs of **exactly 34 characters** matching `[A-Z0-9]{3}[A-Z0-9-]{31}` (`CORE_DOCCODE_RSC_FORMAT`, XSD `rscType`).
- Envelope required non-empty attrs: `CompetitionCode`, `DocumentCode`, `DocumentType`, `Version`, `FeedFlag`, `Date`, `Time`, `LogicalDate`, `Source`. `Version` is a positive integer starting at 1. `FeedFlag` ∈ {`P`,`T`}. `Date`/`LogicalDate` match `[0-9]{4}-[0-9]{2}-[0-9]{2}`.
- `Competition` requires `@Gen` and `@Codes`; child `Discipline@Code` ∈ `DISCIPLINE` table; `CompetitionCode` ∈ `COMPETITION_CODE` table.
- Gender: participant `[MFX]`, team `[MWXGO]`. Entry `@Type` ∈ {`A`,`T`,`H`}. `ScheduleStatus`/`SessionStatus` ∈ scheduleStatusType enum. `@SortOrder` integer ≥ 1, unique among siblings. `Unit@Medal` ∈ {0,1,2,3}.
- v1: bulk only (no `DocumentSubtype`), no message editing, one discipline → four-message bundle per action.

**Reference files (read-only inputs, in the validator repo):**
- XSD: `Rules/SYOG26/xsd/odf2.xsd` (root `OdfBody`/`bodyType`), `odf2-structure.xsd` (complex types), `odf2-values.xsd` (simple types/enums).
- Codes: `Rules/SYOG26/codes/SYOG2026_ODF_Common_Codes_v_1_9_1.xlsx` + SPORT_CODES.
- Pack loader: `odf_validator.ingestion.builder.build_ruleset_pack(Path("Rules/SYOG26")) -> RulePack`.
- `RulePack` fields: `.name`, `.schema` (compiled lxml XMLSchema or None), `.codes` (`CodeRegistry`), `.rules`, `.disciplines: list[str]`.
- `CodeRegistry.table(name) -> CodeTable | None`; `CodeTable.lookup(code)`, `.get(code, field)`, `.field_values(field)`, `._rows` (dict code→CodeRow).
- `Pipeline().run(xml, pack, ctx=None) -> RunResult`; `RunResult.findings: list[Finding]`; `Finding.severity.value ∈ {"error","warning","info"}`, `.rule_id`, `.message`.

---

## Task 0: Project scaffold and validator wiring

**Files:**
- Create: `pyproject.toml`
- Create: `generator/__init__.py`
- Create: `tests/__init__.py`, `tests/unit/__init__.py`
- Create: `tests/conftest.py`
- Create: `README.md`

**Interfaces:**
- Consumes: the installed `odf_validator` package and the `Rules/SYOG26` pack directory.
- Produces: `tests/conftest.py::PACK` (a session-scoped `RulePack`) and `tests/conftest.py::pack` fixture returning it; `generator` importable package.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "odf-message-generator"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "lxml>=5.0",
    "fastapi>=0.110",
    "uvicorn>=0.29",
    "jinja2>=3.1",
    "openpyxl>=3.1",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create empty package markers**

Create `generator/__init__.py`, `tests/__init__.py`, `tests/unit/__init__.py` each containing a single comment line:

```python
# odf-message-generator
```

- [ ] **Step 3: Create `tests/conftest.py` that loads the pack once**

```python
from pathlib import Path
import os
import pytest
from odf_validator.ingestion.builder import build_ruleset_pack

# ODF_PACK_DIR must point at the validator's Rules/SYOG26 directory.
PACK_DIR = Path(os.environ.get("ODF_PACK_DIR", "Rules/SYOG26"))
PACK = build_ruleset_pack(PACK_DIR)


@pytest.fixture(scope="session")
def pack():
    return PACK
```

- [ ] **Step 4: Write a smoke test that the pack loaded with an active schema**

Create `tests/unit/test_pack_smoke.py`:

```python
from tests.conftest import PACK


def test_pack_has_active_schema():
    assert PACK.schema is not None, "XSD must compile for guaranteed structural compliance"


def test_pack_lists_disciplines():
    assert isinstance(PACK.disciplines, list) and len(PACK.disciplines) > 0


def test_discipline_and_competition_tables_present():
    assert PACK.codes.table("DISCIPLINE") is not None
    assert PACK.codes.table("COMPETITION_CODE") is not None
```

- [ ] **Step 5: Run the smoke test**

Run: `ODF_PACK_DIR=/path/to/validator/Rules/SYOG26 pytest tests/unit/test_pack_smoke.py -v`
Expected: 3 PASS. If `test_pack_has_active_schema` fails, the validator pack's XSD is not compiling — fix the pack before continuing (generation cannot guarantee structural compliance without it).

- [ ] **Step 6: Write `README.md`**

```markdown
# ODF Message Generator

Generates fully ODF-compliant DT_PARTIC, DT_PARTIC_TEAMS, DT_ENTRIES and
DT_SCHEDULE messages for a chosen discipline. Compliance is guaranteed by
construction and verified against the `odf_validator` engine.

## Setup
- Install the sibling `odf_validator` package (editable): `pip install -e ../odf-validator`
- `pip install -e .[dev]`
- Point the app at the pack: `export ODF_PACK_DIR=/path/to/Rules/SYOG26`

## Run
`uvicorn api.app:app`

## Test
`pytest -v`
```

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml generator tests README.md
git commit -m "chore: scaffold generator project and wire odf_validator pack"
```

---

## Task 1: Reference-data loader (`refdata.py`)

**Files:**
- Create: `generator/refdata.py`
- Test: `tests/unit/test_refdata.py`

**Interfaces:**
- Consumes: `RulePack` from `tests/conftest.py::PACK`.
- Produces:
  - `class RefData` with constructor `RefData(pack)`.
  - `RefData.disciplines() -> list[str]` — sorted discipline codes from the pack.
  - `RefData.codes(codeset: str) -> list[str]` — all code IDs in a table, sorted; `[]` if the table is missing.
  - `RefData.has_codeset(codeset: str) -> bool`.
  - `RefData.description(codeset: str, code: str, field: str) -> str | None` — passthrough to `CodeTable.get`.
  - `RefData.pack` — the underlying `RulePack` (so callers reach `.schema`, `.codes`).

- [ ] **Step 1: Write the failing test**

```python
from generator.refdata import RefData
from tests.conftest import PACK


def test_disciplines_nonempty_and_sorted():
    rd = RefData(PACK)
    ds = rd.disciplines()
    assert ds == sorted(ds) and len(ds) > 0


def test_codes_returns_sorted_ids():
    rd = RefData(PACK)
    disc = rd.codes("DISCIPLINE")
    assert disc == sorted(disc) and len(disc) > 0


def test_missing_codeset_is_empty_not_error():
    rd = RefData(PACK)
    assert rd.codes("NO_SUCH_CODESET") == []
    assert rd.has_codeset("NO_SUCH_CODESET") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_refdata.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'generator.refdata'`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations


class RefData:
    """Read-only accessor over a validator RulePack: code tables + discipline
    list. All generation constraints that come from the reference files are
    reached through here so builders never touch the pack directly."""

    def __init__(self, pack):
        self.pack = pack

    def disciplines(self) -> list[str]:
        return sorted(self.pack.disciplines)

    def has_codeset(self, codeset: str) -> bool:
        return self.pack.codes.table(codeset) is not None

    def codes(self, codeset: str) -> list[str]:
        table = self.pack.codes.table(codeset)
        if table is None:
            return []
        return sorted(table._rows.keys())

    def description(self, codeset: str, code: str, field: str) -> str | None:
        table = self.pack.codes.table(codeset)
        return None if table is None else table.get(code, field)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_refdata.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add generator/refdata.py tests/unit/test_refdata.py
git commit -m "feat: RefData accessor over validator pack code tables"
```

---

## Task 2: Field synthesizers (`fields.py`)

**Files:**
- Create: `generator/fields.py`
- Test: `tests/unit/test_fields.py`

**Interfaces:**
- Consumes: `RefData` (Task 1); a `random.Random` instance passed to every function.
- Produces (all take `rng: random.Random` as first arg unless noted):
  - `rsc(rng, prefix: str) -> str` — 34-char string, `prefix` (≤3 chars, upper) + random `[A-Z0-9-]`, matches `[A-Z0-9]{3}[A-Z0-9-]{31}`.
  - `gender_participant(rng) -> str` — one of `M`,`F`,`X`.
  - `gender_team(rng) -> str` — one of `M`,`W`,`X`,`G`,`O`.
  - `odf_date(rng) -> str` — `YYYY-MM-DD`, year 2024–2026.
  - `odf_datetime(rng) -> str` — `YYYY-MM-DDThh:mm:ss` (xs:dateTime).
  - `feed_flag(rng) -> str` — `P` or `T`.
  - `name_token(rng, n: int = 8) -> str` — non-empty `[A-Za-z]` string length n.
  - `pos_int(rng, lo: int = 1, hi: int = 999) -> int`.
  - `pick(rng, seq: list[str]) -> str` — random element (raises on empty).
  - `pick_code(rng, refdata: RefData, codeset: str) -> str | None` — random valid code, or `None` if codeset missing/empty.

- [ ] **Step 1: Write the failing test**

```python
import re
import random
from generator.fields import (
    rsc, gender_participant, gender_team, odf_date, odf_datetime,
    feed_flag, name_token, pos_int, pick, pick_code,
)
from generator.refdata import RefData
from tests.conftest import PACK

RSC_RE = re.compile(r"[A-Z0-9]{3}[A-Z0-9-]{31}")
DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
DT_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}")


def rng():
    return random.Random(42)


def test_rsc_is_34_chars_and_matches_pattern():
    v = rsc(rng(), "ARC")
    assert len(v) == 34 and RSC_RE.fullmatch(v)


def test_rsc_prefix_over_three_chars_is_truncated():
    v = rsc(rng(), "ARCHERY")
    assert len(v) == 34 and v[:3] == "ARC"


def test_genders_in_domain():
    assert gender_participant(rng()) in {"M", "F", "X"}
    assert gender_team(rng()) in {"M", "W", "X", "G", "O"}


def test_dates_match_patterns():
    assert DATE_RE.fullmatch(odf_date(rng()))
    assert DT_RE.fullmatch(odf_datetime(rng()))


def test_feed_flag_and_names_and_ints():
    assert feed_flag(rng()) in {"P", "T"}
    assert name_token(rng()).isalpha() and len(name_token(rng())) == 8
    n = pos_int(rng(), 1, 10)
    assert 1 <= n <= 10


def test_pick_code_returns_valid_member():
    r = rng()
    rd = RefData(PACK)
    code = pick_code(r, rd, "DISCIPLINE")
    assert code in set(rd.codes("DISCIPLINE"))
    assert pick_code(r, rd, "NO_SUCH") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_fields.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'generator.fields'`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations
import random
import string

_RSC_TAIL = string.ascii_uppercase + string.digits + "-"
_ALNUM = string.ascii_uppercase + string.digits


def rsc(rng: random.Random, prefix: str) -> str:
    head = (prefix.upper() + "XXX")[:3]
    # head chars must be [A-Z0-9]; replace anything else with a random alnum.
    head = "".join(c if c in _ALNUM else rng.choice(_ALNUM) for c in head)
    tail = "".join(rng.choice(_RSC_TAIL) for _ in range(31))
    return head + tail


def gender_participant(rng: random.Random) -> str:
    return rng.choice(["M", "F", "X"])


def gender_team(rng: random.Random) -> str:
    return rng.choice(["M", "W", "X", "G", "O"])


def odf_date(rng: random.Random) -> str:
    y = rng.randint(2024, 2026)
    m = rng.randint(1, 12)
    d = rng.randint(1, 28)
    return f"{y:04d}-{m:02d}-{d:02d}"


def odf_datetime(rng: random.Random) -> str:
    return f"{odf_date(rng)}T{rng.randint(0,23):02d}:{rng.randint(0,59):02d}:{rng.randint(0,59):02d}"


def feed_flag(rng: random.Random) -> str:
    return rng.choice(["P", "T"])


def name_token(rng: random.Random, n: int = 8) -> str:
    return "".join(rng.choice(string.ascii_letters) for _ in range(n))


def pos_int(rng: random.Random, lo: int = 1, hi: int = 999) -> int:
    return rng.randint(lo, hi)


def pick(rng: random.Random, seq: list[str]) -> str:
    if not seq:
        raise ValueError("pick() from empty sequence")
    return rng.choice(seq)


def pick_code(rng: random.Random, refdata, codeset: str):
    codes = refdata.codes(codeset)
    return rng.choice(codes) if codes else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_fields.py -v`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add generator/fields.py tests/unit/test_fields.py
git commit -m "feat: XSD-conformant field value synthesizers"
```

---

## Task 3: Coherent dataset model and builder (`model.py`, `dataset.py`)

**Files:**
- Create: `generator/model.py`
- Create: `generator/dataset.py`
- Test: `tests/unit/test_dataset.py`

**Interfaces:**
- Consumes: `RefData` (Task 1), field synthesizers (Task 2).
- Produces:
  - Dataclasses in `generator/model.py`:
    - `Participant(code: str, parent: str, family_name: str, given_name: str, gender: str, organisation: str, birth_date: str, is_official: bool)`
    - `Team(code: str, organisation: str, short_name: str, tv_team_name: str, gender: str, team_type: str, member_codes: list[str])`
    - `ScheduleUnit(code: str, phase_type: str, schedule_status: str, sort_order: int, medal: str | None)`
    - `Session(venue: str, venue_name: str, session_code: str, start_date: str, end_date: str, name: str, units: list[ScheduleUnit])`
    - `Dataset(discipline: str, organisations: list[str], participants: list[Participant], teams: list[Team], sessions: list[Session])`
  - `build_dataset(refdata: RefData, discipline: str, seed: int) -> Dataset` in `generator/dataset.py`.

- [ ] **Step 1: Write the failing test**

```python
from generator.dataset import build_dataset
from generator.refdata import RefData
from tests.conftest import PACK


def rd():
    return RefData(PACK)


def test_dataset_is_deterministic_for_a_seed():
    a = build_dataset(rd(), "ARC", seed=7)
    b = build_dataset(rd(), "ARC", seed=7)
    assert [p.code for p in a.participants] == [p.code for p in b.participants]


def test_dataset_has_participants_and_sessions():
    ds = build_dataset(rd(), "ARC", seed=1)
    assert ds.discipline == "ARC"
    assert len(ds.participants) >= 4
    assert len(ds.sessions) >= 1 and len(ds.sessions[0].units) >= 1


def test_team_members_reference_real_participants():
    ds = build_dataset(rd(), "ARC", seed=1)
    athletes = {p.code for p in ds.participants if not p.is_official}
    for team in ds.teams:
        for code in team.member_codes:
            assert code in athletes


def test_unit_sort_orders_unique_within_session():
    ds = build_dataset(rd(), "ARC", seed=3)
    for s in ds.sessions:
        orders = [u.sort_order for u in s.units]
        assert len(orders) == len(set(orders))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_dataset.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'generator.dataset'`

- [ ] **Step 3: Write minimal implementation of `generator/model.py`**

```python
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Participant:
    code: str
    parent: str
    family_name: str
    given_name: str
    gender: str
    organisation: str
    birth_date: str
    is_official: bool = False


@dataclass
class Team:
    code: str
    organisation: str
    short_name: str
    tv_team_name: str
    gender: str
    team_type: str
    member_codes: list[str] = field(default_factory=list)


@dataclass
class ScheduleUnit:
    code: str
    phase_type: str
    schedule_status: str
    sort_order: int
    medal: str | None = None


@dataclass
class Session:
    venue: str
    venue_name: str
    session_code: str
    start_date: str
    end_date: str
    name: str
    units: list[ScheduleUnit] = field(default_factory=list)


@dataclass
class Dataset:
    discipline: str
    organisations: list[str]
    participants: list[Participant]
    teams: list[Team]
    sessions: list[Session]
```

- [ ] **Step 4: Write minimal implementation of `generator/dataset.py`**

```python
from __future__ import annotations
import random
from . import fields
from .model import Participant, Team, ScheduleUnit, Session, Dataset

_SCHEDULE_STATUS = "SCHEDULED"  # a safe scheduleStatusType enum member


def _orgs(rng, refdata) -> list[str]:
    for cs in ("ORGANISATION", "NOC", "COUNTRY"):
        codes = refdata.codes(cs)
        if codes:
            return rng.sample(codes, min(4, len(codes)))
    # Fallback: synthesize 3-letter org codes if no org table exists.
    return [fields.name_token(rng, 3).upper() for _ in range(4)]


def build_dataset(refdata, discipline: str, seed: int) -> Dataset:
    rng = random.Random(seed)
    orgs = _orgs(rng, refdata)

    participants: list[Participant] = []
    for i in range(6):
        org = rng.choice(orgs)
        participants.append(Participant(
            code=str(100 + i),
            parent="0",
            family_name=fields.name_token(rng).upper(),
            given_name=fields.name_token(rng).capitalize(),
            gender=fields.gender_participant(rng),
            organisation=org,
            birth_date=fields.odf_date(rng),
            is_official=(i >= 4),  # last two are officials
        ))

    athletes = [p for p in participants if not p.is_official]
    teams: list[Team] = []
    team_type_cs = f"SC@TeamType@{discipline}"
    tt = fields.pick_code(rng, refdata, team_type_cs) or "ORG"
    for j in range(2):
        org = rng.choice(orgs)
        members = [a.code for a in rng.sample(athletes, min(2, len(athletes)))]
        teams.append(Team(
            code=f"{discipline}T{j:02d}",
            organisation=org,
            short_name=fields.name_token(rng, 5).upper(),
            tv_team_name=fields.name_token(rng, 6).capitalize(),
            gender=fields.gender_team(rng),
            team_type=tt,
            member_codes=members,
        ))

    venue = fields.pick_code(rng, refdata, "VENUE") or fields.name_token(rng, 3).upper()
    venue_name = (refdata.description("VENUE", venue, "ENG_Description")
                  or fields.name_token(rng, 10).capitalize())
    units = []
    for k in range(3):
        units.append(ScheduleUnit(
            code=fields.rsc(rng, discipline),
            phase_type=fields.pick_code(rng, refdata, "PHASE_TYPE") or "1",
            schedule_status=_SCHEDULE_STATUS,
            sort_order=k + 1,
            medal=rng.choice([None, "0", "1"]),
        ))
    sessions = [Session(
        venue=venue,
        venue_name=venue_name,
        session_code=f"{discipline}SES01",
        start_date=fields.odf_datetime(rng),
        end_date=fields.odf_datetime(rng),
        name=fields.name_token(rng, 9).capitalize(),
        units=units,
    )]

    return Dataset(discipline=discipline, organisations=orgs,
                   participants=participants, teams=teams, sessions=sessions)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/unit/test_dataset.py -v`
Expected: 4 PASS

- [ ] **Step 6: Commit**

```bash
git add generator/model.py generator/dataset.py tests/unit/test_dataset.py
git commit -m "feat: coherent per-discipline synthetic dataset"
```

---

## Task 4: Omit-empty serializer (`serialize.py`)

**Files:**
- Create: `generator/serialize.py`
- Test: `tests/unit/test_serialize.py`

**Interfaces:**
- Consumes: nothing beyond `lxml`.
- Produces:
  - `el(tag: str, attrs: dict, *children) -> lxml.etree._Element` — builds an element, **dropping any attribute whose value is None or empty/whitespace**, and dropping any child that is `None`.
  - `to_xml(root) -> bytes` — pretty-printed XML with declaration; raises `ValueError` if any empty attribute or empty element survives (defensive final check).

- [ ] **Step 1: Write the failing test**

```python
from lxml import etree
from generator.serialize import el, to_xml


def test_el_drops_empty_and_none_attrs():
    node = el("Team", {"Code": "T1", "Name": "", "TeamType": None, "Org": "  "})
    assert node.get("Code") == "T1"
    assert node.get("Name") is None
    assert node.get("TeamType") is None
    assert node.get("Org") is None


def test_el_drops_none_children_keeps_real_ones():
    parent = el("Competition", {"Gen": "G"}, el("Discipline", {"Code": "ARC"}), None)
    assert len(parent) == 1 and parent[0].tag == "Discipline"


def test_to_xml_has_declaration_and_content():
    root = el("OdfBody", {"DocumentType": "DT_PARTIC"}, el("Competition", {"Gen": "G", "Codes": "C"},
              el("Discipline", {"Code": "ARC"})))
    xml = to_xml(root)
    assert xml.startswith(b"<?xml")
    assert b'DocumentType="DT_PARTIC"' in xml


def test_to_xml_rejects_empty_element():
    root = el("OdfBody", {"DocumentType": "DT_PARTIC"})
    # Manually attach an empty child that el() would normally never create.
    etree.SubElement(root, "Empty")
    try:
        to_xml(root)
        assert False, "expected ValueError for empty element"
    except ValueError:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_serialize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'generator.serialize'`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations
from lxml import etree


def el(tag: str, attrs: dict, *children):
    node = etree.Element(tag)
    for k, v in attrs.items():
        if v is None:
            continue
        s = str(v)
        if s.strip() == "":
            continue
        node.set(k, s)
    for child in children:
        if child is None:
            continue
        node.append(child)
    return node


def _is_empty(node) -> bool:
    has_text = node.text is not None and node.text.strip() != ""
    return not node.attrib and len(node) == 0 and not has_text


def to_xml(root) -> bytes:
    for node in root.iter("*"):
        if node is root:
            continue
        if _is_empty(node):
            raise ValueError(f"empty element <{node.tag}> would be serialized")
        for k, v in node.attrib.items():
            if v is None or str(v).strip() == "":
                raise ValueError(f"empty attribute @{k} on <{node.tag}>")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_serialize.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add generator/serialize.py tests/unit/test_serialize.py
git commit -m "feat: omit-empty serializer with defensive final check"
```

---

## Task 5: Envelope builder (`envelope.py`)

**Files:**
- Create: `generator/envelope.py`
- Test: `tests/unit/test_envelope.py`

**Interfaces:**
- Consumes: `RefData` (Task 1), field synthesizers (Task 2), `el` (Task 4).
- Produces:
  - `build_odfbody(rng, refdata, discipline: str, document_type: str, competition_code: str) -> (root, competition)` where `root` is the `<OdfBody>` element with all required envelope attrs set, containing a `<Competition Gen Codes>` child with a `<Discipline Code=...>`; returns both so builders can append content to `competition`.
  - `competition_code(refdata) -> str` — a valid `COMPETITION_CODE` member (first sorted, deterministic).

- [ ] **Step 1: Write the failing test**

```python
import random
from generator.envelope import build_odfbody, competition_code
from generator.refdata import RefData
from generator.serialize import to_xml
from tests.conftest import PACK

REQUIRED = ["CompetitionCode", "DocumentCode", "DocumentType", "Version",
            "FeedFlag", "Date", "Time", "LogicalDate", "Source"]


def test_competition_code_is_valid_member():
    rd = RefData(PACK)
    assert competition_code(rd) in set(rd.codes("COMPETITION_CODE"))


def test_envelope_has_all_required_attrs_nonempty():
    rd = RefData(PACK)
    root, comp = build_odfbody(random.Random(1), rd, "ARC", "DT_PARTIC",
                               competition_code(rd))
    for a in REQUIRED:
        assert root.get(a) and root.get(a).strip()
    assert len(root.get("DocumentCode")) == 34
    assert int(root.get("Version")) >= 1
    assert root.get("FeedFlag") in {"P", "T"}


def test_competition_child_has_gen_codes_and_discipline():
    rd = RefData(PACK)
    root, comp = build_odfbody(random.Random(1), rd, "ARC", "DT_PARTIC",
                               competition_code(rd))
    assert comp.get("Gen") and comp.get("Codes")
    disc = comp.find("Discipline")
    assert disc is not None and disc.get("Code") in set(rd.codes("DISCIPLINE"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_envelope.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'generator.envelope'`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations
import random
from . import fields
from .serialize import el


def competition_code(refdata) -> str:
    codes = refdata.codes("COMPETITION_CODE")
    if not codes:
        raise ValueError("COMPETITION_CODE table is empty; cannot build envelope")
    return codes[0]


def _discipline_code(refdata, discipline: str) -> str:
    valid = set(refdata.codes("DISCIPLINE"))
    return discipline if discipline in valid else sorted(valid)[0]


def build_odfbody(rng: random.Random, refdata, discipline: str,
                  document_type: str, competition_code: str):
    disc = _discipline_code(refdata, discipline)
    date = fields.odf_date(rng)
    root = el("OdfBody", {
        "CompetitionCode": competition_code,
        "DocumentCode": fields.rsc(rng, disc),
        "DocumentType": document_type,
        "Version": "1",
        "FeedFlag": fields.feed_flag(rng),
        "Date": date,
        "Time": f"{rng.randint(0,23):02d}{rng.randint(0,59):02d}{rng.randint(0,59):02d}000",
        "LogicalDate": date,
        "Source": "OGEN",
    })
    comp = el("Competition", {"Gen": "OWG2026-1.10", "Codes": "OWG2026-1.20"},
              el("Discipline", {"Code": disc}))
    root.append(comp)
    return root, comp
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_envelope.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add generator/envelope.py tests/unit/test_envelope.py
git commit -m "feat: ODF message envelope builder"
```

---

## Task 6: Self-check wrapper with bounded regeneration (`selfcheck.py`)

**Files:**
- Create: `generator/selfcheck.py`
- Test: `tests/unit/test_selfcheck.py`

**Interfaces:**
- Consumes: `RulePack` (from `RefData.pack`), the validator `Pipeline`.
- Produces:
  - `errors(xml: bytes, pack) -> list[str]` — list of `error`-severity finding descriptions (`"<rule_id>: <message>"`); empty list == clean.
  - `generate_clean(make_xml, pack, seeds: list[int]) -> (xml: bytes, findings: list[str])` — calls `make_xml(seed)` for each seed until `errors()` is empty; returns the first clean XML with `[]`, or the last attempt with its residual error list if none are clean.

- [ ] **Step 1: Write the failing test**

```python
from generator.selfcheck import errors, generate_clean
from tests.conftest import PACK

CLEAN = (b'<?xml version="1.0" encoding="UTF-8"?>'
         b'<OdfBody CompetitionCode="X" DocumentCode="D" DocumentType="DT_PARTIC" '
         b'Version="1" FeedFlag="P" Date="2026-01-01" Time="000000000" '
         b'LogicalDate="2026-01-01" Source="S"><Competition Gen="G" Codes="C">'
         b'<Discipline Code="ARC"/></Competition></OdfBody>')


def test_errors_returns_list_of_strings():
    result = errors(CLEAN, PACK)
    assert isinstance(result, list)
    assert all(isinstance(s, str) for s in result)


def test_generate_clean_returns_first_clean():
    calls = []

    def make(seed):
        calls.append(seed)
        # Only seed 2 yields a message with a valid CompetitionCode/DocumentCode.
        good = seed == 2
        cc = "SYOG2026" if good else ""  # empty CompetitionCode -> error
        return (b'<?xml version="1.0"?><OdfBody CompetitionCode="' + cc.encode() +
                b'" DocumentCode="ARC0000000000000000000000000000000" '
                b'DocumentType="DT_PARTIC" Version="1" FeedFlag="P" '
                b'Date="2026-01-01" Time="000000000" LogicalDate="2026-01-01" '
                b'Source="S"><Competition Gen="G" Codes="C"><Discipline Code="ARC"/>'
                b'</Competition></OdfBody>')

    xml, findings = generate_clean(make, PACK, seeds=[1, 2, 3])
    # It should stop at the first clean seed and not try seed 3.
    assert 3 not in calls
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_selfcheck.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'generator.selfcheck'`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations
from odf_validator.pipeline.orchestrator import Pipeline

_PIPELINE = Pipeline()


def errors(xml: bytes, pack) -> list[str]:
    result = _PIPELINE.run(xml, pack)
    return [f"{f.rule_id}: {f.message}"
            for f in result.findings if f.severity.value == "error"]


def generate_clean(make_xml, pack, seeds: list[int]):
    last_xml = b""
    last_errs: list[str] = ["no seeds provided"]
    for seed in seeds:
        xml = make_xml(seed)
        errs = errors(xml, pack)
        if not errs:
            return xml, []
        last_xml, last_errs = xml, errs
    return last_xml, last_errs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_selfcheck.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add generator/selfcheck.py tests/unit/test_selfcheck.py
git commit -m "feat: validator self-check with bounded regeneration"
```

---

## Task 7: DT_PARTIC builder

**Files:**
- Create: `generator/builders/__init__.py`
- Create: `generator/builders/partic.py`
- Test: `tests/unit/test_build_partic.py`

**Interfaces:**
- Consumes: `RefData`, `build_dataset` (Task 3), `build_odfbody`/`competition_code` (Task 5), `el`/`to_xml` (Task 4), `fields` (Task 2), `errors` (Task 6).
- Produces:
  - `build(refdata: RefData, discipline: str, seed: int) -> bytes` — a serialized `DT_PARTIC` message.

- [ ] **Step 1: Write the failing test**

```python
from generator.builders import partic
from generator.refdata import RefData
from generator.selfcheck import errors
from tests.conftest import PACK


def test_partic_validates_clean_for_arc():
    rd = RefData(PACK)
    xml = partic.build(rd, "ARC", seed=1)
    assert errors(xml, PACK) == []


def test_partic_is_document_type_partic():
    rd = RefData(PACK)
    xml = partic.build(rd, "ARC", seed=1)
    assert b'DocumentType="DT_PARTIC"' in xml
    assert b"<Participant" in xml
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_build_partic.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'generator.builders'`

- [ ] **Step 3: Create `generator/builders/__init__.py`**

```python
# builders package
```

- [ ] **Step 4: Write minimal implementation of `generator/builders/partic.py`**

```python
from __future__ import annotations
import random
from .. import fields
from ..dataset import build_dataset
from ..envelope import build_odfbody, competition_code
from ..serialize import el, to_xml


def _participant_el(p, discipline):
    disc = el("Discipline", {"Code": discipline})
    return el("Participant", {
        "Code": p.code,
        "Parent": p.parent,
        "Status": "1",
        "GivenName": p.given_name,
        "FamilyName": p.family_name,
        "PrintName": f"{p.family_name} {p.given_name}",
        "PrintInitialName": f"{p.family_name} {p.given_name[:1]}",
        "TVName": f"{p.family_name} {p.given_name}",
        "TVInitialName": f"{p.family_name} {p.given_name[:1]}",
        "TVFamilyName": p.family_name,
        "Gender": p.gender,
        "Organisation": p.organisation,
        "BirthDate": p.birth_date,
    }, disc)


def build(refdata, discipline: str, seed: int) -> bytes:
    rng = random.Random(seed)
    ds = build_dataset(refdata, discipline, seed)
    root, comp = build_odfbody(rng, refdata, discipline, "DT_PARTIC",
                               competition_code(refdata))
    for p in ds.participants:
        comp.append(_participant_el(p, comp.find("Discipline").get("Code")))
    return to_xml(root)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/unit/test_build_partic.py -v`
Expected: 2 PASS. If `errors()` is non-empty, read each `rule_id: message`, adjust the offending attribute in `_participant_el` (e.g. a required attr the XSD wants), and re-run. Do not proceed until clean.

- [ ] **Step 6: Commit**

```bash
git add generator/builders/__init__.py generator/builders/partic.py tests/unit/test_build_partic.py
git commit -m "feat: DT_PARTIC builder validating clean"
```

---

## Task 8: DT_PARTIC_TEAMS builder

**Files:**
- Create: `generator/builders/partic_teams.py`
- Test: `tests/unit/test_build_partic_teams.py`

**Interfaces:**
- Consumes: same set as Task 7.
- Produces: `build(refdata, discipline: str, seed: int) -> bytes` — a serialized `DT_PARTIC_TEAMS` message.

- [ ] **Step 1: Write the failing test**

```python
from generator.builders import partic_teams
from generator.refdata import RefData
from generator.selfcheck import errors
from tests.conftest import PACK


def test_partic_teams_validates_clean_for_arc():
    rd = RefData(PACK)
    xml = partic_teams.build(rd, "ARC", seed=1)
    assert errors(xml, PACK) == []


def test_partic_teams_document_type_and_team_element():
    rd = RefData(PACK)
    xml = partic_teams.build(rd, "ARC", seed=1)
    assert b'DocumentType="DT_PARTIC_TEAMS"' in xml
    assert b"<Team" in xml
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_build_partic_teams.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'generator.builders.partic_teams'`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations
import random
from ..dataset import build_dataset
from ..envelope import build_odfbody, competition_code
from ..serialize import el, to_xml


def _team_el(t, discipline):
    disc = el("Discipline", {"Code": discipline})
    return el("Team", {
        "Code": t.code,
        "Status": "1",
        "Organisation": t.organisation,
        "ShortName": t.short_name,
        "TVTeamName": t.tv_team_name,
        "Gender": t.gender,
        "TeamType": t.team_type,
    }, disc)


def build(refdata, discipline: str, seed: int) -> bytes:
    rng = random.Random(seed)
    ds = build_dataset(refdata, discipline, seed)
    root, comp = build_odfbody(rng, refdata, discipline, "DT_PARTIC_TEAMS",
                               competition_code(refdata))
    disc_code = comp.find("Discipline").get("Code")
    for t in ds.teams:
        comp.append(_team_el(t, disc_code))
    return to_xml(root)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_build_partic_teams.py -v`
Expected: 2 PASS. If `errors()` is non-empty (e.g. `ARC_TEAMTYPE_VALID` because the discipline has no `SC@TeamType@<DISC>` entry), fall back in `dataset.build_dataset` so `team_type` is a valid member of that codeset when it exists, and omit the `Team`s entirely for disciplines with no team events. Re-run until clean.

- [ ] **Step 5: Commit**

```bash
git add generator/builders/partic_teams.py tests/unit/test_build_partic_teams.py
git commit -m "feat: DT_PARTIC_TEAMS builder validating clean"
```

---

## Task 9: DT_ENTRIES builder

**Files:**
- Create: `generator/builders/entries.py`
- Test: `tests/unit/test_build_entries.py`

**Interfaces:**
- Consumes: same set as Task 7.
- Produces: `build(refdata, discipline: str, seed: int) -> bytes` — a serialized `DT_ENTRIES` message whose `Entry@Code` values reference dataset participants/teams.

- [ ] **Step 1: Write the failing test**

```python
from lxml import etree
from generator.builders import entries
from generator.dataset import build_dataset
from generator.refdata import RefData
from generator.selfcheck import errors
from tests.conftest import PACK


def test_entries_validates_clean_for_arc():
    rd = RefData(PACK)
    xml = entries.build(rd, "ARC", seed=1)
    assert errors(xml, PACK) == []


def test_entry_codes_reference_dataset_participants():
    rd = RefData(PACK)
    ds = build_dataset(rd, "ARC", seed=1)
    known = {p.code for p in ds.participants} | {t.code for t in ds.teams}
    xml = entries.build(rd, "ARC", seed=1)
    root = etree.fromstring(xml)
    codes = [e.get("Code") for e in root.iter("Entry")]
    assert codes and all(c in known for c in codes)


def test_entry_sort_orders_unique():
    rd = RefData(PACK)
    xml = entries.build(rd, "ARC", seed=1)
    root = etree.fromstring(xml)
    orders = [int(e.get("SortOrder")) for e in root.iter("Entry")]
    assert len(orders) == len(set(orders))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_build_entries.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'generator.builders.entries'`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations
import random
from ..dataset import build_dataset
from ..envelope import build_odfbody, competition_code
from ..serialize import el, to_xml


def _entry_el(code, comp_type, organisation, sort_order):
    return el("Entry", {
        "Code": code,
        "Type": comp_type,
        "Organisation": organisation,
        "SortOrder": str(sort_order),
    })


def build(refdata, discipline: str, seed: int) -> bytes:
    rng = random.Random(seed)
    ds = build_dataset(refdata, discipline, seed)
    root, comp = build_odfbody(rng, refdata, discipline, "DT_ENTRIES",
                               competition_code(refdata))
    order = 1
    for p in ds.participants:
        if p.is_official:
            continue
        comp.append(_entry_el(p.code, "A", p.organisation, order))
        order += 1
    for t in ds.teams:
        comp.append(_entry_el(t.code, "T", t.organisation, order))
        order += 1
    return to_xml(root)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_build_entries.py -v`
Expected: 3 PASS. If `errors()` is non-empty, address each finding by rule_id and re-run until clean.

- [ ] **Step 5: Commit**

```bash
git add generator/builders/entries.py tests/unit/test_build_entries.py
git commit -m "feat: DT_ENTRIES builder validating clean and referencing dataset"
```

---

## Task 10: DT_SCHEDULE builder

**Files:**
- Create: `generator/builders/schedule.py`
- Test: `tests/unit/test_build_schedule.py`

**Interfaces:**
- Consumes: same set as Task 7.
- Produces: `build(refdata, discipline: str, seed: int) -> bytes` — a serialized `DT_SCHEDULE` message with `Session` elements (outer sequence) and `Unit` elements (choice branch).

- [ ] **Step 1: Write the failing test**

```python
from lxml import etree
from generator.builders import schedule
from generator.refdata import RefData
from generator.selfcheck import errors
from tests.conftest import PACK


def test_schedule_validates_clean_for_arc():
    rd = RefData(PACK)
    xml = schedule.build(rd, "ARC", seed=1)
    assert errors(xml, PACK) == []


def test_schedule_has_sessions_units_and_34char_unit_codes():
    rd = RefData(PACK)
    xml = schedule.build(rd, "ARC", seed=1)
    assert b'DocumentType="DT_SCHEDULE"' in xml
    root = etree.fromstring(xml)
    units = list(root.iter("Unit"))
    assert units and all(len(u.get("Code")) == 34 for u in units)


def test_schedule_unit_sort_orders_unique():
    rd = RefData(PACK)
    xml = schedule.build(rd, "ARC", seed=1)
    root = etree.fromstring(xml)
    orders = [int(u.get("Order")) for u in root.iter("Unit") if u.get("Order")]
    assert len(orders) == len(set(orders))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_build_schedule.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'generator.builders.schedule'`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations
import random
from ..dataset import build_dataset
from ..envelope import build_odfbody, competition_code
from ..serialize import el, to_xml


def _session_el(s):
    name = el("SessionName", {"Language": "ENG", "Value": s.name})
    return el("Session", {
        "Venue": s.venue,
        "VenueName": s.venue_name,
        "SessionCode": s.session_code,
        "StartDate": s.start_date,
        "EndDate": s.end_date,
    }, name)


def _unit_el(u):
    item = el("ItemName", {"Language": "ENG", "Value": "Round"})
    return el("Unit", {
        "Code": u.code,
        "PhaseType": u.phase_type,
        "ScheduleStatus": u.schedule_status,
        "Order": str(u.sort_order),
        "Medal": u.medal,
    }, item)


def build(refdata, discipline: str, seed: int) -> bytes:
    rng = random.Random(seed)
    ds = build_dataset(refdata, discipline, seed)
    root, comp = build_odfbody(rng, refdata, discipline, "DT_SCHEDULE",
                               competition_code(refdata))
    # Session elements belong to the competition's outer sequence (before the
    # choice branch); append them first, then the Unit choice branch.
    for s in ds.sessions:
        comp.append(_session_el(s))
    for s in ds.sessions:
        for u in s.units:
            comp.append(_unit_el(u))
    return to_xml(root)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_build_schedule.py -v`
Expected: 3 PASS. XSD note: in `competitionType`, `Session` is in the outer sequence and `Unit` is in the inner choice, so `Session` elements must precede `Unit` elements — the implementation appends them in that order. If `errors()` shows an ordering/`XSD_INVALID` finding, adjust element order per the finding and re-run until clean.

- [ ] **Step 5: Commit**

```bash
git add generator/builders/schedule.py tests/unit/test_build_schedule.py
git commit -m "feat: DT_SCHEDULE builder validating clean"
```

---

## Task 11: Bundle facade + all-disciplines property test

**Files:**
- Create: `generator/bundle.py`
- Test: `tests/unit/test_bundle_all_disciplines.py`

**Interfaces:**
- Consumes: all four builders (Tasks 7–10), `RefData` (Task 1), `generate_clean` (Task 6).
- Produces:
  - `DOC_TYPES: dict[str, callable]` mapping `"DT_PARTIC"|"DT_PARTIC_TEAMS"|"DT_ENTRIES"|"DT_SCHEDULE"` to the matching `build` function.
  - `build_bundle(refdata, discipline: str, seed: int, max_retries: int = 5) -> dict[str, tuple[bytes, list[str]]]` — for each doc type, uses `generate_clean` over seeds `[seed, seed+1, ...]` and returns `{doc_type: (xml, residual_errors)}`.

- [ ] **Step 1: Write the failing test**

```python
from generator.bundle import build_bundle, DOC_TYPES
from generator.refdata import RefData
from tests.conftest import PACK


def test_bundle_covers_four_doc_types():
    assert set(DOC_TYPES) == {"DT_PARTIC", "DT_PARTIC_TEAMS", "DT_ENTRIES", "DT_SCHEDULE"}


def test_bundle_is_clean_for_every_discipline():
    rd = RefData(PACK)
    failures = []
    for disc in rd.disciplines():
        bundle = build_bundle(rd, disc, seed=1)
        for doc_type, (xml, errs) in bundle.items():
            if errs:
                failures.append(f"{disc}/{doc_type}: {errs[:3]}")
    assert not failures, "un-clean messages:\n" + "\n".join(failures)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_bundle_all_disciplines.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'generator.bundle'`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations
from .builders import partic, partic_teams, entries, schedule
from .selfcheck import generate_clean

DOC_TYPES = {
    "DT_PARTIC": partic.build,
    "DT_PARTIC_TEAMS": partic_teams.build,
    "DT_ENTRIES": entries.build,
    "DT_SCHEDULE": schedule.build,
}


def build_bundle(refdata, discipline: str, seed: int, max_retries: int = 5):
    seeds = [seed + i for i in range(max_retries)]
    out = {}
    for doc_type, build_fn in DOC_TYPES.items():
        xml, errs = generate_clean(
            lambda s, fn=build_fn: fn(refdata, discipline, s),
            refdata.pack, seeds)
        out[doc_type] = (xml, errs)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_bundle_all_disciplines.py -v`
Expected: 2 PASS. This is the primary acceptance test. If some `discipline/doc_type` pairs report residual errors, read the finding rule_ids and fix the responsible builder or dataset synthesizer (e.g. a discipline-specific `code_membership` rule); re-run until the list is empty. Team-less disciplines should produce a `DT_PARTIC_TEAMS` with zero `Team`s only if that still validates — otherwise skip teams and confirm no rule requires at least one.

- [ ] **Step 5: Commit**

```bash
git add generator/bundle.py tests/unit/test_bundle_all_disciplines.py
git commit -m "test: all-discipline bundle validates clean (primary acceptance gate)"
```

---

## Task 12: FastAPI + web layer

**Files:**
- Create: `api/__init__.py`
- Create: `api/app.py`
- Create: `web/templates/index.html`
- Test: `tests/integration/__init__.py`
- Test: `tests/integration/test_api.py`

**Interfaces:**
- Consumes: `RefData` (Task 1), `build_bundle` (Task 11), `tests/conftest.py::PACK`.
- Produces: FastAPI `app` with:
  - `GET /` — HTML page with a discipline `<select>` and a Generate button.
  - `GET /api/disciplines` → `{"disciplines": [...]}`.
  - `POST /api/generate` with JSON `{"discipline": "ARC", "seed": 1}` → JSON `{"discipline": "ARC", "messages": {"<doc_type>": {"xml": "<...>", "errors": [...]}}}`.

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient
from api.app import app

client = TestClient(app)


def test_disciplines_endpoint():
    r = client.get("/api/disciplines")
    assert r.status_code == 200
    assert "ARC" in r.json()["disciplines"]


def test_generate_returns_four_clean_messages():
    r = client.post("/api/generate", json={"discipline": "ARC", "seed": 1})
    assert r.status_code == 200
    body = r.json()
    msgs = body["messages"]
    assert set(msgs) == {"DT_PARTIC", "DT_PARTIC_TEAMS", "DT_ENTRIES", "DT_SCHEDULE"}
    for doc_type, payload in msgs.items():
        assert payload["errors"] == [], f"{doc_type}: {payload['errors']}"
        assert payload["xml"].startswith("<?xml")


def test_index_page_renders_select():
    r = client.get("/")
    assert r.status_code == 200 and "<select" in r.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'api.app'`

- [ ] **Step 3: Create `api/__init__.py` and `tests/integration/__init__.py`**

Each contains:

```python
# package marker
```

- [ ] **Step 4: Write `api/app.py`**

```python
from __future__ import annotations
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from odf_validator.ingestion.builder import build_ruleset_pack
from generator.refdata import RefData
from generator.bundle import build_bundle

PACK_DIR = Path(os.environ.get("ODF_PACK_DIR", "Rules/SYOG26"))
REFDATA = RefData(build_ruleset_pack(PACK_DIR))
TEMPLATE = (Path(__file__).resolve().parent.parent / "web" / "templates" / "index.html")

app = FastAPI(title="ODF Message Generator")


class GenerateRequest(BaseModel):
    discipline: str
    seed: int = 1


@app.get("/api/disciplines")
def disciplines():
    return {"disciplines": REFDATA.disciplines()}


@app.post("/api/generate")
def generate(req: GenerateRequest):
    bundle = build_bundle(REFDATA, req.discipline, req.seed)
    return {
        "discipline": req.discipline,
        "messages": {
            doc_type: {"xml": xml.decode("utf-8"), "errors": errs}
            for doc_type, (xml, errs) in bundle.items()
        },
    }


@app.get("/", response_class=HTMLResponse)
def index():
    options = "".join(f'<option value="{d}">{d}</option>'
                      for d in REFDATA.disciplines())
    return TEMPLATE.read_text(encoding="utf-8").replace("<!--OPTIONS-->", options)
```

- [ ] **Step 5: Write `web/templates/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>ODF Message Generator</title></head>
<body>
  <h1>ODF Message Generator</h1>
  <label>Discipline:
    <select id="discipline"><!--OPTIONS--></select>
  </label>
  <button id="go">Generate</button>
  <pre id="out"></pre>
  <script>
    document.getElementById("go").onclick = async () => {
      const discipline = document.getElementById("discipline").value;
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({discipline, seed: 1}),
      });
      const data = await res.json();
      document.getElementById("out").textContent = JSON.stringify(data, null, 2);
    };
  </script>
</body>
</html>
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/integration/test_api.py -v`
Expected: 3 PASS

- [ ] **Step 7: Commit**

```bash
git add api web tests/integration
git commit -m "feat: FastAPI + web layer for discipline-driven generation"
```

---

## Task 13: Zip bundle download + full-suite green

**Files:**
- Modify: `api/app.py` (add `GET /api/generate.zip`)
- Test: `tests/integration/test_api_zip.py`

**Interfaces:**
- Consumes: `build_bundle` (Task 11).
- Produces: `GET /api/generate.zip?discipline=ARC&seed=1` → a `application/zip` response containing four `<doc_type>.xml` files.

- [ ] **Step 1: Write the failing test**

```python
import io
import zipfile
from fastapi.testclient import TestClient
from api.app import app

client = TestClient(app)


def test_zip_contains_four_messages():
    r = client.get("/api/generate.zip", params={"discipline": "ARC", "seed": 1})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    assert set(zf.namelist()) == {
        "DT_PARTIC.xml", "DT_PARTIC_TEAMS.xml", "DT_ENTRIES.xml", "DT_SCHEDULE.xml"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_api_zip.py -v`
Expected: FAIL with 404 (route not defined) → assertion error on status_code.

- [ ] **Step 3: Add the zip route to `api/app.py`**

Add these imports near the top (after existing imports):

```python
import io
import zipfile
from fastapi import Response
```

Add this route at the end of `api/app.py`:

```python
@app.get("/api/generate.zip")
def generate_zip(discipline: str, seed: int = 1):
    bundle = build_bundle(REFDATA, discipline, seed)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for doc_type, (xml, _errs) in bundle.items():
            zf.writestr(f"{doc_type}.xml", xml)
    return Response(content=buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition":
                             f'attachment; filename="{discipline}_bundle.zip"'})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_api_zip.py -v`
Expected: 1 PASS

- [ ] **Step 5: Run the full suite**

Run: `pytest -v`
Expected: all tests PASS (unit + integration). If the sandbox lacks `pytest`/`fastapi`, run the unit core with the fallback runner: `python -m tests.minirunner` (see Task 14).

- [ ] **Step 6: Commit**

```bash
git add api/app.py tests/integration/test_api_zip.py
git commit -m "feat: zip bundle download endpoint; full suite green"
```

---

## Task 14: Dependency-light fallback test runner

**Files:**
- Create: `tests/minirunner.py`

**Interfaces:**
- Consumes: the unit test modules under `tests/unit/`.
- Produces: `python -m tests.minirunner` — imports each `tests/unit/test_*.py`, runs every `test_*` function, prints pass/fail, exits non-zero on any failure. Provided because the validator project's sandbox lacks `pytest`/`fastapi` (carried-over quirk); it runs the web-free unit tests only.

- [ ] **Step 1: Write `tests/minirunner.py`**

```python
from __future__ import annotations
import importlib
import pkgutil
import sys
import traceback
import tests.unit as unit_pkg


def _iter_test_functions():
    for mod_info in pkgutil.iter_modules(unit_pkg.__path__):
        if not mod_info.name.startswith("test_"):
            continue
        module = importlib.import_module(f"tests.unit.{mod_info.name}")
        for attr in dir(module):
            if attr.startswith("test_"):
                yield f"{mod_info.name}.{attr}", getattr(module, attr)


def main() -> int:
    passed = failed = 0
    for name, fn in _iter_test_functions():
        try:
            fn()
            passed += 1
            print(f"PASS {name}")
        except Exception:
            failed += 1
            print(f"FAIL {name}")
            traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the fallback runner**

Run: `ODF_PACK_DIR=/path/to/Rules/SYOG26 python -m tests.minirunner`
Expected: every `PASS`, `0 failed`, exit code 0. (Tests that require FastAPI's `TestClient` live under `tests/integration/` and are intentionally excluded.)

- [ ] **Step 3: Commit**

```bash
git add tests/minirunner.py
git commit -m "test: dependency-light fallback runner for sandbox"
```

---

## Self-Review

**1. Spec coverage:**
- Random generation from reference files, operator picks discipline only → Tasks 2–11 (synthesizers + dataset + builders + bundle). ✓
- All four message types → Tasks 7–10. ✓
- All disciplines in pack → Task 11 property test iterates `RefData.disciplines()`. ✓
- Compliance = zero error findings via `Pipeline.run` → Task 6 `errors()`, asserted in Tasks 7–11. ✓
- Coded values only from `CodeRegistry` → Task 1 `RefData.codes` + Task 2 `pick_code`; dataset uses them. ✓
- Omit-empty guaranteed structurally → Task 4 serializer + defensive check. ✓
- 34-char RSC / DocumentCode → Task 2 `rsc`, asserted in Tasks 5 and 10. ✓
- Envelope required attrs, Version≥1, FeedFlag∈{P,T}, date pattern → Task 5. ✓
- Coherent bundle (entries reference partic/teams) → Task 3 dataset + Task 9 test. ✓
- Bounded regeneration + refuse on inactive XSD → Task 6 `generate_clean`, Task 0 schema smoke test. ✓
- Separate app depending on `odf_validator` → Task 0 `pyproject.toml`. ✓
- Seeded RNG with optional API seed → Task 2 onward take `rng`/`seed`; Task 12 request `seed`. ✓
- Web pick→generate→download (single + zip) → Tasks 12–13. ✓
- Sandbox fallback runner → Task 14. ✓

**2. Placeholder scan:** No "TBD"/"TODO"/"handle edge cases"/"similar to Task N"; every code step shows full code. ✓

**3. Type consistency:** `build(refdata, discipline, seed) -> bytes` is uniform across Tasks 7–10 and referenced identically in Task 11 `DOC_TYPES`. `errors(xml, pack) -> list[str]` and `generate_clean(make_xml, pack, seeds)` match their uses in Tasks 7–13. `build_odfbody(...) -> (root, comp)` return tuple is consumed consistently in all builders. `el`/`to_xml` signatures match every call site. `RefData.codes/description/disciplines/pack` names are stable throughout. ✓

**Note for the implementer:** the exact set of XSD-required attributes and any discipline-specific `code_membership` rules are the likely source of the first red self-check runs in Tasks 7–10. That is by design — the failing `Pipeline.run` output names the rule_id and message; fix the responsible attribute/element and re-run. The dataset's code-table fallbacks (VENUE, PHASE_TYPE, TeamType, ORGANISATION) already prefer real codes when the table exists.
