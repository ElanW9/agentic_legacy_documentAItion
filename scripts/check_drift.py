"""Report drift between legacy_code/, metadata/ and the docs, without an LLM.

Usage:
    python -m scripts.check_drift [--source legacy_code] [--metadata metadata] [--state state/doc-status.json]

Checks. METADATA fails the run; the others are reported but do not fail it, because a code change
cannot bring its own doc update.
    METADATA  a fresh extraction of legacy_code/ differs from the committed metadata/*.json
    NEW       a package in legacy_code/ has no doc yet: no state entry, or status todo
    CHANGED   a package's source differs from the source its doc was written for (the state's
              source hash), or its spec or body moved to another file
    REMOVED   a state entry's package is no longer in legacy_code/; its doc is orphaned

Package checks use the fresh extraction, so they are right even when metadata/ is out of date.
In GitHub Actions every finding also becomes an annotation, and a table goes to the job summary.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from scripts.extract_metadata import REPO_ROOT, extract
from scripts.models import DocState, DocStatusFile, ObjectCatalog
from scripts.publish_confluence import source_hash

METADATA_FILES = ("objects.json", "dependencies.json", "table_usage.json", "risk_flags.json")
REGENERATE = "run python -m scripts.extract_metadata and commit metadata/"


@dataclass
class Finding:
    kind: str           # METADATA, NEW, CHANGED or REMOVED
    subject: str        # package name, or the metadata file
    message: str
    file: str | None = None  # repo path the annotation points at

    @property
    def is_error(self) -> bool:
        return self.kind == "METADATA"


def stale_metadata(source_root: Path, metadata_dir: Path) -> tuple[list[str], ObjectCatalog]:
    """Metadata files that differ from a fresh extraction, and the fresh object catalog."""
    fresh = extract(source_root)
    stale = []
    for name, model in zip(METADATA_FILES, fresh):
        path = metadata_dir / name
        text = model.model_dump_json(indent=2, exclude_none=False) + "\n"  # as extract_metadata writes it
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            stale.append(name)
    return stale, fresh[0]


def package_drift(catalog: ObjectCatalog, state: DocStatusFile, root: Path = REPO_ROOT) -> list[Finding]:
    findings = []
    in_code = {p.name: [r.file for r in (p.spec_ref, p.body_ref) if r] for p in catalog.packages}
    for name, files in sorted(in_code.items()):
        entry = state.entries.get(name)
        if entry is None or entry.status == DocState.TODO:
            findings.append(Finding("NEW", name, f"no doc yet ({', '.join(files)})", files[0]))
        elif sorted(entry.source_files) != sorted(files):
            findings.append(Finding("CHANGED", name, f"source is now in {', '.join(files)}; the doc was written "
                                                     f"for {', '.join(entry.source_files)}", files[0]))
        elif source_hash(entry.source_files, root) != entry.source_hash:
            findings.append(Finding("CHANGED", name, f"source changed since the doc was written "
                                                     f"(status {entry.status}, doc {entry.doc_path})", files[-1]))
    for name, entry in sorted(state.entries.items()):
        if name not in in_code:
            findings.append(Finding("REMOVED", name, f"no longer in the source; {entry.doc_path} is orphaned",
                                    entry.doc_path))
    return findings


def annotate(findings: list[Finding]) -> None:
    """GitHub Actions workflow commands: one annotation per finding."""
    for f in findings:
        level = "error" if f.is_error else "warning"
        where = f"file={f.file}," if f.file else ""
        message = f"{f.subject}: {f.message}".replace("%", "%25").replace("\n", "%0A")
        print(f"::{level} {where}title=Documentation drift ({f.kind})::{message}")


def summary(findings: list[Finding]) -> str:
    if not findings:
        return "## Documentation drift\n\nNo drift: metadata, docs and source agree.\n"
    rows = "".join(f"| {f.kind} | {f.subject} | {f.message.replace('|', '/')} |\n" for f in findings)
    return f"## Documentation drift\n\n| Check | Subject | Finding |\n|---|---|---|\n{rows}"


def main(argv: list[str] | None = None) -> int:
    load_dotenv(REPO_ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", default=os.getenv("LEGACY_CODE_DIR", "legacy_code"))
    ap.add_argument("--metadata", default=os.getenv("METADATA_DIR", "metadata"))
    ap.add_argument("--state", default="state/doc-status.json")
    args = ap.parse_args(argv)

    stale, catalog = stale_metadata((REPO_ROOT / args.source).resolve(), (REPO_ROOT / args.metadata).resolve())
    findings = [Finding("METADATA", name, f"differs from a fresh extraction of the source; {REGENERATE}",
                        f"{args.metadata}/{name}") for name in stale]
    state = DocStatusFile.model_validate_json((REPO_ROOT / args.state).read_text(encoding="utf-8"))
    findings += package_drift(catalog, state)

    for f in findings:
        print(f"{f.kind:<9} {f.subject}: {f.message}")
    if not findings:
        print("no drift: metadata, docs and source agree")
    if os.getenv("GITHUB_ACTIONS") == "true":
        annotate(findings)
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as out:
            out.write(summary(findings))
    return 1 if any(f.is_error for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
