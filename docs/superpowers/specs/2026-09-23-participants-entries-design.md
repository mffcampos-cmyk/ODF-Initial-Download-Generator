# Participants and entries: align with the real SYOG26 feed — design

Date: 2026-09-23. Status: all twelve decisions approved by Marcos as
recommended, 2026-09-23.
Source: section C of `claude/real-feed-comparison-2026-09-23.md` (project),
against the real SYOG26 initial download (DT_PARTIC ×25, DT_PARTIC_TEAMS ×25,
DT_ENTRIES ×150, exported 2026-09-21).

**Guiding rule.** Follow the real feed unless it contradicts the GEN or
discipline Data Dictionary. When it does, follow the DD and log the real
behaviour as a feed defect (section D), as in A and B.

## Decisions

### C1 — `DocumentSubtype="SYNC"` on DT_PARTIC and DT_PARTIC_TEAMS only

- **Real feed:** on all 50 DT_PARTIC and DT_PARTIC_TEAMS messages; absent
  from DT_ENTRIES and DT_SCHEDULE.
- **GEN DD 2.1.2.2 / 2.1.3.2:** SYNC is "for re-synchronisation for ODF
  clients", sent as a bulk once control has passed to OVR. That is what an
  initial download is.
- **Where:** `envelope.build_odfbody` puts it immediately after
  `DocumentType`, as the real feed does, for those two message types only.

### C2 — `Competition@Sport` on DT_ENTRIES only

- **Real feed:** stamps Sport only on DT_ENTRIES.
- **GEN DD:** Sport is `O` on every message.
- **Change:** Sport comes off DT_PARTIC, DT_PARTIC_TEAMS and DT_SCHEDULE.
- **Override:** an explicit `sport` override still applies wherever Sport is
  emitted, i.e. to DT_ENTRIES.

### C3 — `Participant@CountryofBirth` = Nationality

- **Real feed:** present on all 72 participants; equal to Nationality on 62.
  The 10 that differ look like dummy data.
- **GEN DD:** `CountryofBirth | O | CC@COUNTRY`.
- **Rule:** emit it as Nationality, and omit it wherever Nationality is
  omitted (e.g. EOR, whose country `XXB` is not in COUNTRY).
- **Attribute order,** as in the real feed: `… BirthDate, CountryofBirth,
  Nationality, MainFunctionId`.

### C4 — No PSCB names

- **Real feed:** `PSCBName`, `PSCBShortName` and `PSCBLongName` appear on no
  participant and no team.
- **Naming Guidelines (OWG2026-NAME-3.0) 5.3:** scoreboard names are set by the
  scoreboard supplier and ORIS, i.e. not part of the sport-entry download.
- **Change:** remove them from both builders. `names.name_fields` stops
  computing them.

### C5 — Status CNF for every participant and team

- **Real feed:** athletes 49 CNF / 23 NPR, with NPR athletes still entered in
  events; teams 182 LGL / 25 CNF. Teams with named athletes lean CNF (6 of 8).
  `ENT` never appears.
- **Rule:** athletes, officials and teams default to `CNF` (Confirmed). Every
  generated team carries its full squad, and NPR on an entered athlete
  contradicts itself.
- **Unchanged:** the `status` override still stamps any CC@PARTICIPANT_STATUS
  code, and historical athletes stay `HIS`.

### C6 — DT_PARTIC_TEAMS for every discipline

- **Real feed:** one per discipline (25), 15 of them empty.
- **Empty form:** a bare `<OdfBody …/>` with no `<Competition>`, which is what
  the real feed sends. GEN DD 2.1.3.4 declares `Competition (0,1)`, and the
  pinned validator accepts it.
- **Change:** `bundle.build_bundle` stops dropping DT_PARTIC_TEAMS for
  disciplines without team events.

### C7 — Empty DT_ENTRIES are emitted, in the DD-valid form

- **Real feed:** 91 events with no entrants, each sent as `<Competition …/>`
  with no `<Entry>`.
- **Why not copy it:** GEN DD 2.1.5.4 declares `Competition (0,1)` over
  `Entry (1,N)`. The pinned validator rejects the real form with
  `CORE_DD_CARDINALITY` and accepts an OdfBody with no `<Competition>`.
- **Rule:** an event with no entrants is emitted with no `<Competition>`, never
  skipped. The real form is logged under D.
- **When it happens:** normal output always has entrants, so this arises only
  from count overrides (e.g. `athletes=0`).

### C8 — Entries at gender level where the codes say so (GAR)

**Real feed.**
- GAR's DT_ENTRIES are `GARMGEN` and `GARWGEN` only: nothing for the apparatus
  events (`GARM1AA`, `GARW1AA`) and nothing for the team events.
- GAR's DT_PARTIC_TEAMS is empty.
- Its schedule carries the five `GARMGEN/GARWGEN QUAL` subdivisions.

**Codes.**
- GAR is the only discipline whose EVENT table has **gender-level** GEN events
  (`GARMGEN`, `GARWGEN`). Every discipline has a `G`-gender `<DISC>GGEN`
  discipline row.
- The only `Schedule=Y` EVENT_UNIT rows under a GEN event are those five GAR
  qualification units.

