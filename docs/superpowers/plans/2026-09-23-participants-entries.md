# Participants and Entries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make DT_PARTIC, DT_PARTIC_TEAMS and DT_ENTRIES match the real SYOG26
feed wherever it agrees with the Data Dictionaries: decisions C1–C11.

**Architecture:** Small local changes.
- `envelope.py` gets the header rules (C1, C2).
- `names.py` and the participant builders get the attributes (C3, C4, C11).
- `dataset.py` gets the statuses (C5) and the count-override entries (C7).
- Builders and `bundle.py` get the empty-message forms (C6, C7).
- `eventstructure.py` gets gender-level entry events (C8).

**Tech Stack:** Python 3.11+, lxml, pytest, the pinned `odf-validator` (`e0a71e4`).

**Spec:** `docs/superpowers/specs/2026-09-23-participants-entries-design.md`.

## Global Constraints

- **Guiding rule:** follow the real feed unless it contradicts the GEN or
  discipline DD. Then follow the DD and log the real form under D.
- **Empty message form:** `OdfBody` with no `<Competition>`, for DT_PARTIC,
  DT_PARTIC_TEAMS and DT_ENTRIES alike.
- **Tests** run with `/home/claude/venv/bin/python -m pytest -q -p no:cacheprovider`.
- **Starting point:** branch `real-feed-bugfixes` at `7546415`; the suite
  starts at 320 passed and must be fully green at the end of every task.
- **Commits:** author `Marcos <mffcampos@gmail.com>`, with the trailers
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01KaJ7FXU5PU2Vn9C8Rprnei`.
  Commit command template, used by every task:

```bash
git -c user.name="Marcos" -c user.email="mffcampos@gmail.com" commit -q -m "<subject>" \
  --trailer "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
  --trailer "Claude-Session: https://claude.ai/code/session_01KaJ7FXU5PU2Vn9C8Rprnei"
```

## File map

| File | Change |
|---|---|
| `generator/envelope.py` | C1 subtype, C2 Sport placement |
| `generator/names.py` | C4 drop PSCB, C11 TV switching |
| `generator/builders/partic.py` | C3 CountryofBirth, C4, C11, C6/C7 empty form |
| `generator/builders/partic_teams.py` | C4, C6 empty form |
| `generator/builders/entries.py` | C7 empty form |
| `generator/bundle.py` | C6 always DT_PARTIC_TEAMS |
| `generator/dataset.py` | C5 CNF, C7 count-override entries (+ keep `unscheduled`), C8 `entry_events` |
| `generator/model.py` | C5 defaults |
| `generator/eventstructure.py` | C8 `entry_events`, `_is_discipline_level`; plan filter |
| `tests/conftest.py` | `REFUSED_DISCIPLINES = set()` |
| tests | conformance section C; revisions listed per task |
| `README.md`, `samples/` | docs; regenerated (25 disciplines) |

---

### Task 1: Header — `DocumentSubtype` (C1) and `Sport` placement (C2)

**Files:**
- Modify: `generator/envelope.py` (`build_odfbody`)
- Modify: `tests/unit/test_real_feed_conformance.py` (append section C;
  restrict `test_sport_is_the_discipline_dd_reference` to DT_ENTRIES)
- Modify: `tests/unit/test_envelope.py` (three Sport assertions)

**Interfaces:**
- Produces: `envelope.SYNC_TYPES = ("DT_PARTIC", "DT_PARTIC_TEAMS")` and
  `envelope.SPORT_TYPES = ("DT_ENTRIES",)`.

- [ ] **Step 1: Write the failing tests.** Append to
  `tests/unit/test_real_feed_conformance.py`:

```python
# --- C. Participants and entries -------------------------------------------

def test_c1_sync_subtype_on_participant_messages_only():
    """Real feed: DocumentSubtype="SYNC" on all 50 DT_PARTIC/DT_PARTIC_TEAMS,
    right after DocumentType; on nothing else. GEN DD: SYNC is the bulk
    re-synchronisation for ODF clients."""
    for disc, key, root in _all_messages():
        want = ("SYNC" if root.get("DocumentType") in
                ("DT_PARTIC", "DT_PARTIC_TEAMS") else None)
        assert root.get("DocumentSubtype") == want, (disc, key)
    keys = list(_messages("ARC")["DT_PARTIC"].attrib)
    assert keys.index("DocumentSubtype") == keys.index("DocumentType") + 1


def test_c2_sport_only_on_entries():
    """Real feed: Competition@Sport only on DT_ENTRIES (GEN DD: O)."""
    for disc, key, root in _all_messages():
        comp = root.find("Competition")
        if comp is None:
            continue
        assert (comp.get("Sport") is not None) == \
            (root.get("DocumentType") == "DT_ENTRIES"), (disc, key)
```

In the same file, in `test_sport_is_the_discipline_dd_reference`, replace

```python
        for key, root in _messages(disc).items():
            got = root.find("Competition").get("Sport")
