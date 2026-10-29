"""Extract deterministic metadata from the legacy PL/SQL source files.

Regex-based: there is no database. Known limitations are listed in
docs/extraction-limitations.md.

Usage:
    python -m scripts.extract_metadata [--source legacy_code] [--out metadata]

Writes objects.json, dependencies.json, table_usage.json and risk_flags.json,
each validated through the models in scripts/models/.
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

from scripts.models import (  # noqa: E402
    AccessVia,
    Column,
    Constraint,
    ConstraintKind,
    Dependency,
    DependencyGraph,
    DependencyKind,
    ObjectCatalog,
    ObjectType,
    Operation,
    Package,
    PackageVariable,
    Parameter,
    ParamMode,
    RiskFlag,
    RiskFlags,
    RiskKind,
    Sequence,
    SourceFile,
    SourceRef,
    Subprogram,
    Table,
    TableAccess,
    TableUsage,
    Trigger,
    View,
    Visibility,
)

PARSER_VERSION = "0.1.0"

I = re.IGNORECASE
IS_DOTALL = re.IGNORECASE | re.DOTALL


# ---------------------------------------------------------------------------
# Source text with comments / strings masked (offsets and newlines preserved)
# ---------------------------------------------------------------------------

def mask_source(raw: str) -> tuple[str, str]:
    """Return (code, clean).

    code:  comments replaced by spaces, strings kept.
    clean: comments and string contents replaced by spaces (quotes kept).
    Both have the same length and line breaks as raw, so offsets line up.
    """
    code, clean = list(raw), list(raw)
    i, n = 0, len(raw)

    def blank(lst: list[str], a: int, b: int) -> None:
        for k in range(a, b):
            if lst[k] != "\n":
                lst[k] = " "

    while i < n:
        if raw.startswith("--", i):
            j = raw.find("\n", i)
            j = n if j == -1 else j
            blank(code, i, j)
            blank(clean, i, j)
            i = j
        elif raw.startswith("/*", i):
            j = raw.find("*/", i + 2)
            j = n if j == -1 else j + 2
            blank(code, i, j)
            blank(clean, i, j)
            i = j
        elif raw[i] == "'":
            j = i + 1
            while j < n:
                if raw[j] == "'" and j + 1 < n and raw[j + 1] == "'":
                    j += 2
                elif raw[j] == "'":
                    break
                else:
                    j += 1
            blank(clean, i + 1, j)
            i = j + 1
        else:
            i += 1
    return "".join(code), "".join(clean)


@dataclass
class Source:
    path: str  # relative to repo root, posix
    raw: str
    code: str = ""
    clean: str = ""
    line_starts: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.code, self.clean = mask_source(self.raw)
        self.line_starts = [0] + [m.end() for m in re.finditer(r"\n", self.raw)]

    def line(self, pos: int) -> int:
        return bisect.bisect_right(self.line_starts, pos)

    def line_text(self, line: int) -> str:
        start = self.line_starts[line - 1]
        end = self.raw.find("\n", start)
        return self.raw[start:] if end == -1 else self.raw[start:end]

    def ref(self, a: int, b: int) -> SourceRef:
        return SourceRef(file=self.path, start_line=self.line(a), end_line=self.line(max(a, b - 1)))


# ---------------------------------------------------------------------------
# Small text helpers
# ---------------------------------------------------------------------------

def match_paren(text: str, open_pos: int) -> int:
    """Index of the ')' matching '(' at open_pos (text must have strings masked)."""
    depth = 0
    for k in range(open_pos, len(text)):
        if text[k] == "(":
            depth += 1
        elif text[k] == ")":
            depth -= 1
            if depth == 0:
                return k
    return len(text) - 1


def split_top_level(text: str, start: int, end: int, sep: str = ",") -> list[tuple[int, int]]:
    """Split text[start:end] on sep at paren depth 0. Returns (a, b) spans."""
    spans, depth, a = [], 0, start
    for k in range(start, end):
        ch = text[k]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == sep and depth == 0:
            spans.append((a, k))
            a = k + 1
    spans.append((a, end))
    return [(x, y) for x, y in spans if text[x:y].strip()]


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def skip_ws(text: str, pos: int) -> int:
    while pos < len(text) and text[pos].isspace():
        pos += 1
    return pos


# ---------------------------------------------------------------------------
# Packages
# ---------------------------------------------------------------------------

PKG_HDR_RE = re.compile(
    r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:(?:NON)?EDITIONABLE\s+)?PACKAGE\s+(BODY\s+)?"
    r"(?:\w+\.)?(\w+)\s+(?:IS|AS)\b", I)
SUB_RE = re.compile(r"\b(PROCEDURE|FUNCTION)\s+(\w+)", I)
RETURN_RE = re.compile(r"\s*RETURN\s+([\w.%$#]+(?:\s*\([^)]*\))?)", I)
MODIFIERS_RE = re.compile(r"\s*(?:DETERMINISTIC|PIPELINED|PARALLEL_ENABLE|RESULT_CACHE)\b", I)
PARAM_RE = re.compile(
    r"^\s*(\w+)\s+(?:(IN\s+OUT|IN|OUT)\s+)?(?:NOCOPY\s+)?(.+?)(?:\s+(?:DEFAULT)\s+|\s*:=\s*)(.+)$"
    r"|^\s*(\w+)\s+(?:(IN\s+OUT|IN|OUT)\s+)?(?:NOCOPY\s+)?(.+?)\s*$", IS_DOTALL)
VAR_RE = re.compile(
    r"^(\w+)\s+(CONSTANT\s+)?(.+?)(?:\s*(?::=|\bDEFAULT\b)\s*(.+))?$", IS_DOTALL)
DECL_SKIP = {"PROCEDURE", "FUNCTION", "CURSOR", "TYPE", "SUBTYPE", "PRAGMA", "END", "BEGIN"}


@dataclass
class Header:
    kind: str
    name: str
    start: int          # position of PROCEDURE/FUNCTION keyword
    end: int            # position just after IS/AS or ';'
    is_definition: bool
    params: list[Parameter]
    return_type: str | None


def parse_header(src: Source, m: re.Match) -> Header:
    clean, code = src.clean, src.code
    pos = skip_ws(clean, m.end())
    params: list[Parameter] = []
    if pos < len(clean) and clean[pos] == "(":
        close = match_paren(clean, pos)
        for a, b in split_top_level(clean, pos + 1, close):
            params.append(parse_param(code[a:b]))
        pos = close + 1
    return_type = None
    rm = RETURN_RE.match(clean, pos)
    if rm:
        return_type = norm(rm.group(1)).upper()
        pos = rm.end()
    while mm := MODIFIERS_RE.match(clean, pos):
        pos = mm.end()
    tm = re.compile(r"\s*(IS|AS|;)", I).match(clean, pos)
    is_def = bool(tm and tm.group(1) != ";")
    end = tm.end() if tm else pos
    return Header(m.group(1).upper(), m.group(2).upper(), m.start(), end, is_def, params, return_type)


def parse_param(text: str) -> Parameter:
    m = PARAM_RE.match(norm(text))
    if not m:
        raise ValueError(f"cannot parse parameter: {text!r}")
    if m.group(1):
        name, mode, dtype, default = m.group(1), m.group(2), m.group(3), m.group(4)
    else:
        name, mode, dtype, default = m.group(5), m.group(6), m.group(7), None
    mode = norm(mode or "IN").upper()
    return Parameter(
        name=name.upper(),
        mode=ParamMode.IN_OUT if mode == "IN OUT" else ParamMode(mode),
        datatype=norm(dtype).upper(),
        default=norm(default) if default else None,
    )


def signature(h: Header) -> str:
    args = ", ".join(
        f"{p.name} {p.mode.value} {p.datatype}" + (f" DEFAULT {p.default}" if p.default else "")
        for p in h.params
    )
    sig = f"{h.kind} {h.name}" + (f"({args})" if args else "")
    return sig + (f" RETURN {h.return_type}" if h.return_type else "")


def package_end(src: Source, start: int, name: str) -> int:
    """Position just after the package's final 'END [name];'."""
    m = None
    for m in re.finditer(rf"\bEND\s+(?:{name}\s*)?;", src.clean[start:], I):
        pass
    return start + m.end() if m else len(src.clean)


