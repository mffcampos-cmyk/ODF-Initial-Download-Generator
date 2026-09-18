# SOLG28 (LA 2028) Generator Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the ODF Message Generator multi-Games, and add SOLG28 (LA 2028) as a discoverable target that is selectable but refuses to generate — with actionable instructions — until official LA2028 documents are dropped into `Rules/SOLG28/`.

**Architecture:** Games-specific message conventions move out of `generator/envelope.py` into per-pack YAML profiles under `generator/games/`. A new `PackRegistry` discovers every pack under the validator's `Rules/` directory, pairs each with its profile, and computes readiness by inspecting the loaded pack rather than reading a hand-maintained flag. The API and CLI gain a pack selector; not-ready packs return HTTP 409 with the reasons.

**Tech Stack:** Python 3.11+, FastAPI, lxml, PyYAML, `odf_validator` (sibling checkout, imported as a library), pytest with a dependency-light `tests/minirunner.py` fallback.

**Spec:** `docs/plans/2026-07-25-solg28-scaffold-design.md`

## Global Constraints

- **SYOG26 output must not change.** The ODF header carries `Date`, `Time` and `LogicalDate` from `datetime.now()`, so raw bytes differ on every run and a byte-comparison against committed files can never pass. The gate is instead a **content fingerprint**: `/tmp/sdd/snapshot.py` builds every discipline's bundle at seed 1, normalizes those three attributes, and SHA-256s the result. A pre-refactor baseline covering 25 disciplines and 214 messages is saved at `/tmp/sdd/baseline.json` and has been verified reproducible across runs. Any fingerprint change means SYOG2026 output changed. Checked in Tasks 2 and 8.

  ```bash
  source /tmp/sdd/env.sh
  python3 /tmp/sdd/snapshot.py > /tmp/sdd/after.json
  diff /tmp/sdd/baseline.json /tmp/sdd/after.json && echo "GATE PASS"
  ```
- **Nothing about LA2028 may be invented.** No guessed codes, discipline lists, venue codes, or version strings anywhere in the repo. `SOLG28.yaml` carries only the label and `default_source: OGEN`.
- **"Omit, don't empty" (Foundation Principle 6.7)** still governs all emitted XML. No task in this plan emits XML directly, but no change may introduce an empty attribute.
- **Every unit test must run under `python -m tests.minirunner`**, which imports test modules without pytest. That means: no pytest fixtures, no `monkeypatch`, no decorators in `tests/unit/`. Use plain module-level helpers and `try/finally`. (Existing `tests/unit/` files follow this; `tests/integration/` may use pytest and fastapi freely.)
- **Rule ids beginning `CORE_` are reserved by the validator engine.** No rules are authored in this plan; do not add any.
- **Exact reason strings matter.** The readiness reason text in Task 3 is user-facing operator guidance and is asserted by tests. Copy it verbatim.

**Sandbox environment — already set up. Source it in every bash call:**

```bash
source /tmp/sdd/env.sh
```

That sets `PROJ` (and cds to it), `GIT_DIR=/tmp/odfgen.git` with the project as
work tree, `ODF_PACK_DIR=/tmp/Rules/SYOG26`, and `PYTHONPATH` covering the
copied validator at `/tmp/validator`. Established facts about this sandbox:

- **Python is `python3` (3.10).** Not `python`. The project declares 3.11+ but
  the test suites run fine on 3.10.
- **No pytest, no fastapi, no PyPI access.** Unit tests run only via
  `python3 -m tests.minirunner`. That runner imports test modules and calls
  every `test_*` function with no arguments — so no fixtures, no `monkeypatch`,
  no decorators anywhere in `tests/unit/`.
- **`tests/integration/` cannot run here.** Write those files per the plan;
  Marcos runs them on Windows.
- **The mount forbids deleting files.** Creating and overwriting work; `rm`,
  `Path.unlink`, `shutil.rmtree` and `git checkout -- <path>` all fail with
  "Operation not permitted" anywhere under the project. Never write a test that
  deletes a file inside the project. Temp directories under `/tmp` are exempt
  and are where scratch files belong. To restore a tracked file, overwrite it:
  `git show HEAD:path > path`.
- **Git is a sandbox-local repo** at `/tmp/odfgen.git` with `core.fileMode
  false` (the mount reports every file as mode 700). Branch: `solg28-scaffold`.
  Commit normally — `git add` / `git commit` work once `env.sh` is sourced.
- **Baseline verified green:** 101 unit tests passing, pack loads in ~2.3s with
  schema compiled, 25 disciplines, 570 code tables.
- **Each bash call has a 45-second ceiling.** The full unit suite fits; keep
  individual commands under it.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `generator/games.py` (new) | `GamesProfile` dataclass + YAML loader. Knows nothing about packs. |
| `generator/games/SYOG26.yaml` (new) | The four SYOG2026 constants, moved out of `envelope.py`. |
| `generator/games/SOLG28.yaml` (new) | LA 2028 label + `default_source` only. |
| `generator/packs.py` (new) | `PackStatus`, `PackRegistry`: discovery, readiness, default resolution. |
| `generator/refdata.py` (modify) | Carries the profile; lazily resolves it from the pack name. |
| `generator/envelope.py` (modify) | Reads conventions off `refdata.games` instead of module constants. |
| `generator/packload.py` (modify) | Gains a tolerant loader for discovery; keeps the strict one. |
| `generator/dataset.py` (modify) | Gates the embedded SYOG2026 archery profile on the pack name. |
| `generator/export.py` (modify) | `--pack NAME` selector. |
| `api/app.py` (modify) | `GET /api/packs`; `pack` on every generation endpoint; 400/409. |
| `web/templates/index.html` (modify) | Games dropdown; readiness checklist replaces the form. |

---

## Task 1: Games profiles

**Files:**
- Create: `generator/games.py`
- Create: `generator/games/SYOG26.yaml`
- Create: `generator/games/SOLG28.yaml`
- Create: `tests/unit/test_games_profile.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: nothing.
- Produces: `generator.games.GamesProfile` (frozen dataclass with fields `pack_name: str`, `label: str`, `gen: str | None`, `codes: str | None`, `sport_template: str | None`, `sources: dict[str, str]`, `default_source: str`; methods `complete -> bool`, `missing_fields() -> list[str]`, `sport(discipline: str) -> str | None`, `source(discipline: str) -> str`), `generator.games.load_profile(pack_name: str, profile_dir=None) -> GamesProfile`, `generator.games.GamesProfileError`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_games_profile.py`:

