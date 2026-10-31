# Pilot report (step 8)

A comparison of the pilot docs (step 7) against `evaluation/answer_key.md`. It covers what the agent got right and wrong, what would have prevented each error, how the validator performed, what the pilot cost, and what to build next.

## How the pilot was scored

- **Drafting.** Each package was documented by a fresh agent that had only the repo rules (`CLAUDE.md`, the `document-package` and `review-doc` skills, the templates and the glossary). The session that wrote the legacy code and the answer key did not draft any doc. Nobody read `evaluation/` during the pilot. Raw notes are in [pilot-log.md](pilot-log.md).
- **Grading.** Four grading agents, one per package, scored the docs against the answer key, using the answer-key items that belong to that package. A trap that spans two packages, such as T4b, is scored in each package it touches. Verdicts:
  - **Caught:** the doc states everything the answer key's "must mention" column requires, with a correct citation.
  - **Partial:** the doc states only part of it.
  - **Missed:** the doc does not state it.
  - **Wrong:** the doc states something false about it.
- **Beyond the answer key.** Each grader also checked 22–40 other claims against the source, about 110 in total.
- **Spot check of the graders.** The orchestrator checked 7 of the graders' findings against the source, and all 7 hold. One grader found an error in the answer key itself: the `PAYMENTS.PAY_METHOD` comment is on line 13 of `payments.sql`, not line 12, and the doc had it right.
- **Caveat:** the answer key, the drafting agents and the graders all come from the same model family. A human review of a sample is still needed before these numbers are trusted.

## 1. Results

### Answer-key items

| Package | Items | Caught | Partial | Missed | Wrong |
|---------|-------|--------|---------|--------|-------|
| `CUST_MGMT` | 25 | 21 | 3 | 1 | 0 |
| `INV_API` | 23 | 19 | 4 | 0 | 0 |
| `PKG_ORDER` | 29 | 24 | 5 | 0 | 0 |
| `UTIL_LOG` | 15 | 12 | 3 | 0 | 0 |
| **Total** | **92** | **76 (83%)** | **15 (16%)** | **1 (1%)** | **0** |

None of the required traps was missed or described wrongly. Three were only ever partial (T7a, T8b, T8c). In each of those the trap itself is documented and a consequence elsewhere is missing.

| Trap | Verdict | Remark |
|------|---------|--------|
| T1 / T1b dynamic SQL | caught | Runtime table and column names, the static callers, the `_ARCH` assumption, and unchecked input (described as "any text becomes part of the SQL"; the words "SQL injection" are not used). |
| T2 autonomous transaction | caught | |
| T3a–d COMMIT/ROLLBACK in business code | caught | Every doc says the caller's work is committed or rolled back too. |
| T4a–d WHEN OTHERS | caught | Including the -20011 error that its own handler swallows in `UPD_CREDIT_LIMIT`. |
| T5a–c dead code | caught | Both private units, the unreachable `> 50` branch, and the misleading comments. |
| T6a public globals | partial | The `UTIL_LOG` doc says other packages "use" `G_USER`, but not that they write it into `created_by` columns. The `PKG_ORDER` doc does say this. |
| T6b cached globals | partial | "Only new sessions see the change" is stated, but the consequence for pooled connections is not. |
| T6c unused globals | caught | No purpose was invented. |
| T7a `TRG_PAY_AIR` | partial | The comment contradicting the trigger and the 0.05 tolerance are covered. Not stated: the trigger is the only writer of paid amount, invoice status and order status 50, and `ORD_SUMMARY_V` shows status 50 as `UNKNOWN`. |
| T7b `TRG_CUST_BIU` | caught | Including that blocking zeroes the credit limit without writing a history row. |
| T7c `TOTAL_AMT` gross vs net | caught | |
| T8a–c overloads | 1 caught, 2 partial | T8a: both `ADD_LINE` overloads and their differences are documented. T8b: the future-dated invoice for export orders is not stated. T8c: the difference from `GET_OPEN_AMT` is not stated. |
| T9 long procedure | caught | 19-step walkthrough with every outcome. |

