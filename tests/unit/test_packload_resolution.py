"""Pack resolution on a machine that has never seen a validator checkout.

That is the only interesting case for a published repository, and it is the
one the old chain could not serve: it ended at a sibling directory named
after one developer's folder."""
import os
from pathlib import Path

import pytest

from generator import packload
from generator.packload import PROJECT_ROOT, PackDirError, resolve_pack_dir


def test_resolves_the_repo_local_pack_with_no_environment(monkeypatch):
    monkeypatch.delenv("ODF_PACK_DIR", raising=False)
    monkeypatch.delenv("ODF_GAMES", raising=False)
    assert resolve_pack_dir() == PROJECT_ROOT / "Rules" / "SYOG26"


def test_odf_games_selects_a_different_repo_local_pack(monkeypatch):
    monkeypatch.delenv("ODF_PACK_DIR", raising=False)
    monkeypatch.setenv("ODF_GAMES", "SOLG28")
    # SOLG28 ships as a stub with no rules or xsd, so it is not yet a usable
    # pack -- the point here is that ODF_GAMES steers the search, not that the
    # stub resolves.
    with pytest.raises(PackDirError) as excinfo:
        resolve_pack_dir()
    assert "SOLG28" in str(excinfo.value)


def test_explicit_argument_still_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("ODF_PACK_DIR", str(tmp_path / "nowhere"))
    assert resolve_pack_dir(PROJECT_ROOT / "Rules" / "SYOG26") == \
        PROJECT_ROOT / "Rules" / "SYOG26"


def test_error_tells_the_reader_how_to_get_the_documents(monkeypatch, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("ODF_PACK_DIR", str(empty))
    with pytest.raises(PackDirError) as excinfo:
        resolve_pack_dir()
    assert "python -m generator.sources" in str(excinfo.value)


def test_no_sibling_checkout_is_consulted():
    """The old chain ended at a sibling validator checkout, named for the
    folder it happened to occupy on one machine. A published clone has no such
    sibling, and naming one in an error message sends a stranger looking for a
    directory that describes somebody else's disk.

    The guard asserts on the distinctive word rather than the whole folder
    name, because this file ships and the publication filter refuses a tree
    whose code names that folder -- including, if it were spelled out here,
    this assertion."""
    source = Path(packload.__file__).read_text(encoding="utf-8")
    assert "Webapp" not in source
