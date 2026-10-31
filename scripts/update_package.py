"""Prepare a package doc for a source change: report what changed, move citations, mark the rest.

Usage:
    python -m scripts.update_package PACKAGE [--write]

The doc describes the source whose hash state/doc-status.json records. This script finds that
version in git history and compares it line by line with the current source. No LLM is involved.
    report  units whose code changed, units added and removed, and the dependencies, table
            accesses and risk flags added or removed (compared without line numbers)
    move    every citation [ID:a-b] and every number in a line column (Line, Spec, Body,
            Statement line) whose source lines are unchanged gets the new line numbers. The
            Spec and Body columns of a unit's row and the package doc header (Spec, Body,
            Source hash) are refreshed from the metadata
    mark    a citation or line number whose lines changed or were deleted keeps its old numbers
            and gets " !changed" after it. validate_doc fails on the marker, so every one must
            be resolved: re-read the code, fix the claim, remove the marker

Without --write it only reports. The update-package skill does the rest: it rewrites the claims
about the units the report lists. Needs git and up-to-date metadata/ (run the extractor first).
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from scripts.check_drift import stale_metadata
from scripts.extract_metadata import REPO_ROOT, extract
from scripts.gitutil import checkout, git
from scripts.models import DocStatusEntry, DocStatusFile
from scripts.publish_confluence import source_hash
from scripts.validate_doc import (CHANGED_MARK, CITATION_RE, CODE_SPAN_RE, LINE_COLUMNS, NUMBER_RANGE_RE,
                                  Metadata, inside, load_metadata, source_path)

HASH_RE = re.compile(r"\b[0-9a-f]{64}\b")


class UpdateError(Exception):
    pass


def find_base(entry: DocStatusEntry, root: Path) -> str | None:
    """The newest commit whose version of the source files has the hash the doc was written for."""
    for commit in git(root, "log", "--format=%H", "--", *entry.source_files).decode().split():
        try:
            blobs = [git(root, "show", f"{commit}:{f}") for f in entry.source_files]
        except subprocess.CalledProcessError:  # a file did not exist at that commit
            continue
        crlf = [b.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n") for b in blobs]  # checked out with autocrlf
        if entry.source_hash in {hashlib.sha256(b"".join(v)).hexdigest() for v in (blobs, crlf)}:
            return commit
    return None


def lines_of(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n") if path.is_file() else []


def line_map(old: list[str], new: list[str]) -> dict[int, int]:
    """Old line number -> new line number, for the lines the diff keeps (1-based)."""
    out = {}
    for tag, i1, i2, j1, _ in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if tag == "equal":
            out.update({i1 + k + 1: j1 + k + 1 for k in range(i2 - i1)})
    return out


def move(lmap: dict[int, int], start: int, end: int) -> tuple[int, int] | None:
    """New range for old lines start..end; None when a line in it changed or the range was split."""
    new = [lmap.get(n) for n in range(start, end + 1)]
    if None in new or new[-1] - new[0] != end - start:
        return None
    return new[0], new[-1]


def relative(path: str, base: Path) -> str:
    prefix = base.resolve().as_posix() + "/"
    return path[len(prefix):] if path.startswith(prefix) else path


# ---------------------------------------------------------------------------
# What changed
# ---------------------------------------------------------------------------

def unit_texts(meta: Metadata, package: str) -> dict[str, str]:
    """Source text of every unit and variable of the package, for comparing old and new."""
    pkg, cache = meta.package(package), {}

    def text(ref) -> str:
        lines = cache.setdefault(ref.file, lines_of(source_path(ref.file)))
        return "\n".join(lines[ref.start_line - 1:ref.end_line])

    if pkg is None:
        return {}
    out = {s.unit_id: "\n".join(text(r) for r in (s.spec_ref, s.body_ref) if r) for s in pkg.subprograms}
    out |= {f"{package}.{v.name}": text(v.ref) for v in pkg.variables}
    return out


def facts(meta: Metadata, package: str) -> set[str]:
    """Dependencies, table accesses and risk flags of the package, without line numbers."""
    def own(unit: str) -> bool:
        return unit == package or unit.startswith(package + ".")

    out = {f"{e.kind} {e.source} -> {e.target}" for e in meta.graph.edges if own(e.source) or own(e.target)}
    out |= {f"{a.operation} {a.relation} by {a.unit_id} ({a.via})" for a in meta.usage.accesses if own(a.unit_id)}
    out |= {f"{f.kind} in {f.unit_id}: {f.detail}" for f in meta.risks.flags if own(f.unit_id)}
    return out


# ---------------------------------------------------------------------------
# Moving line numbers in a doc
# ---------------------------------------------------------------------------

@dataclass
class Remapper:
    old: Metadata
    old_base: Path                  # where the old source was checked out
    new: Metadata
    new_base: Path
    maps: dict[str, dict[int, int]]  # repo path -> line map, for the files that changed
    package: str
    new_hash: str
    source_dir: str
    moved: int = 0
    marked: list[str] = field(default_factory=list)  # "doc:line  text"

    def shift(self, refs, start: int, end: int, ident: str | None = None) -> tuple[int, int] | None:
        """New range of old lines start..end in whichever file of refs holds them; None if changed."""
        if ident and ident.startswith(self.source_dir + "/"):
            files = {ident}
        else:
            files = {relative(r.file, self.old_base) for r in refs if inside([r], start, end)}
        results = {(start, end) if f not in self.maps else move(self.maps[f], start, end) for f in files}
        return results.pop() if len(results) == 1 else None  # no file, or files that disagree

    def number(self, m: re.Match, units: list[list], refs, where: str) -> str:
        start, end = int(m[1]), int(m[2] or m[1])
        # A line number in a row belongs to the first unit named in it that holds the line (the caller,
        # the "From unit"), not to a callee, table or trigger in the same row.
        refs = next(([r for r in unit if inside([r], start, end)] for unit in units
                     if any(inside([r], start, end) for r in unit)),
                    [r for r in refs if inside([r], start, end)])
        if not refs:
            return m[0]  # did not point into a named unit before either; the validator reports it
        new = self.shift(refs, start, end)
        if new is None:
            self.marked.append(f"{where}  {m[0]}")
            return f"{m[0]} {CHANGED_MARK}"
        self.moved += new != (start, end)
        return f"{new[0]}-{new[1]}" if m[2] else str(new[0])

    def citation(self, m: re.Match, where: str) -> str:
        ident, start, end = m[1], int(m[2]), int(m[3] or m[2])
        refs, error = self.old.resolve(ident)
        if error and not ident.startswith(self.source_dir + "/"):
            return m[0]  # was not a valid citation before the change either
        new = self.shift(refs, start, end, ident)
        if new is None:
            self.marked.append(f"{where}  {m[0]}")
            return f"[{ident}:{m[2]}{'-' + m[3] if m[3] else ''} {CHANGED_MARK}]"
        self.moved += new != (start, end)
        return f"[{ident}:{new[0]}-{new[1]}]" if m[3] else f"[{ident}:{new[0]}]"

    def header_row(self, line: str, key: str) -> str:
        pkg = self.new.package(self.package)
        ref = pkg and {"Spec": pkg.spec_ref, "Body": pkg.body_ref}.get(key)
        if ref:
            line = re.sub(r"`[^`]+`", f"`{relative(ref.file, self.new_base)}`", line, count=1)
            return re.sub(r"lines \d+-\d+", f"lines {ref.start_line}-{ref.end_line}", line)
        return HASH_RE.sub(self.new_hash, line) if key == "Source hash" else line

    def row(self, line: str, header: list[str], subject: str | None, where: str) -> str:
        parts = line.split("|")  # parts[k + 1] is cell k
        if header[:2] == ["field", "value"]:
            return self.header_row(line, parts[1].strip())
        ids = [i.strip() for i in CODE_SPAN_RE.findall(line)] + ([subject] if subject else [])
        refs = [r for i in ids for r in self.old.resolve(i)[0]]
        unit_refs = [self.old.resolve(i)[0] for i in ids if i in self.old.subs or i in self.old.variables]
        units = [self.new.subs[i] for i in ids if i in self.new.subs]
        for k, col in enumerate(header):
            if col not in LINE_COLUMNS or k + 1 >= len(parts) - 1:
                continue
            if col in ("spec", "body") and len(units) == 1:  # the unit's own range: take it from the metadata
                ref = units[0].spec_ref if col == "spec" else units[0].body_ref
                if ref:
                    span = str(ref.start_line) if ref.start_line == ref.end_line else f"{ref.start_line}-{ref.end_line}"
                    parts[k + 1] = NUMBER_RANGE_RE.sub(span, parts[k + 1], count=1)
                    continue
            parts[k + 1] = NUMBER_RANGE_RE.sub(lambda m: self.number(m, unit_refs, refs, where), parts[k + 1])
        return "|".join(parts)

    def remap(self, text: str, doc_path: str) -> str:
        subject = None
        if m := re.search(r"^# `([A-Z0-9_$.#]+)`", text, re.M):
            subject = m[1]
        out, header, in_fence = [], None, False
        for n, line in enumerate(text.split("\n"), 1):
            where = f"{doc_path}:{n}"
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
            if in_fence or line.lstrip().startswith("```"):
                out.append(line)
                continue
            if line.lstrip().startswith("|"):
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if header is None:
                    header = [c.lower() for c in cells]
                elif not all(re.fullmatch(r":?-+:?", c) for c in cells if c):
                    line = self.row(line, header, subject, where)
            else:
                header = None
            out.append(CITATION_RE.sub(lambda m: self.citation(m, where), line))
        return "\n".join(out)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def update(package: str, write: bool, root: Path = REPO_ROOT, source: str = "legacy_code",
           metadata: str = "metadata", state_path: str = "state/doc-status.json") -> list[str]:
    """Report lines; with write, the docs are updated in place."""
    state = DocStatusFile.model_validate_json((root / state_path).read_text(encoding="utf-8"))
    entry = state.entries.get(package)
    if entry is None:
        raise UpdateError(f"no entry for {package} in {state_path}; document it with the document-package skill")
    if stale_metadata(root / source, root / metadata)[0]:
        raise UpdateError("metadata/ is out of date; run python -m scripts.extract_metadata first")
    try:
        new_hash = source_hash(entry.source_files, root)
    except FileNotFoundError:
        raise UpdateError(f"{', '.join(entry.source_files)} no longer exist; re-document {package}") from None
    if new_hash == entry.source_hash:
        return [f"{package}: the source has not changed since the doc was written; nothing to do"]
    base = find_base(entry, root)
    if base is None:
        raise UpdateError(f"no commit has the source the {package} doc was written for (hash "
                          f"{entry.source_hash[:12]}); re-document {package} with the document-package skill")

    new = load_metadata(root / metadata)
    docs = [entry.doc_path] + sorted(p.relative_to(root).as_posix()
                                     for p in (root / entry.doc_path[:-len(".md")]).glob("*.md"))
    with tempfile.TemporaryDirectory() as tmp:
        old_base = Path(tmp)
        checkout(root, base, [source], old_base)
        old = Metadata(*extract(old_base / source))
        changed_files = git(root, "diff", "--name-only", base, "--", source).decode().split()
        maps = {f: line_map(lines_of(old_base / f), lines_of(root / f)) for f in changed_files}

        old_units, new_units = unit_texts(old, package), unit_texts(new, package)
        old_facts, new_facts = facts(old, package), facts(new, package)
        remapper = Remapper(old, old_base, new, root, maps, package, new_hash, source)
        # --write puts the new hash in the package doc header; moving the numbers twice would break them
        done = new_hash in (root / entry.doc_path).read_text(encoding="utf-8")
        for doc in [] if done else docs:
            text = (root / doc).read_text(encoding="utf-8")
            updated = remapper.remap(text, doc)
            if write and updated != text:
                (root / doc).write_text(updated, encoding="utf-8", newline="\n")

    def listing(items) -> str:
        return ", ".join(sorted(items)) or "none"

    report = [
        f"{package}: the doc describes the source at commit {base[:12]}",
        f"changed files: {listing(changed_files)}",
        f"units changed: {listing(u for u in old_units.keys() & new_units.keys() if old_units[u] != new_units[u])}",
        f"units added: {listing(new_units.keys() - old_units.keys())}",
        f"units removed: {listing(old_units.keys() - new_units.keys())}",
        f"facts added: {len(new_facts - old_facts)}",
        *(f"  + {f}" for f in sorted(new_facts - old_facts)),
        f"facts removed: {len(old_facts - new_facts)}",
        *(f"  - {f}" for f in sorted(old_facts - new_facts)),
    ]
    if done:
        left = sum((root / d).read_text(encoding="utf-8").count(CHANGED_MARK) for d in docs)
        return report + [f"line numbers: already moved to this source (the doc header has its hash); "
                         f"{left} {CHANGED_MARK} markers left to resolve"]
    report += [
        f"line numbers {'moved' if write else 'to move'}: {remapper.moved} in {len(docs)} docs",
        f"line numbers {'marked' if write else 'to mark'} {CHANGED_MARK}: {len(remapper.marked)}",
        *(f"  {m}" for m in remapper.marked),
    ]
    if not write:
        report.append("dry run: nothing written; add --write to update the docs")
    return report


def main(argv: list[str] | None = None) -> int:
    load_dotenv(REPO_ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("package", type=str.upper)
    ap.add_argument("--write", action="store_true", help="update the docs in place")
    ap.add_argument("--source", default=os.getenv("LEGACY_CODE_DIR", "legacy_code"))
    ap.add_argument("--metadata", default=os.getenv("METADATA_DIR", "metadata"))
    args = ap.parse_args(argv)
    try:
        for line in update(args.package, args.write, source=args.source, metadata=args.metadata):
            print(line)
    except UpdateError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
