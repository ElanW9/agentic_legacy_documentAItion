"""update_package.py: find the documented version in git, move unchanged line numbers, mark changed ones.

Each test builds a throwaway git repo from the validate fixture: PKG_DEMO documented and committed,
then the body changed (two lines inserted at the top, one statement in SET_STATUS replaced).
"""

import shutil
import subprocess
from datetime import datetime, timezone

import pytest

from scripts.extract_metadata import REPO_ROOT, extract
from scripts.extract_metadata import write_json
from scripts.models import DocState, DocStatusEntry, DocStatusFile
from scripts.publish_confluence import source_hash
from scripts.update_package import UpdateError, line_map, move, update
from scripts.validate_doc import load_metadata, validate

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "validate"
FILES = ["legacy_code/packages/pkg_demo.pks", "legacy_code/packages/pkg_demo.pkb"]
DOC = "docs/packages/pkg_demo.md"


def sh(root, *args):
    subprocess.run(args, cwd=root, check=True, capture_output=True)


def extract_to(root):
    for name, model in zip(("objects.json", "dependencies.json", "table_usage.json", "risk_flags.json"),
                           extract(root / "legacy_code")):
        write_json(model, root / "metadata" / name)


@pytest.fixture
def repo(tmp_path, git_env):
    root = tmp_path / "repo"
    shutil.copytree(FIXTURES / "legacy", root / "legacy_code")
    extract_to(root)
    old_hash = source_hash(FILES, root)
    doc = (FIXTURES / "pkg_demo.md").read_text(encoding="utf-8")
    doc = doc.replace("tests/fixtures/validate/legacy/", "legacy_code/").replace("`0000`", f"`{old_hash}`")
    (root / DOC).parent.mkdir(parents=True)
    (root / DOC).write_text(doc, encoding="utf-8", newline="\n")
    entry = DocStatusEntry(package="PKG_DEMO", doc_path=DOC, source_files=FILES, source_hash=old_hash,
                           status=DocState.APPROVED, updated_at=datetime(2026, 10, 31, tzinfo=timezone.utc),
                           validation_passed=True)
    (root / "state").mkdir()
    (root / "state/doc-status.json").write_text(DocStatusFile(entries={"PKG_DEMO": entry}).model_dump_json(indent=2),
                                                encoding="utf-8")
    sh(root, "git", "init", "-q")
    sh(root, "git", "add", ".")
    sh(root, "git", "commit", "-q", "-m", "documented")
    return root


def change_body(root):
    body = root / FILES[1]
    lines = body.read_text(encoding="utf-8").split("\n")
    lines[5] = "    DELETE FROM demo_items WHERE item_id = p_id;"  # old line 6: g_count := g_count + 1;
    lines[2:2] = ["  -- two lines inserted above set_status", ""]
    body.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    extract_to(root)


def test_line_map_and_move():
    lmap = line_map(["a", "b", "c", "d"], ["x", "a", "b", "C", "d"])
    assert lmap == {1: 2, 2: 3, 4: 5}
    assert move(lmap, 1, 2) == (2, 3)
    assert move(lmap, 2, 3) is None  # line 3 changed
    assert move(lmap, 4, 4) == (5, 5)


def test_nothing_to_do_when_the_source_is_unchanged(repo):
    assert "nothing to do" in update("PKG_DEMO", write=True, root=repo)[0]


def test_dry_run_reports_and_writes_nothing(repo):
    change_body(repo)
    before = (repo / DOC).read_text(encoding="utf-8")
    report = "\n".join(update("PKG_DEMO", write=False, root=repo))
    assert (repo / DOC).read_text(encoding="utf-8") == before
    assert "units changed: PKG_DEMO.SET_STATUS\n" in report  # GET_QTY only moved
    assert "  + DELETE DEMO_ITEMS by PKG_DEMO.SET_STATUS (STATIC)" in report
    assert "dry run" in report


def test_write_moves_unchanged_lines_and_marks_changed_ones(repo):
    change_body(repo)
    report = "\n".join(update("PKG_DEMO", write=True, root=repo))
    doc = (repo / DOC).read_text(encoding="utf-8")

    assert "[PKG_DEMO.GET_QTY:15-16]" in doc            # was 13-14: two lines inserted above
    assert "[PKG_DEMO.SET_STATUS:7]" in doc             # was 5, the UPDATE, unchanged
    assert "[PKG_DEMO.SET_STATUS:6-7 !changed]" in doc  # old line 6 was replaced
    assert "[PKG_DEMO(spec):2]" in doc                  # the spec did not change
    assert "| `PKG_DEMO.GET_QTY` | 18 | WHEN OTHERS |" in doc  # line column, was 16
    # caller first: the line is the call in ADD_QTY#1 (moved 22 -> 24), not a line of ADD_QTY#2
    assert "| `PKG_DEMO.ADD_QTY#1` | `PKG_DEMO.ADD_QTY#2` | 24 |" in doc
    # a row naming the unit and a table: the line belongs to the unit, not to the table's own file
    assert "| `DEMO_ITEMS` | UPDATE | `PKG_DEMO.SET_STATUS` | 7 | STATIC |" in doc
    assert "| 4 | 5-10 |" in doc                        # SET_STATUS spec and body, from the metadata
    assert f"`{source_hash(FILES, repo)}`" in doc       # header hash refreshed
    # 3-8 and 6-7 on SET_STATUS, and 6 twice in the package state row
    assert "line numbers marked !changed: 4" in report, report

    # the doc now fails validation only on the marked lines: the marker itself, and a sentence whose
    # only citation is marked no longer counts as cited
    findings = validate(doc, DOC, load_metadata(repo / "metadata"))
    marked = {n for n, line in enumerate(doc.split("\n"), 1) if "!changed" in line}
    errors = [f for f in findings if f.severity == "ERROR"]
    assert {f.line for f in errors} == marked and "changed" in {f.check for f in errors}

    # a second run must not move the numbers again
    again = "\n".join(update("PKG_DEMO", write=True, root=repo))
    assert (repo / DOC).read_text(encoding="utf-8") == doc
    assert "already moved to this source" in again and "4 !changed markers left" in again


def test_stale_metadata_is_refused(repo):
    (repo / FILES[1]).write_text((repo / FILES[1]).read_text(encoding="utf-8") + "\n-- x\n", encoding="utf-8")
    with pytest.raises(UpdateError, match="metadata/ is out of date"):
        update("PKG_DEMO", write=False, root=repo)


def test_unknown_documented_version(repo):
    change_body(repo)
    state = DocStatusFile.model_validate_json((repo / "state/doc-status.json").read_text(encoding="utf-8"))
    state.entries["PKG_DEMO"].source_hash = "0" * 64
    (repo / "state/doc-status.json").write_text(state.model_dump_json(indent=2), encoding="utf-8")
    with pytest.raises(UpdateError, match="no commit has the source"):
        update("PKG_DEMO", write=False, root=repo)
    with pytest.raises(UpdateError, match="no entry for NOPE"):
        update("NOPE", write=False, root=repo)