**Rule, derived from the codes rather than special-cased for GAR:**
- **Entry events.** A discipline with gender-level GEN events (EVENT
  `Event` starting `GEN` and `Gender` ≠ `G`) takes its entries there: one
  pooled athlete list per GEN event, and no DT_ENTRIES for its other events.
  The new function is `eventstructure.entry_events(refdata, discipline)`.
  - For such a discipline it returns one individual (non-team) `EventInfo`
    per gender-level GEN event.
  - Entrants come from `_entrants` over that GEN event's own units: the
    default 8, since `QUAL` is neither a bracket, heats nor groups. FIG squad
    sizes are not in the codes; the `athletes` override exists for that.
  - For every other discipline it returns `events()` unchanged.
- **Consumers.** `dataset` and `has_team_events` use `entry_events`. For GAR
  this means no team is built and `squad_size` is never asked for GARxTEAM, so
  `UnknownSquadSize` is no longer raised. GAR joins the corpus, with an empty
  DT_PARTIC_TEAMS (C6).
- **Schedule plan.** `schedule_plan` excludes only discipline-level GEN rows
  (`Gender == "G"`) and `------------------`. Gender-level GEN rows are kept,
  so GAR's plan gains its 5 QUAL subdivisions and matches the real GAR row
  count: 19.
- **`UnknownSquadSize` and `_SQUAD_SIZES` stay.** Any future discipline whose
  *entered* team events lack a squad size must still refuse.

### C9 — Officials stay in DT_PARTIC

- **Real feed:** DT_PARTIC holds athletes only, yet its DT_ENTRIES names
  coaches that appear in no DT_PARTIC. That looks like a dummy-data gap, not a
  convention.
- **DD:** officials are participants.
- **No change.**

### C10 — Team entries keep their full Composition

- **Real feed:** 126 of 207 team entries have no Composition. That is dummy
  data; the DD allows Composition, and consumers need the members.
- **No change.**

### C11 — TV-name switching for the listed NOCs

- **Naming Guidelines 5.9:** for CHN, COR, TPE, HKG, JPN, KOR and PRK, TV
  names put the family name first: `SMITH John` and `SMITH J.` (MAC applies
  only to the Paralympic Games).
- **Real sample:** has no athletes from these NOCs, so there is no evidence
  against it.
- **Rule:** `name_fields(given, family, organisation=None)`. For those NOCs:
  - `TVName` = `"FAMILY Given"`;
  - `TVInitialName` = `"FAMILY I.J."`, with initials as in A8;
  - `PrintName`, `PrintInitialName` and `TVFamilyName` are unchanged.

### C12 — Out of scope

- Sport-specific extensions: `Entry/Coaches`, `Athlete@Bib`, `Guide`,
  ExtendedEntry `POSITION` / `CAPTAIN` / `SEED` / `RANK_WLD` / `GROUP`, team
  `DisciplineEntry` `UNIFORM` / `SHORTS`, participant `HAND` / `SHIRT_NAME`.
  The real values are placeholders ("SHIRTNAME", "Left/right handed"), and each
  needs per-discipline code lists. This is a later sport-profile pass.
- Limited mixed case (`de CASTELLA`, `McBAIN`).
- Randomised CountryofBirth, and the real status mix.

## Effects on existing behaviour and tests

- **`REFUSED_DISCIPLINES`** in `tests/conftest.py` becomes `set()`, and
  `test_refused_disciplines_are_exactly_the_known_set` pins that. Sweeping
  tests (clean bundles, obligations, conformance) now include GAR. The
  exporter's `UnknownSquadSize` handling stays for the future case above.
- **`test_schedule_plan.EXPECTED["GAR"]`** moves from `(14, 10)` to the plan's
  new value. It gains the 5 QUAL bouts; the regression pin is re-derived
  deliberately.
- **`test_obligation_coverage.KNOWN_AMBIGUOUS`** may gain entries from GAR.
  Any new entry must be the `<Description>` ambiguity (parent Athlete or
  Entry). Any new *enforceable* omission is a failure to fix, not to pin.
- **Tests pinning the old behaviour:** PSCB (`test_build_partic`), Sport on
  DT_PARTIC (`test_envelope`), ENT status, and DT_PARTIC_TEAMS absence for
  non-team disciplines (`test_bundle_teams_presence`). Revise each by what it
  protected.
- **README and samples:** the README's realism model and its GAR statements
  are updated. `samples/` is regenerated and now has 25 disciplines.
- **D addition:** the real feed's empty DT_ENTRIES (`<Competition>` with no
  `<Entry>`) fails `CORE_DD_CARDINALITY` in the pinned validator.

## Tests

New tests go in `tests/unit/test_real_feed_conformance.py`, section C, one per
decision:

- **C1:** subtype present on exactly DT_PARTIC and DT_PARTIC_TEAMS.
- **C2:** Sport present on exactly DT_ENTRIES.
- **C3:** CountryofBirth equals Nationality and is present iff Nationality is.
- **C4:** no attribute starting `PSCB` anywhere.
- **C5:** every Participant Status is CNF, except HIS under
  `historical_athletes`, and every Team Status is CNF.
- **C6:** every discipline's bundle has DT_PARTIC_TEAMS. Non-team ones are a
  bare OdfBody that validates clean.
- **C7:** `athletes=0` on an individual discipline yields one DT_ENTRIES per
  event, each without Competition and clean.
- **C8:**
  - GAR builds;
  - its DT_ENTRIES keys are exactly `GARMGEN` and `GARWGEN`;
  - DT_PARTIC_TEAMS is empty;
  - the schedule contains the 5 `GEN QUAL` units;
  - entry events equal `events()` for every other discipline.
- **C11:** a KOR participant has `TVName "KIM Minji"` and `TVInitialName
  "KIM M."`; a USA one is unchanged.
