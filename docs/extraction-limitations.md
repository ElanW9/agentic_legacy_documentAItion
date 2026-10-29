# Metadata extraction: how it works and what it misses

`scripts/extract_metadata.py` is a **regex-based parser over the source files**. There is no database access in this PoC. Its output is deterministic: the same source always produces the same JSON. That makes it suitable as ground truth for documentation, but only within the limits below. Treat everything here as "what the parser cannot see", not as proof that something is absent.

## Run

```bash
python -m scripts.extract_metadata   # writes metadata/*.json
python -m scripts.export_schemas     # writes schemas/*.schema.json
```

`LEGACY_CODE_DIR` and `METADATA_DIR` are read from `.env`, and `--source` / `--out` override them.

## How it works

1. **Masking.** Comments are blanked, and string contents are blanked in a second copy. Offsets and line breaks are preserved, so every match maps back to an exact line. Structural regexes run on the masked copy, so keywords inside comments or strings are never matched.
2. **Packages.**
   - Specs give the public declarations and spec variables.
   - Bodies give every top-level `PROCEDURE`/`FUNCTION` up to its matching `END <name>;`. Code outside those units, at package level, gives the body variables.
   - A body unit is `PUBLIC` when the spec declares the same name with the same parameter names.
   - Overloads get `#n` in body order.
3. **Dependencies.**
   - Qualified references `PKG.NAME` are calls when `NAME` is a subprogram, and `VARIABLE_REF` when it is a package variable or constant.
   - Unqualified names that match a subprogram of the same package are calls.
   - An overload is resolved by counting arguments against required and total parameters.
   - `seq.NEXTVAL` is a sequence use. `DBMS_*`/`UTL_*` are external calls.
   - View → relation and trigger → table edges are added.
   - A write to a table adds a `FIRES_TRIGGER` edge to that table's matching triggers.
   - Package cycles are the elementary cycles of the package call graph.
4. **Table usage.**
   - `INSERT INTO`, `UPDATE`, `DELETE [FROM]` and `MERGE INTO` give write operations, and `FROM`/`JOIN` lists and `MERGE ... USING` give reads.
   - Only names that exist as a table or view in `legacy_code/` are kept.
   - `%TYPE` / `%ROWTYPE` anchors are ignored.
5. **Risk flags.**
   - The parser flags `EXECUTE IMMEDIATE`/`DBMS_SQL`, `COMMIT`, `ROLLBACK`, `SAVEPOINT` / `ROLLBACK TO`, and `PRAGMA AUTONOMOUS_TRANSACTION`.
   - A `WHEN OTHERS` handler is classified as swallowing when it contains no `RAISE`.
   - Other flags cover hardcoded literals, package state (reads and writes of non-constant package variables, plus every such variable), writes made by triggers, and units with no caller.

## Known limitations

### Things the parser cannot see
- **Dynamic SQL targets.** When a table or column name is concatenated at runtime (e.g. `'DELETE FROM ' || v_tab`), the access does **not** appear in `table_usage.json`. Only a `DYNAMIC_SQL` risk flag is raised. A table name written literally inside a dynamic SQL string *is* picked up, marked `via: DYNAMIC_LITERAL`. Literal arguments passed by a caller, such as `archive_rows('AUDIT_LOG', ...)`, are not traced through to the dynamic statement.
- **Indirect access through views.** Reading a view is recorded as a read of the view, not of its base tables. Use the `VIEW_SOURCE` edges to expand it.
- **Trigger side effects on callers.** A unit that writes to a table gets a `FIRES_TRIGGER` edge to every trigger on that table with a matching event. For example, `INV_API.REGISTER_PAYMENT` → `TRG_PAY_AIR`. This is conservative: `UPDATE OF <columns>` lists and `WHEN` conditions are not evaluated, so an edge means "may fire". Triggers fired by dynamic SQL, or by another trigger's own writes further down a chain, have to be followed manually through the trigger's `table_usage`.
- **Calls from outside the source tree.** These include schedulers, applications, other schemas and database links. `NO_CALLER` on a public unit means "no caller in `legacy_code/`", not "dead".
- **Runtime facts.** The parser has no visibility into grants, synonyms, invalid objects, actual data values or session settings (NLS, for instance).

### Parsing simplifications
- **Nested subprograms.** Subprograms declared inside another subprogram are treated as part of the enclosing unit, not as units of their own.
- **Overload resolution.** Calls are matched by argument count only. If two overloads accept the same count, the edge targets the base name with `resolved: false`.
- **Name matching.** Matching is by identifier only. A local variable or parameter with the same name as a sibling subprogram would be reported as a call. Synonyms and schema-qualified names (`schema.pkg.proc`) are not resolved.
- **Supported syntax.** The following are not handled: `q'[...]'` quoted strings, the `WITH` clause (CTE) names, `INSERT ALL`, `RETURNING ... BULK COLLECT` subtleties, compound triggers, `INSTEAD OF` triggers on nested tables, conditional compilation (`$IF`), and wrapped (obfuscated) code.
- **`WHEN OTHERS` handler extent.** The handler is found by simple block counting (`BEGIN`/`IF`/`LOOP`/`CASE` … `END`). Unusual layouts can shorten or lengthen it.
- **Hardcoded values.** This is a heuristic.
  - It flags numbers other than 0 and 1, plus string literals of up to 4 characters, inside executable code.
  - It ignores arguments of logging calls, `RAISE_APPLICATION_ERROR`, `TO_CHAR`/`SUBSTR`/`LPAD`/`REPLACE`, the precision argument of `ROUND`/`TRUNC`, datatype lengths and `/ 100`.
  - Longer string literals (messages, parameter names) are not flagged. Expect some noise and some misses.
- **Table DDL.** The parser expects one column or constraint per comma-separated item. `ALTER TABLE ... ADD CONSTRAINT` in separate scripts is not read.

## For real code: use the data dictionary and PL/Scope

With database access, most of this parser should be replaced by Oracle's own metadata, which is compiled and therefore exact:

| Need | Dictionary source |
|------|-------------------|
| Objects, status | `ALL_OBJECTS` |
| Signatures | `ALL_ARGUMENTS`, `ALL_PROCEDURES` (overloads via `OVERLOAD`) |
| Object-level dependencies | `ALL_DEPENDENCIES` |
| Identifiers, calls, line numbers | `ALL_IDENTIFIERS` (PL/Scope, `PLSCOPE_SETTINGS='IDENTIFIERS:ALL'`) |
| SQL statements per unit, tables read/written | `ALL_STATEMENTS` (PL/Scope, `STATEMENTS:ALL`, 12.2+) |
| Columns, constraints, comments | `ALL_TAB_COLUMNS`, `ALL_CONSTRAINTS`, `ALL_CONS_COLUMNS`, `ALL_COL_COMMENTS` |
| Triggers | `ALL_TRIGGERS` |
| Source text | `ALL_SOURCE` |

Even PL/Scope cannot see inside dynamic SQL, so the `DYNAMIC_SQL` flag and human review stay necessary.