The 15 partials and 1 miss:

| Package | What is missing |
|---------|-----------------|
| `CUST_MGMT` | `GET_BALANCE` differs from `INV_API.GET_OPEN_AMT` (T8c). The explicit INSERT bypasses the column default of 5000. Held orders stay on HOLD after unblocking. **Missed:** `CUST_HIST` has no primary key. |
| `INV_API` | T7a "only writer" and `UNKNOWN` (above). T8b future invoice date. Reminder counter overflow (ORA-01438) aborts the run before its COMMIT. `CUST_BALANCE_V` is built on `V_OPEN_INVOICES`. |
| `PKG_ORDER` | No log entry on the `MIN AMOUNT` path, and `APP_PARAMS.MIN_ORDER_AMT = 50` is ignored. The government-customer override is reachable only for status `C`. `NEW_ORDER` lets blocked customers create orders. Status 50 is missing from the status list. A paid order (50) cannot be cancelled. |
| `UTIL_LOG` | T6a `created_by`. T6b pooled connections. The commit chain `HOUSEKEEPING` → `SEND_REMINDERS` → `CHK_OVERDUE_CUSTOMERS` → `BLOCK_CUSTOMER` (COMMIT) is not followed past the first call. |

**Pattern: 12 of the 16 gaps are consequences that sit in another unit, another package, a trigger, a view or a table definition, not in the unit being documented.** The other 4 are consequences inside the package that were not spelled out: no log entry on one path, which statuses pass a guard, the overflow aborting the run, and pooled connections. Each agent described its own package's code very well. It did not follow effects across package boundaries, and the metadata gave it nothing that would lead it there.

### Things the agent invented

None of the eight inventions listed in the answer key (section 6) appear. The misleading comments were quoted as comments and checked against the code every time. `LOG_TABLE`, `INVOICE_HDR`, `ORD_PROC`, the "nightly batch" and the "monthly job" are never presented as existing.

Of the roughly 110 other claims the graders checked, 15 are wrong (about 14%):

| Kind | Count | Examples |
|------|-------|----------|
| Over-generalised behaviour of another package | 5 | "Every log line survives a rollback" appears in 3 of the 4 packages. It ignores the `LOG_LEVEL` filter (`util_log.pkb:71`) and the logger's own swallowed errors. "`G_MODULE` keeps its value for the rest of the session" ignores the other `SET_CTX` callers. "Counts only weekdays" ignores the NLS dependence of `IS_WORKDAY`. |
| Wrong propagation or transaction reasoning | 4 | "An error in the last log call is raised to the caller", but `LOG_MSG` swallows every error. "`CHK_OVERDUE_CUSTOMERS`' writes are not committed" ignores the COMMIT inside `BLOCK_CUSTOMER`. Invoices "stay cancelled" ignores Oracle's statement-level rollback. A NULL return from `CHK_CREDIT` is suggested, but it cannot happen. |
| Ignores the table definition | 3 | "No check that `P_TO` exists", but foreign keys enforce it. A NULL order-status path, but the column is NOT NULL. "No FIRES_TRIGGER edge" reads like a metadata gap, but there is simply no trigger on that table. |
| Wrong detail or citation | 3 | `DBG` "reads `G_USER`" (it reads only `G_MODULE`). The weekend check is cited to `ADD_WORKDAYS` instead of `IS_WORKDAY`. A function "cannot be called from SQL" (it can, just not from a query). |

**Claims from general Oracle knowledge.** Claims based on general Oracle behaviour rather than this code were mostly correct: NLS-dependent day names, `VALUE_ERROR` from `TO_NUMBER`, an endless loop on a NULL date, `#` overflow in format masks, fetch across commit. Two out of roughly 20 were wrong. They are also the claims a reviewer finds hardest to check, because nothing in the repo backs them.

**No missing information was guessed.** Every business purpose is "Unknown: needs human input". The 76 open questions in the package docs are specific and cited.

## 2. Changes that would have prevented each error

