"""What the real SYOG26 initial download does, pinned against the generator.

The reference is the SYOG26 initial download supplied on 2026-09-23 (DT_PARTIC,
DT_PARTIC_TEAMS, DT_ENTRIES exported 2026-09-21; DT_SCHEDULE publish history
2026-09-23). That feed is not vendored here -- its athlete records are real
people's -- so each expectation below states the observation it encodes.

Only the values the real feed, the GEN/discipline Data Dictionaries and the
Common Codes agree on are pinned. Where the real feed contradicts the documents
(e.g. BS5 entries stamped Sport="SYOG-2026-BK3-1.3"), the documents win.
"""
from __future__ import annotations

import functools

from lxml import etree

from generator import arc_profile
from generator.builders import entries, partic, partic_teams, schedule
from generator.eventstructure import has_team_events
from generator.lengths import clamp
from generator.names import name_fields
from generator.overrides import Overrides
from generator.refdata import RefData
from tests.conftest import PACK, REFUSED_DISCIPLINES

SEED = 1


@functools.lru_cache(maxsize=None)
def _rd() -> RefData:
    from generator.packload import resolve_pack_dir
    return RefData(PACK, pack_dir=resolve_pack_dir(None))


def _disciplines() -> list[str]:
    return [d for d in _rd().disciplines() if d not in REFUSED_DISCIPLINES]


@functools.lru_cache(maxsize=None)
def _messages(discipline: str, seed: int = SEED) -> dict[str, etree._Element]:
    """Every message of one discipline's bundle, parsed, keyed by doc type
    (DT_ENTRIES keyed per event)."""
    rd = _rd()
    out = {
        "DT_PARTIC": partic.build(rd, discipline, seed),
        "DT_SCHEDULE": schedule.build(rd, discipline, seed),
    }
    if has_team_events(rd, discipline):
        out["DT_PARTIC_TEAMS"] = partic_teams.build(rd, discipline, seed)
    for rsc, xml in entries.build_all(rd, discipline, seed):
        out[f"DT_ENTRIES_{rsc.rstrip('-')}"] = xml
    return {k: etree.fromstring(v) for k, v in out.items()}


def _all_messages(seed: int = SEED):
    for disc in _disciplines():
        for key, root in _messages(disc, seed).items():
            yield disc, key, root


# --- A1. PhaseType ---------------------------------------------------------

def test_every_competition_unit_has_phase_type_competition():
    """Real feed: PhaseType="3" (CC@PHASE_TYPE "Competition") on all 2,790
    competition units it shares with the generator. Was drawn at random from
    the whole PHASE_TYPE table, so press conferences and draws appeared."""
    wrong = {}
    for disc in _disciplines():
        for u in _messages(disc)["DT_SCHEDULE"].iter("Unit"):
            if "VICT" in u.get("Code"):
                continue  # ceremonies are "6", pinned by their own tests
            if u.get("PhaseType") != "3":
                wrong.setdefault(disc, set()).add(u.get("PhaseType"))
    assert not wrong, f"non-competition PhaseType on competition units: {wrong}"


def test_victory_ceremony_units_have_phase_type_medal_ceremony():
    """Real feed: all 150 VICTMEDAL units carry PhaseType="6"
    ("Medal/Flower Ceremony")."""
    rd = _rd()
    root = etree.fromstring(schedule.build(
        rd, "ATH", SEED, overrides=Overrides(victory_ceremonies=True)))
    vict = [u for u in root.iter("Unit") if "VICT" in u.get("Code")]
    assert vict, "victory_ceremonies produced no VICT units"
    assert {u.get("PhaseType") for u in vict} == {"6"}
    others = {u.get("PhaseType") for u in root.iter("Unit")
              if "VICT" not in u.get("Code")}
    assert others == {"3"}


# --- A2. FeedFlag ----------------------------------------------------------

def test_feed_flag_is_production_on_every_message():
    """Real feed: FeedFlag="P" on all 235 messages. It was a coin toss per
    message, so one bundle mixed production and test messages."""
    flags = {}
    for seed in (1, 2, 3):
        for disc, key, root in _all_messages(seed):
            flags.setdefault(root.get("FeedFlag"), []).append(f"{disc}/{key}")
    assert set(flags) == {"P"}, {k: v[:3] for k, v in flags.items()}