def statements(text: str, a: int, b: int) -> list[tuple[int, int]]:
    """Split text[a:b] on ';' into stripped (start, end) spans."""
    spans, s = [], a
    for k in range(a, b):
        if text[k] == ";":
            spans.append((s, k))
            s = k + 1
    spans.append((s, b))
    out = []
    for x, y in spans:
        x = skip_ws(text, x)
        if x < y and text[x:y].strip():
            out.append((x, y))
    return out


def parse_variables(src: Source, regions: list[tuple[int, int]], vis: Visibility) -> list[PackageVariable]:
    out = []
    for a, b in regions:
        for x, y in statements(src.clean, a, b):
            stmt_clean = src.clean[x:y].strip()
            first = stmt_clean.split()[0].upper() if stmt_clean.split() else ""
            if first in DECL_SKIP or first == "/":
                continue
            m = VAR_RE.match(norm(src.code[x:y]))
            if not m:
                continue
            out.append(PackageVariable(
                name=m.group(1).upper(),
                datatype=norm(m.group(3)).upper(),
                is_constant=bool(m.group(2)),
                default=norm(m.group(4)) if m.group(4) else None,
                visibility=vis,
                ref=src.ref(x, y + 1),
            ))
    return out


@dataclass
class BodyUnit:
    header: Header
    end: int        # position just after 'END name;'
    body_end: int   # position of 'END name;' (exclusive end of executable text)
    src: Source


def parse_package_spec(src: Source, m: re.Match):
    name = m.group(2).upper()
    end = package_end(src, m.end(), name)
    decls: list[tuple[Header, int]] = []
    regions, cur = [], m.end()
    for sm in SUB_RE.finditer(src.clean, m.end(), end):
        if sm.start() < cur:
            continue
        h = parse_header(src, sm)  # spec declarations end with ';', so h.end is after it
        regions.append((cur, sm.start()))
        decls.append((h, src.ref(h.start, h.end)))
        cur = h.end
    regions.append((cur, end))
    variables = parse_variables(src, regions, Visibility.PUBLIC)
    return name, src.ref(m.start(), end), decls, variables


def parse_package_body(src: Source, m: re.Match):
    name = m.group(2).upper()
    end = package_end(src, m.end(), name)
    units: list[BodyUnit] = []
    regions, cur = [], m.end()
    for sm in SUB_RE.finditer(src.clean, m.end(), end):
        if sm.start() < cur:
            continue  # nested subprogram: part of the enclosing unit
        h = parse_header(src, sm)
        if not h.is_definition:
            continue  # forward declaration
        em = re.compile(rf"\bEND\s+{h.name}\s*;", I).search(src.clean, h.end, end)
        if em:
            u_end, body_end = em.end(), em.start()
        else:  # fallback: up to the next top-level header
            nxt = SUB_RE.search(src.clean, h.end, end)
            u_end = body_end = nxt.start() if nxt else end
        regions.append((cur, sm.start()))
        units.append(BodyUnit(h, u_end, body_end, src))
        cur = u_end
    regions.append((cur, end))
    variables = parse_variables(src, regions, Visibility.PRIVATE)
    return name, src.ref(m.start(), end), units, variables


