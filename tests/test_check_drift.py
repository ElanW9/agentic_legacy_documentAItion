"""check_drift.py: stale metadata and new, changed and removed packages, on a copy of the validate fixture."""

import shutil
from datetime import datetime, timezone

import pytest

import scripts.check_drift as cd
from scripts.extract_metadata import REPO_ROOT, extract, write_json
from scripts.models import DocState, DocStatusEntry, DocStatusFile
from scripts.publish_confluence import source_hash

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "validate" / "legacy"


def demo_package(root):
    return next(p for p in extract(root / "legacy")[0].packages if p.name == "PKG_DEMO")


@pytest.fixture(autouse=True)
def not_in_github(monkeypatch):
    # the suite itself runs in GitHub Actions: keep these runs from making real annotations
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setattr(cd, "load_dotenv", lambda *a, **k: None)


@pytest.fixture
def repo(tmp_path):
    """A documented copy of the fixture: source, fresh metadata, and a state entry for PKG_DEMO."""
    shutil.copytree(FIXTURE, tmp_path / "legacy")
    for name, model in zip(cd.METADATA_FILES, extract(tmp_path / "legacy")):
        write_json(model, tmp_path / "metadata" / name)
    pkg = demo_package(tmp_path)
    files = [pkg.spec_ref.file, pkg.body_ref.file]
    write_state(tmp_path, {"PKG_DEMO": entry("PKG_DEMO", files, source_hash(files, REPO_ROOT))})
    return tmp_path


def entry(name, files, src_hash, status=DocState.APPROVED):
    return DocStatusEntry(package=name, doc_path=f"docs/packages/{name.lower()}.md", source_files=files,
                          source_hash=src_hash, status=status,
                          updated_at=datetime(2026, 10, 31, tzinfo=timezone.utc), validation_passed=True)


def write_state(root, entries):
    (root / "state.json").write_text(DocStatusFile(entries=entries).model_dump_json(indent=2), encoding="utf-8")


def run(root):
    return cd.main(["--source", str(root / "legacy"), "--metadata", str(root / "metadata"),
                    "--state", str(root / "state.json")])


def test_no_drift(repo, capsys):
    assert run(repo) == 0
    assert "no drift" in capsys.readouterr().out


def test_changed_source_fails_on_stale_metadata(repo, capsys):
    body = next((repo / "legacy").rglob("*.pkb"))
    body.write_text("-- a new first line moves every unit down\n" + body.read_text(encoding="utf-8"),
                    encoding="utf-8")
    assert run(repo) == 1
    out = capsys.readouterr().out
    assert "METADATA  objects.json: differs from a fresh extraction" in out
    assert "CHANGED   PKG_DEMO: source changed since the doc was written (status approved" in out


def test_changed_source_with_fresh_metadata_only_warns(repo, capsys):
    body = next((repo / "legacy").rglob("*.pkb"))
    body.write_text(body.read_text(encoding="utf-8") + "\n-- trailing comment\n", encoding="utf-8")
    for name, model in zip(cd.METADATA_FILES, extract(repo / "legacy")):
        write_json(model, repo / "metadata" / name)
    assert run(repo) == 0
    out = capsys.readouterr().out
    assert "CHANGED   PKG_DEMO" in out and "METADATA" not in out


def test_new_todo_and_removed_packages(repo, capsys):
    write_state(repo, {"OLD_PKG": entry("OLD_PKG", ["legacy/old_pkg.pks"], "0" * 64)})
    assert run(repo) == 0
    out = capsys.readouterr().out
    assert "NEW       PKG_DEMO: no doc yet" in out
    assert "REMOVED   OLD_PKG: no longer in the source; docs/packages/old_pkg.md is orphaned" in out

    write_state(repo, {"PKG_DEMO": entry("PKG_DEMO", [], "", status=DocState.TODO)})
    assert run(repo) == 0
    assert "NEW       PKG_DEMO" in capsys.readouterr().out


def test_moved_source_file(repo, capsys):
    pkg = demo_package(repo)
    write_state(repo, {"PKG_DEMO": entry("PKG_DEMO", ["legacy/elsewhere.pks", pkg.body_ref.file], "0" * 64)})
    assert run(repo) == 0
    assert "the doc was written for legacy/elsewhere.pks" in capsys.readouterr().out


def test_github_annotations_and_summary(repo, monkeypatch, capsys, tmp_path):
    write_state(repo, {})
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    assert run(repo) == 0
    assert "::warning file=" in capsys.readouterr().out
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "| NEW | PKG_DEMO | no doc yet" in text


def test_summary_without_findings():
    assert "No drift" in cd.summary([])