# --- A3. IFId --------------------------------------------------------------

def test_entries_do_not_invent_an_ifid():
    """IFId is the International Federation's own identifier. The real feed
    carries it only when the federation supplied one (11 of 84 athletes) and
    never equal to the ODF participant code. The generator has no IF IDs, so
    it must omit the attribute rather than copy @Code into it."""
    offenders = [f"{disc}/{key}" for disc, key, root in _all_messages()
                 if key.startswith("DT_ENTRIES")
                 and root.xpath(".//Athlete/Description[@IFId]")]
    assert not offenders, offenders[:5]


# --- A4. TeamType ----------------------------------------------------------

def test_every_team_is_an_organisation_team():
    """Real feed: TeamType="ORG" on all 207 teams, including TTE mixed
    doubles and VBV pairs. The generator emitted CPLM (TTE) and CUSTOM (VBV)."""
    seen = {}
    for disc, key, root in _all_messages():
        if key == "DT_PARTIC_TEAMS":
            for t in root.iter("Team"):
                seen.setdefault(t.get("TeamType"), set()).add(disc)
    assert set(seen) == {"ORG"}, seen


# --- A5. Participating NOCs only -------------------------------------------

def _participating_nocs() -> set[str]:
    table = PACK.codes.table("NOC")
    return {c for c, r in table._rows.items()
            if r.fields.get("Participation") == "P"}


def test_participants_and_teams_come_from_participating_nocs():
    """CC@NOC marks each NOC P (participating), H (historical: EUN, SCG, URS,
    FRG...) or NP (not participating: AIN, BOC, ROC). A 2026 feed only has P.
    EUN appeared in 14 disciplines' samples and SCG in 9."""
    ok = _participating_nocs()
    bad = {}
    for disc, key, root in _all_messages():
        if key in ("DT_PARTIC", "DT_PARTIC_TEAMS"):
            for e in root.xpath("//Participant|//Team"):
                if e.get("Organisation") not in ok:
                    bad.setdefault(e.get("Organisation"), set()).add(disc)
    assert not bad, bad


def test_arc_profile_nocs_are_all_participating():
    """The embedded ARC profile listed URS and FRG as dual-entry NOCs, which
    produced a "Federal Republic of Germany" mixed team."""
    ok = _participating_nocs()
    listed = (arc_profile.DUAL_NOCS + arc_profile.MEN_NOCS
              + arc_profile.WOMEN_NOCS)
    assert not [n for n in listed if n not in ok]
    assert len(set(listed)) == len(listed)


# --- A6. Header versions ---------------------------------------------------

# Competition@Sport = the discipline Data Dictionary's document reference, as
# printed on its cover (without the "SCOG/" prefix some carry) -- the real feed
# stamps exactly these. BS5 and HBB are taken from their DDs: the real feed
# stamps both BS5 and HBB entries "SYOG-2026-BK3-1.3", a copy-paste error on
# its side.
SPORT_REFERENCES = {
    "ARC": "SYOG-2026-ARC-1.2", "ATH": "SYOG-2026-ATH-1.3",
    "BDM": "SYOG-2026-BDM-1.2", "BK3": "SYOG-2026-BK3-1.3",
    "BKG": "SYOG-2026-BKG-1.1", "BOX": "SYOG-2026-BOX-1.2",
    "BS5": "SYOG-2026-BS5-1.4", "CRD": "SYOG-2026-CRD-1.4",
    "EQU": "SYOG-2026-EQU-EJP-1.0", "FBS": "SYOG-2026-FBS-1.3",
    "FEN": "SYOG-2026-FEN-1.3", "GAR": "SYOG-2026-GAR-1.2",
    "HBB": "SYOG-2026-HBB-1.2", "JUD": "SYOG-2026-JUD-1.3",
    "RCB": "SYOG-2026-RCB-1.3", "RU7": "SYOG-2026-RU7-1.1",
    "SAL": "SYOG-2026-SAL-1.3", "SKB": "SYOG-2026-SKB-1.0",
    "SWM": "SYOG-2026-SWM-1.2", "TKW": "SYOG-2026-TKW-1.2",
    "TRI": "SYOG-2026-TRI-1.1", "TTE": "SYOG-2026-TTE-1.3",
    "VBV": "SYOG-2026-VBV-1.2", "WRB": "SYOG-2026-WRB-1.2",
    "WST": "SYOG-2026-WST-1.0",
}