# ---------------------------------------------------------------------------
# Tables, views, triggers, sequences
# ---------------------------------------------------------------------------

TABLE_RE = re.compile(r"\bCREATE\s+(?:GLOBAL\s+TEMPORARY\s+)?TABLE\s+(?:\w+\.)?(\w+)\s*\(", I)
COL_RE = re.compile(r"^(\w+)\s+(\w+(?:\s*\(\s*\d+(?:\s*,\s*\d+)?\s*(?:BYTE|CHAR)?\s*\))?)(.*)$", IS_DOTALL)
DEFAULT_RE = re.compile(
    r"\bDEFAULT\s+(.+?)(?=\s+(?:NOT\s+NULL|NULL|CONSTRAINT|PRIMARY|UNIQUE|CHECK|REFERENCES)\b|$)", IS_DOTALL)
CONS_RE = re.compile(
    r"^(?:CONSTRAINT\s+(\w+)\s+)?(PRIMARY\s+KEY|UNIQUE|FOREIGN\s+KEY|CHECK)\s*\((.*)$", IS_DOTALL)
COMMENT_RE = re.compile(r"\bCOMMENT\s+ON\s+(COLUMN|TABLE)\s+([\w.]+)\s+IS\s+'((?:[^']|'')*)'", I)
VIEW_RE = re.compile(r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:(?:NO\s+)?FORCE\s+)?VIEW\s+(?:\w+\.)?(\w+)\s+AS\b", I)
TRIGGER_RE = re.compile(
    r"\bCREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\s+(?:\w+\.)?(\w+)\s+(BEFORE|AFTER|INSTEAD\s+OF)\s+"
    r"(.+?)\s+ON\s+(?:\w+\.)?(\w+)(.*?)(?=\bDECLARE\b|\bBEGIN\b|\bWHEN\b)", IS_DOTALL)
SEQ_RE = re.compile(r"\bCREATE\s+SEQUENCE\s+(?:\w+\.)?(\w+)", I)


def parse_cols(text: str) -> list[str]:
    return [c.strip().upper() for c in text.split(",") if c.strip()]


def parse_tables(src: Source) -> list[Table]:
    tables = []
    comments = {}
    for cm in COMMENT_RE.finditer(src.code):
        parts = cm.group(2).upper().split(".")
        key = (parts[-2], parts[-1]) if cm.group(1).upper() == "COLUMN" else (parts[-1], None)
        comments[key] = cm.group(3).replace("''", "'")
    for m in TABLE_RE.finditer(src.clean):
        name = m.group(1).upper()
        open_pos = m.end() - 1
        close = match_paren(src.clean, open_pos)
        semi = src.clean.find(";", close)
        columns, constraints = [], []
        for a, b in split_top_level(src.clean, open_pos + 1, close):
            item_clean = norm(src.clean[a:b])
            item_code = norm(src.code[a:b])
            cm = CONS_RE.match(item_code)
            if cm and (item_clean.upper().startswith("CONSTRAINT") or cm.group(1) is None):
                constraints.append(parse_constraint(item_code))
                continue
            col = COL_RE.match(item_code)
            if not col:
                continue
            rest = col.group(3)
            dm = DEFAULT_RE.search(rest)
            cname = col.group(1).upper()
            columns.append(Column(
                name=cname,
                datatype=norm(col.group(2)).upper(),
                nullable=not re.search(r"\bNOT\s+NULL\b", rest, I),
                default=norm(dm.group(1)) if dm else None,
                comment=comments.get((name, cname)),
            ))
            if re.search(r"\bPRIMARY\s+KEY\b", rest, I):
                constraints.append(Constraint(kind=ConstraintKind.PRIMARY_KEY, columns=[cname]))
            if rm := re.search(r"\bREFERENCES\s+(\w+)\s*(?:\(([^)]*)\))?", rest, I):
                constraints.append(Constraint(kind=ConstraintKind.FOREIGN_KEY, columns=[cname],
                                              ref_table=rm.group(1).upper(),
                                              ref_columns=parse_cols(rm.group(2) or "")))
        tables.append(Table(
            name=name,
            ref=src.ref(m.start(), (semi if semi != -1 else close) + 1),
            columns=columns,
            constraints=constraints,
            comment=comments.get((name, None)),
        ))
    return tables


def parse_constraint(item: str) -> Constraint:
    m = CONS_RE.match(item)
    cname, kind = m.group(1), norm(m.group(2)).upper()
    rest = "(" + m.group(3)
    close = match_paren(rest, 0)
    inner, after = rest[1:close], rest[close + 1:]
    if kind == "CHECK":
        return Constraint(name=cname and cname.upper(), kind=ConstraintKind.CHECK, condition=norm(inner))
    c = Constraint(name=cname and cname.upper(), kind=ConstraintKind(kind), columns=parse_cols(inner))
    if kind == "FOREIGN KEY":
        rm = re.search(r"\bREFERENCES\s+(?:\w+\.)?(\w+)\s*(?:\(([^)]*)\))?", after, I)
        if rm:
            c.ref_table = rm.group(1).upper()
            c.ref_columns = parse_cols(rm.group(2) or "")
    return c


def top_level_from(text: str, start: int) -> int:
    depth = 0
    for fm in re.finditer(r"[()]|\bFROM\b", text[start:], I):
        tok = fm.group(0)
        if tok == "(":
            depth += 1
        elif tok == ")":
            depth -= 1
        elif depth == 0:
            return start + fm.start()
    return len(text)