Ordered by how many errors each change prevents. The **kind** column says where the change goes:
- **extractor:** `scripts/extract_metadata.py` and the models
- **validator:** `scripts/validate_doc.py`
- **template**
- **rule:** `CLAUDE.md` or a skill

| # | Change | Kind | Prevents |
|---|--------|------|----------|
| 1 | **Transitive effects per unit**: COMMIT/ROLLBACK reachable through calls, "never raises" (the callee swallows every error), and triggers fired with what they write. Add a "transitive" row to the template's Transaction control and Error handling sections. | extractor + template | Commit chain via `HOUSEKEEPING`, "not committed" claim, "last log call raises", reminder abort before COMMIT |
| 2 | **One shared doc for `UTIL_LOG` behaviour** (autonomous, level-filtered, swallows errors). Other package docs link to it and do not paraphrase it. | rule + template | 6 over-generalisations about logging |
| 3 | **Value domains**: every literal written to each status or code column, by any unit or trigger, plus the views that decode it. The validator fails a doc that lists a column's codes but omits one. | extractor + validator | Status 50 missing twice, `UNKNOWN` in `ORD_SUMMARY_V`, the "cannot cancel a paid order" case |
| 4 | **Column writers and readers**: which units write each column, including `created_by` from `UTIL_LOG.G_USER` and `SHIP_DT` from `PROCESS_ORDER`. Plus writers of each package variable across packages. | extractor | T6a `created_by`, T8b future invoice date, T7a "only writer", the `G_MODULE` overstatement |
| 5 | **Table facts in the template**: the "Tables touched" table gets columns for PK, NOT NULL and defaults, filled from `objects.json`, which already has them. Rule: before claiming "no check", look at the constraints. | template + rule | `CUST_HIST` no PK, default bypass, "no check P_TO", NULL-status path |
| 6 | **`APP_PARAMS` usage**: compare seeded parameters with `GET_PARAM` calls, and flag parameters nobody reads. | extractor | `MIN_ORDER_AMT` ignored |
| 7 | **Claim-to-source check**: every backticked name and every quoted literal in a sentence must occur in the lines it cites. | validator | `DBG` / `G_USER`, the SAT/SUN citation, the constraint line 17 vs 18 found in self-review |
| 8 | **Tag claims from general Oracle knowledge** as `[oracle]` so that `review-doc` checks each of them. | rule + skill | The two wrong Oracle inferences, and faster review of the correct ones |
| 9 | **Guard and branch rules**: for each status guard, list the values that pass as well as the ones rejected. For a branch on a callee's result, say which input states reach it. | rule (skill) | `NEW_ORDER` lets B through, government-customer reachability |
| 10 | **Flow docs**: write `docs/flows/` for order → invoice → payment and for the housekeeping chain, after the package docs. | process | Most cross-package partials together. This is the step the pilot skipped. |

Smaller fixes: name an overloaded unit's doc file `<unit>_<n>.md`, not `<unit>#<n>.md`, and add Spec-field guidance for private units to `templates/procedure.md`. Also add a column for the dependency kind to the "Called by" table, and a way to record tables that are only known at runtime.

## 3. Validator results

The validator passed all 15 final docs with 0 errors and 0 warnings. **So every one of the 31 problems above passed validation.** That was expected for the semantic gaps, but some of them are structural checks the validator could have made.

### False positives (errors raised against correct text)

| Case | Count | Fix |
|------|-------|-----|
| The sentence splitter breaks at `...` before a capital letter (`SELECT ... FOR UPDATE`) | 1 | Do not split on an ellipsis. |
| The sentence splitter breaks inside a quoted source comment | 2 | Treat quoted text as one unit. |
| An open question in the form "Question. Unknown: needs human input [cite]" fails because its first sentence has no citation | about 5 | Check open questions per item, not per sentence. |
| WARN for a name that occurs only in a comment, on a line that quotes that comment | 2 | Also accept "comment at" anywhere in the same sentence. The agent removed the backticks instead, so the name was no longer checked at all. |

About half of the 16 errors raised during the pilot were false positives (about 8, plus 2 warnings). The true positives were about 8:
- 6 citations of the comment line just above a unit, which lies outside the unit's range;
- 2 uncited sentences.

