# Repo plan: inspection findings and proposal (step 1)

Source inspected: `legacy_code/` only. `evaluation/` was not used. Counts come from grep and reading, not from a parser. Step 3 replaces them with extracted numbers.

## 1. Inspection findings

### File layout

```
legacy_code/
  install_order.sql      SQL*Plus script, @@-includes every object in creation order, ends with COMPILE_SCHEMA
  packages/              4 x (.pks spec + .pkb body)
  tables/                10 files, one CREATE TABLE each (app_params.sql also contains seed INSERTs + COMMIT)
  sequences/             5 files
  views/                 3 files
  triggers/              3 files
```

30 source files, about 1 300 lines.

### Object counts

| Type | Count | Names |
|------|-------|-------|
| Packages | 4 | `CUST_MGMT`, `PKG_ORDER`, `INV_API`, `UTIL_LOG` |
| Subprograms (bodies) | 43 (23 procedures, 20 functions) | 36 public, 7 private (body only) |
| Overloaded names | 3 | `PKG_ORDER.ADD_LINE` (3 vs. 4 params), `INV_API.CREATE_INVOICE` (1 vs. 2), `CUST_MGMT.GET_BALANCE` (1 vs. 2) |
| Tables | 10 | `CUSTOMERS`, `CUST_HIST`, `PRODUCTS`, `ORDERS`, `ORDER_LINES`, `INVOICES`, `PAYMENTS`, `AUDIT_LOG`, `AUDIT_LOG_ARCH`, `APP_PARAMS` |
| Views | 3 | `V_OPEN_INVOICES`, `CUST_BALANCE_V` (built on `V_OPEN_INVOICES`), `ORD_SUMMARY_V` |
| Triggers | 3 | `TRG_CUST_BIU` (customers), `TRG_ORDL_AIUD` (order_lines), `TRG_PAY_AIR` (payments). All are row-level. |
| Sequences | 5 | `SEQ_CUSTOMERS`, `ORD_SEQ`, `INV_SEQ`, `PAY_ID_SEQ`, `AUDIT_LOG_SEQ` |

| Package | Spec P/F | Body P/F | Private units | Body lines |
|---------|----------|----------|---------------|------------|
| `CUST_MGMT` | 5 / 5 | 6 / 5 | 1 | 245 |
| `PKG_ORDER` | 5 / 2 | 6 / 3 | 2 | 280 |
| `INV_API` | 4 / 4 | 5 / 6 | 3 | 249 |
| `UTIL_LOG` | 6 / 5 | 6 / 6 | 1 | 169 |

### Naming conventions observed (inconsistent across packages)

- **Package names:** there is no single scheme. Names use an `_MGMT` suffix, a `PKG_` prefix, an `_API` suffix, or `UTIL_`.
- **Keyword case:** `CUST_MGMT` is all uppercase with 3-space indentation and Toad-style headers. `PKG_ORDER` is all lowercase with 2-space indentation. `INV_API` and `UTIL_LOG` use uppercase keywords with lowercase identifiers.
- **Parameters:** always `p_`.
- **Locals:** `V_` in `CUST_MGMT`, `l_` in `PKG_ORDER`, and `v_` in `INV_API` and `UTIL_LOG`.
- **Globals:** `g_`. Constants use `c_` in `UTIL_LOG` and `INV_API`, `st_` (status constants) in `PKG_ORDER`, and `V_` in `CUST_MGMT` (`V_MAX_LIMIT`).
- **Sequences:** three patterns: `SEQ_<table>`, `<abbr>_SEQ` and `<table>_SEQ`.
- **Views:** both `V_` prefix and `_V` suffix.
- **Triggers:** `TRG_<abbr>_<timing><events>`, e.g. `BIU` = before insert/update, `AIR` = after insert row, `AIUD` = after insert/update/delete.
- **Abbreviations:** cust, ord, ordl, inv, pay, amt, dt, cd, no, disc, pct, st, chk, upd, ctry, arch, hist, ref, sev, usr, obj, yn, ovd.
- **Status codes:** `CUSTOMERS.STATUS` uses A/B/C, `CUST_TYPE` uses R/W/G, `ORDERS.ORD_STATUS` is numeric, `INVOICES.INV_STATUS` uses OPEN/PART/PAID/CANC, and `PAY_METHOD` uses BT/CC/CA.