def parse_views(src: Source) -> list[tuple[View, int, int]]:
    out = []
    for m in VIEW_RE.finditer(src.clean):
        semi = src.clean.find(";", m.end())
        semi = len(src.clean) if semi == -1 else semi
        sel = re.compile(r"\bSELECT\b", I).search(src.clean, m.end(), semi)
        cols = []
        if sel:
            frm = top_level_from(src.clean[:semi], sel.end())
            for a, b in split_top_level(src.clean, sel.end(), frm):
                item = norm(src.clean[a:b])
                if re.fullmatch(r"(?:\w+\.)?\w+", item):
                    cols.append(item.split(".")[-1].upper())
                elif am := re.search(r"[\s)]\s*(?:AS\s+)?(\w+)$", item, I):
                    cols.append(am.group(1).upper())
        out.append((View(name=m.group(1).upper(), ref=src.ref(m.start(), semi + 1), columns=cols),
                    m.end(), semi))
    return out


def parse_triggers(src: Source) -> list[tuple[Trigger, int, int]]:
    out = []
    for m in TRIGGER_RE.finditer(src.clean):
        events = []
        for ev in re.split(r"\bOR\b", m.group(3), flags=I):
            word = ev.strip().split()[0].upper() if ev.strip() else ""
            if word in ("INSERT", "UPDATE", "DELETE"):
                events.append(word)
        end_m = None
        for end_m in re.finditer(r"\bEND\s*\w*\s*;", src.clean[m.end():], I):
            pass
        end = m.end() + end_m.end() if end_m else len(src.clean)
        trg = Trigger(
            name=m.group(1).upper(),
            table=m.group(4).upper(),
            timing=norm(m.group(2)).upper(),
            events=events,
            row_level=bool(re.search(r"\bFOR\s+EACH\s+ROW\b", m.group(5), I)),
            ref=src.ref(m.start(), end),
        )
        out.append((trg, m.end(), end))
    return out


def parse_sequences(src: Source) -> list[Sequence]:
    out = []
    for m in SEQ_RE.finditer(src.clean):
        semi = src.clean.find(";", m.end())
        out.append(Sequence(name=m.group(1).upper(), ref=src.ref(m.start(), (semi if semi != -1 else m.end()) + 1)))
    return out


# ---------------------------------------------------------------------------
# Analysis of unit bodies: dependencies, table usage, risk flags
# ---------------------------------------------------------------------------

@dataclass
class Unit:
    unit_id: str
    unit_type: ObjectType
    package: str | None
    src: Source
    start: int       # start of unit (header)
    body_start: int  # after IS/AS (or trigger header)
    body_end: int    # exclusive


@dataclass
class Context:
    packages: dict[str, dict]       # name -> {"subs": {NAME: [Subprogram]}, "vars": {NAME: PackageVariable}}
    tables: set[str]
    views: set[str]
    sequences: set[str]


TYPE_ANCHOR_RE = re.compile(r"\b\w+(?:\.\w+)?%(?:ROW)?TYPE\b", I)
QUAL_RE = re.compile(r"(?<![\w.:$#])(\w+)\.(\w+)\b")
FROM_RE = re.compile(r"\b(FROM|JOIN)\s+([\w$#.]+(?:\s+\w+)?(?:\s*,\s*[\w$#.]+(?:\s+\w+)?)*)", I)
DML_RES = [
    (Operation.INSERT, re.compile(r"\bINSERT\s+INTO\s+(?:\w+\.)?(\w+)", I)),
    (Operation.UPDATE, re.compile(r"(?<!\bFOR\s)\bUPDATE\s+(?:\w+\.)?(\w+)", I)),
    (Operation.DELETE, re.compile(r"\bDELETE\s+(?:FROM\s+)?(?:\w+\.)?(\w+)", I)),
    (Operation.MERGE, re.compile(r"\bMERGE\s+INTO\s+(?:\w+\.)?(\w+)", I)),
    (Operation.SELECT, re.compile(r"\bUSING\s+(?:\w+\.)?(\w+)", I)),  # MERGE ... USING src
]
EXTERNAL_PREFIX_RE = re.compile(r"^(DBMS_|UTL_|APEX_|OWA_|HTP$|HTF$|SYS$)", I)


def count_args(text: str, pos: int) -> int:
    p = skip_ws(text, pos)
    if p >= len(text) or text[p] != "(":
        return 0
    close = match_paren(text, p)
    return len(split_top_level(text, p + 1, close))


def resolve_overload(subs: list[Subprogram], argc: int) -> tuple[str, bool]:
    if len(subs) == 1:
        return subs[0].unit_id, True
    cands = [s for s in subs
             if sum(1 for p in s.params if p.default is None) <= argc <= len(s.params)]
    if len(cands) == 1:
        return cands[0].unit_id, True
    return f"{subs[0].package}.{subs[0].name}", False


def masked_body(u: Unit) -> str:
    """Unit body (clean) with %TYPE anchors blanked, as a full-length string."""
    text = u.src.clean
    seg = TYPE_ANCHOR_RE.sub(lambda m: " " * len(m.group(0)), text[u.body_start:u.body_end])
    return text[:u.body_start] + seg + text[u.body_end:]