```

with

```python
        for key, root in _messages(disc).items():
            if root.get("DocumentType") != "DT_ENTRIES":
                continue  # C2: Sport is stamped on DT_ENTRIES only
            got = root.find("Competition").get("Sport")
```

- [ ] **Step 2: Run and verify they fail.**

  Run: `/home/claude/venv/bin/python -m pytest -q -p no:cacheprovider tests/unit/test_real_feed_conformance.py -k "c1 or c2"`

  Expected: 2 failed. C1 fails on `None != 'SYNC'`; C2 fails on Sport
  present on DT_PARTIC.

- [ ] **Step 3: Implement.** In `generator/envelope.py`, add below
  `FEED_FLAG = "P"`:

```python

# GEN DD 2.1.2.2 / 2.1.3.2: DocumentSubtype SYNC = bulk re-synchronisation
# for ODF clients; the real SYOG26 initial download carries it on exactly
# these two message types.
SYNC_TYPES = ("DT_PARTIC", "DT_PARTIC_TEAMS")
# Competition@Sport is optional (O) on every message; the real feed stamps it
# on DT_ENTRIES only.
SPORT_TYPES = ("DT_ENTRIES",)
```

In `build_odfbody`, change

```python
        "DocumentType": document_type,
        "Version": "1",
```

to

```python
        "DocumentType": document_type,
        "DocumentSubtype": "SYNC" if document_type in SYNC_TYPES else None,
        "Version": "1",
```

and change

```python
        "Sport": ov.sport if ov and ov.sport else profile.sport(disc),
```

to

```python
        "Sport": ((ov.sport if ov and ov.sport else profile.sport(disc))
                  if document_type in SPORT_TYPES else None),
```

In `tests/unit/test_envelope.py`:

- In `test_header_overrides_applied`, change `"DT_PARTIC"` to `"DT_ENTRIES"`.
  The Sport override applies where Sport is emitted.
- Replace the body of `test_blank_overrides_keep_defaults` with:

```python
    rd = RefData(PACK)
    root, comp = build_odfbody(random.Random(1), rd, "ARC", "DT_PARTIC",
                               competition_code(rd), overrides=Overrides())
    assert root.get("Source") == "SEQ"                # message-type default
    assert comp.get("Sport") is None                  # C2: DT_ENTRIES only
    _root, ecomp = build_odfbody(random.Random(1), rd, "ARC", "DT_ENTRIES",
                                 competition_code(rd), overrides=Overrides())
    assert ecomp.get("Sport") == "SYOG-2026-ARC-1.2"  # ARC DD reference
```

- In `test_envelope_takes_versions_from_the_games_profile`, change
  `"DT_PARTIC"` to `"DT_ENTRIES"` in the `build_odfbody` call, and
  `rd.games.source("DT_PARTIC")` to `rd.games.source("DT_ENTRIES")`.

- [ ] **Step 4: Verify.**

  Run: `/home/claude/venv/bin/python -m pytest -q -p no:cacheprovider tests/unit/test_real_feed_conformance.py tests/unit/test_envelope.py`

  Expected: all pass. Then run the full suite: 322 passed.

- [ ] **Step 5: Commit** with subject `Stamp SYNC on participant messages
  and Sport on entries only`, after
  `git add generator/envelope.py tests/unit/test_real_feed_conformance.py tests/unit/test_envelope.py`.

---

### Task 2: Participant attributes — CountryofBirth (C3), no PSCB (C4), TV switching (C11)

**Files:**
- Modify: `generator/names.py` (module docstring, `name_fields`)
- Modify: `generator/builders/partic.py` (`_participant_el`)
- Modify: `generator/builders/partic_teams.py` (`_team_el`, imports)
- Modify: `tests/unit/test_build_partic.py` (PSCB and TV assertions)
- Test: `tests/unit/test_real_feed_conformance.py`

**Interfaces:**
- Produces:
  - `names.TV_SWITCH_NOCS: frozenset[str]`;
  - `names.name_fields(given: str, family: str, organisation: str | None = None) -> dict[str, str]`,
    which no longer returns any `PSCB*` key.

- [ ] **Step 1: Write the failing tests.** Append to the conformance file:

```python
def test_c3_country_of_birth_follows_nationality():
    """Real feed: CountryofBirth on every participant (GEN DD: O,
    CC@COUNTRY). Emitted as Nationality, and only where Nationality is."""
    for disc, key, root in _all_messages():
        if key != "DT_PARTIC":
            continue
        for p in root.iter("Participant"):
            assert p.get("CountryofBirth") == p.get("Nationality"), \
                (disc, p.get("Code"))
            if p.get("Nationality"):
                keys = list(p.attrib)
                assert keys.index("CountryofBirth") == keys.index("BirthDate") + 1
                assert keys.index("Nationality") == keys.index("CountryofBirth") + 1


