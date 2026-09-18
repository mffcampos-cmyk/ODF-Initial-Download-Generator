"""The app must refuse to boot from a decoy pack directory.

Regression: running the app/tests without ODF_PACK_DIR resolved the default
'Rules/SYOG26' relative to the CWD; the validator's ingestion then created an
empty decoy dir containing only .ingestion_state.json ('{}'), which passed the
old `is_dir()` guard and produced an empty disciplines dropdown."""
import os
import tempfile
from pathlib import Path

from generator.games import GamesProfileError
from generator.packload import (PackDirError, looks_like_pack,
                                resolve_pack_dir, load_refdata)


def _tmp(*children):
    d = Path(tempfile.mkdtemp())
    for c in children:
        p = d / c
        if c.endswith("/"):
            p.mkdir(parents=True, exist_ok=True)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("{}")
    return d


def test_decoy_dir_with_only_state_file_is_not_a_pack():
    decoy = _tmp(".ingestion_state.json")
    assert not looks_like_pack(decoy)


def test_real_pack_layout_is_recognized():
    pack = _tmp("codes/", "rules/", "xsd/")
    assert looks_like_pack(pack)


def test_resolve_rejects_decoy_with_helpful_error():
    decoy = _tmp(".ingestion_state.json")
    old = os.environ.get("ODF_PACK_DIR")
    os.environ["ODF_PACK_DIR"] = str(decoy)
    try:
        try:
            resolve_pack_dir()
            raise AssertionError("expected PackDirError")
        except PackDirError as e:
            msg = str(e)
            assert "ODF_PACK_DIR" in msg
            assert str(decoy) in msg
    finally:
        if old is None:
            os.environ.pop("ODF_PACK_DIR", None)
        else:
            os.environ["ODF_PACK_DIR"] = old


def test_load_refdata_rejects_empty_pack():
    decoy = _tmp(".ingestion_state.json")
    try:
        load_refdata(decoy)
        raise AssertionError("expected PackDirError")
    except PackDirError as e:
        assert "empty" in str(e).lower() or "no code tables" in str(e).lower()


def test_load_refdata_works_on_real_pack():
    rd = load_refdata()  # resolves via env (set by test runner) or fallbacks
    assert rd.disciplines()
    assert rd.codes("COMPETITION_CODE")


def test_load_refdata_rejects_pack_with_codes_but_no_disciplines():
    """Finding C: the empty-pack guard used to be `not disciplines AND not
    codes`, so a pack with code tables but zero disciplines slipped past the
    strict loader while the registry reported it not-ready -- a silent
    success (--pack-dir --all wrote zero files and exited 0). The guard must
    be `or`: either signal alone means the pack is unusable."""
    import shutil

    real_pack_dir = Path(tempfile.mkdtemp()) / "CODESONLY"
    real_pack_dir.mkdir(parents=True)
    (real_pack_dir / "codes").mkdir()
    (real_pack_dir / "codes" / "codes.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Codesets><Codeset name="DISCIPLINE">'
        '<Code id="ZZZ" description="Test"/>'
        "</Codeset></Codesets>\n", encoding="utf-8")
    try:
        load_refdata(real_pack_dir)
        raise AssertionError(
            "expected PackDirError: codes present but zero disciplines "
            "must still be rejected by the strict loader")
    except PackDirError as e:
        assert "empty" in str(e).lower()
    finally:
        shutil.rmtree(real_pack_dir.parent, ignore_errors=True)


def test_load_refdata_succeeds_on_a_differently_named_real_pack():
    """Regression 1: a byte-identical copy of a real, fully-populated pack
    under a folder name with no matching generator/games/<name>.yaml (a
    dated copy, a restored backup, anything not named after a known Games)
    must still load fine -- merely reading a pack's content (its discipline
    list, its code tables) never needed a complete Games profile. Only
    something that actually needs the GEN-document constants should, and it
    should still fail actionably when it does (RefData.games, resolved
    lazily -- see refdata.py).

    Neither existing fixture above reaches this: both are synthetic dirs
    that fail the *emptiness* guard before ever reaching the profile lookup,
    so this is the coverage gap that let Regression 1 through. Uses a real
    copy of the pack ODF_PACK_DIR already names (warm ingestion-state cache
    included, via shutil.copytree, so the copy ingests in ~2.3s rather than
    redoing draft extraction from scratch)."""
    import shutil

    real_pack_dir = Path(resolve_pack_dir())
    copy_dir = Path(tempfile.mkdtemp()) / "ADIFFERENTNAME"
    shutil.copytree(real_pack_dir, copy_dir)
    try:
        rd = load_refdata(copy_dir)
        assert rd.disciplines()
        assert rd.codes("COMPETITION_CODE")
        try:
            rd.games
            raise AssertionError("expected GamesProfileError")
        except GamesProfileError as e:
            msg = str(e)
            assert "ADIFFERENTNAME" in msg
            assert "No Games profile" in msg
    finally:
        shutil.rmtree(copy_dir.parent, ignore_errors=True)


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
