"""An exported bundle records what produced it.

A generated message is only worth anything if you can say which documents it
was derived from. Three facts are needed and all three were previously lost the
moment the files hit disk:

- the seed that ACTUALLY produced the bundle (the retry loop is free to walk
  away from the one you asked for),
- the rule pack and the IOC source documents behind it, by content hash, and
- which validator revision called it clean.
"""
from __future__ import annotations

import hashlib
import json

from generator import bundle as bundle_mod
from generator.export import export_bundle
from generator.manifest import MANIFEST_NAME, build_manifest
from generator.refdata import RefData
from tests.conftest import PACK

RD = RefData(PACK)


def _manifest(tmp_path, **kw):
    export_bundle(RD, "ARC", out_dir=tmp_path, **kw)
    return json.loads((tmp_path / "ARC" / MANIFEST_NAME).read_text())


def test_export_writes_a_manifest_beside_the_messages(tmp_path):
    m = _manifest(tmp_path)
    assert m["discipline"] == "ARC"
    assert m["generated_at"].endswith("Z")


def test_manifest_records_the_seed_that_was_actually_used(tmp_path, monkeypatch):
    """Asking for seed 1 and being handed seed 2 is the case that matters."""
    contexts = []

    def reject_first_attempt(xml, pack, ctx=None):
        contexts.append(ctx)
        return ["FAKE_RULE: forced"] if ctx is contexts[0] else []

    monkeypatch.setattr(bundle_mod, "check_errors", reject_first_attempt)
    m = _manifest(tmp_path, seed=1)
    assert m["seed_requested"] == 1
    assert m["seed_used"] == 2, \
        "the manifest must record the seed that produced these bytes"
    assert m["clean"] is True


def test_manifest_hashes_every_message_it_wrote(tmp_path):
    m = _manifest(tmp_path)
    assert m["messages"], "no messages recorded"
    for filename, digest in m["messages"].items():
        data = (tmp_path / "ARC" / filename).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest, \
            f"{filename} does not match its recorded digest"
    on_disk = {p.name for p in (tmp_path / "ARC").iterdir()
               if p.suffix == ".xml"}
    assert set(m["messages"]) == on_disk, \
        "every written message is listed, and nothing else"


def test_manifest_names_the_pack(tmp_path):
    m = _manifest(tmp_path)
    assert m["pack"]["name"] == PACK.name
    assert m["pack"]["version"] == PACK.version
    assert isinstance(m["pack"]["sources"], dict)


def test_source_documents_come_through_with_their_digests(tmp_path):
    """.sources.json is the validator's own provenance record, and it nests the
    records under "entries" alongside a "last_checked" stamp. Reading the outer
    dict instead of the inner one yields one entry called "entries" whose value
    is empty -- which looks like a populated manifest and carries nothing."""
    from generator.packload import load_refdata

    refdata = load_refdata()
    if not (refdata.pack_dir
            and (refdata.pack_dir / ".sources.json").is_file()):
        return          # pack assembled by hand; nothing to assert

    export_bundle(refdata, "ARC", out_dir=tmp_path)
    m = json.loads((tmp_path / "ARC" / MANIFEST_NAME).read_text())
    sources = m["pack"]["sources"]

    assert "entries" not in sources, "the outer wrapper was recorded, not the records"
    assert "last_checked" not in sources
    assert sources, "the pack has a .sources.json but no source was recorded"
    for target, record in sources.items():
        assert len(record.get("sha256", "")) == 64, f"{target} has no digest"
    assert any(r.get("url") for r in sources.values()), \
        "at least one source should say where it came from"


def test_an_unknown_validator_revision_is_null_and_says_why(tmp_path):
    """Never invent a revision. A manifest claiming a SHA it did not read is
    worse than one admitting it could not find one."""
    m = _manifest(tmp_path)
    validator = m["validator"]
    assert "revision" in validator
    if validator["revision"] is None:
        assert validator.get("reason"), \
            "a missing revision must carry the reason it is missing"
    else:
        assert len(validator["revision"]) == 40, "expected a full git SHA"


def test_manifest_records_the_options_that_shaped_the_output(tmp_path):
    from generator.overrides import Overrides
    export_bundle(RD, "ARC", out_dir=tmp_path,
                  overrides=Overrides(victory_ceremonies=True))
    m = json.loads((tmp_path / "ARC" / MANIFEST_NAME).read_text())
    assert m["options"]["victory_ceremonies"] is True
    assert m["options"]["realistic_entries"] is False


def test_no_manifest_suppresses_it(tmp_path):
    """The committed reference corpus is regenerated deliberately and diffed by
    hand; a timestamp that changes on every run is noise there."""
    written = export_bundle(RD, "ARC", out_dir=tmp_path, manifest=False)
    assert not (tmp_path / "ARC" / MANIFEST_NAME).exists()
    assert all(p.suffix == ".xml" for p in written)


def test_build_manifest_is_independent_of_writing_files():
    """The manifest is derived from a bundle, not from the filesystem, so it
    can be inspected before anything is written."""
    from generator.bundle import build_bundle
    b = build_bundle(RD, "ARC", seed=1)
    m = build_manifest(RD, "ARC", b, seed_requested=1, overrides=None)
    assert m["seed_used"] == b.seed_used
    assert set(m["messages"]) == {f"{k}.xml" for k in b}