def test_gen_is_the_gen_document_reference():
    """GEN Data Dictionary cover and page headers: "OWG2026-GEN-4.6"."""
    gens = {c.get("Gen") for _d, _k, root in _all_messages()
            for c in root.iter("Competition")}
    assert gens == {"OWG2026-GEN-4.6"}


def test_codes_names_the_common_codes_release_in_the_pack():
    """Real feed format: Codes="YOG-2026-<major>.<minor>". The pack holds
    SYOG2026_ODF_Common_Codes_v_2_4.xlsx, so this pack's messages say 2.4."""
    codes = {c.get("Codes") for _d, _k, root in _all_messages()
             for c in root.iter("Competition")}
    assert codes == {"YOG-2026-2.4"}


def test_codes_version_is_read_from_the_loaded_workbook():
    """Derived, not typed: v_2_2 -> v_2_4 happened within two days, and a
    hardcoded string would have gone on claiming the old release. The source
    is the workbook the pack actually loaded (LoadReport.loaded_files)."""
    from generator.refdata import codes_version
    assert codes_version(["SYOG2026_ODF_Common_Codes_v_3_10.xlsx"]) == "3.10"
    assert codes_version(["notes.txt"]) is None
    assert codes_version([]) is None
    assert codes_version(PACK.report.loaded_files) == "2.4"


def test_sport_is_the_discipline_dd_reference():
    wrong = {}
    for disc in _disciplines():
        for key, root in _messages(disc).items():
            got = root.find("Competition").get("Sport")
            if got != SPORT_REFERENCES[disc]:
                wrong[f"{disc}/{key}"] = got
    assert not wrong, dict(list(wrong.items())[:5])


def test_every_pack_discipline_has_a_sport_reference():
    """No template fallback: a discipline without a known DD reference must
    not silently get an invented version."""
    assert set(_rd().games.sports) == set(_rd().disciplines())


# --- A7. Source ------------------------------------------------------------

def test_source_follows_the_document_type():
    """Real feed: Source="SEQ" on DT_PARTIC, DT_PARTIC_TEAMS and DT_ENTRIES,
    Source="OSM" on DT_SCHEDULE -- per message type, for every discipline."""
    seen = {}
    for disc, key, root in _all_messages():
        seen.setdefault(root.get("DocumentType"), set()).add(root.get("Source"))
    assert seen == {"DT_PARTIC": {"SEQ"}, "DT_PARTIC_TEAMS": {"SEQ"},
                    "DT_ENTRIES": {"SEQ"}, "DT_SCHEDULE": {"OSM"}}


# --- A8. Name fields -------------------------------------------------------

def test_initials_cover_every_given_name():
    """Two given names give two initials ("M.L. BRENNER" / "BRENNER ML"), as
    the real feed does."""
    nf = name_fields("Maria Luisa", "Brenner")
    assert nf["TVInitialName"] == "M.L. BRENNER"
    assert nf["PrintInitialName"] == "BRENNER ML"


def test_hyphenated_given_names_give_one_initial_per_part():
    """ODF Name Language Guidelines (OWG2026-NAME-3.0) 5.2 and 5.5:
    Anne-Marie Jones -> "JONES AM" and "A.M. JONES"."""
    nf = name_fields("Anne-Marie", "Jones")
    assert nf["PrintInitialName"] == "JONES AM"
    assert nf["TVInitialName"] == "A.M. JONES"


def test_single_given_name_initials_are_unchanged():
    nf = name_fields("Tomas", "Lund")
    assert nf["TVInitialName"] == "T. LUND"
    assert nf["PrintInitialName"] == "LUND T"


def test_participant_name_fields_respect_the_gen_dd_lengths():
    """GEN DD, Participant: PrintName S(35), PrintInitialName S(18),
    TVName S(35), TVInitialName S(18), TVFamilyName S(18). The real feed cuts
    at exactly these widths."""
    limits = {"PrintName": 35, "PrintInitialName": 18, "TVName": 35,
              "TVInitialName": 18, "TVFamilyName": 18}
    for attr, n in limits.items():
        assert clamp("Participant", attr, "X" * 60) == "X" * n
    over = []
    for disc, key, root in _all_messages():
        if key == "DT_PARTIC":
            for p in root.iter("Participant"):
                over += [(attr, p.get(attr)) for attr, n in limits.items()
                         if len(p.get(attr) or "") > n]
    assert not over, over[:5]


