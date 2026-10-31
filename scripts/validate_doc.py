"""Validate documentation files against the extracted metadata.

Usage:
    python -m scripts.validate_doc DOC [DOC ...] [--metadata metadata]

Checks. ERROR fails the doc; WARN is reported but does not fail it.
    leftover   template comments and {{placeholders}} are removed
    section    the "##" headings of the matching template are present, in order;
               the fixed "###" headings are present
    citation   [ID:start-end] and [path:start-end] resolve, and the lines fall inside
               the range objects.json gives for that id (glossary/conventions.md)
    reference  `UPPERCASE` names exist: units, variables, parameters, tables, columns.
               Names not in the metadata must at least occur in the code of legacy_code/
    signature  `PROCEDURE ...` / `FUNCTION ...` spans match a signature in objects.json
    uncited    every prose sentence and every table row carries a citation or a line column
    coverage   a package doc mentions every subprogram of the package (ERROR) and every
               variable, table and transaction/error/dynamic-SQL risk flag (WARN)
    changed    no "!changed" marker is left: update_package puts it on line numbers whose
               source lines changed, and the claim must be checked before it goes

Line numbers in the report are lines of the doc. Exit code 0 when every doc passes.
"""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from scripts.extract_metadata import REPO_ROOT, mask_source
from scripts.models import (
    UNKNOWN,
    AccessVia,
    ConstraintKind,
    DependencyGraph,
    DependencyKind,
    ObjectCatalog,
    ObjectType,
    Operation,
    ParamMode,
    RiskFlags,
    RiskKind,
    SourceRef,
    Subprogram,
    TableUsage,
    Visibility,
)

TEMPLATES = REPO_ROOT / "templates"
NONE_FOUND = "None found in metadata."

CITATION_RE = re.compile(r"\[([A-Za-z0-9_$#.()/\-]+):(\d+)(?:-(\d+))?\]")
LOOSE_CITATION_RE = re.compile(r"\[[A-Za-z0-9_$#.()/\-]+:[^\]]*\]")
CODE_SPAN_RE = re.compile(r"`([^`]+)`")
NAME_RE = re.compile(r"([A-Z][A-Z0-9_$]*)(?:\.([A-Z][A-Z0-9_$]*))?(#\d+)?(?:\((spec|body)\))?")
SIGNATURE_RE = re.compile(r"(PROCEDURE|FUNCTION)\s", re.I)
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_$#]*")
LIST_ITEM_RE = re.compile(r"\s*(?:[-*+]|\d+\.)\s+")
LINK_RE = re.compile(r"\[[^\]]*\]\([^)]*\.md[^)]*\)")
NUMBER_RANGE_RE = re.compile(r"\b(\d+)(?:\s*-\s*(\d+))?\b")
LINE_COLUMNS = {"line", "spec", "body", "statement line"}
CHANGED_MARK = "!changed"  # set by update_package on line numbers whose source lines changed

# Risk kinds that every package doc must cite. HARDCODED_VALUE and PACKAGE_STATE are too
# numerous to require one citation per flag; review-doc covers them.
COVERED_RISKS = set(RiskKind) - {RiskKind.HARDCODED_VALUE, RiskKind.PACKAGE_STATE}

# Oracle names a doc may mention that need not occur in legacy_code/.
ORACLE_TERMS = {
    "NO_DATA_FOUND", "TOO_MANY_ROWS", "DUP_VAL_ON_INDEX", "VALUE_ERROR", "ZERO_DIVIDE",
    "INVALID_NUMBER", "OTHERS", "SQLERRM", "SQLCODE", "SQL%ROWCOUNT", "SYSDATE", "SYSTIMESTAMP",
    "NULL", "TRUE", "FALSE", "COMMIT", "ROLLBACK", "SAVEPOINT", "PRAGMA", "AUTONOMOUS_TRANSACTION",
    "EXECUTE", "IMMEDIATE", "RAISE", "RAISE_APPLICATION_ERROR", "NEXTVAL", "CURRVAL", "SELECT",
    "INSERT", "UPDATE", "DELETE", "MERGE", "BEFORE", "AFTER", "ROW", "STATEMENT",
}
ENUM_VALUES = {
    str(v) for enum in (ObjectType, Visibility, ParamMode, DependencyKind, RiskKind, Operation,
                        AccessVia, ConstraintKind) for v in enum
}