```python
"""The Games profile is the only place Games-specific message conventions live.

SYOG26's profile must reproduce exactly the constants envelope.py shipped
with, or the refactor in Task 2 silently changes SYOG2026 output.
"""
import tempfile
from pathlib import Path

from generator.games import GamesProfile, GamesProfileError, load_profile


def test_syog26_profile_reproduces_the_shipped_constants():
    p = load_profile("SYOG26")
    assert p.gen == "OWG-2026-GEN-V4.5"
    assert p.codes == "SYOG-2026-CC-V0.04"
    assert p.sport_template == "SYOG-2026-{disc}-1.0"
    assert p.sources == {"ARC": "AWAARC1", "SWM": "CTO1"}
    assert p.default_source == "OGEN"


def test_sport_renders_per_discipline():
    p = load_profile("SYOG26")
    assert p.sport("SWM") == "SYOG-2026-SWM-1.0"
    assert p.sport("ARC") == "SYOG-2026-ARC-1.0"


def test_source_falls_back_to_default():
    p = load_profile("SYOG26")
    assert p.source("ARC") == "AWAARC1"
    assert p.source("ATH") == "OGEN"


def test_syog26_profile_is_complete():
    p = load_profile("SYOG26")
    assert p.complete
    assert p.missing_fields() == []


def test_solg28_profile_has_no_invented_versions():
    p = load_profile("SOLG28")
    assert p.label
    assert p.default_source == "OGEN"
    assert p.gen is None and p.codes is None and p.sport_template is None
    assert not p.complete
    assert p.missing_fields() == ["gen", "codes", "sport_template"]
    assert p.sport("ARC") is None


def test_missing_profile_raises_with_the_expected_path():
    d = Path(tempfile.mkdtemp())
    try:
        load_profile("NOPE", profile_dir=d)
        raise AssertionError("expected GamesProfileError")
    except GamesProfileError as e:
        assert "NOPE" in str(e)
        assert str(d / "NOPE.yaml") in str(e)


def test_non_mapping_profile_raises():
    d = Path(tempfile.mkdtemp())
    (d / "BAD.yaml").write_text("- just\n- a\n- list\n", encoding="utf-8")
    try:
        load_profile("BAD", profile_dir=d)
        raise AssertionError("expected GamesProfileError")
    except GamesProfileError as e:
        assert "mapping" in str(e)


def test_profile_is_frozen():
    p = load_profile("SYOG26")
    try:
        p.gen = "x"
        raise AssertionError("expected the dataclass to be frozen")
    except AttributeError:
        pass


def test_label_defaults_to_pack_name_when_absent():
    d = Path(tempfile.mkdtemp())
    (d / "X9.yaml").write_text("default_source: OGEN\n", encoding="utf-8")
    assert load_profile("X9", profile_dir=d).label == "X9"


def test_profile_dataclass_defaults():
    p = GamesProfile(pack_name="T", label="T")
    assert p.sources == {} and p.default_source == "OGEN"
    assert not p.complete
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m tests.minirunner test_games_profile`
Expected: FAIL — `ModuleNotFoundError: No module named 'generator.games'`

- [ ] **Step 3: Create `generator/games.py`**

```python
"""Games-specific message conventions.

Everything else the generator needs -- competition code, disciplines, event
structure, venues, entry counts -- is derived from the validator rule pack and
is therefore Games-agnostic for free. Four values are not derivable: they are
published in a Games' GEN document. They live here, one YAML file per pack, in
``generator/games/<PACK>.yaml``.

A profile whose ``gen`` / ``codes`` / ``sport_template`` are still null is
*incomplete*: the pack it belongs to is reported not-ready and generation is
refused, rather than emitting an invented version string.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

PROFILE_DIR = Path(__file__).resolve().parent / "games"

# Fields published in the Games' GEN document; all three are required before a
# pack can generate. Order is the order they are reported to the operator.
REQUIRED_FIELDS = ("gen", "codes", "sport_template")


class GamesProfileError(RuntimeError):
    """No profile file exists for a pack, or the file cannot be read."""


@dataclass(frozen=True)
class GamesProfile:
    """The Games-specific half of an ODF message header."""

    pack_name: str
    label: str
    gen: str | None = None
    codes: str | None = None
    sport_template: str | None = None
    sources: dict[str, str] = field(default_factory=dict)
    default_source: str = "OGEN"

    @property
    def complete(self) -> bool:
        """True when every GEN-document value is known."""
        return not self.missing_fields()

    def missing_fields(self) -> list[str]:
        return [name for name in REQUIRED_FIELDS if not getattr(self, name)]

    def sport(self, discipline: str) -> str | None:
        """``Competition/@Sport`` for a discipline, or None if unknown."""
        if not self.sport_template:
            return None
        return self.sport_template.format(disc=discipline)

    def source(self, discipline: str) -> str:
        """``OdfBody/@Source``: the system generating the message."""
        return self.sources.get(discipline, self.default_source)


def load_profile(pack_name: str,
                 profile_dir: Path | str | None = None) -> GamesProfile:
    directory = Path(profile_dir) if profile_dir is not None else PROFILE_DIR
    path = directory / f"{pack_name}.yaml"
    if not path.exists():
        raise GamesProfileError(
            f"No Games profile for pack '{pack_name}': expected {path}. "
            f"Create it with the pack's label and, once that Games' GEN "
            f"document is available, its gen / codes / sport_template.")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        raise GamesProfileError(f"Games profile {path} is unreadable: {e}") from e
    if not isinstance(raw, dict):
        raise GamesProfileError(f"Games profile {path} must be a YAML mapping")
    return GamesProfile(
        pack_name=pack_name,
        label=raw.get("label") or pack_name,
        gen=raw.get("gen"),
        codes=raw.get("codes"),
        sport_template=raw.get("sport_template"),
        sources=dict(raw.get("sources") or {}),
        default_source=raw.get("default_source") or "OGEN",
    )
```

- [ ] **Step 4: Create `generator/games/SYOG26.yaml`**

These values are moved verbatim from `generator/envelope.py` lines 8–14. Do not
retype them from memory — copy them.

```yaml
# Youth Olympic Games 2026. Values as observed in the real-life feed and
# previously hardcoded in generator/envelope.py.
label: Youth Olympic Games 2026
gen: OWG-2026-GEN-V4.5
codes: SYOG-2026-CC-V0.04
sport_template: SYOG-2026-{disc}-1.0
# SCGEN@Source: the system generating the message. Real-life feeds observed so
# far: World Archery "AWAARC1" (ARC), CTO "CTO1" (SWM).
sources:
  ARC: AWAARC1
  SWM: CTO1
default_source: OGEN
```

- [ ] **Step 5: Create `generator/games/SOLG28.yaml`**

```yaml
# LA 2028. No official LA2028 source documents exist yet.
#
# gen, codes and sport_template are published in the LA2028 GEN document and
# cannot be derived from the rule pack. Until they are filled in here, this
# pack is reported not-ready and the generator refuses to emit LA2028 messages
# rather than inventing version strings. Do not guess these values.
label: LA 2028
gen:
codes:
sport_template:
default_source: OGEN
```

- [ ] **Step 6: Declare PyYAML and ship the profile files**

In `pyproject.toml`, add `"pyyaml>=6.0"` to `[project].dependencies` (it is
currently only a transitive dependency of `odf_validator`), and add package
data so the YAML files are installed alongside the code:

```toml
dependencies = [
    "lxml>=5.0",
    "fastapi>=0.110",
    "uvicorn>=0.29",
    "jinja2>=3.1",
    "openpyxl>=3.1",
    "pyyaml>=6.0",
]
```

```toml
[tool.setuptools.package-data]
generator = ["games/*.yaml"]
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m tests.minirunner test_games_profile`
Expected: PASS — 10 passed, 0 failed

- [ ] **Step 8: Commit**

```bash
git add generator/games.py generator/games/SYOG26.yaml generator/games/SOLG28.yaml tests/unit/test_games_profile.py pyproject.toml
git commit -m "feat: Games profiles for per-Games message conventions"
```

---

## Task 2: Envelope reads the profile

**Files:**
- Modify: `generator/refdata.py:9-11` (the `__init__`)
- Modify: `generator/envelope.py:1-62` (whole file)
- Modify: `generator/packload.py:96`
- Modify: `tests/unit/test_envelope.py`

**Interfaces:**
- Consumes: `generator.games.load_profile`, `generator.games.GamesProfile` from Task 1.
- Produces: `RefData.games -> GamesProfile` (lazy property, resolves by `self.pack.name` when no profile was injected); `RefData(pack, pack_dir=None, profile=None)`. `build_odfbody`'s signature is unchanged — the profile arrives via `refdata`, so no builder call site changes.

**Why the profile rides on `RefData` rather than a new `build_odfbody`
parameter:** all four builders already receive `refdata` and its docstring
states that every reference-file-derived constraint is reached through it.
Threading a fifth positional argument through `partic.py`, `partic_teams.py`,
`entries.py` and `schedule.py` would touch four call sites for no benefit and
put the byte-identical regression gate at risk. This is a deliberate
refinement of the spec's wording, not a change to its intent.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_envelope.py`:

```python
def test_envelope_takes_versions_from_the_games_profile():
    rd = RefData(PACK)
    root, comp = build_odfbody(random.Random(1), rd, "SWM", "DT_PARTIC",
                               competition_code(rd))
    assert comp.get("Gen") == rd.games.gen
    assert comp.get("Codes") == rd.games.codes
    assert comp.get("Sport") == rd.games.sport("SWM")
    assert root.get("Source") == rd.games.source("SWM")


def test_envelope_refuses_an_incomplete_profile():
    from generator.games import GamesProfile
    rd = RefData(PACK, profile=GamesProfile(pack_name="SOLG28", label="LA 2028"))
    try:
        build_odfbody(random.Random(1), rd, "ARC", "DT_PARTIC",
                      competition_code(rd))
        raise AssertionError("expected ValueError for an incomplete profile")
    except ValueError as e:
        assert "SOLG28" in str(e)
        assert "gen" in str(e)


def test_no_syog_literal_remains_in_envelope():
    import pathlib
    src = pathlib.Path("generator/envelope.py").read_text(encoding="utf-8")
    assert "SYOG-2026" not in src
    assert "OWG-2026" not in src
    assert "AWAARC1" not in src
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m tests.minirunner test_envelope`
Expected: FAIL — `AttributeError: 'RefData' object has no attribute 'games'`

- [ ] **Step 3: Add the lazy profile to `RefData`**

In `generator/refdata.py`, replace the `__init__` with:

```python
    def __init__(self, pack, pack_dir=None, profile=None):
        self.pack = pack
        self.pack_dir = pack_dir
        self._profile = profile
        self._func_cache: dict[str, list] = {}

    @property
    def games(self):
        """The GamesProfile for this pack, resolved lazily by pack name so
        every existing ``RefData(pack)`` call site keeps working."""
        if self._profile is None:
            from .games import load_profile
            self._profile = load_profile(self.pack.name)
        return self._profile
```

- [ ] **Step 4: Rewrite `generator/envelope.py`**

Replace the whole file with:

```python
from __future__ import annotations
import datetime
import random
from . import fields
from .serialize import el


def competition_code(refdata) -> str:
    codes = refdata.codes("COMPETITION_CODE")
    if not codes:
        raise ValueError("COMPETITION_CODE table is empty; cannot build envelope")
    return codes[0]


def _discipline_code(refdata, discipline: str) -> str:
    valid = set(refdata.pack.disciplines)
    return discipline if discipline in valid else sorted(valid)[0]


def build_odfbody(rng: random.Random, refdata, discipline: str,
                  document_type: str, competition_code: str,
                  document_code: str | None = None, overrides=None):
    disc = _discipline_code(refdata, discipline)
    ov = overrides.normalize() if overrides is not None else None
    profile = refdata.games
    if not profile.complete:
        raise ValueError(
            f"Games profile for '{profile.pack_name}' is incomplete: "
            f"{', '.join(profile.missing_fields())} are unknown. Fill them in "
            f"from that Games' GEN document in "
            f"generator/games/{profile.pack_name}.yaml before generating.")

    # Date/Time/LogicalDate always reflect the real moment of generation
    # (not user-customizable), per the ODF header definition.
    now = datetime.datetime.now()
    date = now.date().isoformat()                       # YYYY-MM-DD
    time = now.strftime("%H%M%S") + f"{now.microsecond // 1000:03d}"  # HHMMSSmmm

    comp_code = ov.competition_code if ov and ov.competition_code else competition_code
    source = ov.source if ov and ov.source else profile.source(disc)

    root = el("OdfBody", {
        "CompetitionCode": comp_code,
        # Full RSC per message spec: discipline level (CC@DISCIPLINE) by
        # default; per-event messages (DT_ENTRIES) pass their Event RSC.
        "DocumentCode": document_code or fields.rsc(rng, disc),
        "DocumentType": document_type,
        "Version": "1",
        "FeedFlag": fields.feed_flag(rng),
        "Date": date,
        "Time": time,
        "LogicalDate": date,
        "Source": source,
    })
    comp = el("Competition", {
        "Gen": ov.gen if ov and ov.gen else profile.gen,
        "Sport": ov.sport if ov and ov.sport else profile.sport(disc),
        "Codes": ov.codes if ov and ov.codes else profile.codes,
    })
    root.append(comp)
    return root, comp
```

Note: `_discipline_code` falls back to the first valid discipline, so
`profile.sport(disc)` is always called with a discipline the pack knows —
matching the previous behaviour where `f"SYOG-2026-{disc}-1.0"` used the same
resolved `disc`.

- [ ] **Step 5: Inject the profile at load time**

In `generator/packload.py`, change the final line of `load_refdata` from
`return RefData(pack, pack_dir=resolved)` to:

```python
    from .games import load_profile
    return RefData(pack, pack_dir=resolved, profile=load_profile(pack.name))
```

- [ ] **Step 6: Run the envelope tests**

Run: `python -m tests.minirunner test_envelope`
Expected: PASS — all envelope tests, including the three new ones.

- [ ] **Step 7: Run the full unit suite**

Run: `python -m tests.minirunner`
Expected: PASS, 0 failed.

- [ ] **Step 8: Verify SYOG26 content is unchanged (the regression gate)**

```bash
source /tmp/sdd/env.sh
python3 /tmp/sdd/snapshot.py > /tmp/sdd/after-task2.json
diff /tmp/sdd/baseline.json /tmp/sdd/after-task2.json && echo "GATE PASS"
```

Expected: `GATE PASS` with no diff output. The baseline covers 25 disciplines
and 214 messages, fingerprinted with `Date`/`Time`/`LogicalDate` normalized
(those three are `datetime.now()` values and legitimately differ every run).

Any fingerprint difference means this refactor changed SYOG2026 output — stop
and fix before continuing. `diff` names the discipline and document type, which
localizes the regression immediately.

- [ ] **Step 9: Commit**

```bash
git add generator/refdata.py generator/envelope.py generator/packload.py tests/unit/test_envelope.py
git commit -m "refactor: envelope reads Games conventions from the profile"
```

---

## Task 3: Pack registry and readiness

