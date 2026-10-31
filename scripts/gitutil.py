"""Reading older versions of the repo from git, for update_package and publish_confluence."""

from __future__ import annotations

import subprocess
from pathlib import Path


def git(root: Path, *args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True).stdout


def checkout(root: Path, commit: str, paths: list[str], dest: Path) -> None:
    """Write the files under paths as they were at commit to dest/, keeping their repo paths."""
    for path in git(root, "ls-tree", "-r", "--name-only", commit, "--", *paths).decode().splitlines():
        (dest / path).parent.mkdir(parents=True, exist_ok=True)
        (dest / path).write_bytes(git(root, "show", f"{commit}:{path}"))
