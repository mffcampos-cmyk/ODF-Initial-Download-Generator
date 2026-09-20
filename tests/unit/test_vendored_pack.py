"""The pack this repository ships is a real pack, and it declares where the
documents it does not ship come from.

Both halves matter. A pack directory that loses its rules is caught by the
first test; a pack whose pack.yaml loses its source.index_url still loads and
still validates, but `python -m generator.sources` has nowhere to fetch from,
and the failure surfaces only on a fresh clone."""
import re
import subprocess
from pathlib import Path

import pytest
import yaml

from generator.packload import PROJECT_ROOT, looks_like_pack

VENDORED = PROJECT_ROOT / "Rules" / "SYOG26"


def test_vendored_pack_is_a_real_pack():
    assert looks_like_pack(VENDORED), f"{VENDORED} is not a usable rule pack"
    assert (VENDORED / "xsd").is_dir()
    assert list(VENDORED.glob("rules/*.yaml")), "no authored rules"
    assert list(VENDORED.glob("Disciplines/*/rules/*.yaml")), "no discipline rules"


def test_vendored_pack_declares_its_upstream_index():
    config = yaml.safe_load((VENDORED / "pack.yaml").read_text(encoding="utf-8"))
    assert config["source"]["index_url"].startswith("https://")


def test_vendored_pack_ships_no_ioc_documents():
    """The workbook and the Data Dictionaries are fetched, never committed.

    Asked of git, not of the filesystem. The first version of this test walked
    the pack directory -- which is right only until someone follows the README:
    `python -m generator.sources` fills that directory with precisely the
    documents the test forbids, so it passed on a fresh clone and failed on
    every working one. The property that matters is that none of them are
    COMMITTED.

    `git ls-files` rather than `.gitignore`: an ignore rule that stops matching
    is silent, and a file added with `git add -f` is not ignored at all. The
    index is what decides what a clone receives."""
    try:
        tracked = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "ls-files", "Rules"],
            capture_output=True, text=True, check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError) as exc:
        pytest.skip(f"not a git checkout ({exc}); nothing to ask about commits")
    offenders = [f for f in tracked
                 if f.lower().endswith((".pdf", ".xlsx"))
                 or f.endswith("Data_Dictionary.md")]
    assert not offenders, f"IOC documents committed to the pack: {offenders}"


def test_provenance_records_a_real_commit_sha():
    """Named for what it must catch: a PROVENANCE.md whose placeholder was
    never filled in. A 40-character hex string is the cheapest check that
    distinguishes a commit from `<VALIDATOR_PIN>`."""
    text = (VENDORED / "PROVENANCE.md").read_text(encoding="utf-8")
    assert "ODF-Validator" in text
    assert "python -m generator.sources" in text
    assert re.search(r"\b[0-9a-f]{40}\b", text), (
        "PROVENANCE.md names no commit SHA -- was the placeholder filled in?")