def test_c4_no_scoreboard_names():
    """Real feed: no PSCB* attribute on any participant or team."""
    for disc, key, root in _all_messages():
        for e in root.iter():
            assert not [a for a in e.attrib if a.startswith("PSCB")], (disc, key)


def test_c11_tv_names_switch_for_the_listed_nocs():
    """Naming Guidelines 5.9: family name first on TV for CHN, COR, TPE, HKG,
    JPN, KOR, PRK."""
    kor = name_fields("Minji", "Kim", "KOR")
    assert (kor["TVName"], kor["TVInitialName"]) == ("KIM Minji", "KIM M.")
    assert (kor["PrintName"], kor["PrintInitialName"], kor["TVFamilyName"]) \
        == ("KIM Minji", "KIM M", "KIM")
    usa = name_fields("Minji", "Kim", "USA")
    assert (usa["TVName"], usa["TVInitialName"]) == ("Minji KIM", "M. KIM")
    assert name_fields("Minji", "Kim") == usa
```

- [ ] **Step 2: Run and verify they fail.**

  Run with `-k "c3 or c4 or c11"`. Expected: 3 failed (no CountryofBirth;
  PSCB present; `name_fields` takes no third argument).

- [ ] **Step 3: Implement.**

  **`generator/names.py`.** Replace the docstring lines from
  `- TVName           = "Given FAMILY"` through the PSCB lines with:

```
- TVName           = "Given FAMILY"   ("FAMILY Given" for TV_SWITCH_NOCS)
- TVInitialName    = "I.J. FAMILY"    ("FAMILY I.J." for TV_SWITCH_NOCS)
- Passport names   = uppercase, accents stripped
- No PSCB (scoreboard) names: those are set by the scoreboard supplier and
  ORIS (Naming Guidelines 5.3), and the real SYOG26 download has none.
```

Then replace the whole `name_fields` function with:

```python
# ODF Name Language Guidelines (OWG2026-NAME-3.0) 5.9: TV names put the
# family name first for these NOCs (MAC applies to the Paralympic Games only).
TV_SWITCH_NOCS = frozenset({"CHN", "COR", "TPE", "HKG", "JPN", "KOR", "PRK"})


def name_fields(given: str, family: str,
                organisation: str | None = None) -> dict[str, str]:
    """Derive all ODF name attributes from a given/family pair.

    Widths are not applied here: ``lengths.clamp`` cuts every attribute to its
    GEN DD S(n) where it is serialised, as the real feed does."""
    fam_upper = strip_accents(family).upper()
    initials = given_initials(given)
    dotted = "".join(i + "." for i in initials)
    if organisation in TV_SWITCH_NOCS:
        tv_name, tv_initial = f"{fam_upper} {given}", f"{fam_upper} {dotted}"
    else:
        tv_name, tv_initial = f"{given} {fam_upper}", f"{dotted} {fam_upper}"
    return {
        "GivenName": given,
        "FamilyName": family,
        "PassportGivenName": strip_accents(given).upper(),
        "PassportFamilyName": fam_upper,
        "PrintName": f"{fam_upper} {given}",
        "PrintInitialName": f"{fam_upper} {''.join(initials)}",
        "TVName": tv_name,
        "TVInitialName": tv_initial,
        "TVFamilyName": fam_upper,
    }
```

  **`generator/builders/partic.py`, in `_participant_el`:**
  - Change `nf = name_fields(p.given_name, p.family_name)` to
    `nf = name_fields(p.given_name, p.family_name, p.organisation)`.
  - Change the lines

```python
        "BirthDate": p.birth_date,
        "Nationality": p.nationality,       # dropped by el() when empty
```

    to

```python
        "BirthDate": p.birth_date,
        # C3: the real feed carries CountryofBirth on every participant; the
        # generator has no birth country apart from nationality.
        "CountryofBirth": p.nationality,    # dropped by el() when empty
        "Nationality": p.nationality,       # dropped by el() when empty
```

  - Delete the four lines starting
    `    # PSCB names appear on athletes only in the real-life feed`, down to
    `        attrs["PSCBLongName"] = nf["PSCBLongName"]`.

  **`generator/builders/partic_teams.py`:**
  - Delete the three `"PSCB…"` entries in `_team_el`.
  - Delete the line `from ..names import strip_accents`.

  **`tests/unit/test_build_partic.py`.** Replace the block

```python
        if p.get("MainFunctionId") == "AA01":
            assert 2009 <= year <= 2011
            assert p.get("PSCBName")
        else:
            assert 1961 <= year <= 1996
            assert p.get("PSCBName") is None
        # TV conventions from the real-life feed: "Given FAMILY" / "I. FAMILY"
        fam_upper = p.get("TVFamilyName")
        assert p.get("TVName").endswith(fam_upper)
        assert p.get("TVInitialName")[1:3] == ". "
```