**Files:**
- Create: `generator/packs.py`
- Create: `tests/unit/test_pack_registry.py`
- Modify: `tests/unit/test_packload.py` (one test's expectation changes)

**Interfaces:**
- Consumes: `generator.games.load_profile`, `GamesProfile`, `GamesProfileError`; `generator.packload.looks_like_pack`, `resolve_pack_dir`, `PackDirError`; `generator.refdata.RefData`.
- Produces:
  - `generator.packs.PackStatus` — frozen dataclass, fields `name: str`, `label: str`, `ready: bool`, `reasons: tuple[str, ...]`, `disciplines: tuple[str, ...]`. The two sequence fields are coerced to tuples in `__post_init__`, so `frozen=True` is real rather than nominal: the registry hands out the same object to every caller, and a caller cannot corrupt it. Compare against tuples (`== ()`, `== ("ZZZ",)`), not lists. `to_dict()` converts both back to plain `list` for JSON serialization.
  - `generator.packs.PackRegistry` — `discover(rules_dir=None, profile_dir=None) -> PackRegistry` (classmethod), `names() -> list[str]`, `get(name) -> RefData` (raises `PackNotReady` / `UnknownPack`), `status(name) -> PackStatus`, `statuses() -> list[PackStatus]`, `default_name() -> str`. `profile_dir` overrides where Games profiles are read from; it exists so tests can supply a hermetic profile directory instead of writing into `generator/games/`.
  - `generator.packs.UnknownPack`, `generator.packs.PackNotReady` (both subclass `RuntimeError`).
  - `generator.packs.rules_dir_from_env() -> Path`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_pack_registry.py`:

```python
"""Pack discovery must tolerate an empty pack (SOLG28 today) while still
refusing to generate against one."""
import os
import tempfile
from pathlib import Path

from generator.packs import (PackNotReady, PackRegistry, PackStatus,
                             UnknownPack, rules_dir_from_env)

RULES_DIR = Path(os.environ["ODF_PACK_DIR"]).parent


def _registry():
    return PackRegistry.discover(RULES_DIR)


def test_discovery_finds_both_packs():
    reg = _registry()
    assert "SYOG26" in reg.names()
    assert "SOLG28" in reg.names()


def test_syog26_is_ready_with_disciplines():
    st = _registry().status("SYOG26")
    assert st.ready
    assert st.reasons == ()
    assert "ARC" in st.disciplines


def test_solg28_is_not_ready_and_says_why():
    st = _registry().status("SOLG28")
    assert not st.ready
    assert st.disciplines == ()
    joined = " ".join(st.reasons)
    assert "No XSD compiles" in joined
    assert "No Common Codes loaded" in joined
    assert "No disciplines" in joined
    assert "Games profile incomplete" in joined
    # Every reason names the folder the operator has to put something into.
    assert "Rules/SOLG28" in joined
    assert "generator/games/SOLG28.yaml" in joined


def test_get_returns_refdata_for_a_ready_pack():
    rd = _registry().get("SYOG26")
    assert rd.disciplines()
    assert rd.games.complete


def test_get_refuses_a_not_ready_pack_with_the_reasons():
    try:
        _registry().get("SOLG28")
        raise AssertionError("expected PackNotReady")
    except PackNotReady as e:
        assert "SOLG28" in str(e)
        assert "No XSD compiles" in str(e)


def test_get_rejects_an_unknown_pack():
    try:
        _registry().get("NOPE")
        raise AssertionError("expected UnknownPack")
    except UnknownPack as e:
        assert "NOPE" in str(e)
        assert "SYOG26" in str(e)


def test_decoy_directory_is_discovered_not_ready_rather_than_raising():
    d = Path(tempfile.mkdtemp())
    decoy = d / "DECOY"
    decoy.mkdir()
    (decoy / "pack.yaml").write_text("version: ''\n", encoding="utf-8")
    (decoy / ".ingestion_state.json").write_text("{}", encoding="utf-8")
    reg = PackRegistry.discover(d)
    assert reg.names() == ["DECOY"]
    st = reg.status("DECOY")
    assert not st.ready
    # No profile file exists for DECOY; that is a reason, not a crash.
    assert any("Games profile" in r for r in st.reasons)


def test_zero_packs_is_a_hard_failure():
    empty = Path(tempfile.mkdtemp())
    try:
        PackRegistry.discover(empty)
        raise AssertionError("expected PackDirError")
    except Exception as e:
        assert "no rule packs" in str(e).lower()


def test_default_name_prefers_odf_games():
    old = os.environ.get("ODF_GAMES")
    os.environ["ODF_GAMES"] = "SOLG28"
    try:
        assert _registry().default_name() == "SOLG28"
    finally:
        if old is None:
            os.environ.pop("ODF_GAMES", None)
        else:
            os.environ["ODF_GAMES"] = old


def test_default_name_rejects_an_unknown_odf_games():
    old = os.environ.get("ODF_GAMES")
    os.environ["ODF_GAMES"] = "NOPE"
    try:
        _registry().default_name()
        raise AssertionError("expected UnknownPack")
    except UnknownPack:
        pass
    finally:
        if old is None:
            os.environ.pop("ODF_GAMES", None)
        else:
            os.environ["ODF_GAMES"] = old


def test_default_name_falls_back_to_the_pack_dir_pack():
    old = os.environ.get("ODF_GAMES")
    os.environ.pop("ODF_GAMES", None)
    try:
        assert _registry().default_name() == "SYOG26"
    finally:
        if old is not None:
            os.environ["ODF_GAMES"] = old


def test_rules_dir_from_env_uses_the_pack_dir_parent():
    assert rules_dir_from_env() == RULES_DIR


def test_status_is_frozen():
    st = PackStatus(name="X", label="X", ready=False, reasons=[], disciplines=[])
    try:
        st.ready = True
        raise AssertionError("expected the dataclass to be frozen")
    except AttributeError:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m tests.minirunner test_pack_registry`
Expected: FAIL — `ModuleNotFoundError: No module named 'generator.packs'`

- [ ] **Step 3: Create `generator/packs.py`**

```python
"""Discovery of every Games rule pack, and whether each one can generate.

The generator used to bind one pack at import time. It now discovers every
pack under the validator's ``Rules/`` directory so the operator can choose a
Games in the UI, and reports *why* a pack cannot generate rather than either
crashing at startup or silently producing nothing.

Readiness is computed from the loaded pack, never from a hand-maintained flag:
drop the official documents into ``Rules/<PACK>/``, restart, and the pack
becomes ready by itself.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .games import GamesProfile, GamesProfileError, load_profile
from .packload import PackDirError, resolve_pack_dir
from .refdata import RefData


class UnknownPack(RuntimeError):
    """A pack name that was never discovered."""


class PackNotReady(RuntimeError):
    """A discovered pack that cannot generate yet."""


@dataclass(frozen=True)
class PackStatus:
    name: str
    label: str
    ready: bool
    reasons: list[str] = field(default_factory=list)
    disciplines: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"name": self.name, "label": self.label, "ready": self.ready,
                "reasons": list(self.reasons),
                "disciplines": list(self.disciplines)}


def rules_dir_from_env() -> Path:
    """The directory holding one subfolder per pack.

    ``ODF_RULES_DIR`` wins; otherwise it is the parent of whatever
    ``resolve_pack_dir()`` settles on, which keeps the existing
    ``ODF_PACK_DIR`` setup working untouched."""
    explicit = os.environ.get("ODF_RULES_DIR")
    if explicit:
        return Path(explicit)
    return Path(resolve_pack_dir()).parent


def _readiness(pack, profile: GamesProfile | None,
               profile_error: str | None) -> list[str]:
    """Reasons this pack cannot generate. Empty means ready.

    The wording mirrors the numbered drop-in steps in
    ``Rules/<PACK>/_reference/README.md`` so an operator who has never read
    that file still learns exactly what to do."""
    name = pack.name
    reasons: list[str] = []
    if getattr(pack, "schema", None) is None:
        reasons.append(
            f"No XSD compiles - drop the {name} schema file(s) under "
            f"Rules/{name}/ and set root_xsd in pack.yaml if the entry point "
            f"is not odf2.xsd.")
    if not pack.codes.names():
        reasons.append(
            f"No Common Codes loaded - drop the {name} Common Codes workbook "
            f"(.xlsx, or .xml with <Codeset> elements) under "
            f"Rules/{name}/codes/.")
    if not pack.disciplines:
        reasons.append(
            f"No disciplines - create Rules/{name}/Disciplines/<CODE>/ per "
            f"sport and drop that discipline's Data Dictionary in.")
    if profile is None:
        reasons.append(
            f"Games profile missing - {profile_error} "
            f"See generator/games/{name}.yaml.")
    elif not profile.complete:
        reasons.append(
            f"Games profile incomplete - set "
            f"{', '.join(profile.missing_fields())} in "
            f"generator/games/{name}.yaml from the {name} GEN document.")
    return reasons


class PackRegistry:
    """Every discovered pack, its profile, and its readiness."""

    def __init__(self, entries: dict[str, tuple]):
        # name -> (RefData, PackStatus)
        self._entries = entries

    @classmethod
    def discover(cls, rules_dir: Path | str | None = None,
                 profile_dir: Path | str | None = None) -> "PackRegistry":
        directory = Path(rules_dir) if rules_dir is not None else rules_dir_from_env()
        entries: dict[str, tuple] = {}
        for child in sorted(p for p in directory.iterdir() if p.is_dir()):
            if not (child / "pack.yaml").exists():
                continue
            entries[child.name] = cls._load_one(child, profile_dir)
        if not entries:
            raise PackDirError(
                f"Found no rule packs under {directory}. A pack is a subfolder "
                f"containing a pack.yaml. Set ODF_RULES_DIR (or ODF_PACK_DIR) "
                f"to the validator's Rules folder.")
        return cls(entries)

    @staticmethod
    def _load_one(pack_dir: Path, profile_dir: Path | str | None = None) -> tuple:
        from odf_validator.ingestion.builder import build_ruleset_pack

        name = pack_dir.name
        profile: GamesProfile | None = None
        profile_error: str | None = None
        try:
            profile = load_profile(name, profile_dir)
        except GamesProfileError as e:
            profile_error = str(e)

        try:
            pack = build_ruleset_pack(pack_dir)
        except Exception as e:
            status = PackStatus(
                name=name, label=(profile.label if profile else name),
                ready=False,
                reasons=[f"Pack failed to load: {e}"], disciplines=[])
            return (None, status)

        reasons = _readiness(pack, profile, profile_error)
        refdata = RefData(pack, pack_dir=pack_dir, profile=profile)
        status = PackStatus(
            name=name, label=(profile.label if profile else name),
            ready=not reasons, reasons=reasons,
            disciplines=sorted(pack.disciplines))
        return (refdata, status)

    def names(self) -> list[str]:
        return sorted(self._entries)

    def status(self, name: str) -> PackStatus:
        if name not in self._entries:
            raise UnknownPack(
                f"unknown pack: {name}. Known packs: {', '.join(self.names())}")
        return self._entries[name][1]

    def statuses(self) -> list[PackStatus]:
        return [self._entries[n][1] for n in self.names()]

    def get(self, name: str) -> RefData:
        status = self.status(name)
        if not status.ready:
            raise PackNotReady(
                f"pack {name} cannot generate yet:\n"
                + "\n".join(f"  - {r}" for r in status.reasons))
        return self._entries[name][0]

    def default_name(self) -> str:
        chosen = os.environ.get("ODF_GAMES")
        if chosen:
            if chosen not in self._entries:
                raise UnknownPack(
                    f"ODF_GAMES names an unknown pack: {chosen}. "
                    f"Known packs: {', '.join(self.names())}")
            return chosen
        try:
            from_pack_dir = Path(resolve_pack_dir()).name
            if from_pack_dir in self._entries:
                return from_pack_dir
        except PackDirError:
            pass
        for name in self.names():
            if self._entries[name][1].ready:
                return name
        return self.names()[0]
```

- [ ] **Step 4: Run the registry tests**

Run: `python -m tests.minirunner test_pack_registry`
Expected: PASS — 13 passed, 0 failed.

If `test_solg28_is_not_ready_and_says_why` fails on the `Rules/SOLG28`
substring, check that the reason strings use forward slashes exactly as
written above; they are operator-facing text, not filesystem paths.

- [ ] **Step 5: Update the one changed expectation in `test_packload.py`**

`load_refdata` keeps its strict behaviour — this is the *selection* path, not
the discovery path — so `test_load_refdata_rejects_empty_pack` still passes
unchanged. Add a test pinning the new division of responsibility so a future
reader knows it is intentional. Append to `tests/unit/test_packload.py`:

```python
def test_strict_load_and_tolerant_discovery_are_different_paths():
    """load_refdata() is the strict selection path and still refuses an empty
    pack; PackRegistry.discover() is the tolerant listing path and reports the
    same pack as not-ready instead. Both behaviours are intentional."""
    import tempfile
    from pathlib import Path

    from generator.packs import PackRegistry

    d = Path(tempfile.mkdtemp())
    empty = d / "EMPTYPACK"
    empty.mkdir()
    (empty / "pack.yaml").write_text("version: ''\n", encoding="utf-8")

    try:
        load_refdata(empty)
        raise AssertionError("expected PackDirError from the strict path")
    except PackDirError:
        pass

    reg = PackRegistry.discover(d)
    assert reg.status("EMPTYPACK").ready is False
```

- [ ] **Step 6: Run the full unit suite**

Run: `python -m tests.minirunner`
Expected: PASS, 0 failed.

- [ ] **Step 7: Commit**

```bash
git add generator/packs.py tests/unit/test_pack_registry.py tests/unit/test_packload.py
git commit -m "feat: pack registry with derived readiness"
```

---

## Task 4: Prove the drop-in path works

**Files:**
- Create: `tests/unit/test_pack_dropin.py`

**Interfaces:**
- Consumes: `generator.packs.PackRegistry.discover(rules_dir, profile_dir)`.
- Produces: nothing consumed by later tasks. This task is a proof, not a feature.

Everything this test creates lives in a temp directory — both the synthetic
pack and its Games profile, via `discover`'s `profile_dir` argument. Nothing is
written into `generator/games/`, so the test leaves no residue and cannot be
affected by (or affect) the real profiles.

The entire design promises "SOLG28 starts working the day the documents land."
Without LA2028 documents that promise is untestable — unless a minimal
synthetic pack stands in for them. That is what this task builds.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_pack_dropin.py`:

```python
"""The drop-in proof.

A pack that is not-ready must become ready purely by adding files -- no code
change, no flag to flip. This builds a minimal synthetic pack in a temp
directory, asserts it starts not-ready, adds an XSD, a codes file, a
discipline folder and a complete profile, and asserts it flips to ready.
"""
import shutil
import tempfile
from pathlib import Path

from generator.packs import PackRegistry

MINIMAL_XSD = """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="OdfBody">
    <xs:complexType>
      <xs:anyAttribute processContents="skip"/>
    </xs:complexType>
  </xs:element>
</xs:schema>
"""

MINIMAL_CODES = """<?xml version="1.0" encoding="UTF-8"?>
<Codesets>
  <Codeset name="DISCIPLINE">
    <Code value="ZZZ" description="Test discipline"/>
  </Codeset>
  <Codeset name="COMPETITION_CODE">
    <Code value="TEST0000" description="Test competition"/>
  </Codeset>
</Codesets>
"""

PROFILE = """label: Test Games
gen: TEST-GEN-V1.0
codes: TEST-CC-V1.0
sport_template: TEST-{disc}-1.0
default_source: OGEN
"""


def _fresh(profile_text: str | None = None):
    """A synthetic rules dir + profile dir, both under a temp root."""
    root = Path(tempfile.mkdtemp())
    rules, profiles = root / "Rules", root / "profiles"
    pack = rules / "DROPIN"
    pack.mkdir(parents=True)
    profiles.mkdir()
    (pack / "pack.yaml").write_text("version: ''\n", encoding="utf-8")
    if profile_text is not None:
        (profiles / "DROPIN.yaml").write_text(profile_text, encoding="utf-8")
    return root, rules, profiles, pack


def _add_documents(pack: Path) -> None:
    """Everything an operator drops into Rules/<PACK>/ for a real Games."""
    (pack / "xsd").mkdir()
    (pack / "xsd" / "odf2.xsd").write_text(MINIMAL_XSD, encoding="utf-8")
    (pack / "codes").mkdir()
    (pack / "codes" / "codes.xml").write_text(MINIMAL_CODES, encoding="utf-8")
    (pack / "Disciplines" / "ZZZ").mkdir(parents=True)
    (pack / "Disciplines" / "ZZZ" / "ODF_ZZZ_Data_Dictionary.md").write_text(
        "# ZZZ Data Dictionary\n", encoding="utf-8")


def test_empty_pack_starts_not_ready():
    root, rules, profiles, _pack = _fresh(PROFILE)
    try:
        st = PackRegistry.discover(rules, profiles).status("DROPIN")
        assert not st.ready
        assert st.reasons
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dropping_in_documents_flips_the_pack_to_ready():
    root, rules, profiles, pack = _fresh(PROFILE)
    try:
        _add_documents(pack)
        st = PackRegistry.discover(rules, profiles).status("DROPIN")
        assert st.ready, f"still not ready: {st.reasons}"
        assert st.disciplines == ("ZZZ",)
        assert st.label == "Test Games"

        rd = PackRegistry.discover(rules, profiles).get("DROPIN")
        assert rd.games.sport("ZZZ") == "TEST-ZZZ-1.0"
        assert rd.games.source("ZZZ") == "OGEN"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_incomplete_profile_alone_keeps_the_pack_not_ready():
    """Documents present but version strings unknown -- exactly SOLG28's state
    once the XSD and codes arrive but before the GEN document is read."""
    root, rules, profiles, pack = _fresh(
        "label: Test Games\ndefault_source: OGEN\n")
    try:
        _add_documents(pack)
        st = PackRegistry.discover(rules, profiles).status("DROPIN")
        assert not st.ready
        assert len(st.reasons) == 1
        assert "Games profile incomplete" in st.reasons[0]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_missing_profile_is_a_reason_not_a_crash():
    root, rules, profiles, pack = _fresh(None)
    try:
        _add_documents(pack)
        st = PackRegistry.discover(rules, profiles).status("DROPIN")
        assert not st.ready
        assert any("Games profile missing" in r for r in st.reasons)
    finally:
        shutil.rmtree(root, ignore_errors=True)
```

- [ ] **Step 2: Run the test**

Run: `python3 -m tests.minirunner test_pack_dropin`
Expected: PASS — 4 passed, 0 failed.

This task adds no production code. If a test fails, the bug is in Task 3's
readiness logic, not here. Likely causes: the validator's ingestion does not
recognise a `<Codesets>` XML file at that path (check
`odf_validator/codes/xml.py` for the element names it expects), or the minimal
XSD does not compile. Fix by adjusting the fixture content to whatever the
ingestion actually accepts — not by weakening the readiness checks.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_pack_dropin.py
git commit -m "test: prove a not-ready pack becomes ready by adding files"
```

---

## Task 5: API pack selection

**Files:**
- Modify: `api/app.py` (whole file)
- Create: `tests/integration/test_api_packs.py`

**Interfaces:**
- Consumes: `generator.packs.PackRegistry`, `PackNotReady`, `UnknownPack`.
- Produces: `api.app.REGISTRY` (a `PackRegistry`); `GET /api/packs`; a `pack: str | None` field on `GenerateRequest` and a `pack` query parameter on `/api/disciplines` and `/api/generate.zip`; `api.app.resolve(pack_name) -> RefData` raising the two errors above.

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_api_packs.py`:

```python
from fastapi.testclient import TestClient

from api.app import app

client = TestClient(app)


def test_packs_endpoint_lists_both_with_readiness():
    r = client.get("/api/packs")
    assert r.status_code == 200
    body = r.json()
    assert body["default"] == "SYOG26"
    by_name = {p["name"]: p for p in body["packs"]}
    assert by_name["SYOG26"]["ready"] is True
    assert "ARC" in by_name["SYOG26"]["disciplines"]
    assert by_name["SOLG28"]["ready"] is False
    assert by_name["SOLG28"]["label"] == "LA 2028"
    assert by_name["SOLG28"]["disciplines"] == []
    assert any("No XSD compiles" in r_ for r_ in by_name["SOLG28"]["reasons"])


def test_generate_against_a_not_ready_pack_returns_409_with_reasons():
    r = client.post("/api/generate",
                    json={"discipline": "ARC", "seed": 1, "pack": "SOLG28"})
    assert r.status_code == 409
    body = r.json()
    assert body["pack"] == "SOLG28"
    assert body["reasons"]
    assert any("Rules/SOLG28" in reason for reason in body["reasons"])


def test_generate_against_an_unknown_pack_returns_400():
    r = client.post("/api/generate",
                    json={"discipline": "ARC", "seed": 1, "pack": "NOPE"})
    assert r.status_code == 400
    assert "SYOG26" in " ".join(r.json()["known"])


def test_generate_defaults_to_syog26_when_pack_is_omitted():
    r = client.post("/api/generate", json={"discipline": "ARC", "seed": 1})
    assert r.status_code == 200
    for payload in r.json()["messages"].values():
        assert payload["errors"] == []


def test_disciplines_endpoint_is_pack_scoped():
    r = client.get("/api/disciplines?pack=SOLG28")
    assert r.status_code == 409
    r = client.get("/api/disciplines?pack=SYOG26")
    assert r.status_code == 200 and "ARC" in r.json()["disciplines"]


def test_zip_endpoint_rejects_a_not_ready_pack():
    r = client.get("/api/generate.zip?discipline=ARC&pack=SOLG28")
    assert r.status_code == 409
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_api_packs.py -v`
Expected: FAIL — 404 on `/api/packs`, and `pack` is rejected as an unknown field.

- [ ] **Step 3: Replace the module header of `api/app.py`**

Replace lines 8–19 (the imports through `app = FastAPI(...)`) with:

```python
from generator.packs import PackNotReady, PackRegistry, UnknownPack
from generator.bundle import build_bundle
from generator.export import export_bundle, PROJECT_ROOT
from generator.overrides import Overrides

# Discovers every pack under the validator's Rules/ folder. A pack that cannot
# generate yet (no XSD, no codes, no disciplines, or an incomplete Games
# profile) is still listed, with the reasons, instead of crashing startup.
# Discovering no packs at all remains a hard failure.
REGISTRY = PackRegistry.discover()
TEMPLATE = (Path(__file__).resolve().parent.parent / "web" / "templates" / "index.html")

app = FastAPI(title="ODF Message Generator")


def resolve(pack_name: str | None) -> RefData:
    """The RefData for a request's pack, defaulting to the startup default."""
    return REGISTRY.get(pack_name or REGISTRY.default_name())


def _pack_error(exc: Exception, pack_name: str | None) -> JSONResponse:
    name = pack_name or REGISTRY.default_name()
    if isinstance(exc, UnknownPack):
        return JSONResponse(status_code=400,
                            content={"error": str(exc), "pack": name,
                                     "known": REGISTRY.names()})
    status = REGISTRY.status(name)
    return JSONResponse(status_code=409,
                        content={"error": str(exc), "pack": name,
                                 "reasons": status.reasons})
```

Add `from generator.refdata import RefData` to the imports at the top of the
file (it is used in the `resolve` annotation).

- [ ] **Step 4: Add `pack` to the request model**

In `GenerateRequest`, add as the first field after `discipline`:

```python
    pack: str | None = None
```

- [ ] **Step 5: Replace the endpoints**

Replace `disciplines`, `generate`, `save`, `index` and `generate_zip` with:

```python
@app.get("/api/packs")
def packs():
    return {"default": REGISTRY.default_name(),
            "packs": [s.to_dict() for s in REGISTRY.statuses()]}


@app.get("/api/disciplines")
def disciplines(pack: str | None = None):
    try:
        refdata = resolve(pack)
    except (UnknownPack, PackNotReady) as e:
        return _pack_error(e, pack)
    return {"pack": pack or REGISTRY.default_name(),
            "disciplines": refdata.disciplines()}


@app.post("/api/generate")
def generate(req: GenerateRequest):
    try:
        refdata = resolve(req.pack)
    except (UnknownPack, PackNotReady) as e:
        return _pack_error(e, req.pack)
    if req.discipline not in refdata.disciplines():
        return JSONResponse(status_code=400,
                            content={"error": f"unknown discipline: {req.discipline}"})
    bundle = build_bundle(refdata, req.discipline, req.seed,
                          overrides=req.overrides())
    return {
        "pack": req.pack or REGISTRY.default_name(),
        "discipline": req.discipline,
        "messages": {
            doc_type: {"xml": xml.decode("utf-8"), "errors": errs}
            for doc_type, (xml, errs) in bundle.items()
        },
    }


@app.post("/api/save")
def save(req: GenerateRequest):
    try:
        refdata = resolve(req.pack)
    except (UnknownPack, PackNotReady) as e:
        return _pack_error(e, req.pack)
    if req.discipline not in refdata.disciplines():
        return JSONResponse(status_code=400,
                            content={"error": f"unknown discipline: {req.discipline}"})
    try:
        written = export_bundle(refdata, req.discipline, req.seed,
                                overrides=req.overrides())
    except ValueError as e:
        return JSONResponse(status_code=422, content={"error": str(e)})
    try:
        rel = [str(p.relative_to(PROJECT_ROOT)) for p in written]
    except ValueError:
        rel = [str(p) for p in written]
    return {"discipline": req.discipline, "saved": rel, "count": len(written)}


@app.get("/", response_class=HTMLResponse)
def index():
    return TEMPLATE.read_text(encoding="utf-8")


@app.get("/api/generate.zip")
def generate_zip(discipline: str, seed: int = 1, pack: str | None = None,
                 competition_code: str | None = None, source: str | None = None,
                 gen: str | None = None, sport: str | None = None,
                 codes: str | None = None, status: str | None = None,
                 athletes: int | None = None, teams: int | None = None,
                 coaches: int | None = None,
                 realistic_entries: bool = False, seeded_heats: bool = False,
                 victory_ceremonies: bool = False,
                 historical_athletes: bool = False):
    try:
        refdata = resolve(pack)
    except (UnknownPack, PackNotReady) as e:
        return _pack_error(e, pack)
    if discipline not in refdata.disciplines():
        return JSONResponse(status_code=400,
                            content={"error": f"unknown discipline: {discipline}"})
    ov = Overrides(competition_code=competition_code, source=source, gen=gen,
                   sport=sport, codes=codes, status=status, athletes=athletes,
                   teams=teams, coaches=coaches,
                   realistic_entries=realistic_entries,
                   seeded_heats=seeded_heats,
                   victory_ceremonies=victory_ceremonies,
                   historical_athletes=historical_athletes)
    bundle = build_bundle(refdata, discipline, seed, overrides=ov)
    residual = {doc_type: errs for doc_type, (_xml, errs) in bundle.items() if errs}
    if residual:
        return JSONResponse(status_code=422, content=residual)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for doc_type, (xml, _errs) in bundle.items():
            zf.writestr(f"{doc_type}.xml", xml)
    return Response(content=buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition":
                             f'attachment; filename="{discipline}_bundle.zip"'})
