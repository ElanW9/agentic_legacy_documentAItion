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