### Unusual things noticed (to be confirmed by extraction, not yet documented)

- **Dependencies:** packages call each other in cycles (`CUST_MGMT`↔`INV_API`, `PKG_ORDER`↔`INV_API`). The utility package `UTIL_LOG` calls a business package (`INV_API`).
- **Dynamic SQL:** `EXECUTE IMMEDIATE` appears in `CUST_MGMT` (1) and `UTIL_LOG` (2), with table or column names concatenated from parameters.
- **Autonomous transaction:** one `PRAGMA AUTONOMOUS_TRANSACTION` in `UTIL_LOG`.
- **Transaction control:** `COMMIT`/`ROLLBACK` statements appear in all four package bodies, including `ROLLBACK TO SAVEPOINT`.
- **Exception handling:** there are 5 `WHEN OTHERS` handlers, and some of them return NULL/0 or do nothing.
- **Triggers:** all three triggers write to other tables (`CUST_HIST`, `ORDERS`, `INVOICES`).
- **Package state:** public mutable globals in a package spec (`UTIL_LOG`, `PKG_ORDER`) plus private body globals.
- **Long unit:** `PKG_ORDER.PROCESS_ORDER` is about 135 lines and deeply nested.
- **Unclear private units:** some private units have no caller found by grep. This needs confirmation by the dependency extraction.
- **Hardcoded values:** many literal amounts and percentages, status numbers, and country codes.
- **Comments:** some comments mention objects that do not exist in `legacy_code/` (e.g. `LOG_TABLE`, `INVOICE_HDR`, `ORD_PROC`). Comments must not be trusted as facts.
- **Parameter table:** `APP_PARAMS` is seeded in its DDL file. It is unclear whether every seeded parameter is actually read.

## 2. Proposed repo structure

```
.
├── CLAUDE.md                   agent rules (step 5)
├── README.md                   workflow, setup, .env, branch convention
├── .gitignore / .env.example   (.env is local and untracked)
├── requirements.txt            pinned: pydantic, python-dotenv, pytest
├── legacy_code/                read-only after step 0
├── evaluation/                 answer key, step 8 only
├── metadata/                   generated JSON (objects, dependencies, table_usage, risk_flags)
├── schemas/                    JSON Schema exported from the Pydantic models
├── scripts/
│   ├── models/                 all Pydantic models (single package)
│   ├── extract_metadata.py     regex parser -> metadata/*.json
│   ├── export_schemas.py       models -> schemas/*.json
│   └── validate_doc.py         doc vs. metadata checks (step 6)
├── tests/                      pytest (fixtures: tiny PL/SQL snippets + sample docs)
├── templates/                  package.md, procedure.md, flow.md
├── glossary/                   domain-terms.md, conventions.md
├── docs/
│   ├── repo-plan.md            this file
│   ├── packages/               one .md per package (pilot output)
│   └── flows/                  cross-package flows (e.g. order -> invoice -> payment)
├── state/doc-status.json       per-package doc status + source hash
└── .claude/skills/             document-package/, review-doc/
```

`tests/` is the only addition to the list in the brief.

## 3. Proposed Pydantic models (`scripts/models/`)

All models use `model_config = ConfigDict(extra="forbid")`. Names are stored in UPPERCASE. Lines are 1-based and inclusive.

**Unit id convention.** Citations and cross-file links use the unit id:

- `PACKAGE.SUBPROGRAM` for a subprogram, with a `#n` suffix for overloads, numbered in body order. Example: `PKG_ORDER.ADD_LINE#2`.
- The bare name for tables, views, triggers and sequences.

### `common.py`
- `SourceRef(file: str, start_line: int, end_line: int)`. Validated so that `start_line <= end_line`.
- Enums:
  - `ObjectType`: PACKAGE, PROCEDURE, FUNCTION, TABLE, VIEW, TRIGGER, SEQUENCE
  - `Visibility`: PUBLIC, PRIVATE
  - `ParamMode`: IN, OUT, IN_OUT