The split for `PKG_ORDER` is approximate, because its agent reported "most" of its 7 errors as the open-question form.

### False negatives (wrong or unchecked content that passed)

| Gap | Fix |
|-----|-----|
| A sentence or table row that contains "Unknown: needs human input" skips all checks, including line ranges | Exempt only the cell or clause that contains the marker. |
| A table row in a unit doc passes whenever its line falls inside the doc's own unit, so an invented dependency row passed | Check each dependency row against an actual edge in `dependencies.json`. |
| A broad citation, such as `[CUST_MGMT(body):1-244]`, satisfies both the citation check and the risk-flag coverage check | Cap the span of a citation (for example 40 lines) and require a flag to be cited within ±2 lines. |
| A "Called by" row passes with a wrong caller line, as long as the line falls inside some unit named in the row | Match the row against the CALL edge, not just the range. |
| Nothing checks that calls out, callers and cycles are complete, or that HARDCODED_VALUE and PACKAGE_STATE flags are covered | Add coverage checks for these as WARN. |
| The validator does not check what a claim says | Change 7 above (claim-to-source check) covers part of this. The rest needs review. |

## 4. Time and token cost

Token counts are the agent totals reported by the harness. They include re-reading cached input, so they overstate what was actually billed. Elapsed times are agent wall-clock times.

| Package | Body lines | Drafting tokens | Drafting time | Grading tokens | Grading time | Validator runs |
|---------|------------|-----------------|---------------|----------------|--------------|----------------|
| `CUST_MGMT` | 245 | 141 613 | 6.9 min | 103 852 | 2.1 min | 4 |
| `INV_API` | 249 | 156 705 | 7.8 min | 99 638 | 2.2 min | 4 |
| `PKG_ORDER` | 280 | 145 045 | 7.1 min | 94 359 | 2.2 min | 3 |
| `UTIL_LOG` | 169 | 128 067 | 6.3 min | 88 377 | 2.1 min | 6 |
| **Total** | 943 | **571 430** | **28.1 min** | **386 226** | **8.6 min** | 17 |

- **Drafting cost** is about 140k tokens and 7 minutes per package of 170–280 body lines. Cost depends more on the number of units and edges than on line count.
- **Running packages in parallel.** Two packages ran in parallel at the owner's request, which cut elapsed time from about 28 minutes to about 15. Parallel runs are safe only if one process owns `state/doc-status.json`.
- **Human review** was not measured. As an estimate, checking a package doc with `review-doc` and the cited source would take about 30–60 minutes per package. That is the real cost at scale, and the `[oracle]` tag and claim-to-source check aim to reduce it.

## 5. Recommendation

The approach works: facts from deterministic extraction, LLM explanation, mandatory citations, "Unknown" instead of guesses.
- Required traps: 0 wrong and 0 missed.
- Answer-key items overall: 83% fully caught; the 1 missed item is a table-definition detail, not a trap.
- No invented business intent.

The remaining errors all have one cause: the agent sees one package at a time, so it misses effects that start in another package. The next step is to give it cross-unit facts, not more prompting.

**Build next, in this order:**
1. **Extractor:** transitive effects, value domains, column writers and `APP_PARAMS` usage (changes 1, 3, 4 and 6). This is deterministic, cheap, and covers most of the partials.
2. **Validator fixes:**
   - Fix the false positives above.
   - Close the Unknown-exemption gap and the dependency-row gap.
   - Add the claim-to-source check (change 7).
3. **Shared `UTIL_LOG` doc and flow docs** (changes 2 and 10), then re-run the pilot on the same 4 packages and compare against this report. Keep `evaluation/` closed until the re-run is done.
4. **Human review of one package** by someone who knows Oracle, to calibrate the graders and measure review time.

### Real code: use the data dictionary, not regexes

This PoC had no database, so the metadata comes from a regex parser ([extraction-limitations.md](extraction-limitations.md)). For real code, read the same facts from the database. Use a read-only account, with credentials only in `.env` (`DB_USER`, `DB_PASSWORD` and `DB_DSN` are already in `.env.example`).