```

Note `index()` no longer substitutes `<!--OPTIONS-->`; the discipline list is
fetched client-side in Task 6. The existing integration test
`test_index_page_renders_select` still passes because the template keeps a
`<select>` element.

- [ ] **Step 6: Run the API tests**

Run: `pytest tests/integration/ -v`
Expected: PASS — the new file plus all three existing integration files.

`tests/integration/test_api_save.py` monkeypatches `appmod.export_bundle` and
passes `refdata` positionally; the `save` endpoint above still calls
`export_bundle(refdata, discipline, seed, overrides=...)`, so it is unaffected.

- [ ] **Step 7: Commit**

```bash
git add api/app.py tests/integration/test_api_packs.py
git commit -m "feat: pack selection on the API with 400/409 for unusable packs"
```

---

## Task 6: Games dropdown in the web UI

**Files:**
- Modify: `web/templates/index.html`

**Interfaces:**
- Consumes: `GET /api/packs`, `GET /api/disciplines?pack=NAME` from Task 5.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Add the Games control and the readiness panel**

Replace lines 5–8 of `web/templates/index.html` (the `<h1>` through the
closing `</label>` of the discipline picker) with:

```html
  <h1>ODF Message Generator</h1>
  <label>Games:
    <select id="pack"></select>
  </label>
  <label>Discipline:
    <select id="discipline"></select>
  </label>
  <div id="notready" style="display:none;border:1px solid #b00;padding:8px;margin:8px 0">
    <strong>This Games cannot generate yet.</strong>
    <p>Add the following, then restart the app:</p>
    <ul id="reasons"></ul>
  </div>
  <div id="form">