### `objects.py` → `metadata/objects.json`
- `Parameter(name, mode, datatype, default: str | None)`
- `Subprogram(unit_id, package, name, kind: PROCEDURE|FUNCTION, visibility, overload: int | None, params: list[Parameter], return_type: str | None, spec_ref: SourceRef | None, body_ref: SourceRef, signature: str)`
- `PackageVariable(name, datatype, is_constant: bool, default: str | None, visibility, ref: SourceRef)`
- `Package(name, spec_ref, body_ref, subprograms, variables)`
- `Column(name, datatype, nullable: bool, default: str | None, comment: str | None)`
- `Constraint(name, kind: PK|FK|UK|CHECK, columns, ref_table: str | None, condition: str | None)`
- `Table(name, ref, columns, constraints, comment: str | None)`
- `View(name, ref, columns: list[str])`
- `Trigger(name, table, timing: BEFORE|AFTER|INSTEAD_OF, events: list[INSERT|UPDATE|DELETE], row_level: bool, ref)`
- `Sequence(name, ref)`
- `ObjectCatalog(source_root, generated_at, parser_version, packages, tables, views, triggers, sequences)`

### `dependencies.py` → `metadata/dependencies.json`
- `Dependency(source: str, target: str, target_type: ObjectType, kind: CALL|READS_VIEW|USES_SEQUENCE|VARIABLE_REF|TRIGGER_ON|VIEW_SOURCE, line: int, file: str)`
- `DependencyGraph(edges: list[Dependency], cycles: list[list[str]], unresolved: list[str])`, plus the derived `callers_of(unit)` helper.

### `table_usage.py` → `metadata/table_usage.json`
- `TableAccess(unit_id, table, operation: SELECT|INSERT|UPDATE|DELETE|MERGE, line, file, via: STATIC|DYNAMIC_LITERAL)`
- `TableUsage(accesses: list[TableAccess])`

Dynamic SQL whose table name can't be resolved is not guessed. It goes into `risk_flags` instead.

### `risk_flags.py` → `metadata/risk_flags.json`
- `RiskKind` enum:
  - DYNAMIC_SQL
  - COMMIT
  - ROLLBACK
  - SAVEPOINT
  - AUTONOMOUS_TRANSACTION
  - WHEN_OTHERS_SWALLOW
  - WHEN_OTHERS_HANDLED
  - HARDCODED_VALUE
  - PACKAGE_STATE
  - TRIGGER_DML
  - NO_CALLER
- `RiskFlag(unit_id, kind, line, file, snippet: str, detail: str | None)`
- `RiskFlags(flags: list[RiskFlag])`

The last three kinds are cheap extras over the brief, kept because they target known blind spots.

### `doc_status.py` → `state/doc-status.json`
- `DocStatus` enum: TODO, DRAFT, REVIEWED, APPROVED, STALE
- `DocStatusEntry(package, doc_path, source_files: list[str], source_hash: str (sha256 of spec+body), status, updated_at: datetime, validation_passed: bool | None)`
- `DocStatusFile(entries: dict[str, DocStatusEntry])`

### `doc_summary.py` (structured summary of a documented unit; future LLM structured output)
- `Citation(unit_id, file, start_line, end_line)`
- `Claim(text, citations: list[Citation])`, with at least one citation required.
- `UnitSummary(unit_id, purpose: str, side_effects: list[Claim], tables_touched: list[str], risks: list[Claim], open_questions: list[str])`
- `PackageSummary(package, purpose: Claim | "Unknown: needs human input", units: list[UnitSummary], open_questions: list[str])`

## 4. Decisions to confirm

1. **`tests/` folder:** add it at the repo root, which is not in the brief's list. I recommend yes.
2. **Overload ids:** use `#n` in body order as the overload id. The alternative is a parameter-count suffix, which is ambiguous when two overloads have the same number of parameters.
3. **Extra risk kinds:** add `SAVEPOINT`, `PACKAGE_STATE`, `TRIGGER_DML` and `NO_CALLER` in addition to the kinds in the brief.