def find_dependencies(u: Unit, ctx: Context) -> list[Dependency]:
    deps = []
    text = u.src.clean
    seg_start, seg_end = u.body_start, u.body_end

    def add(target, ttype, kind, pos, resolved=True):
        deps.append(Dependency(source=u.unit_id, source_type=u.unit_type, target=target,
                               target_type=ttype, kind=kind, file=u.src.path,
                               line=u.src.line(pos), resolved=resolved))

    for m in QUAL_RE.finditer(text, seg_start, seg_end):
        pre, name = m.group(1).upper(), m.group(2).upper()
        if pre in ctx.packages:
            pkg = ctx.packages[pre]
            if name in pkg["subs"]:
                target, ok = resolve_overload(pkg["subs"][name], count_args(text, m.end()))
                kind = ObjectType.FUNCTION if pkg["subs"][name][0].kind == ObjectType.FUNCTION else ObjectType.PROCEDURE
                add(target, kind, DependencyKind.CALL, m.start(), ok)
            elif name in pkg["vars"]:
                add(f"{pre}.{name}", ObjectType.PACKAGE, DependencyKind.VARIABLE_REF, m.start())
        elif pre in ctx.sequences and name in ("NEXTVAL", "CURRVAL"):
            add(pre, ObjectType.SEQUENCE, DependencyKind.SEQUENCE_USE, m.start())
        elif EXTERNAL_PREFIX_RE.match(pre):
            add(f"{pre}.{name}", ObjectType.EXTERNAL, DependencyKind.EXTERNAL_CALL, m.start())

    if u.package:  # unqualified calls to subprograms of the same package
        for name, subs in ctx.packages[u.package]["subs"].items():
            for m in re.finditer(rf"(?<![\w.:$#]){name}\b(?!\s*%)", text[:seg_end], I):
                if m.start() < seg_start:
                    continue
                target, ok = resolve_overload(subs, count_args(text, m.end()))
                kind = ObjectType.FUNCTION if subs[0].kind == ObjectType.FUNCTION else ObjectType.PROCEDURE
                add(target, kind, DependencyKind.CALL, m.start(), ok)
    return deps


def relation_type(name: str, ctx: Context) -> ObjectType | None:
    if name in ctx.tables:
        return ObjectType.TABLE
    if name in ctx.views:
        return ObjectType.VIEW
    return None


def find_relations(text: str, a: int, b: int, ctx: Context) -> list[tuple[str, int]]:
    """Known tables/views in FROM/JOIN clauses of text[a:b] (excluding DELETE FROM)."""
    out = []
    for m in FROM_RE.finditer(text, a, b):
        if m.group(1).upper() == "FROM" and re.search(r"\bDELETE\s+$", text[max(0, m.start() - 10):m.start()], I):
            continue
        list_start = m.start(2)
        for x, y in split_top_level(text, list_start, m.end(2)):
            tok = text[x:y].strip().split()[0].split(".")[-1].upper()
            if relation_type(tok, ctx):
                out.append((tok, x + (len(text[x:y]) - len(text[x:y].lstrip()))))
    return out


def find_table_usage(u: Unit, ctx: Context) -> list[TableAccess]:
    text = masked_body(u)
    accesses = []

    def add(rel, op, pos, via=AccessVia.STATIC):
        rtype = relation_type(rel, ctx)
        if rtype:
            accesses.append(TableAccess(unit_id=u.unit_id, unit_type=u.unit_type, relation=rel,
                                        relation_type=rtype, operation=op, file=u.src.path,
                                        line=u.src.line(pos), via=via))

    for op, rx in DML_RES:
        for m in rx.finditer(text, u.body_start, u.body_end):
            add(m.group(1).upper(), op, m.start())
    for rel, pos in find_relations(text, u.body_start, u.body_end, ctx):
        add(rel, Operation.SELECT, pos)

    if re.search(r"\bEXECUTE\s+IMMEDIATE\b", text[u.body_start:u.body_end], I):
        # table names written literally inside dynamic SQL strings
        for qpos, lit in string_literals(u.src, u.body_start, u.body_end):
            base = qpos + 1
            for op, rx in DML_RES[:4]:
                for m in rx.finditer(lit):
                    add(m.group(1).upper(), op, base + m.start(), AccessVia.DYNAMIC_LITERAL)
            for rel, pos in find_relations(lit, 0, len(lit), ctx):
                add(rel, Operation.SELECT, base + pos, AccessVia.DYNAMIC_LITERAL)
    return accesses


HANDLER_TOKEN_RE = re.compile(r"\b(END\s+IF|END\s+LOOP|END\s+CASE|BEGIN|IF|LOOP|CASE|END|WHEN)\b", I)
LOG_CALL_RE = re.compile(r"\b(?:\w+\.)?(?:\w*log\w*|dbg|put_line)\s*\(", I)


def handler_span(text: str, start: int, limit: int) -> int:
    depth = 0
    for m in HANDLER_TOKEN_RE.finditer(text, start, limit):
        tok = norm(m.group(1)).upper()
        if tok in ("BEGIN", "IF", "LOOP", "CASE"):
            depth += 1
        elif tok in ("END IF", "END LOOP", "END CASE"):
            depth -= 1
        elif tok == "END":
            if depth == 0:
                return m.start()
            depth -= 1
        elif tok == "WHEN" and depth == 0:
            return m.start()
    return limit


# Calls whose literal arguments are messages/formats, not business values.
NON_BUSINESS_CALL_RE = re.compile(
    r"\b(?:RAISE_APPLICATION_ERROR|(?:\w+\.)?(?:\w*log\w*|dbg|set_ctx|put_line)|TO_CHAR|TO_DATE|"
    r"SUBSTR|LPAD|RPAD|INSTR|REPLACE)\s*\(", I)
ROUND_RE = re.compile(r"\b(?:ROUND|TRUNC)\s*\(", I)
DATATYPE_RE = re.compile(r"\b(?:VARCHAR2|NVARCHAR2|CHAR|NUMBER|RAW)\s*\([^)]*\)", I)
NUM_RE = re.compile(r"(?<![\w.$#])(\d+(?:\.\d+)?)(?![\w.])")
LITERAL_RE = re.compile(r"'[^']*'")  # on clean text: quote pairs are exactly literal boundaries