# ---------------------------------------------------------------------------
# Metadata with lookup indexes
# ---------------------------------------------------------------------------

def source_path(path: str, root: Path = REPO_ROOT) -> Path:
    p = Path(path)
    return p if p.is_absolute() else root / p


@dataclass
class Metadata:
    catalog: ObjectCatalog
    graph: DependencyGraph
    usage: TableUsage
    risks: RiskFlags
    subs: dict[str, Subprogram] = field(default_factory=dict)
    overloads: dict[str, list[str]] = field(default_factory=dict)  # PKG.NAME -> [PKG.NAME#1, ...]
    variables: dict[str, SourceRef] = field(default_factory=dict)  # PKG.VAR -> ref
    objects: dict[str, SourceRef] = field(default_factory=dict)    # tables, views, triggers, sequences
    columns: dict[str, set[str]] = field(default_factory=dict)     # table or view -> columns
    files: dict[str, int] = field(default_factory=dict)            # path -> line count
    signatures: set[str] = field(default_factory=set)
    externals: set[str] = field(default_factory=set)
    known_names: set[str] = field(default_factory=set)             # bare names a doc may use
    code_words: set[str] = field(default_factory=set)              # identifiers in code
    comment_words: set[str] = field(default_factory=set)           # identifiers only in comments
    root: Path = REPO_ROOT  # where the source files are; an older checkout for publish_confluence

    def __post_init__(self) -> None:
        c = self.catalog
        for s in c.subprograms():
            self.subs[s.unit_id] = s
            if s.overload is not None:
                self.overloads.setdefault(f"{s.package}.{s.name}", []).append(s.unit_id)
            self.signatures.add(norm(s.signature))
            self.known_names.add(s.name)
            self.known_names.update(p.name for p in s.params)
        for p in c.packages:
            self.known_names.add(p.name)
            for v in p.variables:
                self.variables[f"{p.name}.{v.name}"] = v.ref
                self.known_names.add(v.name)
        for t in c.tables:
            self.objects[t.name] = t.ref
            self.columns[t.name] = {col.name for col in t.columns}
        for v in c.views:
            self.objects[v.name] = v.ref
            self.columns[v.name] = set(v.columns)
        for o in [*c.triggers, *c.sequences]:
            self.objects[o.name] = o.ref
        self.known_names |= set(self.objects) | {col for cols in self.columns.values() for col in cols}
        self.externals = {e.target for e in self.graph.edges if e.kind == DependencyKind.EXTERNAL_CALL}
        self.known_names |= {e.split(".")[0] for e in self.externals}
        for f in c.files:
            self.files[f.path] = f.line_count
            raw = source_path(f.path, self.root).read_text(encoding="utf-8").replace("\r\n", "\n")
            code, _ = mask_source(raw)
            self.code_words |= {w.upper() for w in WORD_RE.findall(code)}
            self.comment_words |= {w.upper() for w in WORD_RE.findall(raw)}
        self.comment_words -= self.code_words

    def package(self, name: str):
        return next((p for p in self.catalog.packages if p.name == name), None)

    def resolve(self, ident: str) -> tuple[list[SourceRef], str | None]:
        """Source ranges of a citable id, or an error message."""
        m = re.fullmatch(r"([A-Z0-9_$]+)\((spec|body)\)", ident)
        if m:
            p = self.package(m[1])
            ref = p and (p.spec_ref if m[2] == "spec" else p.body_ref)
            return ([ref], None) if ref else ([], f"no package {m[2]} for {m[1]}")
        if ident in self.subs:
            s = self.subs[ident]
            return [r for r in (s.spec_ref, s.body_ref) if r], None
        if ident in self.overloads:
            return [], f"{ident} is overloaded; cite one of {', '.join(self.overloads[ident])}"
        if ident in self.variables:
            return [self.variables[ident]], None
        if ident in self.objects:
            return [self.objects[ident]], None
        if ident in self.files:
            return [SourceRef(file=ident, start_line=1, end_line=self.files[ident])], None
        if self.package(ident):
            return [], f"cite {ident}(spec), {ident}(body) or one of its units, not the package"
        return [], f"unknown id {ident}"

    def params_in_scope(self, doc: Doc) -> set[str]:
        if doc.kind == "procedure" and doc.subject in self.subs:
            units = [self.subs[doc.subject]]
        elif doc.kind == "package":
            units = [s for s in self.subs.values() if s.package == doc.subject]
        else:
            units = list(self.subs.values())
        return {p.name for s in units for p in s.params}