```

- [ ] **Step 2: Close the new wrapper div**

Line 32 currently reads `<button id="save">Save to samples/</button>`. Insert a
closing `</div>` immediately after it, so the `#form` div wraps every fieldset
and both buttons but not `#status` or `#out`:

```html
  <button id="save">Save to samples/</button>
  </div>
  <p id="status"></p>
  <pre id="out"></pre>
```

- [ ] **Step 3: Add the pack-loading script**

Immediately after `const outEl = document.getElementById("out");` inside the
`<script>` block, insert:

```javascript
    const packEl = document.getElementById("pack");
    const notReadyEl = document.getElementById("notready");
    const reasonsEl = document.getElementById("reasons");
    const formEl = document.getElementById("form");
    let packs = {};

    async function loadPacks() {
      const res = await fetch("/api/packs");
      const data = await res.json();
      packs = Object.fromEntries(data.packs.map((p) => [p.name, p]));
      packEl.innerHTML = data.packs
        .map((p) => `<option value="${p.name}">${p.label}${p.ready ? "" : " (not ready)"}</option>`)
        .join("");
      packEl.value = data.default;
      applyPack();
    }

    function applyPack() {
      const p = packs[packEl.value];
      if (!p) return;
      reasonsEl.innerHTML = p.reasons.map((r) => `<li>${r}</li>`).join("");
      notReadyEl.style.display = p.ready ? "none" : "block";
      formEl.style.display = p.ready ? "block" : "none";
      disciplineEl.innerHTML = p.disciplines
        .map((d) => `<option value="${d}">${d}</option>`)
        .join("");
    }

    packEl.onchange = applyPack;
    loadPacks();
```

