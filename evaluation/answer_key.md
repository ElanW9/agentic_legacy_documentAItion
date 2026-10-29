# Answer key: planted traps and quirks

> **Do not read during the pilot (step 7).** Used only in step 8 to score the generated docs.

Line ranges refer to the files in `legacy_code/` as created in step 0 (branch `feature/step-0-fake-codebase`).
Severity: **T** = one of the required traps from the brief, **Q** = extra quirk or buried business rule.

## 1. Required traps

| # | Trap | Unit | File : lines | What it is | A correct doc must mention |
|---|------|------|--------------|------------|----------------------------|
| T1 | Dynamic SQL with runtime table name | `UTIL_LOG.ARCHIVE_ROWS` | `util_log.pkb:130-155` (SQL built 138-144) | Builds `INSERT INTO <p_tab>_ARCH ...` and `DELETE FROM <p_tab> WHERE <p_date_col> < ...` by concatenation | Table and column names are runtime parameters, so static analysis cannot see which tables are touched. The only static caller is `HOUSEKEEPING` with `AUDIT_LOG`/`LOG_TS`, so it touches `AUDIT_LOG` and `AUDIT_LOG_ARCH`. It assumes a `<table>_ARCH` table exists with the same columns plus one trailing date column. Parameters are not sanitised, so SQL injection is possible. |
| T1b | Dynamic SQL with runtime column name | `CUST_MGMT.GET_CUST_ATTR` | `cust_mgmt.pkb:212-224` | `SELECT TO_CHAR(<p_col>) FROM CUSTOMERS ...` | Column name comes from the caller. Static callers (in `INV_API`) pass `COUNTRY_CD`, `VAT_NO` and `EMAIL`. Any error, including an invalid column or injection attempt, returns NULL silently (see T4b). |
| T2 | Autonomous transaction | `UTIL_LOG.LOG_MSG` | `util_log.pkb:59-86` (pragma line 63, commit 82) | `PRAGMA AUTONOMOUS_TRANSACTION` plus its own `COMMIT` | Log rows persist even when the caller rolls back. The commit does not affect the caller's transaction. Messages below `LOG_LEVEL` (from `APP_PARAMS`, cached) are dropped. |
| T3a | COMMIT in business procedure | `CUST_MGMT.BLOCK_CUSTOMER` | `cust_mgmt.pkb:113` | Commits the caller's whole transaction | Called inside the cursor loop of `CHK_OVERDUE_CUSTOMERS` (fetch across commit). Commits any pending work of the caller. |
| T3b | COMMIT and ROLLBACK in business procedure | `INV_API.REGISTER_PAYMENT` | `inv_api.pkb:193-198` | Full `ROLLBACK` before raising the cash-limit error, and a `COMMIT` on success | The rollback undoes all of the caller's uncommitted work, not only the payment. The cash rule is checked after the insert. |
| T3c | Batch commits | `PKG_ORDER.PROCESS_ORDER` | `pkg_order.pkb:241-244, 253` | Commits every 50 orders and at the end, with `ROLLBACK TO sp_ord` per order (145, 217, 247) | It commits even in single-order mode, which also commits the caller's pending work. Failed orders are rolled back to the savepoint, and the batch continues. |
| T3d | COMMIT in batch/utility | `INV_API.SEND_REMINDERS` (`inv_api.pkb:243`), `UTIL_LOG.ARCHIVE_ROWS` (`util_log.pkb:148, 153`) | | | Both commit and roll back independently. |
| T4a | WHEN OTHERS swallows error, including its own validation | `CUST_MGMT.UPD_CREDIT_LIMIT` | `cust_mgmt.pkb:79-95` (handler 92-94) | `WHEN OTHERS THEN NULL` also swallows the `-20011 'Limit too high'` raised at line 83 | The 250 000 maximum is not enforced: the call silently does nothing and reports no error. Unknown or closed customers are a silent no-op too. |
| T4b | WHEN OTHERS returns default | `CUST_MGMT.GET_CUST_ATTR` (`cust_mgmt.pkb:221-223`), `INV_API.CALC_VAT` (`inv_api.pkb:69-71`) | | Returns NULL or 0 on any error | On any failure `CALC_VAT` returns VAT = 0, which can produce invoices without VAT. |
| T4c | WHEN OTHERS in logger | `UTIL_LOG.LOG_MSG` | `util_log.pkb:83-85` | Rollback, then nothing | Logging failures are invisible ("never fails" comment at line 58). |
| T4d | WHEN OTHERS per order | `PKG_ORDER.PROCESS_ORDER` | `pkg_order.pkb:245-249` | Logs the error and continues | Errors are not raised to the caller. Only the audit log and the final count show them. |
| T5a | Dead procedure (never called) | `CUST_MGMT.MERGE_CUST` (private) | `cust_mgmt.pkb:18-33` | Not in spec, no caller anywhere | Must be flagged as dead code. The comment "called from nightly batch" is false. The procedure would merge orders and invoices and close the source customer. |
| T5b | Dead procedure (never called) | `INV_API.RECALC_PAID` (private) | `inv_api.pkb:24-32` | Not in spec, no caller | Dead. The comment "run monthly!" is misleading, because nothing can call it. |
| T5c | Branch that can never execute | `PKG_ORDER.PROCESS_ORDER` | `pkg_order.pkb:182-187` | `IF l_disc > 50` right after `l_disc := LEAST(l_disc, 15)` (line 180) | The manager-approval branch is unreachable. The maximum effective discount is 15%, and in practice 9.5% given `CALC_DISC`. |
| T6a | Package-level global state | `UTIL_LOG` spec | `util_log.pks:4-6` | Public `g_module`, `g_user`, `g_debug` | They persist for the session. `SET_CTX` does not reset `g_user` when `p_user` is NULL (`util_log.pkb:29-31`), so a later call inherits the previous user. For example, after `HOUSEKEEPING` every action in the session is logged as `BATCH`. `PKG_ORDER.NEW_ORDER` and `INV_API.REGISTER_PAYMENT` write `g_user` into `created_by`. |
| T6b | Cached session globals | `UTIL_LOG.g_log_level` (`util_log.pkb:12, 65-67`), `INV_API.g_vat_rate` (`inv_api.pkb:12, 55-57`) | | Loaded once per session | A change to `APP_PARAMS` (`VAT_RATE`, `LOG_LEVEL`) is ignored until the session reconnects, which matters for pooled connections. |
| T6c | Write-only or unused globals | `PKG_ORDER.g_last_ord_id` (`pkg_order.pks:12`), `g_line_cnt` (`pkg_order.pkb:7`), `g_disc_cache` (`pkg_order.pkb:8`), `UTIL_LOG.g_call_cnt` (`util_log.pkb:13`) | | Set but never read, or never used | These should be noted as unused state, without inventing a purpose. |
| T7a | Trigger writes to another table | `TRG_PAY_AIR` | `triggers/trg_pay_air.sql:9-20` | After payment insert: adds to `INVOICES.PAID_AMT`, sets `INV_STATUS` `PAID`/`PART`, and sets `ORDERS.ORD_STATUS = 50` | This is the only place where paid amount, invoice status and order status 50 are maintained. `REGISTER_PAYMENT`'s comment (`inv_api.pkb:184`) suggests the package does it, but it only re-reads. Status 50 is not in the `PKG_ORDER` constants or in `ORD_SUMMARY_V` (shown as `UNKNOWN`). The tolerance is 0.05. |
| T7b | Trigger writes to another table | `TRG_CUST_BIU` | `triggers/trg_cust_biu.sql:16-24` | Inserts into `CUST_HIST` on a credit-limit change, and forces `CREDIT_LIMIT = 0` when status is `B` | Blocking a customer zeroes the credit limit without a history row, because `UPDATING('CREDIT_LIMIT')` is false. `UNBLOCK_CUSTOMER` does not restore it. The trigger also uppercases `CUST_NAME` and sets `UPD_DT` and `UPD_BY`. |
| T7c | Trigger writes to another table | `TRG_ORDL_AIUD` | `triggers/trg_ordl_aiud.sql:5-11` | Keeps `ORDERS.TOTAL_AMT` in sync with line amounts | `PROCESS_ORDER` overwrites `TOTAL_AMT` with the discounted net (`pkg_order.pkb:194-198`). After that, the trigger and the package disagree on what `TOTAL_AMT` means (gross vs. net). |
| T8a | Overloads with similar signatures | `PKG_ORDER.ADD_LINE` (3 or 4 args) | `pkg_order.pkb:57-73` and `76-95` | The 3-arg version reads `PRODUCTS.LIST_PRICE` (active only) and applies a 3% discount for qty >= 100. The 4-arg version uses the given price with no discount and no active check. | Both overloads must be documented separately, including the behavioural differences. |
| T8b | Overloads | `INV_API.CREATE_INVOICE` (1 or 2 args) | `inv_api.pkb:75-83` and `86-127` | The 1-arg version uses `NVL(ship_dt, SYSDATE)` as the invoice date | For export orders `ship_dt` is the next workday, so the invoice date can be in the future. |
| T8c | Overloads | `CUST_MGMT.GET_BALANCE` (1 or 2 args) | `cust_mgmt.pkb:180-184` and `188-208` | The 1-arg version delegates with SYSDATE | The 2-arg version subtracts payments on cancelled invoices too, and the result differs from `INV_API.GET_OPEN_AMT`. |
| T9 | Very long, deeply nested procedure | `PKG_ORDER.PROCESS_ORDER` | `pkg_order.pkb:114-255` (body 120-255) | About 135 lines, up to 8 levels of nesting | It needs a step-by-step flow with the outcomes listed in section 3. |