def load_metadata(meta_dir: Path, root: Path = REPO_ROOT) -> Metadata:
    def read(model, name):
        return model.model_validate_json((meta_dir / name).read_text(encoding="utf-8"))

    return Metadata(read(ObjectCatalog, "objects.json"), read(DependencyGraph, "dependencies.json"),
                    read(TableUsage, "table_usage.json"), read(RiskFlags, "risk_flags.json"), root=root)


# ---------------------------------------------------------------------------
# Doc parsing
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    line: int | None  # doc line, None for whole-doc findings
    severity: str     # ERROR or WARN
    check: str
    message: str


@dataclass
class Doc:
    path: str
    kind: str | None = None     # package, procedure or flow
    subject: str | None = None  # package name or unit id
    content: list[tuple[int, str]] = field(default_factory=list)   # lines outside fences/comments
    sections: dict[int, str | None] = field(default_factory=dict)  # line -> "##" section (None = header)


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_doc(text: str, path: str, findings: list[Finding]) -> Doc:
    doc = Doc(path=path)
    in_fence = in_comment = False
    section = None
    for n, line in enumerate(text.splitlines(), 1):
        if "{{" in line:
            findings.append(Finding(n, "ERROR", "leftover", "template placeholder {{...}} left in the doc"))
        if "<!--" in line:
            findings.append(Finding(n, "ERROR", "leftover", "HTML comment left in the doc"))
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if in_comment:
            in_comment = "-->" not in line
            continue
        if "<!--" in line:
            in_comment = "-->" not in line.split("<!--", 1)[1]
            continue
        if line.startswith("# ") and doc.kind is None:
            title = line[2:].strip()
            if m := re.fullmatch(r"Package `([A-Z0-9_$]+)`", title):
                doc.kind, doc.subject = "package", m[1]
            elif title.startswith("Flow:"):
                doc.kind = "flow"
            elif m := re.fullmatch(r"`([A-Z0-9_$.#]+)`", title):
                doc.kind, doc.subject = "procedure", m[1]
        if line.startswith("## "):
            section = line[3:].strip()
        doc.content.append((n, line))
        doc.sections[n] = section
    return doc


def template_headings(kind: str) -> tuple[list[str], list[str]]:
    """Fixed "##" and "###" headings of a template, in order."""
    text = (TEMPLATES / f"{kind}.md").read_text(encoding="utf-8")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    h2 = [ln[3:].strip() for ln in text.splitlines() if ln.startswith("## ")]
    h3 = [ln[4:].strip() for ln in text.splitlines() if ln.startswith("### ") and "{{" not in ln]
    return h2, h3


def table_rows(doc: Doc):
    """Yield (line, header cells, row cells) for every data row of every table."""
    header = None
    for n, line in doc.content:
        if not line.lstrip().startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            header = [c.lower() for c in cells]
        elif not all(re.fullmatch(r":?-+:?", c) for c in cells if c):
            yield n, header, cells


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_sections(doc: Doc, findings: list[Finding]) -> None:
    required, fixed_h3 = template_headings(doc.kind)
    found = [(n, line[3:].strip()) for n, line in doc.content if line.startswith("## ")]
    names = [h for _, h in found]
    for h in required:
        if h not in names:
            findings.append(Finding(None, "ERROR", "section", f"missing section '## {h}'"))
        elif names.count(h) > 1:
            findings.append(Finding(None, "ERROR", "section", f"section '## {h}' appears more than once"))
    present = [(n, h) for n, h in found if h in required]
    expected = [h for h in required if h in names]
    for (n, h), want in zip(present, expected):
        if h != want:
            findings.append(Finding(n, "ERROR", "section", f"'## {h}' is out of order; expected '## {want}' here"))
            break
    for n, h in found:
        if h not in required:
            findings.append(Finding(n, "WARN", "section", f"'## {h}' is not a template section"))
    h3 = {line[4:].strip() for _, line in doc.content if line.startswith("### ")}
    for h in fixed_h3:
        if h not in h3:
            findings.append(Finding(None, "ERROR", "section", f"missing subsection '### {h}'"))