def string_literals(src: Source, a: int, b: int) -> list[tuple[int, str]]:
    """(position of opening quote, literal content) for each string literal in [a, b)."""
    return [(m.start(), src.code[m.start() + 1:m.end() - 1].replace("''", "'"))
            for m in LITERAL_RE.finditer(src.clean, a, b)]


def hardcoded_literals(u: Unit) -> dict[int, list[str]]:
    """Business-looking literals per line. Heuristic, see docs/extraction-limitations.md."""
    code, clean = u.src.code, u.src.clean
    a, b = u.body_start, u.body_end
    excluded = [False] * len(code)

    def exclude(x, y):
        for k in range(x, y):
            excluded[k] = True

    for m in NON_BUSINESS_CALL_RE.finditer(clean, a, b):
        exclude(m.start(), match_paren(clean, m.end() - 1) + 1)
    for m in ROUND_RE.finditer(clean, a, b):
        close = match_paren(clean, m.end() - 1)
        parts = split_top_level(clean, m.end(), close)
        if len(parts) > 1:
            exclude(*parts[-1])
    for m in DATATYPE_RE.finditer(clean, a, b):
        exclude(m.start(), m.end())
    for m in re.finditer(r"/\s*100\b|\bROWNUM\b|:\d+", clean[:b], I):
        if m.start() >= a:
            exclude(m.start(), m.end())

    found: dict[int, list[str]] = {}
    for m in NUM_RE.finditer(clean, a, b):
        if not excluded[m.start()] and m.group(1) not in ("0", "1"):
            found.setdefault(u.src.line(m.start()), []).append(m.group(1))
    for pos, lit in string_literals(u.src, a, b):
        if not excluded[pos] and re.search(r"\w", lit) and len(lit) <= 4:
            found.setdefault(u.src.line(pos), []).append(f"'{lit}'")
    return found


def find_risk_flags(u: Unit, ctx: Context, accesses: list[TableAccess],
                    deps: list[Dependency]) -> list[RiskFlag]:
    src, text = u.src, u.src.clean
    a, b = u.body_start, u.body_end
    flags = []

    def add(kind, pos, detail=None, line=None):
        ln = line or src.line(pos)
        flags.append(RiskFlag(unit_id=u.unit_id, kind=kind, file=src.path, line=ln,
                              snippet=src.line_text(ln).strip(), detail=detail))

    autonomous = re.search(r"\bPRAGMA\s+AUTONOMOUS_TRANSACTION\b", text[a:b], I)
    if autonomous:
        add(RiskKind.AUTONOMOUS_TRANSACTION, a + autonomous.start(),
            "Runs in its own transaction; its COMMIT/ROLLBACK does not affect the caller.")

    for m in re.finditer(r"\bEXECUTE\s+IMMEDIATE\s+([^;]*)", text[:b], I):
        if m.start() < a:
            continue
        arg = m.group(1).strip()
        if "||" in arg.split(" USING ")[0].split(" INTO ")[0]:
            detail = "SQL text concatenated at runtime"
        else:
            var = re.match(r"(\w+)", arg)
            detail = f"SQL text taken from variable {var.group(1).upper()}" if var else "SQL text from expression"
            if var and re.search(rf"\b{var.group(1)}\s*:=[^;]*\|\|", text[a:b], I):
                detail += " (built by concatenation)"
        add(RiskKind.DYNAMIC_SQL, m.start(), detail)
    for m in re.finditer(r"\bDBMS_SQL\.\w+", text[:b], I):
        if m.start() >= a:
            add(RiskKind.DYNAMIC_SQL, m.start(), "DBMS_SQL")

    for m in re.finditer(r"\bCOMMIT\b", text[:b], I):
        if m.start() >= a:
            add(RiskKind.COMMIT, m.start(),
                "inside autonomous transaction" if autonomous else "commits the caller's transaction")
    for m in re.finditer(r"\bROLLBACK\b(\s+TO\b)?", text[:b], I):
        if m.start() < a:
            continue
        if m.group(1):
            add(RiskKind.SAVEPOINT, m.start(), "rollback to savepoint")
        else:
            add(RiskKind.ROLLBACK, m.start(),
                "inside autonomous transaction" if autonomous else "rolls back the caller's whole transaction")
    for m in re.finditer(r"(?<!\bTO\s)\bSAVEPOINT\s+(\w+)", text[:b], I):
        if m.start() >= a:
            add(RiskKind.SAVEPOINT, m.start(), f"savepoint {m.group(1).upper()}")

    for m in re.finditer(r"\bWHEN\s+OTHERS\s+THEN\b", text[:b], I):
        if m.start() < a:
            continue
        h_end = handler_span(text, m.end(), b)
        body = text[m.end():h_end]
        if re.search(r"\bRAISE(?:_APPLICATION_ERROR)?\b", body, I):
            add(RiskKind.WHEN_OTHERS_HANDLED, m.start(), "handler re-raises")
            continue
        parts = []
        if re.fullmatch(r"\s*NULL\s*;\s*", body, I):
            parts.append("handler body is NULL")
        if re.search(r"\bRETURN\b", body, I):
            parts.append("returns a value instead of raising")
        if re.search(r"\bROLLBACK\b", body, I):
            parts.append("rolls back")
        if LOG_CALL_RE.search(body):
            parts.append("logs the error")
        parts.append("error is not propagated")
        add(RiskKind.WHEN_OTHERS_SWALLOW, m.start(), "; ".join(parts))

    for line, lits in sorted(hardcoded_literals(u).items()):
        add(RiskKind.HARDCODED_VALUE, 0, "literals: " + ", ".join(dict.fromkeys(lits)), line=line)

    if u.package:  # own-package variables read or written
        own_vars = ctx.packages[u.package]["vars"]
        seen = set()
        for name, var in own_vars.items():
            if var.is_constant:
                continue
            for m in re.finditer(rf"(?<![\w.]){name}\b(\s*:=)?", text[:b], I):
                if m.start() < a:
                    continue
                mode = "writes" if m.group(1) else "reads"
                if (name, mode) not in seen:
                    seen.add((name, mode))
                    add(RiskKind.PACKAGE_STATE, m.start(), f"{mode} package variable {u.package}.{name}")
    for d in deps:  # other packages' non-constant variables
        if d.kind == DependencyKind.VARIABLE_REF:
            pkg, name = d.target.split(".")
            var = ctx.packages[pkg]["vars"].get(name)
            if var and not var.is_constant and pkg != u.package:
                add(RiskKind.PACKAGE_STATE, 0, f"uses package variable {d.target}", line=d.line)

    if u.unit_type == ObjectType.TRIGGER:
        for acc in accesses:
            if acc.operation != Operation.SELECT:
                add(RiskKind.TRIGGER_DML, 0, f"{acc.operation.value} {acc.relation} as a trigger side effect",
                    line=acc.line)
    return flags