- [ ] **Step 4: Send the pack with every request**

In `payload()`, add `pack: packEl.value,` immediately after `discipline: disciplineEl.value,`.

- [ ] **Step 5: Verify by hand**

```powershell
uvicorn api.app:app
```

Open `http://127.0.0.1:8000/`. Expected:

- The Games dropdown shows "Youth Olympic Games 2026" and "LA 2028 (not ready)".
- SYOG26 selected: discipline list populates, Generate works as before.
- LA 2028 selected: the form disappears and four bullets appear naming the
  XSD, the Common Codes workbook, the Disciplines folders, and
  `generator/games/SOLG28.yaml`.

Stop the server with Ctrl+C.

- [ ] **Step 6: Commit**

```bash
git add web/templates/index.html
git commit -m "feat: Games dropdown with a readiness checklist"
```

---

## Task 7: `--pack` on the exporter

**Files:**
- Modify: `generator/export.py:56-95` (the `main` function)
- Create: `tests/unit/test_export_pack.py`

**Interfaces:**
- Consumes: `generator.packs.PackRegistry`, `PackNotReady`, `UnknownPack`.
- Produces: `python -m generator.export --pack NAME`; `export.main` returns 2 for an unusable pack.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_export_pack.py`:

```python
"""The CLI must refuse a not-ready pack the same way the API does."""
import io
import sys
from contextlib import redirect_stderr, redirect_stdout

from generator.export import main


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            code = main(argv)
    except SystemExit as e:            # argparse.error() exits
        code = e.code if isinstance(e.code, int) else 2
    return code, out.getvalue() + err.getvalue()


def test_export_refuses_a_not_ready_pack():
    code, text = _run(["--discipline", "ARC", "--pack", "SOLG28"])
    assert code == 2
    assert "SOLG28" in text
    assert "No XSD compiles" in text


def test_export_rejects_an_unknown_pack():
    code, text = _run(["--discipline", "ARC", "--pack", "NOPE"])
    assert code == 2
    assert "NOPE" in text


