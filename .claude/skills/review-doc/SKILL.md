---
name: review-doc
description: Checklist to verify a draft doc in docs/packages/ or docs/flows/ against metadata/ and the source in legacy_code/. Use after drafting a doc, or when asked to review one.
---

# Review a draft doc

Review the doc as a sceptic: assume every sentence is wrong until a citation proves it. Do not open `evaluation/`. Report findings first; change the doc only after listing them.

## Automated check

- [ ] `python -m scripts.validate_doc <doc>` passes. A pass only covers structure, ids and the presence of citations. The checks below cover whether the claims are true.

## Facts against metadata

- [ ] Header: the spec and body ranges match `objects.json`. The source hash matches `state/doc-status.json`.
- [ ] Public API: one row per PUBLIC subprogram, in spec order, with each signature exactly as in `objects.json`. Overloads are listed separately with `#n`.
- [ ] Every PRIVATE subprogram and every package variable is listed.
- [ ] Calls out and called by match `dependencies.json`, including `FIRES_TRIGGER` and `VARIABLE_REF` edges. Every package cycle with this package is listed.
- [ ] Tables touched matches `table_usage.json`, with no access missing and none added. `DYNAMIC_LITERAL` accesses are marked.
- [ ] Every flag in `risk_flags.json` for the package is addressed in "Side effects and risks" or "Error handling".

## Claims against source

Open the cited lines for a sample of at least five claims, plus every claim about transactions, errors and triggers.
- [ ] The cited lines exist, belong to the cited unit, and say what the claim says.
- [ ] COMMIT, ROLLBACK and SAVEPOINT: the doc says what gets committed or undone for the **caller**, not just that the statement exists.
- [ ] Autonomous transaction: the doc says the write survives a rollback by the caller.
- [ ] WHEN OTHERS: the doc says what the caller receives instead of the error (NULL, 0, nothing, or a re-raise).
- [ ] Dynamic SQL: the doc says which table or column names are built at runtime, and that `table_usage` cannot see them.
- [ ] Triggers fired: the doc names what each trigger writes.
- [ ] Package state: the doc says who writes each variable and that the value persists between calls in a session.
- [ ] Unreachable branches and units with no caller are described as such, with the condition cited. They are not called "dead" without that evidence.

## Invention check

- [ ] No business purpose, meaning of a code value, or reason for a hardcoded number appears without code that states it. Otherwise it reads `Unknown: needs human input`.
- [ ] No object, column, parameter or caller is named that is not in the metadata or the source.
- [ ] Comments are used only as "the comment at [..] says ...", and are checked against the code.
- [ ] Abbreviations are not expanded as facts. `glossary/domain-terms.md` is unconfirmed.

## Open questions

- [ ] Every `Unknown` in the body is repeated as an open question.
- [ ] Every comment that contradicts the code, every metadata gap, and every parser limitation that applies is listed, with a citation.

## Report

List the findings as `doc line -> problem -> evidence [ID:line]`, then give the verdict: ready for human review, or needs another pass.