def test_long_names_are_cut_not_dropped():
    nf = name_fields("Aurelia Maximiliana", "Hohenberger Villanueva Stroud")
    assert clamp("Participant", "TVInitialName", nf["TVInitialName"]) \
        == "A.M. HOHENBERGER V"
    assert clamp("Participant", "PrintInitialName", nf["PrintInitialName"]) \
        == "HOHENBERGER VILLAN"


# --- B. Schedule attributes ------------------------------------------------

def _schedules():
    for disc in _disciplines():
        yield disc, _messages(disc)["DT_SCHEDULE"]


def test_every_unit_carries_medal_and_no_order_or_unitnum():
    """Real feed: Medal on all 3,077 units ("0" when none); no Order and no
    UnitNum anywhere."""
    bad = []
    for disc, root in _schedules():
        for u in root.iter("Unit"):
            if u.get("Medal") not in ("0", "1", "3"):
                bad.append((disc, u.get("Code"), "Medal", u.get("Medal")))
            for attr in ("Order", "UnitNum"):
                if u.get(attr) is not None:
                    bad.append((disc, u.get("Code"), attr, u.get(attr)))
    assert not bad, bad[:5]


def test_sessions_are_named_by_code_and_count_their_gold_medals():
    """Real feed: SessionName@Value = SessionCode; no SessionType;
    Session@Medal = number of Medal="1" units in it, omitted when zero -- true
    for all 186 real sessions."""
    for disc, root in _schedules():
        golds = {}
        for u in root.iter("Unit"):
            if u.get("Medal") == "1" and u.get("SessionCode"):
                golds[u.get("SessionCode")] = golds.get(u.get("SessionCode"), 0) + 1
        for s in root.iter("Session"):
            code = s.get("SessionCode")
            assert s.find("SessionName").get("Value") == code, disc
            assert s.get("SessionType") is None, disc
            n = golds.get(code, 0)
            assert s.get("Medal") == (str(n) if n else None), (disc, code)


def test_scheduled_units_carry_time_venue_and_session_and_unscheduled_none():
    for disc, root in _schedules():
        for u in root.iter("Unit"):
            placed = [u.get(a) for a in ("StartDate", "EndDate", "Venue",
                                          "SessionCode")]
            if u.get("ScheduleStatus") == "SCHEDULED":
                assert all(placed), (disc, u.get("Code"))
                assert u.find("VenueDescription") is not None
            else:
                assert u.get("ScheduleStatus") == "UNSCHEDULED"
                assert not any(placed) and u.get("Location") is None
                assert u.find("VenueDescription") is None


def test_unscheduled_units_come_before_scheduled_ones():
    for disc, root in _schedules():
        statuses = [u.get("ScheduleStatus") for u in root.iter("Unit")]
        assert statuses == sorted(statuses, key=lambda s: s != "UNSCHEDULED"), disc


def test_ceremonies_are_scheduled_without_any_option():
    """Real feed: 150 VICTMEDAL units, all SCHEDULED, PhaseType 6. They are
    part of the default schedule now, not an option."""
    for disc in ("ATH", "SWM", "JUD"):
        root = _messages(disc)["DT_SCHEDULE"]
        cer = [u for u in root.iter("Unit") if "VICT" in u.get("Code")]
        assert cer, disc
        assert {(u.get("ScheduleStatus"), u.get("PhaseType")) for u in cer} \
            == {("SCHEDULED", "6")}, disc


def test_blocks_are_scheduled_and_the_bouts_under_them_are_not():
    root = _messages("FEN")["DT_SCHEDULE"]
    status = {u.get("Code"): u.get("ScheduleStatus") for u in root.iter("Unit")}
    assert status["FENMEPEE--------------8FNL--------"] == "SCHEDULED"
    assert status["FENMEPEE--------------8FNL000100--"] == "UNSCHEDULED"