with

```python
        if p.get("MainFunctionId") == "AA01":
            assert 2009 <= year <= 2011
        else:
            assert 1961 <= year <= 1996
        assert p.get("PSCBName") is None  # C4: no scoreboard names
        # TV conventions (Naming Guidelines 5.5 / 5.9): "Given FAMILY" and
        # "I. FAMILY", family first for the listed East Asian NOCs.
        fam_upper = p.get("TVFamilyName")
        if p.get("Organisation") in TV_SWITCH_NOCS:
            assert p.get("TVName").startswith(fam_upper)
            assert p.get("TVInitialName").startswith(fam_upper)
        else:
            assert p.get("TVName").endswith(fam_upper)
            assert p.get("TVInitialName")[1:3] == ". "
```

  Also add `from generator.names import TV_SWITCH_NOCS` to that file's
  imports.

- [ ] **Step 4: Verify.** Run the three new tests and
  `tests/unit/test_build_partic.py`: all pass. Full suite: 325 passed.

- [ ] **Step 5: Commit** with subject `CountryofBirth, no scoreboard names,
  and family-first TV names where the guidelines say`, after
  `git add generator/names.py generator/builders/partic.py generator/builders/partic_teams.py tests/unit/test_build_partic.py tests/unit/test_real_feed_conformance.py`.

---

### Task 3: Status CNF (C5)

**Files:**
- Modify: `generator/dataset.py` (`_PARTICIPANT_STATUS` and its comment)
- Modify: `generator/model.py` (`Participant.status` and `Team.status`
  defaults)
- Test: `tests/unit/test_real_feed_conformance.py`

- [ ] **Step 1: Write the failing test.** Append:

```python
def test_c5_every_participant_and_team_is_confirmed():
    """Real feed: CNF/NPR athletes, LGL/CNF teams, never ENT. Every generated
    team has its full squad, so the default is CNF (Confirmed) throughout;
    the status override still stamps any CC@PARTICIPANT_STATUS code."""
    for disc, key, root in _all_messages():
        for e in root.xpath("//Participant|//Team"):
            assert e.get("Status") == "CNF", (disc, key, e.get("Code"))
```

- [ ] **Step 2: Run and verify it fails**, on `'ENT' == 'CNF'`.

- [ ] **Step 3: Implement.** In `generator/dataset.py`, replace

```python
_PARTICIPANT_STATUS = "ENT"  # Entered — default sport-entry status for an initial download
```

with

```python
# Default sport-entry status: CNF (Confirmed). The real SYOG26 download uses
# CNF/NPR for athletes and LGL/CNF for teams and never ENT; teams with named
# athletes lean CNF, and every generated team has its full squad.
_PARTICIPANT_STATUS = "CNF"
```

In `generator/model.py`, change both `status: str = "ENT"` lines to
`status: str = "CNF"`.

- [ ] **Step 4: Verify.** Run the test: it passes. Full suite: 326 passed.
  `test_customization` still passes, because its `status="ENT"` override is
  an explicit choice.

- [ ] **Step 5: Commit** with subject `Default every participant and team to
  CNF, as the real feed never says ENT`, after
  `git add generator/dataset.py generator/model.py tests/unit/test_real_feed_conformance.py`.

---

### Task 4: Empty messages — DT_PARTIC_TEAMS always (C6), empty DT_ENTRIES emitted (C7)

**Files:**
- Modify: `generator/bundle.py` (drop the DT_PARTIC_TEAMS pop)
- Modify: `generator/builders/partic_teams.py`, `generator/builders/partic.py`
  (bare OdfBody when empty)
