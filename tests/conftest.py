from pathlib import Path

import pytest

from scripts.extract_metadata import REPO_ROOT, extract


@pytest.fixture(scope="session")
def legacy():
    """Metadata extracted from the real legacy_code/ tree: (catalog, graph, usage, risks)."""
    return extract(REPO_ROOT / "legacy_code")


@pytest.fixture
def extract_snippet(tmp_path: Path):
    """Write {filename: source} into a temp tree and run the extractor on it."""

    def run(files: dict[str, str]):
        for name, text in files.items():
            (tmp_path / name).write_text(text, encoding="utf-8")
        return extract(tmp_path)

    return run


@pytest.fixture
def git_env(tmp_path: Path, monkeypatch):
    """An isolated git for throwaway test repos: no user or system config, so signing or hooks set up
    elsewhere don't apply, and a fixed author."""
    (tmp_path / "gitconfig").write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for var in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(var, "Test")
    for var in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(var, "test@example.com")
