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


def test_export_pack_dir_with_no_matching_games_profile_exits_cleanly():
    """Finding C, updated for the Regression 1 fix: --pack-dir used to call
    load_profile(pack.name) unguarded inside load_refdata() itself, so a pack
    folder whose name has no matching generator/games/<NAME>.yaml produced an
    uncaught GamesProfileError traceback before generation was ever attempted
    (export.main() caught only PackDirError around load_refdata()).

    load_refdata() no longer requires a profile just to load the pack -- see
    packload.py -- so this fixture must be a pack that clears every other
    check (including a non-empty COMPETITION_CODE table, or envelope-building
    fails on that first with an unrelated ValueError) purely to prove the
    *profile* is what finally stops it: it must still exit 2 with an
    actionable message once generation is actually attempted, the same as
    every other --pack-dir failure -- just raised lazily now, from inside
    export_bundle() instead of from load_refdata()."""
    import shutil
    import tempfile
    from pathlib import Path

    d = Path(tempfile.mkdtemp()) / "NOPROFILEPACK"
    d.mkdir(parents=True)
    (d / "codes").mkdir()
    (d / "codes" / "codes.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Codesets><Codeset name="DISCIPLINE">'
        '<Code id="ZZZ" description="t"/></Codeset>'
        '<Codeset name="COMPETITION_CODE">'
        '<Code id="TEST0000" description="Test competition"/></Codeset>'
        "</Codesets>\n",
        encoding="utf-8")
    (d / "xsd").mkdir()
    (d / "xsd" / "odf2.xsd").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
        '<xs:element name="OdfBody"><xs:complexType>'
        '<xs:anyAttribute processContents="skip"/>'
        "</xs:complexType></xs:element></xs:schema>", encoding="utf-8")
    (d / "Disciplines" / "ZZZ").mkdir(parents=True)
    (d / "Disciplines" / "ZZZ" / "dd.md").write_text("# dd\n", encoding="utf-8")
    try:
        code, text = _run(["--discipline", "ZZZ", "--pack-dir", str(d)])
        assert code == 2
        assert "No Games profile" in text
        assert "NOPROFILEPACK" in text
    finally:
        shutil.rmtree(d.parent, ignore_errors=True)