| Need | Source |
|------|--------|
| Source text and line numbers | `ALL_SOURCE` |
| Objects, overloads, signatures | `ALL_PROCEDURES`, `ALL_ARGUMENTS` (overloads are numbered by Oracle, so the `#n` convention maps directly) |
| Dependencies between objects | `ALL_DEPENDENCIES`, which covers synonyms, views and cross-schema references the parser cannot see |
| Identifier-level calls and variable use | **PL/Scope** (`ALL_IDENTIFIERS`), compiled with `PLSCOPE_SETTINGS='IDENTIFIERS:ALL'`. It replaces the regex call and variable analysis, and package-variable writers (change 4) come for free. |
| SQL statements per unit, with tables and columns | PL/Scope `ALL_STATEMENTS` (12.2+) plus `ALL_IDENTIFIERS` for column references. Column writers and value domains (changes 3 and 4) become queries. |
| Tables, columns, constraints, defaults | `ALL_TAB_COLUMNS`, `ALL_CONSTRAINTS`, `ALL_CONS_COLUMNS` |
| Triggers, including UPDATE OF columns and WHEN clauses | `ALL_TRIGGERS`, `ALL_TRIGGER_COLS`. This fixes the FIRES_TRIGGER over-reporting. |
| Views and their sources | `ALL_VIEWS`, `ALL_DEPENDENCIES` |
| Parameters actually used | A query on `APP_PARAMS` joined with the PL/Scope references to `GET_PARAM` |

**Dynamic SQL stays invisible in every static approach.** Cover it with runtime evidence (`V$SQL`, `DBA_HIST_SQLTEXT`, unified auditing) and keep it as an open question for humans. Callers outside the database, such as schedulers, applications and `DBMS_SCHEDULER` jobs, are partly visible through `ALL_SCHEDULER_JOBS`. The rest needs input from the application teams.

The Pydantic models stay the same; only the extractor's input changes. Build the dictionary extractor next to the regex one and check that both produce the same output for the fake codebase before switching.

### Publishing to Confluence (proposed step 9)

Publishing was out of scope for this PoC. This is how to add it without weakening the review process:

- **Git stays the source of truth.** Docs are written and reviewed as markdown in pull requests. Confluence is a read-only copy: nobody edits pages there. Each page shows a banner saying it is generated, with a link to the source file and commit.
- **Only reviewed docs are published.** Publish only entries in `state/doc-status.json` with status `approved`. A merged PR sets that status, so the `reviewed` and `approved` values the model already has get used. If the source hash no longer matches, the entry becomes `stale`, and its page gets a "source changed since review" banner instead of being silently left as it was.
- **Pages:**
  - one parent page per system;
  - one child page per package, with a child page per unit doc;
  - a "Flows" section;
  - a glossary page.

  Each page is identified by a stable key, the unit id stored as a page property, so renames don't create duplicates.
- **Conversion.** Convert markdown to Confluence storage format in a script (`scripts/publish_confluence.py`), not by asking an LLM to write the pages, so the publishing step is deterministic and testable.
  - Citations `[ID:lines]` become links to the source at that commit (in the git host), or expandable code excerpts.
  - Open questions become a Confluence task list, so domain experts can answer them where they read.
- **Answers to open questions** flow back as PRs that edit the doc and the glossary, not as Confluence edits. A small job can list unanswered tasks per page.
- **Access.** Use the Confluence REST API, or the Atlassian MCP connector when an agent should do the publishing. A dedicated service account holds a token in `.env` (`CONFLUENCE_URL`, `CONFLUENCE_SPACE_KEY`, `CONFLUENCE_USER`, `CONFLUENCE_API_TOKEN`). Add these to `.env.example` in the commit that first uses them. Start with a dry run that writes the converted pages locally, then publish to a test space.
- **Trigger.** Run the publish on merge to `main` (CI), only for changed docs, and record the published page version per entry in the state file.

This keeps the property the pilot showed matters most: every published sentence is traceable to a reviewed line of source.
