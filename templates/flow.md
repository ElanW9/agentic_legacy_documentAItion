<!--
TEMPLATE: one cross-package flow, for example order -> invoice -> payment. Copy to docs/flows/<flow-name>.md.
- A flow follows the call graph and trigger edges in metadata/dependencies.json. Do not add steps that have no edge.
- Keep every "##" heading below, with the same text and in the same order. The validator checks them.
- Every claim ends with a citation [UNIT_ID:start-end]. See glossary/conventions.md.
- The business process name and its trigger in the real world are usually not in the code: write exactly
  "Unknown: needs human input" for what you cannot cite.
- Delete these HTML comments and every {{placeholder}} before validation. Write "None found in metadata." for an empty section.
-->

# Flow: {{flow name}}

## Purpose

{{1-3 sentences on what the flow does in the code}} [{{UNIT_ID}}:{{start}}-{{end}}]

## Entry points

<!-- Units where the flow starts. Units with NO_CALLER may be called from outside legacy_code/ (scheduler, application). -->

| Unit | Called from |
|------|-------------|
| `{{PACKAGE.UNIT}}` | {{`CALLER` [CALLER:line], or "no caller in legacy_code/" [PACKAGE.UNIT:start]}} |

## Steps

<!-- Numbered, in execution order. Indent sub-steps for nested calls. Include trigger executions as their own step
     ("TRG_X fires on the INSERT at line N"). Show branches as "if <condition>" with a citation to the condition. -->

1. `{{PACKAGE.UNIT}}` {{does what}} [{{PACKAGE.UNIT}}:{{start}}-{{end}}]
   1. calls `{{PACKAGE.UNIT}}` {{does what}} [{{PACKAGE.UNIT}}:{{line}}]

## Tables touched

| Step | Table / view | Operation | Unit | Line |
|------|--------------|-----------|------|------|
| {{n}} | `{{TABLE}}` | {{operation}} | `{{PACKAGE.UNIT}}` | {{line}} |

## Transactions

<!-- Where the flow commits or rolls back, which unit owns that decision, savepoints, autonomous transactions.
     State what is committed at each point and what is lost on an error after it. -->

| Unit | Line | Statement | What it ends |
|------|------|-----------|--------------|
| `{{PACKAGE.UNIT}}` | {{line}} | {{COMMIT/ROLLBACK/ROLLBACK TO/AUTONOMOUS}} | {{effect}} |

## Error paths

<!-- What happens when a step fails: which handler catches it, whether the flow stops or continues, which data stays half-written. -->

## Open questions

1. {{question}} [{{UNIT_ID}}:{{line}}]