- Modify: `generator/builders/entries.py` (`build_all`: emit, don't skip)
- Modify: `generator/dataset.py` (`_apply_count_overrides`: an entry per
  entry event, and keep `unscheduled`)
- Modify: `tests/unit/test_bundle_teams_presence.py` (rewrite)
- Test: `tests/unit/test_real_feed_conformance.py`

**Interfaces:**
- Produces: builders return an `OdfBody` without `<Competition>` when they
  have nothing to list. `Dataset.entries` holds one `EventEntries` per entry
  event, possibly empty.

- [ ] **Step 1: Write the failing tests.** Append to the conformance file:

```python
def test_c6_every_discipline_sends_a_teams_message():
    """Real feed: one DT_PARTIC_TEAMS per discipline (25), 15 of them a bare
    OdfBody with no Competition -- GEN DD: Competition (0,1)."""
    from generator.bundle import build_bundle
    for disc in _disciplines():
        bundle = build_bundle(_rd(), disc, seed=SEED)
        assert "DT_PARTIC_TEAMS" in bundle, disc
        xml, errs = bundle["DT_PARTIC_TEAMS"]
        assert errs == [], (disc, errs[:2])
        root = etree.fromstring(xml)
        comp = root.find("Competition")
        assert comp is None or len(comp), f"{disc}: empty <Competition>"


def test_c7_an_event_without_entrants_is_sent_empty_not_skipped():
    """The real feed sends one DT_ENTRIES per event even with no entrants.
    Its form (<Competition> with no <Entry>) breaks the DD's Entry (1,N), so
    the DD form is used: no <Competition>."""
    from generator.bundle import build_bundle
    from generator.dataset import build_dataset
    rd = _rd()
    bundle = build_bundle(rd, "SWM", seed=SEED,
                          overrides=Overrides(athletes=0))
    entries = {k: v for k, v in bundle.items() if k.startswith("DT_ENTRIES")}
    expected = {f"DT_ENTRIES_{e.event_rsc.rstrip('-')}"
                for e in build_dataset(rd, "SWM", SEED).entries}
    assert set(entries) == expected
    for key, (xml, errs) in entries.items():
        assert errs == [], (key, errs[:2])
        assert etree.fromstring(xml).find("Competition") is None, key


def test_count_overrides_keep_the_unscheduled_units():
    """B regression: _apply_count_overrides rebuilt the Dataset without
    `unscheduled`, silently dropping every UNSCHEDULED unit."""
    from generator.dataset import build_dataset
    rd = _rd()
    plain = build_dataset(rd, "FEN", SEED)
    counted = build_dataset(rd, "FEN", SEED, Overrides(athletes=10))
    assert plain.unscheduled
    assert [u.code for u in counted.unscheduled] == \
        [u.code for u in plain.unscheduled]
```

Rewrite `tests/unit/test_bundle_teams_presence.py` as:

```python
"""DT_PARTIC_TEAMS is sent for every discipline, as in the real SYOG26 feed
(25 messages, 15 of them empty). It carries teams exactly when the
discipline's entry events include a team event; otherwise it is a bare
OdfBody with no Competition (GEN DD: Competition (0,1))."""
from lxml import etree

from generator import eventstructure
from generator.bundle import build_bundle
from generator.refdata import RefData
from tests.conftest import PACK, REFUSED_DISCIPLINES


def rd():
    return RefData(PACK)


def test_disciplines_without_team_events_send_a_bare_teams_message():
    for disc in ("SWM", "ATH", "JUD", "TRI"):
        xml, errs = build_bundle(rd(), disc, seed=1)["DT_PARTIC_TEAMS"]
        assert errs == [], disc
        assert etree.fromstring(xml).find("Competition") is None, disc


def test_tkw_mixed_team_event_gets_teams_message():
    bundle = build_bundle(rd(), "TKW", seed=1)
    xml, errs = bundle["DT_PARTIC_TEAMS"]
    assert errs == []
    teams = list(etree.fromstring(xml).iter("Team"))
    assert len(teams) == 8  # X TEAM4: default 8 entrant slots


def test_teams_message_has_teams_exactly_when_team_events_exist():
    for disc in rd().disciplines():
        if disc in REFUSED_DISCIPLINES:
            continue
        xml, _errs = build_bundle(rd(), disc, seed=1)["DT_PARTIC_TEAMS"]
        has_teams = bool(list(etree.fromstring(xml).iter("Team")))
        assert has_teams == eventstructure.has_team_events(rd(), disc), disc
```

- [ ] **Step 2: Run and verify they fail.** Run the conformance C6/C7/count
  tests and `test_bundle_teams_presence.py`. Expected failures:
  - C6: `DT_PARTIC_TEAMS` not in the bundle for SWM;
  - C7: the key sets differ, because the empty events are skipped;
  - count test: `counted.unscheduled` is empty;
  - the bare-teams test: a `KeyError`.

- [ ] **Step 3: Implement.**

**`generator/bundle.py`:** delete the two lines

```python
    if not eventstructure.has_team_events(refdata, discipline):
        doc_types.pop("DT_PARTIC_TEAMS", None)
```

Then, if `eventstructure` is no longer used in the file, delete
`from . import eventstructure`. Check with `grep -n eventstructure generator/bundle.py`.

**`generator/builders/partic_teams.py`:** before `return to_xml(root)` in
`build`, add:

```python
    if not len(comp):
        # No teams: the real feed sends a bare OdfBody, which the DD allows
        # (Competition (0,1)) and an empty <Competition> would not be.
        root.remove(comp)
```

**`generator/builders/partic.py`:** add the same three lines before
`return to_xml(root)` in `build`, with the comment `# No participants: bare
OdfBody (Competition (0,1)), as for DT_PARTIC_TEAMS.`

**`generator/builders/entries.py`:** in `build_all`, replace

```python
        # GEN 2.1.5.2 gives Entry cardinality (1,N): a DT_ENTRIES with no
        # entrants is not a valid message, so skip the event rather than emit
        # an envelope with nothing in it. Nothing in the validator catches
        # this -- it has no cardinality primitive, and the XSD does not
        # constrain Entry either.
        if not (ev.athlete_codes or ev.team_codes):
            continue
        root, comp = build_odfbody(rng, refdata, discipline, "DT_ENTRIES",
                                   competition_code(refdata),
                                   document_code=ev.event_rsc,
                                   overrides=overrides)
```

with

```python
        root, comp = build_odfbody(rng, refdata, discipline, "DT_ENTRIES",
                                   competition_code(refdata),
                                   document_code=ev.event_rsc,
                                   overrides=overrides)
        if not (ev.athlete_codes or ev.team_codes):
            # The real feed sends every event, entrants or not, but as a
            # <Competition> with no <Entry>, which breaks the DD's Entry
            # (1,N) (the pinned validator says CORE_DD_CARDINALITY).
            # Competition itself is (0,1), so the valid empty form has none.
            root.remove(comp)
            out.append((ev.event_rsc, to_xml(root)))
            continue
```

**`generator/dataset.py`, in `_apply_count_overrides`:**

- Replace

```python
    for i, a in enumerate(athletes):
        if not indiv_evs:
            break
```

  with

```python
    # Every entry event gets its message, entrants or not (C7).
    for ev in all_evs:
        bucket(ev.gender, ev.event)
    for i, a in enumerate(athletes):
        if not indiv_evs:
            break
```

- Replace

```python
    # Only events that actually have entrants. Emitting an EventEntries with
    # neither athletes nor teams produced a DT_ENTRIES with zero <Entry>
    # elements, violating Entry (1,N) -- reachable with athletes=0&teams=0.
    entries = [e for _key, e in sorted(by_event.items())
               if e.athlete_codes or e.team_codes]
    out = Dataset(discipline=discipline, organisations=used_nocs,
                  participants=participants, teams=teams,
                  sessions=ds.sessions, entries=entries)
```

  with

```python
    # Every entry event, including those left without entrants: the builder
    # sends those in the DD-valid empty form (no <Competition>).
    entries = [e for _key, e in sorted(by_event.items())]
    out = Dataset(discipline=discipline, organisations=used_nocs,
                  participants=participants, teams=teams,
                  sessions=ds.sessions, entries=entries,
                  unscheduled=ds.unscheduled)
```

- [ ] **Step 4: Verify.** Run the targeted tests: they pass. Then run the full
  suite. Expected: 329 passed (326 + 3 conformance; the teams-presence file
  stays at 3 tests).

  If `test_customization` asserts that empty events are absent, read what it
  protected. It protected Entry (1,N), which the empty form now satisfies.
  Change it to assert that the empty messages carry no Competition.

- [ ] **Step 5: Commit** with subject `Send every teams and entries message,
  empty ones in the DD-valid form`, after
  `git add generator/bundle.py generator/builders/partic_teams.py generator/builders/partic.py generator/builders/entries.py generator/dataset.py tests/unit/test_bundle_teams_presence.py tests/unit/test_real_feed_conformance.py`,
  plus `tests/unit/test_customization.py` if it was changed.

---

### Task 5: Gender-level entry events — GAR joins (C8)

**Files:**
- Modify: `generator/eventstructure.py`:
  - add `_is_discipline_level`, `gender_gen_events` and `entry_events`;
  - `schedule_plan` filter;
  - `has_team_events`.
- Modify: `generator/dataset.py`: the two `eventstructure.events(` calls
  become `entry_events(`.
- Modify: `tests/conftest.py` (`REFUSED_DISCIPLINES`)
- Modify: `tests/unit/test_schedule_plan.py` (`_schedule_y_rows`, the
  `EXPECTED["GAR"]` pin)
- Test: `tests/unit/test_real_feed_conformance.py`

**Interfaces:**
- Produces:
  - `eventstructure.gender_gen_events(refdata, discipline) -> list[tuple[str, str]]`,
    sorted `(gender, event)`;
  - `eventstructure.entry_events(refdata, discipline) -> list[EventInfo]`.

- [ ] **Step 1: Write the failing tests.** Append to the conformance file:

```python
def test_c8_gar_is_entered_by_gender_like_the_real_feed():
    """Real feed: GAR's DT_ENTRIES are GARMGEN and GARWGEN only, and its
    DT_PARTIC_TEAMS is empty. GAR is the only discipline with gender-level
    GEN events in the codes, so the rule is derived, not special-cased."""
    from generator.bundle import build_bundle
    bundle = build_bundle(_rd(), "GAR", seed=SEED)
    assert bundle.clean, bundle.errors
    assert {k for k in bundle if k.startswith("DT_ENTRIES")} == \
        {"DT_ENTRIES_GARMGEN", "DT_ENTRIES_GARWGEN"}
    teams_xml, _ = bundle["DT_PARTIC_TEAMS"]
    assert etree.fromstring(teams_xml).find("Competition") is None
    sched = etree.fromstring(bundle["DT_SCHEDULE"][0])
    quals = {u.get("Code") for u in sched.iter("Unit")
             if u.get("Code")[3:7] in ("MGEN", "WGEN")}
    assert len(quals) == 5  # the five qualification subdivisions


def test_c8_entry_events_are_events_everywhere_else():
    from generator import eventstructure
    rd = _rd()
    for disc in rd.disciplines():
        if disc == "GAR":
            continue
        assert eventstructure.gender_gen_events(rd, disc) == [], disc
        assert eventstructure.entry_events(rd, disc) == \
            eventstructure.events(rd, disc), disc
```

In `tests/conftest.py`, replace the `REFUSED_DISCIPLINES` comment block and
assignment with:

```python
# Disciplines the generator deliberately refuses to build, and why. Tests that
# sweep every discipline skip these rather than treating a designed refusal as
# a failure -- but the set is asserted exactly (see
# test_refused_disciplines_are_exactly_the_known_set), so a discipline that
# starts refusing for a new reason is caught rather than absorbed.
#
# Empty since 2026-09-23: GAR used to refuse (its team events carry no squad
# size), but it is entered by gender (GARMGEN/GARWGEN) like the real feed, so
# no team is built and no squad size is needed.
REFUSED_DISCIPLINES: set[str] = set()
```

In `tests/unit/test_schedule_plan.py`, replace `_schedule_y_rows` with:

```python
def _schedule_y_rows(discipline):
    """Read from the table, not from eventstructure: a second opinion.
    Discipline-level rows (Gender G GEN events, and the blank event) are
    not schedule rows; gender-level GEN events (GAR's qualification) are."""
    table = PACK.codes.table("EVENT_UNIT")
    return {code for code, row in table._rows.items()
            if row.fields.get("Discipline") == discipline
            and row.fields.get("Level") in ("Unit", "Phase", "Medals")
            and row.fields.get("Schedule") == "Y"
            and row.fields.get("Event") != "------------------"
            and not (row.fields.get("Event", "").startswith("GEN")
                     and row.fields.get("Gender") == "G")}
```

and in `EXPECTED` change `"GAR": (14, 10)` to `"GAR": (19, 15)`. That adds the
5 GEN QUAL bouts, all SCHEDULED; 19 rows is the real GAR schedule's count.

- [ ] **Step 2: Run and verify they fail.** Expected failures:
  - `test_c8_gar…`: `UnknownSquadSize`;
  - `test_c8_entry_events…`: `AttributeError`, since `gender_gen_events` is
    missing;
  - `test_plan_lists_exactly…` for GAR: the 5 QUAL rows are missing;
  - `test_plan_sizes_are_pinned`: GAR is (14, 10);
  - `test_refused_disciplines…`: GAR still refuses.

- [ ] **Step 3: Implement** in `generator/eventstructure.py`.

  (a) After `GEN_EVENTS = (...)`, add:

```python


def _is_discipline_level(f: dict) -> bool:
    """A discipline-level EVENT/EVENT_UNIT row -- the <DISC>GGEN row (Gender
    G) or the blank event -- rather than competition. Gender-level GEN events
    (GARMGEN, GARWGEN) are competition: GAR's entries and its qualification
    subdivisions live there."""
    event = f.get("Event", "")
    return (event == "------------------"
            or (event.startswith("GEN") and f.get("Gender") == "G"))
```

  (b) In `schedule_plan`, replace `or f.get("Event") in GEN_EVENTS):` with
  `or _is_discipline_level(f)):`.

  (c) Before `def has_team_events`, add:

```python
def gender_gen_events(refdata, discipline: str) -> list[tuple[str, str]]:
    """(gender, event) of the discipline's gender-level GEN events. Only GAR
    has them (GARMGEN, GARWGEN) in SYOG26."""
    table = refdata.pack.codes.table("EVENT")
    if table is None:
        return []
    return sorted(
        (row.fields.get("Gender", ""), row.fields.get("Event", ""))
        for row in table._rows.values()
        if row.fields.get("Discipline") == discipline
        and row.fields.get("Event", "").startswith("GEN")
        and not _is_discipline_level(row.fields))


def entry_events(refdata, discipline: str) -> list[EventInfo]:
    """The events that get a DT_ENTRIES.

    Normally the competitive events (``events``). A discipline with
    gender-level GEN events is entered there instead, one pooled list per
    gender, and its other events get no DT_ENTRIES -- as the real SYOG26 feed
    does for GAR (GARMGEN / GARWGEN only; no apparatus or team entries, an
    empty DT_PARTIC_TEAMS). No team is built, so no squad size is needed.
    Entrants follow ``_entrants`` over the GEN event's own units."""
    gens = gender_gen_events(refdata, discipline)
    if not gens:
        return events(refdata, discipline)
    table = refdata.pack.codes.table("EVENT_UNIT")
    out = []
    for gender, event in gens:
        phases: dict[str, int] = {}
        for row in table._rows.values():
            f = row.fields
            if (f.get("Discipline") == discipline and f.get("Gender") == gender
                    and f.get("Event") == event and f.get("Level") == "Unit"
                    and f.get("Schedule") == "Y"):
                phases[f.get("Phase", "")] = phases.get(f.get("Phase", ""), 0) + 1
        out.append(EventInfo(gender=gender, event=event, is_team=False,
                             team_size=1, entrants=_entrants(phases),
                             phases=phases))
    return out
```

  (d) In `has_team_events`, change
  `return any(e.is_team for e in events(refdata, discipline))` to
  `return any(e.is_team for e in entry_events(refdata, discipline))`, and add
  to its docstring: `Entry events, not events: GAR schedules team events but
  enters no teams.`

  (e) In `generator/dataset.py`, change both `eventstructure.events(refdata,
  discipline)` calls (in `_build_codes_dataset` and `_apply_count_overrides`)
  to `eventstructure.entry_events(refdata, discipline)`.

- [ ] **Step 4: Verify.** Run the conformance C8 tests,
  `tests/unit/test_schedule_plan.py` and
  `tests/unit/test_bundle_all_disciplines.py`: all pass. Then run the full
  suite; expected 331 passed.

  If `test_obligation_coverage` fails:
  - A new **enforceable** omission is a real defect in GAR output. Fix the
    builder; don't pin it.
  - A new **ambiguous** entry with parent `Athlete` or `Entry` on
    `Description` is the documented ambiguity. Add it to `KNOWN_AMBIGUOUS`
    with a comment naming GAR.

- [ ] **Step 5: Commit** with subject `Enter GAR by gender as the codes and
  the real feed do, and stop refusing it`, after
  `git add generator/eventstructure.py generator/dataset.py tests/conftest.py tests/unit/test_schedule_plan.py tests/unit/test_real_feed_conformance.py`,
  plus `tests/unit/test_obligation_coverage.py` if it was changed.

---

### Task 6: README, samples, verification, delivery

**Files:**
- Modify: `README.md` (realism model: participants bullet; any statement
  that GAR is skipped or refused)
- Regenerate: `samples/` (adds `samples/GAR/`)

- [ ] **Step 1: README.**
  - Run `grep -n "GAR\|refus\|24 discipline\|PSCB\|Status" README.md`.
  - Replace every statement about PSCB names, ENT status or GAR being
    skipped with the new behaviour.
  - Then add, after the header bullet (the one starting
    `- Header, from \`generator/games/SYOG26.yaml\``):

```markdown
- Participants and entries, as in the real SYOG26 download: DT_PARTIC and
  DT_PARTIC_TEAMS carry `DocumentSubtype="SYNC"`; `Competition@Sport` is on
  DT_ENTRIES only; every participant has `CountryofBirth` (= Nationality) and
  no PSCB scoreboard names; every participant and team is `Status="CNF"`; TV
  names put the family name first for CHN, COR, TPE, HKG, JPN, KOR and PRK.
  DT_PARTIC_TEAMS is sent for every discipline, and a message with nothing to
  list is a bare `OdfBody` with no `Competition` (GEN DD: Competition (0,1)).
  GAR is entered by gender (`GARMGEN`, `GARWGEN`), as the codes and the real
  feed do, so all 25 disciplines generate.
```

- [ ] **Step 2: Regenerate the samples.**

```bash
cd /home/claude/gen && /home/claude/venv/bin/python -m generator.export --all --seed 1 --no-manifest --out-dir samples
```

  Expected: 25 disciplines written; no `SKIP`.

- [ ] **Step 3: Verify.**
  - Full suite: 0 failures.
  - `python -m generator.obligations`: exit 0.
  - Regenerate into `/tmp/claude-0/regen`; it must be identical to `samples/`
    apart from Date, Time and LogicalDate.
  - Re-run `/home/claude/cmp/profile.py` and check the DT_PARTIC,
    DT_PARTIC_TEAMS and DT_ENTRIES sections against the real feed:
    - DocumentSubtype;
    - Sport placement;
    - CountryofBirth;
    - no PSCB;
    - Status;
    - file counts: DT_PARTIC 25, DT_PARTIC_TEAMS 25, DT_ENTRIES 150.

- [ ] **Step 4: Commit and deliver.**
  - Commit with subject `Regenerate samples with participants and entries as
    the real feed has them`, after `git add README.md samples`.
  - Run `git format-patch daa2bba..HEAD -o /mnt/user-data/outputs/real-feed-patches-c`
    (the laptop's `053f8bb` has the same tree as `daa2bba`).
  - Verify the series applies to `daa2bba` in a scratch clone and reproduces
    HEAD's tree.
  - Write the folder into the laptop repo.
  - Update the project doc: mark C done and add the new D item.
