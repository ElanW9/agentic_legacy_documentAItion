# Pilot log (step 7)

Raw notes for the retrospective (step 8). Each package was documented by a fresh agent that had only the repo rules (`CLAUDE.md`, the `document-package` and `review-doc` skills, templates, glossary); the orchestrating session wrote the legacy code and the answer key, so it did not draft docs itself. `evaluation/` was not read during the pilot.

## Order

Increasing risk, scored by the count of high-risk flags in `metadata/risk_flags.json` (COMMIT, ROLLBACK, SAVEPOINT, AUTONOMOUS_TRANSACTION, DYNAMIC_SQL, WHEN_OTHERS_SWALLOW):

| Order | Package | Score |
|-------|---------|-------|
| 1 | `CUST_MGMT` | 4 |
| 2 | `INV_API` | 5 |
| 3 | `PKG_ORDER` | 6 |
| 4 | `UTIL_LOG` | 8 |

## Cost and result per package

Tokens and duration are the drafting agent's totals as reported by the harness (input + output, all turns). The validator and state checks were re-run by the orchestrator.

| Package | Tokens | Tool calls | Duration | Validator runs | Final result | Docs | Open questions |
|---------|--------|------------|----------|----------------|--------------|------|----------------|
| `CUST_MGMT` | 141 613 | 37 | 6.9 min | 4 | PASS, 0 warnings | package + 4 unit docs | 19 |
| `INV_API` | 156 705 | 35 | 7.8 min | 4 | PASS, 0 warnings | package + 4 unit docs | 22 |
| `PKG_ORDER` | 145 045 | 26 | 7.1 min | 3 | PASS, 0 warnings | package + 1 unit doc | 15 |
| `UTIL_LOG` | 128 067 | 28 | 6.3 min | 6 | PASS, 0 warnings | package + 2 unit docs | 20 |
| **Total** | **571 430** | **126** | **28.1 min of agent time** (about 15 min elapsed, because three ran in parallel) | | | 4 packages + 11 unit docs | 76 |

The open-question counts are for the package docs only. The unit docs add more, but those mostly repeat the package-level questions.

`PKG_ORDER` and `UTIL_LOG` were run in parallel (on the owner's request, to save time) while `INV_API` was still running. Because three agents were running at once, those two did not write `state/doc-status.json` themselves; the orchestrator added their entries.

## Issues reported by the drafting agents

### `CUST_MGMT`

- Metadata: `FIRES_TRIGGER` over-reports. Every write to `CUSTOMERS` gets an edge to `TRG_CUST_BIU`, but the trigger only writes `CUST_HIST` when `CREDIT_LIMIT` is updated.
- Metadata: there is no flag kind for `RAISE_APPLICATION_ERROR`. A raise that the unit's own `WHEN OTHERS` swallows shows up only as `WHEN_OTHERS_SWALLOW`.
- Metadata: the hardcoded-value heuristic skips some string literals and `SUBSTR` lengths (by design).
- Validator false negative: a sentence or row containing `Unknown: needs human input` skips both the citation check and the line-range check.
- Validator false negative: a very broad citation, such as a whole package body, satisfies the citation check and the risk-flag coverage check.
- Validator gap: it does not check that unit docs are linked from the package doc.
- Template gap: `procedure.md` gives no guidance for the Spec field of a PRIVATE unit.
- The agent found 4 comments that contradict the code. The orchestrator spot-checked 3 of them against the source and all 3 are correct.

### `INV_API`

- Validator errors on the first run were all of one kind: the agent cited the comment line above a unit with the unit's id, but a unit's range starts at its PROCEDURE/FUNCTION line. It fixed them by citing `INV_API(body)` instead.
- The agent's own review found two errors the validator could not catch. A check constraint was cited as line 17 instead of 18; the orchestrator confirmed the line is 18. A VAT fallback condition was also described incompletely.
- Metadata: the literal `'-'` in `NEXT_INV_NO` has no HARDCODED_VALUE flag.
- Convention gap: the unit doc file name for an overload breaks, because `#` in `create_invoice#2.md` is read as a link fragment. The agent named the file `create_invoice_2.md` instead.
- Validator false negative: in a unit doc, any Dependencies row with a line number passes, because the doc's own unit counts as the owner of that line. A row that invented an edge ("no caller | NO_CALLER | 25") passed.
- Skill gap: the criterion for when a unit gets its own doc ("several tables") is vague.
- Template gap: the same as CUST_MGMT, no guidance for the Spec field of a PRIVATE unit.
- Risks the agent inferred from Oracle behaviour rather than from the code: invoice number truncation to 6 digits colliding with a unique key, and `REMINDER_CNT` NUMBER(2) overflowing.

### `PKG_ORDER`

- Validator false positive: the sentence splitter splits at "..." followed by a capital letter (`SELECT ... FOR UPDATE`).
- Validator friction: an open question written as "Question. Unknown: needs human input [cit]" fails, because the first sentence has no citation of its own. The marker and the citation have to be in the same sentence as the question.
- Validator false negative: a table row that contains the Unknown marker skips all checks. (CUST_MGMT reported the same.)
- Template gap: the "Called by" table has no Kind column, but review-doc asks for VARIABLE_REF edges there.
- Validator gap: nothing checks that calls out, callers or package cycles are complete, or that the HARDCODED_VALUE and PACKAGE_STATE flags are covered. The agent checked these by hand.
- Metadata imprecision: the WHEN_OTHERS_SWALLOW detail at line 246 says "rolls back", but the code rolls back to a savepoint.
- Open item the agent left: whether `ROLLBACK TO sp_ord` undoes all the work in `INV_API` depends on deeper call chains not committing. The agent did not trace them.

### `UTIL_LOG`

- Validator false positive: the sentence splitter broke a quoted source comment that contains a full stop, so the second half was reported as uncited.
- Validator false positive (arguable): `LOG_TABLE` gave a WARN for "only in a source comment" although the line quoted the comment. The agent removed the backticks, so the name is no longer checked at all.
- Validator false negative: a sentence that contains "Unknown: needs human input" is exempt from the citation check even when it also states a fact.
- Validator false negative: a "Called by" row passes with a wrong line, as long as the line falls inside any unit named in the row.
- Metadata gap (known limitation): the dynamic SQL in `ARCHIVE_ROWS` hides the `AUDIT_LOG` read and delete and the `AUDIT_LOG_ARCH` insert from `table_usage`. The doc says so and lists it as an open question.
- Template gap: the procedure doc's "Tables touched" table has no place for tables that are only known at runtime.
- Claims the agent inferred from Oracle behaviour rather than from the code:
  - `TO_NUMBER` raising `VALUE_ERROR`.
  - NLS date-language dependence in `IS_WORKDAY`.
  - `#` overflow in `FMT_AMT`.
  - `SQLERRM` outside a handler.
  - A possible endless loop in `ADD_WORKDAYS` on NULL.
- Package-cycle direction: the agent read the order of the names in `dependencies.json` as the direction of the calls. The metadata does not say this.
- The state entry was written by the orchestrator. The docs were re-validated before writing it, and the hash matches the doc header.