def inside(refs: list[SourceRef], start: int, end: int) -> bool:
    return any(r.start_line <= start and end <= r.end_line for r in refs)


def check_citations(doc: Doc, meta: Metadata, findings: list[Finding]) -> list[tuple[str, int, int]]:
    """Validate every citation; return the valid ones as (id, start, end)."""
    cited = []
    for n, line in doc.content:
        if CHANGED_MARK in line:
            findings.append(Finding(n, "ERROR", "changed",
                                    f"the source lines here changed since the doc was written; re-read the code, "
                                    f"fix the claim and its line numbers, then remove '{CHANGED_MARK}'"))
        for m in LOOSE_CITATION_RE.finditer(line):
            if CHANGED_MARK in m[0]:
                continue  # reported above
            if not CITATION_RE.fullmatch(m[0]):
                findings.append(Finding(n, "ERROR", "citation", f"malformed citation {m[0]}; use [ID:start-end]"))
        for m in CITATION_RE.finditer(line):
            ident, start = m[1], int(m[2])
            end = int(m[3]) if m[3] else start
            refs, error = meta.resolve(ident)
            if error:
                findings.append(Finding(n, "ERROR", "citation", f"{m[0]}: {error}"))
            elif end < start:
                findings.append(Finding(n, "ERROR", "citation", f"{m[0]}: end line before start line"))
            elif not inside(refs, start, end):
                ranges = ", ".join(f"{r.file}:{r.start_line}-{r.end_line}" for r in refs)
                findings.append(Finding(n, "ERROR", "citation", f"{m[0]}: lines outside {ident} ({ranges})"))
            else:
                cited.append((ident, start, end))
                if ident in meta.files:
                    owner = next((name for name, r in meta.objects.items()
                                  if r.file == ident and inside([r], start, end)), None)
                    for p in meta.catalog.packages:
                        for part, r in (("spec", p.spec_ref), ("body", p.body_ref)):
                            if owner is None and r and r.file == ident and inside([r], start, end):
                                owner = f"{p.name}({part})"
                    if owner:
                        findings.append(Finding(n, "WARN", "citation",
                                                f"{m[0]}: lines belong to {owner}; cite the id, not the path"))
    return cited


def check_name(span: str, doc: Doc, meta: Metadata, line: str, scope_params: set[str]) -> tuple[str, str] | None:
    """Return (severity, message) when an `UPPERCASE` name does not exist."""
    m = NAME_RE.fullmatch(span)
    if not m:
        return None
    head, tail, ov, part = m.groups()
    if part:
        return None if meta.package(head) else ("ERROR", f"`{span}`: no package {head}")
    if tail is None and ov is None:
        if head.startswith("P_"):
            if head in scope_params:
                return None
            scope = doc.subject or "any unit"
            return "ERROR", f"`{span}`: not a parameter of {scope} in objects.json"
        if head in meta.known_names or head in ENUM_VALUES or head in ORACLE_TERMS:
            return None
        return fallback(span, [head], line, meta)
    ident = f"{head}.{tail}{ov or ''}" if tail else f"{head}{ov}"
    if meta.package(head):
        if ident in meta.subs or ident in meta.variables or (ov is None and ident in meta.overloads):
            return None
        return "ERROR", f"`{span}`: no subprogram or variable {ident} in objects.json"
    if head in meta.columns:
        if ov is None and tail in meta.columns[head]:
            return None
        return "ERROR", f"`{span}`: {head} has no column {tail} in objects.json"
    if ident in meta.externals or head in {e.split(".")[0] for e in meta.externals}:
        return None
    return fallback(span, [head] + ([tail] if tail else []), line, meta)