## 2. Circular / awkward dependencies

| Cycle | Evidence |
|-------|----------|
| `CUST_MGMT` <-> `INV_API` | `CUST_MGMT.CHK_CREDIT` -> `INV_API.GET_OPEN_AMT` (`cust_mgmt.pkb:167`). `INV_API` -> `CUST_MGMT.GET_CUST_TYPE` / `GET_CUST_ATTR` / `CHK_OVERDUE_CUSTOMERS` (`inv_api.pkb:38, 59-60, 230, 245`) |
| `PKG_ORDER` <-> `INV_API` | `PKG_ORDER.PROCESS_ORDER` -> `INV_API.CREATE_INVOICE` (214), `CANCEL_ORDER` -> `INV_API.CANCEL_INVOICE_FOR_ORDER` (265). `INV_API.CREATE_INVOICE` / `CANCEL_INVOICE` -> `PKG_ORDER.SET_STATUS` and constants (`inv_api.pkb:119, 147`) |
| `UTIL_LOG` -> `INV_API` (utility calls business logic) | `UTIL_LOG.HOUSEKEEPING` -> `INV_API.SEND_REMINDERS` (`util_log.pkb:165`). Chain: `HOUSEKEEPING` -> `SEND_REMINDERS` -> `CUST_MGMT.CHK_OVERDUE_CUSTOMERS` -> `BLOCK_CUSTOMER` (commit) |

