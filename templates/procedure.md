<!--
TEMPLATE: one procedure or function. Use it only for units that are too long or too complex for a subsection of the
package doc (for example many branches, a COMMIT, or several tables). Copy to docs/packages/<package>/<unit>.md and
link it from the package doc.
- Keep every "##" heading below, with the same text and in the same order. The validator checks them.
- Facts come from metadata/*.json. Every claim ends with a citation [UNIT_ID:start-end]. See glossary/conventions.md.
- When business intent is not visible in the code, write exactly: Unknown: needs human input
- Delete these HTML comments and every {{placeholder}} before validation. Write "None found in metadata." for an empty section.
-->

# `{{PACKAGE.UNIT}}`

| Field | Value |
|-------|-------|
| Package doc | [{{package}}](../{{package}}.md) |
| Kind | {{PROCEDURE/FUNCTION}} |
| Visibility | {{PUBLIC/PRIVATE}} |
| Spec | `{{file}}` line {{line}} |
| Body | `{{file}}` lines {{start}}-{{end}} |

```sql
{{signature copied from objects.json}}
```

## Purpose

{{1-3 sentences}} [{{PACKAGE.UNIT}}:{{start}}-{{end}}]

## Parameters

| Name | Mode | Type | Default | Used for |
|------|------|------|---------|----------|
| `{{P_NAME}}` | {{IN/OUT/IN_OUT}} | {{datatype}} | {{default or -}} | {{effect in the code}} [{{PACKAGE.UNIT}}:{{line}}] |

<!-- Functions: add one line for the return value and every distinct value or expression it can return. -->

## Logic walkthrough

<!-- Numbered steps in code order. One step per branch or statement group, each with its own line range.
     Describe what the code does, not what it is probably meant to do. -->

1. {{step}} [{{PACKAGE.UNIT}}:{{start}}-{{end}}]

## Dependencies

| Direction | Unit / object | Kind | Line |
|-----------|---------------|------|------|
| calls | `{{TARGET}}` | {{CALL/USES_SEQUENCE/VARIABLE_REF}} | {{line}} |
| called by | `{{CALLER}}` | CALL | {{line}} |

## Tables touched

| Table / view | Operation | Line | Via |
|--------------|-----------|------|-----|
| `{{TABLE}}` | {{operation}} | {{line}} | {{STATIC/DYNAMIC_LITERAL}} |

<!-- Add the triggers fired by these statements (FIRES_TRIGGER) and what they write. -->

## Side effects and risks

<!-- Every risk flag for this unit: transaction control, package state read/written, dynamic SQL, hardcoded values,
     triggers fired. State the consequence for the caller. -->

## Error handling

| Line | Handler / raise | Effect for the caller |
|------|-----------------|-----------------------|
| {{line}} | {{handler}} | {{effect}} |

## Open questions

1. {{question}} [{{PACKAGE.UNIT}}:{{line}}]