def find_package_cycles(edges: list[Dependency]) -> list[list[str]]:
    graph: dict[str, set[str]] = {}
    for e in edges:
        if e.kind in (DependencyKind.CALL, DependencyKind.VARIABLE_REF) and e.source_type != ObjectType.TRIGGER:
            src_pkg, dst_pkg = e.source.split(".")[0], e.target.split(".")[0]
            if src_pkg != dst_pkg:
                graph.setdefault(src_pkg, set()).add(dst_pkg)
    cycles = set()

    def dfs(start, node, path):
        for nxt in sorted(graph.get(node, ())):
            if nxt == start:
                k = path.index(min(path))
                cycles.add(tuple(path[k:] + path[:k]))
            elif nxt not in path and nxt > start:
                dfs(start, nxt, path + [nxt])

    for s in sorted(graph):
        dfs(s, s, [s])
    return [list(c) for c in sorted(cycles, key=lambda c: (len(c), c))]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def rel_path(p: Path) -> str:
    """Path relative to the repo root when inside it, else absolute (e.g. test fixtures)."""
    try:
        return p.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return p.resolve().as_posix()


def load_sources(root: Path) -> list[Source]:
    out = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in (".sql", ".pks", ".pkb", ".pls", ".plb", ".trg", ".vw"):
            raw = p.read_text(encoding="utf-8").replace("\r\n", "\n")
            out.append(Source(path=rel_path(p), raw=raw))
    return out