Every package calls `UTIL_LOG`. `UTIL_LOG` calls `INV_API`, which closes the cycle.

## 3. Buried business rules (a correct doc should state them, cited)

| Rule | Location |
|------|----------|
| Discount: >10 000 -> 5%, >25 000 -> 7.5%, wholesale +2% (max 9.5%). The comment says "10% for wholesale", which is wrong. | `pkg_order.pkb:17-32` |
| Discount cap 15% | `pkg_order.pkb:180` |
| Minimum order value 25: orders below it are set to CANCELLED (90) with remark `MIN AMOUNT`, without a log entry. `APP_PARAMS.MIN_ORDER_AMT = 50` exists but is ignored. | `pkg_order.pkb:138, 157-161`, `tables/app_params.sql:10` |
| Orders with inactive products go to HOLD (15) | `pkg_order.pkb:163-173` |
| Orders of blocked customers go to HOLD without a log entry | `pkg_order.pkb:174-175` |
| Batch mode picks only status 10, so held (15) orders are never retried automatically. Single mode accepts 10 or 15. | `pkg_order.pkb:126, 147` |
| Export (country not BE): ship date = next workday | `pkg_order.pkb:206-211` |
| Government (`G`) customer with failed credit check is confirmed anyway. This is reachable only when the G customer is not active (status `C`), because `CHK_CREDIT` returns 1 for active G. | `pkg_order.pkb:225-231`, `cust_mgmt.pkb:159-165` |
| Credit check: status must be `A`, G always passes, NULL limit = unlimited, 10% tolerance over the limit (`* 1.1`), and open amount includes confirmed or shipped uninvoiced orders. Returns 1/0, although the spec comment says "Y/N". | `cust_mgmt.pkb:146-177`, `cust_mgmt.pks:20-21`, `inv_api.pkb:204-221` |
| Default credit limits: W 20 000, G NULL (unlimited), others 2 500. The comment says 5 000, and the table default 5 000 is bypassed. | `cust_mgmt.pkb:59-66`, `tables/customers.sql:8` |
| Max credit limit 250 000, not enforced (T4a) | `cust_mgmt.pkb:16, 81-83` |
| `CREATE_CUSTOMER` duplicate check on normalised VAT (uppercase, no spaces) | `cust_mgmt.pkb:48-57` |
| `NEW_ORDER` rejects only closed (`C`) customers. Blocked customers can still create orders. | `pkg_order.pkb:41-44` |
| Order statuses 10/15/20/30/40/50/90. 15 and 50 are missing from the column comment, and 50 is missing from the package constants. | `pkg_order.pks:4-9`, `tables/orders.sql:16`, `trg_pay_air.sql:17` |
| `CANCEL_ORDER`: status 40 cancels the invoice first. Status > 40 (50, 90) raises -20103, so you cannot cancel twice or cancel a paid order. An invoice with payments raises -20200. | `pkg_order.pkb:258-277`, `inv_api.pkb:130-150` |
| `CANCEL_INVOICE` resets the order to CONFIRMED (20). `CANCEL_ORDER` then sets it to 90. | `inv_api.pkb:146-147` |
| `SET_STATUS` does not validate transitions | `pkg_order.pkb:98-104` |
| Line numbers increment by 10 | `pkg_order.pkb:89` |
| VAT: rate from `APP_PARAMS.VAT_RATE` (default 21). BE or NULL country -> VAT. NL/FR/DE/LU with a VAT number -> 0 (reverse charge). Everything else, including other EU countries, -> full VAT. The comment says "intra-EU", but the list has only 4 countries. | `inv_api.pkb:50-72` |
| Due date: G = 60 *workdays*, W = 45 calendar days, others 30 | `inv_api.pkb:35-47` |
| Invoice number format `INV<YYYY>-<6 digits of inv_id>`. The year is taken from SYSDATE, not the invoice date. LPAD truncates beyond 999 999. | `inv_api.pkb:18-21` |
| `CREATE_INVOICE` requires order status 20 or 30 and no existing non-cancelled invoice, otherwise returns NULL (no error). It sets the order to 40. | `inv_api.pkb:92-107, 119` |
| Payment methods BT/CC/CA (the CA comment is missing on the table). Cash > 3 000 is rejected. Overpayment > 0.05 is only logged. | `inv_api.pkb:177-196`, `tables/payments.sql:12` |
| Reminders: invoices > 14 days overdue are only *logged*, never sent (TODO). `reminder_cnt` increments on every run. `NUMBER(2)` overflows after 99 runs (ORA-01438). | `inv_api.pkb:224-246`, `tables/invoices.sql:13` |
| Auto-block: customers with invoices > 90 days overdue (the comment says 60), except G | `cust_mgmt.pkb:227-242` |
| `GET_CUST_TYPE` returns `R` for an unknown customer | `cust_mgmt.pkb:140-142` |
| Audit retention `AUDIT_KEEP_DAYS` (default 90). The orders archive is commented out (dead, ticket 4471). | `util_log.pkb:161-164` |
| Workday check uses `TO_CHAR(dt,'DY')` against English `SAT`/`SUN` and depends on NLS. Under Dutch/French NLS every day counts as a workday. | `util_log.pkb:103-106` |

