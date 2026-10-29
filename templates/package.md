<!--
TEMPLATE: one package. Copy to docs/packages/<package_lowercase>.md.
- Keep every "##" heading below, with the same text and in the same order. The validator checks them.
- Facts (names, signatures, lines, tables, calls, flags) are copied from metadata/*.json. Prose explains them; it never adds facts.
- Every claim ends with at least one citation: [UNIT_ID:start-end] or [UNIT_ID:line]. See glossary/conventions.md.
- When business intent is not visible in the code, write exactly: Unknown: needs human input
- Comments in the legacy code are not facts. Quote them only as "the comment at [..] says ..." and check them against the code.
- Delete these HTML comments and every {{placeholder}} before validation. If a section has nothing to report, write "None found in metadata." and do not delete the heading.
-->

# Package `{{PACKAGE}}`

| Field | Value |
|-------|-------|
| Spec | `{{legacy_code/packages/x.pks}}` lines {{start}}-{{end}} |
| Body | `{{legacy_code/packages/x.pkb}}` lines {{start}}-{{end}} |
| Source hash | `{{sha256 of spec + body, same value as state/doc-status.json}}` |
| Status | draft |

## Purpose

<!-- 2-4 sentences: what the package does, judged from what its units do. Cite the units the summary is based on.
     The business reason why the package exists is usually not in the code: write "Unknown: needs human input" for that part. -->

{{purpose}} [{{UNIT_ID}}:{{start}}-{{end}}]

## Public API

<!-- One row per PUBLIC subprogram in objects.json, in spec order. Signature copied verbatim. Overloads use #n. -->

| Unit | Kind | Signature | Spec | Body |
|------|------|-----------|------|------|
| `{{PACKAGE.UNIT}}` | {{PROCEDURE/FUNCTION}} | `{{signature}}` | {{line}} | {{start}}-{{end}} |

### `{{PACKAGE.UNIT}}`

<!-- One subsection per public unit. What it does, step by step only where needed. Parameters that change the behaviour.
     Long or complex units (see templates/procedure.md) get a separate doc; link to it here. -->

{{what the unit does}} [{{PACKAGE.UNIT}}:{{start}}-{{end}}]

### Private units

<!-- PRIVATE subprograms (body only). Name, signature, one line on what it does, who calls it. -->

| Unit | Signature | Body | Called by |
|------|-----------|------|-----------|
| `{{PACKAGE.UNIT}}` | `{{signature}}` | {{start}}-{{end}} | {{callers or "no caller in legacy_code/"}} |

## Dependencies

<!-- From dependencies.json. Group by target. Include the line of each call. -->

### Calls out

| From unit | To | Kind | Line |
|-----------|----|------|------|
| `{{PACKAGE.UNIT}}` | `{{TARGET}}` | {{CALL/EXTERNAL_CALL/SEQUENCE_USE/VARIABLE_REF/...}} | {{line}} |

### Called by

| Caller | Unit called | Line |
|--------|-------------|------|
| `{{CALLER}}` | `{{PACKAGE.UNIT}}` | {{line}} |

### Package cycles

<!-- Every cycle from dependencies.json that contains this package. "None found in metadata." otherwise. -->

## Tables touched

<!-- From table_usage.json. Mark via=DYNAMIC_LITERAL accesses. Access through dynamic SQL with a runtime table name is NOT
     in table_usage: list it under "Side effects and risks" instead. -->

| Table / view | Operation | Unit | Line | Via |
|--------------|-----------|------|------|-----|
| `{{TABLE}}` | {{SELECT/INSERT/UPDATE/DELETE/MERGE}} | `{{PACKAGE.UNIT}}` | {{line}} | {{STATIC/DYNAMIC_LITERAL}} |

### Triggers fired

<!-- FIRES_TRIGGER edges: the trigger runs as part of this unit's statement ("may fire": UPDATE OF columns and WHEN are not evaluated).
     Say what the trigger itself writes, cited to the trigger. -->

| Unit | Statement line | Trigger | What the trigger writes |
|------|----------------|---------|-------------------------|
| `{{PACKAGE.UNIT}}` | {{line}} | `{{TRIGGER}}` | {{tables}} [{{TRIGGER}}:{{start}}-{{end}}] |

## Side effects and risks

<!-- Address every flag in risk_flags.json for this package. Group per kind. Explain the consequence for a caller,
     e.g. "a COMMIT here also commits the caller's open work". -->

### Transaction control

<!-- COMMIT, ROLLBACK, SAVEPOINT, AUTONOMOUS_TRANSACTION. -->

### Package state

<!-- Package variables (spec = visible to every session caller, body = private), who reads and writes them, and when the
     value survives between calls in the same session. -->

| Variable | Visibility | Constant | Written by | Read by |
|----------|------------|----------|------------|---------|
| `{{PACKAGE.NAME}}` | {{PUBLIC/PRIVATE}} | {{yes/no}} | `{{PACKAGE.UNIT}}` [{{PACKAGE.UNIT}}:{{line}}] | `{{PACKAGE.UNIT}}` [{{PACKAGE.UNIT}}:{{line}}] |

### Dynamic SQL

### Hardcoded values

<!-- Literal values that encode business rules (amounts, rates, codes, country lists). Value, unit, line. Their meaning: Unknown unless the code states it. -->

### Other

<!-- NO_CALLER, TRIGGER_DML, anything else observed. -->

## Error handling

<!-- For each unit that raises or handles errors: RAISE_APPLICATION_ERROR codes and messages, WHEN OTHERS handlers
     (swallow = no RAISE: what the caller receives instead), NO_DATA_FOUND / TOO_MANY_ROWS handling. -->

| Unit | Line | Handler / raise | Effect for the caller |
|------|------|-----------------|-----------------------|
| `{{PACKAGE.UNIT}}` | {{line}} | {{WHEN OTHERS / RAISE_APPLICATION_ERROR(-20xxx)}} | {{re-raised / returns NULL / ignored}} |

## Open questions

<!-- Numbered. Each question cites the code it is about. Includes every "Unknown: needs human input" above,
     contradictions between comments and code, and anything the parser cannot see (see docs/extraction-limitations.md). -->

1. {{question}} [{{UNIT_ID}}:{{line}}]
