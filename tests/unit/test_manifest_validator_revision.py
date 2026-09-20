"""Where the manifest gets the validator's revision from.

The manifest exists so a bundle can say which engine validated it. That claim
is only worth having if it names the engine -- and until this was fixed it
named whatever repository happened to enclose the interpreter.

`validator_revision()` resolved the validator's root as
`Path(odf_validator.__file__).parent.parent`. After the install the README
documents, that is `site-packages`; git discovers a repository by walking UP,
and the documented layout puts `.venv/` inside the project, so `git -C
site-packages rev-parse HEAD` returned the GENERATOR clone's HEAD. Every
manifest a reader produced recorded their own checkout's SHA under
`validator.revision`, which is precisely the false claim the module's own
docstring says is worse than admitting ignorance.
"""
import json

from generator import manifest


def test_reads_the_commit_pip_recorded_for_a_vcs_install(monkeypatch, tmp_path):
    """A `name @ git+https://...@<sha>` install is the documented path, and pip
    writes the resolved commit into direct_url.json. That is authoritative: it
    is the revision that was installed, not an inference about the filesystem.
    """
    sha = "3cccfd3707e0999f46ddb4aa93408c31a98e50b2"
    monkeypatch.setattr(manifest, "_direct_url", lambda: {
        "url": "https://github.com/mffcampos-cmyk/ODF-Validator.git",
        "vcs_info": {"vcs": "git", "commit_id": sha},
    })
    monkeypatch.setattr(manifest, "_checkout_root", lambda: None)

    info = manifest.validator_revision()

    assert info["revision"] == sha
    assert info["source"] == "installed distribution"


def test_does_not_report_an_enclosing_repository_as_the_validator(monkeypatch):
    """The bug itself. With no recorded install metadata and no validator
    checkout, the answer is "unknown" -- never the SHA of whatever repository
    the interpreter happens to sit inside."""
    monkeypatch.setattr(manifest, "_direct_url", lambda: None)
    monkeypatch.setattr(manifest, "_checkout_root", lambda: None)

    info = manifest.validator_revision()

    assert info["revision"] is None
    assert "reason" in info


def test_uses_git_only_when_the_validator_really_is_a_checkout(monkeypatch, tmp_path):
    """Developing against a clone is still supported: when the validator's own
    directory is a git repository, its HEAD is the right answer."""
    import subprocess
    repo = tmp_path / "ODF-Validator"
    (repo / "odf_validator").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "--allow-empty", "-m", "x"], check=True)
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()

    monkeypatch.setattr(manifest, "_direct_url", lambda: None)
    monkeypatch.setattr(manifest, "_checkout_root", lambda: repo)

    info = manifest.validator_revision()

    assert info["revision"] == head
    assert info["source"] == "checkout"


def test_a_checkout_is_only_a_checkout_if_it_holds_the_package(tmp_path):
    """_checkout_root must not accept site-packages just because some ancestor
    is a repository -- the whole bug in one assertion."""
    import subprocess
    outer = tmp_path / "generator-clone"
    sitepkgs = outer / ".venv" / "lib" / "python3.11" / "site-packages"
    (sitepkgs / "odf_validator").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(outer)], check=True)

    assert manifest._checkout_root(sitepkgs / "odf_validator" / "__init__.py") is None