def fallback(span: str, words: list[str], line: str, meta: Metadata) -> tuple[str, str] | None:
    """Names the metadata does not model (locals, cursors, literals) must occur in the code."""
    if all(w in meta.code_words for w in words):
        return None
    if any(w in meta.comment_words for w in words):
        severity = "WARN" if "comment" in line.lower() else "ERROR"
        return severity, f"`{span}`: occurs only in a source comment, not as code"
    return "ERROR", f"`{span}`: not found in metadata or in legacy_code/"


def check_references(doc: Doc, meta: Metadata, findings: list[Finding]) -> set[str]:
    """Check code spans; return every name mentioned in a span."""
    scope_params = meta.params_in_scope(doc)
    mentioned = set()
    for n, line in doc.content:
        for m in CODE_SPAN_RE.finditer(line):
            span = m[1].strip()
            if SIGNATURE_RE.match(span):
                if norm(span) not in meta.signatures:
                    findings.append(Finding(n, "ERROR", "signature",
                                            f"`{span}` does not match any signature in objects.json"))
                continue
            mentioned.add(span)
            if problem := check_name(span, doc, meta, line, scope_params):
                findings.append(Finding(n, problem[0], "reference", problem[1]))
    return mentioned


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    out: list[str] = []
    for part in parts:
        lead = re.match(r"(?:\[[^\]]+\]\s*)+", part)
        if out and lead and CITATION_RE.match(part):
            out[-1] += " " + lead[0].strip()  # citation written after the full stop
            part = part[lead.end():]
        if out and part and not part[0].isupper() and not part[0] in "`*_\"(":
            out[-1] += " " + part  # e.g. "i.e. the", "line 5. then"
        elif part:
            out.append(part)
    return out


def exempt(sentence: str) -> bool:
    s = sentence.strip()
    # Questions and lead-ins ("The unit has three branches:") are not claims.
    return (UNKNOWN in s or NONE_FOUND in s or not re.search(r"[A-Za-z]", s) or s.endswith((":", "?"))
            or bool(LINK_RE.search(s)))


def check_uncited(doc: Doc, meta: Metadata, findings: list[Finding]) -> list[tuple[str, int, int]]:
    """Every sentence and table row in a section needs a citation. Returns (id, start, end) of row lines."""
    points = []
    blocks: list[list[tuple[int, str]]] = []
    for n, line in doc.content:
        if doc.sections[n] is None or line.startswith("#") or line.lstrip().startswith("|") or not line.strip():
            blocks.append([])  # block boundary
        elif item := LIST_ITEM_RE.match(line):
            blocks.append([(n, line[item.end():])])
        elif blocks:
            blocks[-1].append((n, line.strip()))
        else:
            blocks.append([(n, line.strip())])
    for block in filter(None, blocks):
        text, starts = "", []
        for n, line in block:
            starts.append((len(text), n))
            text += line.strip() + " "
        if doc.sections[block[0][0]] == "Open questions" and not CITATION_RE.search(text) and UNKNOWN not in text:
            findings.append(Finding(block[0][0], "ERROR", "uncited",
                                    f"open question without citation or '{UNKNOWN}': {text[:70]!r}"))
        offset = 0
        for sentence in split_sentences(text.strip()):
            offset = text.find(sentence[:20], offset)
            n = max((ln for pos, ln in starts if pos <= max(offset, 0)), default=block[0][0])
            if not exempt(sentence) and not CITATION_RE.search(sentence):
                findings.append(Finding(n, "ERROR", "uncited", f"sentence without citation: {sentence[:70]!r}"))

    for n, header, cells in table_rows(doc):
        if doc.sections[n] is None:
            continue
        row = " | ".join(cells)
        if UNKNOWN in row or NONE_FOUND in row:
            continue
        values = []
        for col, cell in zip(header, cells):
            if col in LINE_COLUMNS:
                values += [(int(a), int(b or a)) for a, b in NUMBER_RANGE_RE.findall(cell)]
        if not values:
            if not CITATION_RE.search(row):
                findings.append(Finding(n, "ERROR", "uncited", "table row without citation or line number"))
            continue
        ids = [s.strip() for s in CODE_SPAN_RE.findall(row)]
        if doc.kind == "procedure" and doc.subject:
            ids.append(doc.subject)
        candidates = [(i, meta.resolve(i)[0]) for i in ids]
        candidates = [(i, refs) for i, refs in candidates if refs]
        if not candidates:
            findings.append(Finding(n, "ERROR", "citation", "line number in a row without a known unit id"))
            continue
        for start, end in values:
            owners = [i for i, refs in candidates if inside(refs, start, end)]
            if not owners:
                findings.append(Finding(n, "ERROR", "citation",
                                        f"line {start}-{end} is not inside any unit named in the row"))
            points += [(i, start, end) for i in owners]
    return points