def test_export_pack_and_pack_dir_are_mutually_exclusive():
    code, text = _run(["--discipline", "ARC", "--pack", "SYOG26",
                       "--pack-dir", "somewhere"])
    assert code == 2
    assert "not allowed with" in text or "mutually exclusive" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m tests.minirunner test_export_pack`
Expected: FAIL — `unrecognized arguments: --pack SOLG28`

- [ ] **Step 3: Add the argument**

In `generator/export.py`, inside `main`, replace the `--pack-dir` argument
definition with a mutually exclusive group:

```python
    pack_group = parser.add_mutually_exclusive_group()
    pack_group.add_argument("--pack", default=None,
                            help="pack name to generate for, e.g. SYOG26 or "
                                 "SOLG28 (default: ODF_GAMES, else the pack "
                                 "ODF_PACK_DIR points at)")
    pack_group.add_argument("--pack-dir", default=None,
                            help="explicit path to a validator rule pack "
                                 "(default: ODF_PACK_DIR or known fallbacks)")
```

- [ ] **Step 4: Resolve through the registry**

Replace the resolution block:

```python
    try:
        refdata = load_refdata(args.pack_dir)
    except PackDirError as exc:
        parser.error(str(exc))
```

with:

```python
    if args.pack_dir:
        try:
            refdata = load_refdata(args.pack_dir)
        except PackDirError as exc:
            parser.error(str(exc))
    else:
        from .packs import PackNotReady, PackRegistry, UnknownPack
        try:
            registry = PackRegistry.discover()
            refdata = registry.get(args.pack or registry.default_name())
        except (PackDirError, PackNotReady, UnknownPack) as exc:
            parser.error(str(exc))
```

`parser.error` prints to stderr and exits 2, which is what the test asserts.

- [ ] **Step 5: Fix the stale help text**

In the same file, the `--pack-dir` help previously said "path to the validator
Rules/SYOG26 pack". The replacement in Step 3 already drops that; confirm no
other occurrence of `SYOG26` remains:

Run: `grep -n "SYOG26" generator/export.py`
Expected: no output.

- [ ] **Step 6: Run the tests**

Run: `python -m tests.minirunner test_export_pack test_export`
Expected: PASS.

- [ ] **Step 7: Verify the default path still exports SYOG26**

```powershell
python -m generator.export --discipline ARC
git status --porcelain samples/
```

Expected: exports succeed, `samples/` unchanged.

- [ ] **Step 8: Commit**

```bash
git add generator/export.py tests/unit/test_export_pack.py
git commit -m "feat: --pack selector on the exporter"
```

---

## Task 8: Gate the archery profile, document, and verify

**Files:**
- Modify: `generator/dataset.py:674-694` (`build_dataset`)
- Create: `tests/unit/test_arc_profile_is_pack_scoped.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `RefData.games` from Task 2.
- Produces: nothing. This is the final task.

`generator/arc_profile.py` holds real SYOG2026 archery data — the actual NOC
mix and the real 9-session, 83-unit schedule. Under any other Games it would
be fabricated data in an official-looking message.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_arc_profile_is_pack_scoped.py`:

```python
"""The embedded archery profile is real SYOG2026 data and must never appear in
another Games' messages."""
from generator.dataset import build_dataset
from generator.games import GamesProfile
from generator.refdata import RefData
from tests.conftest import PACK

OTHER = GamesProfile(pack_name="OTHER", label="Other Games",
                     gen="X-GEN-V1.0", codes="X-CC-V1.0",
                     sport_template="X-{disc}-1.0")


def test_arc_uses_the_embedded_profile_under_syog26():
    ds = build_dataset(RefData(PACK), "ARC", 1)
    # The embedded profile's real schedule: 9 sessions.
    assert len(ds.sessions) == 9


def test_arc_falls_back_to_the_codes_engine_under_another_games():
    ds = build_dataset(RefData(PACK, profile=OTHER), "ARC", 1)
    assert len(ds.sessions) != 9


def test_the_two_paths_produce_different_schedules():
    syog = build_dataset(RefData(PACK), "ARC", 1)
    other = build_dataset(RefData(PACK, profile=OTHER), "ARC", 1)
    assert [s.session_code for s in syog.sessions] != \
           [s.session_code for s in other.sessions]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m tests.minirunner test_arc_profile_is_pack_scoped`
Expected: FAIL — `test_arc_falls_back_to_the_codes_engine_under_another_games`
fails because both paths return 9 sessions.

- [ ] **Step 3: Add the gate**

In `generator/dataset.py`, in `build_dataset`, change:

```python
    if discipline == "ARC":
```

to:

```python
    # The embedded profile is real SYOG2026 archery data (exact schedule times,
    # real NOC mix). It must never be emitted under another Games.
    if discipline == "ARC" and refdata.games.pack_name == "SYOG26":
```

- [ ] **Step 4: Run the test**

Run: `python -m tests.minirunner test_arc_profile_is_pack_scoped`
Expected: PASS — 3 passed, 0 failed.

- [ ] **Step 5: Update the README**

In `README.md`, add this section immediately before `## Setup`:

```markdown
## Multiple Games

The generator discovers every rule pack under the validator's `Rules/` folder
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
   Dictionaries into `Rules/SOLG28/` as described in
   `Rules/SOLG28/_reference/README.md`.
2. Copy `Gen`, `Codes` and the `Sport` template from the LA2028 GEN document
   into `generator/games/SOLG28.yaml`. These cannot be derived — do not guess
   them.
3. Restart the app. Readiness is recomputed from what is actually present;
   there is no flag to flip.

Select a Games from the CLI with `--pack SOLG28`, or set `ODF_GAMES=SOLG28` to
change the startup default. `ODF_PACK_DIR` keeps working and determines the
default when `ODF_GAMES` is unset.
```

- [ ] **Step 6: Full verification**

```bash
source /tmp/sdd/env.sh
python3 -m tests.minirunner
python3 /tmp/sdd/snapshot.py > /tmp/sdd/after-final.json
diff /tmp/sdd/baseline.json /tmp/sdd/after-final.json && echo "GATE PASS"
grep -rn "SYOG-2026\|OWG-2026\|AWAARC1" generator/ api/ --include=*.py
```

Expected, in order: unit suite green (101 baseline tests plus everything this
plan adds); `GATE PASS` with no diff; and the grep returns no matches — every
SYOG2026 literal now lives only in `generator/games/SYOG26.yaml`.

If the gate diffs, do not commit. The refactor altered SYOG2026 output
somewhere; the diff names the discipline and document type.

**Not verifiable in this sandbox** (no pytest, no fastapi, no PyPI): the
`tests/integration/` suite and the browser check in Task 6. Marcos runs those
on Windows:

```powershell
$env:ODF_PACK_DIR = "<validator-checkout>\Rules\SYOG26"
pytest -v
uvicorn api.app:app
```

- [ ] **Step 7: Commit**

```bash
git add generator/dataset.py tests/unit/test_arc_profile_is_pack_scoped.py README.md
git commit -m "feat: scope the archery profile to SYOG26; document multi-Games"
```

---

## Acceptance check

Against the spec's six criteria:

1. `GET /api/packs` lists both with readiness — Task 5, `test_packs_endpoint_lists_both_with_readiness`.
2. Selecting SOLG28 shows the checklist, not a broken form — Task 6, Step 5.
3. Generating against SOLG28 returns 409 / CLI exits non-zero — Task 5 and Task 7.
4. SYOG26 output byte-identical at seed 1 — Task 2 Step 8 and Task 8 Step 6.
5. A synthetic minimal pack flips to ready and generates — Task 4.
6. No SYOG2026 constant remains in `envelope.py` or reachable under another pack — Task 2 Step 1 (`test_no_syog_literal_remains_in_envelope`), Task 8 Step 6 (repo-wide grep), Task 8 Steps 1–4 (archery gate).