def extract(source_root: Path):
    sources = load_sources(source_root)
    files = [SourceFile(path=s.path, sha256=hashlib.sha256(s.raw.encode("utf-8")).hexdigest(),
                        line_count=len(s.line_starts)) for s in sources]

    specs, bodies = {}, {}
    tables, views, triggers, sequences = [], [], [], []
    for s in sources:
        for m in PKG_HDR_RE.finditer(s.clean):
            if m.group(1):
                bodies[m.group(2).upper()] = parse_package_body(s, m)
            else:
                specs[m.group(2).upper()] = parse_package_spec(s, m)
        tables += parse_tables(s)
        views += [(v, s, a, b) for v, a, b in parse_views(s)]
        triggers += [(t, s, a, b) for t, a, b in parse_triggers(s)]
        sequences += parse_sequences(s)

    packages, units = [], []
    for name in sorted(set(specs) | set(bodies)):
        spec = specs.get(name)
        body = bodies.get(name)
        spec_decls = spec[2] if spec else []
        body_units = body[2] if body else []
        counts: dict[str, int] = {}
        for bu in body_units:
            counts[bu.header.name] = counts.get(bu.header.name, 0) + 1
        seen: dict[str, int] = {}
        subs = []
        for bu in body_units:
            h = bu.header
            seen[h.name] = seen.get(h.name, 0) + 1
            overload = seen[h.name] if counts[h.name] > 1 else None
            pnames = [p.name for p in h.params]
            spec_ref = next((ref for sh, ref in spec_decls
                             if sh.name == h.name and [p.name for p in sh.params] == pnames), None)
            sub = Subprogram(
                unit_id=f"{name}.{h.name}" + (f"#{overload}" if overload else ""),
                package=name, name=h.name, kind=ObjectType(h.kind),
                visibility=Visibility.PUBLIC if spec_ref else Visibility.PRIVATE,
                overload=overload, params=h.params, return_type=h.return_type,
                signature=signature(h),
                spec_ref=spec_ref,
                body_ref=bu.src.ref(h.start, bu.end),
            )
            subs.append(sub)
            units.append(Unit(sub.unit_id, sub.kind, name, bu.src, h.start, h.end, bu.body_end))
        variables = (spec[3] if spec else []) + (body[3] if body else [])
        packages.append(Package(name=name, spec_ref=spec[1] if spec else None,
                                body_ref=body[1] if body else None,
                                subprograms=subs, variables=variables))

    for t, s, a, b in triggers:
        units.append(Unit(t.name, ObjectType.TRIGGER, None, s, a, a, b))

    catalog = ObjectCatalog(
        parser_version=PARSER_VERSION,
        source_root=rel_path(source_root),
        files=files, packages=packages, tables=sorted(tables, key=lambda t: t.name),
        views=sorted([v for v, *_ in views], key=lambda v: v.name),
        triggers=sorted([t for t, *_ in triggers], key=lambda t: t.name),
        sequences=sorted(sequences, key=lambda s: s.name),
    )

    ctx = Context(
        packages={p.name: {"subs": group_subs(p.subprograms), "vars": {v.name: v for v in p.variables}}
                  for p in packages},
        tables={t.name for t in catalog.tables},
        views={v.name for v in catalog.views},
        sequences={s.name for s in catalog.sequences},
    )

    edges, accesses, flags = [], [], []
    for u in units:
        d = find_dependencies(u, ctx)
        acc = find_table_usage(u, ctx)
        edges += d
        accesses += acc
        flags += find_risk_flags(u, ctx, acc, d)

    for v, s, a, b in views:
        vu = Unit(v.name, ObjectType.VIEW, None, s, a, a, b)
        for rel, pos in find_relations(s.clean, a, b, ctx):
            edges.append(Dependency(source=v.name, source_type=ObjectType.VIEW, target=rel,
                                    target_type=relation_type(rel, ctx), kind=DependencyKind.VIEW_SOURCE,
                                    file=s.path, line=s.line(pos)))
        accesses += find_table_usage(vu, ctx)
    for t, s, a, b in triggers:
        edges.append(Dependency(source=t.name, source_type=ObjectType.TRIGGER, target=t.table,
                                target_type=relation_type(t.table, ctx) or ObjectType.TABLE,
                                kind=DependencyKind.TRIGGER_ON, file=s.path, line=t.ref.start_line))

    graph = DependencyGraph(parser_version=PARSER_VERSION, edges=dedupe(edges, key=lambda e: (
        e.source, e.target, e.kind, e.line)), package_cycles=find_package_cycles(edges))

    for p in packages:  # NO_CALLER and package-level state/constants
        for sub in p.subprograms:
            if not graph.callers_of(sub.unit_id):
                detail = ("private unit with no caller: unreachable" if sub.visibility == Visibility.PRIVATE
                          else "no caller inside the source tree (may be called externally)")
                src_line = sub.body_ref.start_line
                flags.append(RiskFlag(unit_id=sub.unit_id, kind=RiskKind.NO_CALLER, file=sub.body_ref.file,
                                      line=src_line, snippet=source_line(sources, sub.body_ref.file, src_line),
                                      detail=detail))
        for v in p.variables:
            snippet = source_line(sources, v.ref.file, v.ref.start_line)
            if v.is_constant:
                if v.default and re.search(r"\d|'", v.default):
                    flags.append(RiskFlag(unit_id=p.name, kind=RiskKind.HARDCODED_VALUE, file=v.ref.file,
                                          line=v.ref.start_line, snippet=snippet,
                                          detail=f"package constant {v.name} = {v.default}"))
            else:
                flags.append(RiskFlag(unit_id=p.name, kind=RiskKind.PACKAGE_STATE, file=v.ref.file,
                                      line=v.ref.start_line, snippet=snippet,
                                      detail=f"{v.visibility.value.lower()} package variable {v.name}; "
                                             f"persists for the database session"))

    usage = TableUsage(parser_version=PARSER_VERSION, accesses=sorted(
        dedupe(accesses, key=lambda x: (x.unit_id, x.relation, x.operation, x.line, x.via)),
        key=lambda x: (x.unit_id, x.line, x.relation, x.operation)))
    risks = RiskFlags(parser_version=PARSER_VERSION, flags=sorted(
        dedupe(flags, key=lambda f: (f.unit_id, f.kind, f.line, f.detail)),
        key=lambda f: (f.unit_id, f.line, f.kind)))
    graph.edges.sort(key=lambda e: (e.source, e.line, e.target, e.kind))
    return catalog, graph, usage, risks


def group_subs(subs: list[Subprogram]) -> dict[str, list[Subprogram]]:
    out: dict[str, list[Subprogram]] = {}
    for s in subs:
        out.setdefault(s.name, []).append(s)
    return out


def dedupe(items, key):
    seen, out = set(), []
    for it in items:
        k = key(it)
        if k not in seen:
            seen.add(k)
            out.append(it)
    return out


def source_line(sources: list[Source], path: str, line: int) -> str:
    for s in sources:
        if s.path == path:
            return s.line_text(line).strip()
    return ""


def write_json(model, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = model.model_dump_json(indent=2, exclude_none=False) + "\n"
    type(model).model_validate_json(text)  # round-trip validation
    path.write_text(text, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    load_dotenv(REPO_ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", default=os.getenv("LEGACY_CODE_DIR", "legacy_code"))
    ap.add_argument("--out", default=os.getenv("METADATA_DIR", "metadata"))
    args = ap.parse_args(argv)

    source_root = (REPO_ROOT / args.source).resolve()
    out_dir = (REPO_ROOT / args.out).resolve()
    catalog, graph, usage, risks = extract(source_root)

    write_json(catalog, out_dir / "objects.json")
    write_json(graph, out_dir / "dependencies.json")
    write_json(usage, out_dir / "table_usage.json")
    write_json(risks, out_dir / "risk_flags.json")

    subs = catalog.subprograms()
    print(f"files: {len(catalog.files)}  packages: {len(catalog.packages)}  "
          f"subprograms: {len(subs)} ({sum(s.visibility == Visibility.PUBLIC for s in subs)} public)  "
          f"tables: {len(catalog.tables)}  views: {len(catalog.views)}  "
          f"triggers: {len(catalog.triggers)}  sequences: {len(catalog.sequences)}")
    print(f"dependency edges: {len(graph.edges)}  package cycles: {graph.package_cycles}")
    print(f"table accesses: {len(usage.accesses)}  risk flags: {len(risks.flags)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