def check_coverage(doc: Doc, meta: Metadata, mentioned: set[str], points: list[tuple[str, int, int]],
                   findings: list[Finding]) -> None:
    pkg = meta.package(doc.subject)
    if pkg is None:
        findings.append(Finding(None, "ERROR", "reference", f"package {doc.subject} not in objects.json"))
        return
    names = mentioned | {i for i, _, _ in points}
    for s in pkg.subprograms:
        if s.unit_id not in names:
            findings.append(Finding(None, "ERROR", "coverage", f"subprogram {s.unit_id} is not documented"))
    for v in pkg.variables:
        if f"{pkg.name}.{v.name}" not in names:
            findings.append(Finding(None, "WARN", "coverage", f"variable {pkg.name}.{v.name} is not mentioned"))
    own = pkg.name + "."
    for rel in sorted({a.relation for a in meta.usage.accesses if a.unit_id.startswith(own)}):
        if rel not in names:
            findings.append(Finding(None, "WARN", "coverage", f"table or view {rel} is not mentioned"))
    for f in meta.risks.flags:
        if f.kind not in COVERED_RISKS or not (f.unit_id == pkg.name or f.unit_id.startswith(own)):
            continue
        owner = (lambda i: re.split(r"[.(]", i)[0]) if f.unit_id == pkg.name else (lambda i: i)
        if not any(owner(i) == f.unit_id for i, s, e in points if s <= f.line <= e):
            findings.append(Finding(None, "WARN", "coverage",
                                    f"{f.kind} at {f.file}:{f.line} ({f.unit_id}) is not cited"))


def validate(text: str, path: str, meta: Metadata) -> list[Finding]:
    findings: list[Finding] = []
    doc = parse_doc(text, path, findings)
    if doc.kind is None:
        findings.append(Finding(1, "ERROR", "section",
                                "title must be '# Package `X`', '# `PACKAGE.UNIT`' or '# Flow: name'"))
        return findings
    check_sections(doc, findings)
    cited = check_citations(doc, meta, findings)
    mentioned = check_references(doc, meta, findings)
    points = check_uncited(doc, meta, findings)
    if doc.kind == "package":
        check_coverage(doc, meta, mentioned, cited + points, findings)
    elif doc.kind == "procedure" and doc.subject not in meta.subs:
        findings.append(Finding(1, "ERROR", "reference", f"unit {doc.subject} not in objects.json"))
    return findings


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def report(path: str, findings: list[Finding]) -> str:
    errors = sum(f.severity == "ERROR" for f in findings)
    warns = len(findings) - errors
    lines = [f"{'FAIL' if errors else 'PASS'} {path} ({errors} errors, {warns} warnings)"]
    for f in sorted(findings, key=lambda f: (f.line is None, f.line or 0, f.severity)):
        where = f"L{f.line}" if f.line else "-"
        lines.append(f"  {where:<6} {f.severity:<5} {f.check:<9} {f.message}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    load_dotenv(REPO_ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("docs", nargs="+")
    ap.add_argument("--metadata", default=os.getenv("METADATA_DIR", "metadata"))
    args = ap.parse_args(argv)

    meta = load_metadata((REPO_ROOT / args.metadata).resolve())
    failed = 0
    for d in args.docs:
        findings = validate(Path(d).read_text(encoding="utf-8"), d, meta)
        print(report(d, findings))
        failed += any(f.severity == "ERROR" for f in findings)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