## 4. Outdated / misleading comments (should not be repeated as fact)

| Comment | Location | Reality |
|---------|----------|---------|
| "all logging goes to LOG_TABLE" | `util_log.pkb:9` | Table is `AUDIT_LOG` |
| "Replaces the old INVOICE_HDR / INVOICE_DTL logic" | `inv_api.pkb:4` | Those tables do not exist |
| "returns Y/N" | `cust_mgmt.pks:20` | Returns NUMBER 1/0 |
| "default limit: 5000" | `cust_mgmt.pkb:59` | 2 500 |
| "10% for wholesale" | `pkg_order.pkb:17` | +2 percentage points |
| "> 60 days overdue" | `cust_mgmt.pkb:227` | > 90 |
| "called from nightly batch" | `cust_mgmt.pkb:18` | Never called |
| "run monthly!" | `inv_api.pkb:24` | Never called |
| "update invoice paid amount and status" | `inv_api.pkb:184` | Done by `TRG_PAY_AIR`, not here |
| "rewrite of ORD_PROC (old package dropped)" | `pkg_order.pkb:3` | Historical, so `ORD_PROC` must not be documented as existing |
| Column comment `cust_type` "R=retail W=wholesale" | `tables/customers.sql:19` | `G` (government) also exists |
| Column comment `status` "A/B" | `tables/customers.sql:20` | `C` (closed) also exists |

