"""Tests for generator.export.

These use a stub bundle so they run fast without building the validator rule
pack, and work under both pytest and tests.minirunner (no fixtures required).
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from generator import export
from generator.bundle import Bundle


def _with_stub_bundle(bundle: dict):
    """Return a context-manager-ish pair that patches export.build_bundle.

    The stub returns a real ``Bundle``, not a bare dict: build_bundle's
    contract now includes ``.clean`` and ``.seed_used``, and a stub that does
    not carry them tests a shape production never sees.
    """
    original = export.build_bundle
    clean = not any(errs for _xml, errs in bundle.values())

    def fake_build_bundle(refdata, discipline, seed, max_retries=5,
                          overrides=None):
        return Bundle(bundle, seed_used=seed, clean=clean)

    export.build_bundle = fake_build_bundle
    return original


def test_export_writes_four_files_in_discipline_folder():
    bundle = {
        "DT_PARTIC": (b"<a/>", []),
        "DT_PARTIC_TEAMS": (b"<b/>", []),
        "DT_ENTRIES": (b"<c/>", []),
        "DT_SCHEDULE": (b"<d/>", []),
    }
    original = _with_stub_bundle(bundle)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            # manifest=False: these tests stub the bundle and pass no
            # refdata, so there is no pack to record provenance from. The
            # manifest has its own tests, against a real one.
            written = export.export_bundle(None, "ARC", seed=1, out_dir=tmp,
                                           manifest=False)
            names = {p.name for p in written}
            assert names == {
                "DT_PARTIC.xml", "DT_PARTIC_TEAMS.xml",
                "DT_ENTRIES.xml", "DT_SCHEDULE.xml"}
            folder = Path(tmp) / "ARC"
            assert (folder / "DT_PARTIC.xml").read_bytes() == b"<a/>"
            assert all(p.parent == folder for p in written)
    finally:
        export.build_bundle = original


def test_default_out_dir_is_output_not_the_reference_corpus():
    """samples/ is the committed reference corpus, checked by hand when a
    change alters generated output. If the default write target drifts back
    onto it, every Save silently rewrites the baseline it is measured against
    -- with no signal in the UI. Assert the default explicitly rather than
    trusting a comment."""
    assert export.DEFAULT_OUT_DIR == export.PROJECT_ROOT / "output"
    assert export.DEFAULT_OUT_DIR.name != "samples"


def test_export_refuses_unclean_messages_by_default():
    bundle = {
        "DT_PARTIC": (b"<a/>", ["some error"]),
        "DT_PARTIC_TEAMS": (b"<b/>", []),
        "DT_ENTRIES": (b"<c/>", []),
        "DT_SCHEDULE": (b"<d/>", []),
    }
    original = _with_stub_bundle(bundle)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            raised = False
            try:
                export.export_bundle(None, "ARC", out_dir=tmp)
            except ValueError:
                raised = True
            assert raised, "expected ValueError for un-clean bundle"
            # nothing should have been written
            assert not (Path(tmp) / "ARC").exists()
    finally:
        export.build_bundle = original


def test_export_allows_unclean_when_opted_in():
    bundle = {
        "DT_PARTIC": (b"<a/>", ["some error"]),
        "DT_PARTIC_TEAMS": (b"<b/>", []),
        "DT_ENTRIES": (b"<c/>", []),
        "DT_SCHEDULE": (b"<d/>", []),
    }
    original = _with_stub_bundle(bundle)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            written = export.export_bundle(None, "ARC", out_dir=tmp,
                                           require_clean=False, manifest=False)
            assert len(written) == 4
            assert (Path(tmp) / "ARC" / "DT_PARTIC.xml").read_bytes() == b"<a/>"
    finally:
        export.build_bundle = original