## 5. Other things a correct doc should get right

- `GET_ORDER_TOTAL` returns the undiscounted sum of lines, which differs from `ORDERS.TOTAL_AMT` after processing (`pkg_order.pkb:107-112`).
- `GET_OPEN_AMT` reads view `V_OPEN_INVOICES`. `CUST_BALANCE_V` depends on `V_OPEN_INVOICES` (view on view). `ORD_SUMMARY_V` decodes status 50 as `UNKNOWN`.
- `ARCHIVE_ROWS` evaluates `SYSDATE` separately for INSERT and DELETE. Rows crossing the threshold in between cause a count mismatch, a full ROLLBACK and an error log (`util_log.pkb:136-151`).
- `CHK_OVERDUE_CUSTOMERS` re-blocks already-blocked customers on every run and overwrites `BLOCKED_REASON`.
- `UNBLOCK_CUSTOMER` does not commit, while `BLOCK_CUSTOMER` does. Held orders stay on HOLD after unblocking.
- `CUST_HIST` has no primary key. `AUDIT_LOG_ARCH` must stay column-compatible with `AUDIT_LOG` because of `SELECT t.*`.

## 6. Things an agent is likely to invent (count as hallucinations if present)

- Email sending in `SEND_REMINDERS`.
- That `REGISTER_PAYMENT` updates `INVOICES` directly.
- A manager-approval workflow for discounts.
- Existence of `LOG_TABLE`, `INVOICE_HDR`, `INVOICE_DTL`, `ORD_PROC`.
- That `MERGE_CUST` or `RECALC_PAID` run in a nightly or monthly job.
- That `UPD_CREDIT_LIMIT` enforces a maximum.
- Any business purpose for `g_last_ord_id`, `g_line_cnt` or `g_disc_cache`.
- Who schedules `HOUSEKEEPING` or `PROCESS_ORDER` batch mode. This is unknown from the code and should be listed as an open question.
