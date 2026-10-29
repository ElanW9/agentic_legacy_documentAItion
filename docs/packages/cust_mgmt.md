# Package `CUST_MGMT`

| Field | Value |
|-------|-------|
| Spec | `legacy_code/packages/cust_mgmt.pks` lines 1-31 |
| Body | `legacy_code/packages/cust_mgmt.pkb` lines 1-244 |
| Source hash | `1157cbb9f7dc25b98a2882f7eca548d971f7a1c97445caf0c33ebe6554cf4776` |
| Status | draft |

## Purpose

The package creates rows in `CUSTOMERS` and updates their credit limit and status [CUST_MGMT.CREATE_CUSTOMER:36-76] [CUST_MGMT.UPD_CREDIT_LIMIT:79-95] [CUST_MGMT.BLOCK_CUSTOMER:98-114] [CUST_MGMT.UNBLOCK_CUSTOMER:117-127].
It also offers read functions for a customer's type, a credit check, a balance and any single column of `CUSTOMERS` [CUST_MGMT.GET_CUST_TYPE:130-143] [CUST_MGMT.CHK_CREDIT:147-177] [CUST_MGMT.GET_BALANCE#2:188-208] [CUST_MGMT.GET_CUST_ATTR:212-224].
`CUST_MGMT.CHK_OVERDUE_CUSTOMERS` blocks every customer whose type is not `'G'` and who has a row in `V_OPEN_INVOICES` with `DAYS_OVERDUE` above 90 [CUST_MGMT.CHK_OVERDUE_CUSTOMERS:228-242].
The comment at [CUST_MGMT(body):5] says the purpose is "customer maintenance"; the business reason for the package and for its rules is Unknown: needs human input.

## Public API

| Unit | Kind | Signature | Spec | Body |
|------|------|-----------|------|------|
| `CUST_MGMT.CREATE_CUSTOMER` | PROCEDURE | `PROCEDURE CREATE_CUSTOMER(P_NAME IN VARCHAR2, P_TYPE IN CHAR, P_VAT IN VARCHAR2, P_EMAIL IN VARCHAR2, P_CTRY IN VARCHAR2, P_CUST_ID OUT NUMBER)` | 5-10 | 36-76 |
| `CUST_MGMT.UPD_CREDIT_LIMIT` | PROCEDURE | `PROCEDURE UPD_CREDIT_LIMIT(P_CUST_ID IN NUMBER, P_LIMIT IN NUMBER)` | 12 | 79-95 |
| `CUST_MGMT.BLOCK_CUSTOMER` | PROCEDURE | `PROCEDURE BLOCK_CUSTOMER(P_CUST_ID IN NUMBER, P_REASON IN VARCHAR2)` | 14 | 98-114 |
| `CUST_MGMT.UNBLOCK_CUSTOMER` | PROCEDURE | `PROCEDURE UNBLOCK_CUSTOMER(P_CUST_ID IN NUMBER)` | 16 | 117-127 |
| `CUST_MGMT.GET_CUST_TYPE` | FUNCTION | `FUNCTION GET_CUST_TYPE(P_CUST_ID IN NUMBER) RETURN CHAR` | 18 | 130-143 |
| `CUST_MGMT.CHK_CREDIT` | FUNCTION | `FUNCTION CHK_CREDIT(P_CUST_ID IN NUMBER, P_AMT IN NUMBER) RETURN NUMBER` | 21 | 147-177 |
| `CUST_MGMT.GET_BALANCE#1` | FUNCTION | `FUNCTION GET_BALANCE(P_CUST_ID IN NUMBER) RETURN NUMBER` | 23 | 180-184 |
| `CUST_MGMT.GET_BALANCE#2` | FUNCTION | `FUNCTION GET_BALANCE(P_CUST_ID IN NUMBER, P_AS_OF IN DATE) RETURN NUMBER` | 25 | 188-208 |
| `CUST_MGMT.GET_CUST_ATTR` | FUNCTION | `FUNCTION GET_CUST_ATTR(P_CUST_ID IN NUMBER, P_COL IN VARCHAR2) RETURN VARCHAR2` | 27 | 212-224 |
| `CUST_MGMT.CHK_OVERDUE_CUSTOMERS` | PROCEDURE | `PROCEDURE CHK_OVERDUE_CUSTOMERS` | 29 | 228-242 |

### `CUST_MGMT.CREATE_CUSTOMER`

Detailed walkthrough: [create_customer](cust_mgmt/create_customer.md).
It sets the logging module of `UTIL_LOG` to `'CUST_MGMT'` [CUST_MGMT.CREATE_CUSTOMER:46].
When `P_VAT` is not NULL it counts `CUSTOMERS` rows whose `VAT_NO` equals `P_VAT` upper-cased with spaces removed, and raises `-20010` if there is one or more [CUST_MGMT.CREATE_CUSTOMER:48-57].
It picks the credit limit from `P_TYPE`: 20000 for `'W'`, NULL for `'G'`, and 2500 for any other value, NULL included [CUST_MGMT.CREATE_CUSTOMER:60-66].
It takes the new id from `SEQ_CUSTOMERS` into `P_CUST_ID` and inserts the row with type `NVL(P_TYPE, 'R')`, the normalised VAT number, the lower-cased e-mail, country `NVL(P_CTRY, 'BE')`, the chosen limit and status `'A'` [CUST_MGMT.CREATE_CUSTOMER:68-73].
It then writes a log line through `UTIL_LOG.LOG_MSG` [CUST_MGMT.CREATE_CUSTOMER:75].
It does not commit [CUST_MGMT.CREATE_CUSTOMER:36-76].
It has no caller in legacy_code/ [CUST_MGMT.CREATE_CUSTOMER:36].

### `CUST_MGMT.UPD_CREDIT_LIMIT`

If `P_LIMIT` is greater than `CUST_MGMT.V_MAX_LIMIT` it raises `-20011` [CUST_MGMT.UPD_CREDIT_LIMIT:82-84].
That raise is inside the block whose `WHEN OTHERS THEN NULL` handler is at lines 92-94, so the error never reaches the caller and the limit is simply not changed [CUST_MGMT.UPD_CREDIT_LIMIT:82-94].
Otherwise it sets `CREDIT_LIMIT` to `P_LIMIT` for the customer, unless the customer's `STATUS` is `'C'` [CUST_MGMT.UPD_CREDIT_LIMIT:86-89].
A NULL `P_LIMIT` passes the check at line 82 (the comparison is not true) and sets the limit to NULL [CUST_MGMT.UPD_CREDIT_LIMIT:82-89].
It logs the new limit through `UTIL_LOG.LOG_MSG`, also when no row was updated [CUST_MGMT.UPD_CREDIT_LIMIT:91].
It does not commit [CUST_MGMT.UPD_CREDIT_LIMIT:79-95].
It has no caller in legacy_code/ [CUST_MGMT.UPD_CREDIT_LIMIT:79].

### `CUST_MGMT.BLOCK_CUSTOMER`

Detailed walkthrough: [block_customer](cust_mgmt/block_customer.md).
It sets `STATUS` to `'B'` and `BLOCKED_REASON` to the first 200 characters of `P_REASON` [CUST_MGMT.BLOCK_CUSTOMER:101-104].
It sets `ORD_STATUS` to 15 on the customer's `ORDERS` rows whose `ORD_STATUS` is 10 or 20 [CUST_MGMT.BLOCK_CUSTOMER:107-110].
It logs with severity `'W'` and then issues a `COMMIT`, which commits all open work of the caller's transaction [CUST_MGMT.BLOCK_CUSTOMER:112-113].
It does not check that the customer exists: with no matching row it still logs and commits [CUST_MGMT.BLOCK_CUSTOMER:101-113].

### `CUST_MGMT.UNBLOCK_CUSTOMER`

It sets `STATUS` to `'A'` and `BLOCKED_REASON` to NULL, only for a customer whose `STATUS` is `'B'` [CUST_MGMT.UNBLOCK_CUSTOMER:120-124].
It does not change `CREDIT_LIMIT`, which `TRG_CUST_BIU` set to 0 when the status became `'B'` [CUST_MGMT.UNBLOCK_CUSTOMER:120-124] [TRG_CUST_BIU:22-24].
It logs through `UTIL_LOG.LOG_MSG`, also when no row was updated [CUST_MGMT.UNBLOCK_CUSTOMER:126].
It does not commit [CUST_MGMT.UNBLOCK_CUSTOMER:117-127].
It has no caller in legacy_code/ [CUST_MGMT.UNBLOCK_CUSTOMER:117].

### `CUST_MGMT.GET_CUST_TYPE`

It returns `CUST_TYPE` of the customer [CUST_MGMT.GET_CUST_TYPE:134-139].
When the customer does not exist (`NO_DATA_FOUND`) it returns `'R'` [CUST_MGMT.GET_CUST_TYPE:141-142].
Callers are `INV_API.GET_DUE_DT` and `CUST_MGMT.CHK_OVERDUE_CUSTOMERS` [INV_API.GET_DUE_DT:38] [CUST_MGMT.CHK_OVERDUE_CUSTOMERS:238].

### `CUST_MGMT.CHK_CREDIT`

Detailed walkthrough: [chk_credit](cust_mgmt/chk_credit.md).
It returns 0 or 1 [CUST_MGMT.CHK_CREDIT:159-176].
The comment at [CUST_MGMT(spec):20] says it "returns Y/N"; the code returns the numbers 0 and 1, so the comment does not match the code [CUST_MGMT.CHK_CREDIT:160] [CUST_MGMT.CHK_CREDIT:164].
It returns 0 when the customer does not exist or its `STATUS` is not `'A'`, and 1 when its `CUST_TYPE` is `'G'` [CUST_MGMT.CHK_CREDIT:154-165] [CUST_MGMT.CHK_CREDIT:175-176].
Otherwise it gets the open amount from `INV_API.GET_OPEN_AMT` and returns 1 when the limit is NULL or the open amount plus `P_AMT` is at most 1.1 times the limit, else 0 [CUST_MGMT.CHK_CREDIT:167-173].
The only caller in legacy_code/ is `PKG_ORDER.PROCESS_ORDER`, which compares the result with 1 [PKG_ORDER.PROCESS_ORDER:191-193].

### `CUST_MGMT.GET_BALANCE#1`

It returns `GET_BALANCE(P_CUST_ID, SYSDATE)`, i.e. overload #2 as of now [CUST_MGMT.GET_BALANCE#1:183].
It has no caller in legacy_code/ [CUST_MGMT.GET_BALANCE#1:180].

### `CUST_MGMT.GET_BALANCE#2`

It sums `GROSS_AMT` of the customer's `INVOICES` with `INV_DT` up to `P_AS_OF` and `INV_STATUS` other than `'CANC'` [CUST_MGMT.GET_BALANCE#2:193-198].
It sums `PAY_AMT` of `PAYMENTS` on any invoice of the customer with `PAY_DT` up to `P_AS_OF`; this second query has no filter on `INV_STATUS`, so payments on `'CANC'` invoices are subtracted too [CUST_MGMT.GET_BALANCE#2:200-205].
It returns invoiced minus paid, both defaulting to 0 [CUST_MGMT.GET_BALANCE#2:193] [CUST_MGMT.GET_BALANCE#2:200] [CUST_MGMT.GET_BALANCE#2:207].
The comment at [CUST_MGMT(body):187] says "balance = invoiced - paid", which matches the return expression [CUST_MGMT.GET_BALANCE#2:207].
Its only caller in legacy_code/ is `CUST_MGMT.GET_BALANCE#1` [CUST_MGMT.GET_BALANCE#1:183].

### `CUST_MGMT.GET_CUST_ATTR`

It builds `SELECT TO_CHAR(<P_COL>) FROM CUSTOMERS WHERE CUST_ID = :1` by concatenating `P_COL` into the SQL text and returns the result [CUST_MGMT.GET_CUST_ATTR:216-220].
Any error, including an invalid column name or a missing customer, returns NULL to the caller [CUST_MGMT.GET_CUST_ATTR:221-223].
Callers in legacy_code/ pass `'COUNTRY_CD'`, `'VAT_NO'` and `'EMAIL'` [INV_API.CALC_VAT:59-60] [INV_API.SEND_REMINDERS:230].
The comment at [CUST_MGMT(body):211] says it is "used by reports"; the only callers in legacy_code/ are in `INV_API`, and report callers outside the source tree cannot be seen [INV_API.CALC_VAT:59] [INV_API.SEND_REMINDERS:230].

### `CUST_MGMT.CHK_OVERDUE_CUSTOMERS`

It loops over the distinct `CUST_ID` values in `V_OPEN_INVOICES` with `DAYS_OVERDUE` greater than 90 (cursor `C_OVD`) [CUST_MGMT.CHK_OVERDUE_CUSTOMERS:230-236].
For each customer whose `GET_CUST_TYPE` is not `'G'` it calls `CUST_MGMT.BLOCK_CUSTOMER` with reason `'AUTO: overdue invoices'` [CUST_MGMT.CHK_OVERDUE_CUSTOMERS:238-240].
Because `CUST_MGMT.BLOCK_CUSTOMER` commits, every blocked customer is committed separately, while the cursor is still open [CUST_MGMT.CHK_OVERDUE_CUSTOMERS:236-241] [CUST_MGMT.BLOCK_CUSTOMER:113].
`V_OPEN_INVOICES` has no filter on the customer's `STATUS`, so customers that are already `'B'` or `'C'` are blocked again and their `BLOCKED_REASON` is overwritten [V_OPEN_INVOICES:12-14] [CUST_MGMT.BLOCK_CUSTOMER:101-104].
The comment at [CUST_MGMT(body):227] says "block customers with invoices > 60 days overdue"; the code uses 90, so the comment does not match the code [CUST_MGMT.CHK_OVERDUE_CUSTOMERS:234].
Its caller is `INV_API.SEND_REMINDERS`, which commits its own work just before the call [INV_API.SEND_REMINDERS:243-245].

### Private units

| Unit | Signature | Body | Called by |
|------|-----------|------|-----------|
| `CUST_MGMT.MERGE_CUST` | `PROCEDURE MERGE_CUST(P_FROM IN NUMBER, P_TO IN NUMBER)` | 19-33 | no caller in legacy_code/ |

`CUST_MGMT.MERGE_CUST` moves `ORDERS` and `INVOICES` rows from customer `P_FROM` to `P_TO` and sets the `STATUS` of `P_FROM` to `'C'`, without commit, log or exception handler [CUST_MGMT.MERGE_CUST:19-33].
It is PRIVATE and nothing in the package body calls it, so it cannot be reached from any caller [CUST_MGMT.MERGE_CUST:19].
The comment at [CUST_MGMT(body):18] says it is "called from nightly batch"; a private unit cannot be called from outside the package, so the comment does not match the code [CUST_MGMT.MERGE_CUST:19].
Detailed walkthrough: [merge_cust](cust_mgmt/merge_cust.md).

## Dependencies

### Calls out

| From unit | To | Kind | Line |
|-----------|----|------|------|
| `CUST_MGMT.MERGE_CUST` | `TRG_CUST_BIU` | FIRES_TRIGGER | 30 |
| `CUST_MGMT.CREATE_CUSTOMER` | `UTIL_LOG.SET_CTX` | CALL | 46 |
| `CUST_MGMT.CREATE_CUSTOMER` | `SEQ_CUSTOMERS` | SEQUENCE_USE | 68 |
| `CUST_MGMT.CREATE_CUSTOMER` | `TRG_CUST_BIU` | FIRES_TRIGGER | 70 |
| `CUST_MGMT.CREATE_CUSTOMER` | `UTIL_LOG.LOG_MSG` | CALL | 75 |
| `CUST_MGMT.UPD_CREDIT_LIMIT` | `TRG_CUST_BIU` | FIRES_TRIGGER | 86 |
| `CUST_MGMT.UPD_CREDIT_LIMIT` | `UTIL_LOG.LOG_MSG` | CALL | 91 |
| `CUST_MGMT.BLOCK_CUSTOMER` | `TRG_CUST_BIU` | FIRES_TRIGGER | 101 |
| `CUST_MGMT.BLOCK_CUSTOMER` | `UTIL_LOG.LOG_MSG` | CALL | 112 |
| `CUST_MGMT.UNBLOCK_CUSTOMER` | `TRG_CUST_BIU` | FIRES_TRIGGER | 120 |
| `CUST_MGMT.UNBLOCK_CUSTOMER` | `UTIL_LOG.LOG_MSG` | CALL | 126 |
| `CUST_MGMT.CHK_CREDIT` | `INV_API.GET_OPEN_AMT` | CALL | 167 |
| `CUST_MGMT.GET_BALANCE#1` | `CUST_MGMT.GET_BALANCE#2` | CALL | 183 |
| `CUST_MGMT.CHK_OVERDUE_CUSTOMERS` | `CUST_MGMT.GET_CUST_TYPE` | CALL | 238 |
| `CUST_MGMT.CHK_OVERDUE_CUSTOMERS` | `CUST_MGMT.BLOCK_CUSTOMER` | CALL | 239 |

`UTIL_LOG.LOG_MSG` runs as an autonomous transaction and commits its `AUDIT_LOG` row on its own, so every log line written by this package survives a rollback by the caller [UTIL_LOG.LOG_MSG:63] [UTIL_LOG.LOG_MSG:72] [UTIL_LOG.LOG_MSG:82].
`UTIL_LOG.LOG_MSG` swallows its own errors with `WHEN OTHERS` and `ROLLBACK`, so a logging failure never reaches this package [UTIL_LOG.LOG_MSG:83-85].
`UTIL_LOG.SET_CTX` writes the package variable `UTIL_LOG.G_MODULE`, which keeps the value `'CUST_MGMT'` for the rest of the session and is used by every later `UTIL_LOG.LOG_MSG` call in that session, from any package [UTIL_LOG.SET_CTX:28] [UTIL_LOG.LOG_MSG:75].
Only `CUST_MGMT.CREATE_CUSTOMER` calls `UTIL_LOG.SET_CTX`; the other units log with whatever module was set last in the session [CUST_MGMT.CREATE_CUSTOMER:46].

### Called by

| Caller | Unit called | Line |
|--------|-------------|------|
| `INV_API.GET_DUE_DT` | `CUST_MGMT.GET_CUST_TYPE` | 38 |
| `INV_API.CALC_VAT` | `CUST_MGMT.GET_CUST_ATTR` | 59 |
| `INV_API.CALC_VAT` | `CUST_MGMT.GET_CUST_ATTR` | 60 |
| `INV_API.SEND_REMINDERS` | `CUST_MGMT.GET_CUST_ATTR` | 230 |
| `INV_API.SEND_REMINDERS` | `CUST_MGMT.CHK_OVERDUE_CUSTOMERS` | 245 |
| `PKG_ORDER.PROCESS_ORDER` | `CUST_MGMT.CHK_CREDIT` | 191 |
| `CUST_MGMT.CHK_OVERDUE_CUSTOMERS` | `CUST_MGMT.GET_CUST_TYPE` | 238 |
| `CUST_MGMT.CHK_OVERDUE_CUSTOMERS` | `CUST_MGMT.BLOCK_CUSTOMER` | 239 |
| `CUST_MGMT.GET_BALANCE#1` | `CUST_MGMT.GET_BALANCE#2` | 183 |

`INV_API.SEND_REMINDERS` is itself called by `UTIL_LOG.HOUSEKEEPING` [UTIL_LOG.HOUSEKEEPING:165].
Callers outside legacy_code/ (schedulers, applications, other schemas) cannot be seen [CUST_MGMT(spec):1-31].

### Package cycles

| Cycle | Edges that close it |
|-------|---------------------|
| `CUST_MGMT` -> `INV_API` -> `CUST_MGMT` | [CUST_MGMT.CHK_CREDIT:167] [INV_API.CALC_VAT:59] |
| `CUST_MGMT` -> `INV_API` -> `PKG_ORDER` -> `CUST_MGMT` | [CUST_MGMT.CHK_CREDIT:167] [INV_API.CANCEL_INVOICE:147] [PKG_ORDER.PROCESS_ORDER:191] |
| `CUST_MGMT` -> `UTIL_LOG` -> `INV_API` -> `CUST_MGMT` | [CUST_MGMT.CREATE_CUSTOMER:75] [UTIL_LOG.HOUSEKEEPING:165] [INV_API.SEND_REMINDERS:245] |
| `CUST_MGMT` -> `UTIL_LOG` -> `INV_API` -> `PKG_ORDER` -> `CUST_MGMT` | [CUST_MGMT.CREATE_CUSTOMER:75] [UTIL_LOG.HOUSEKEEPING:165] [INV_API.CANCEL_INVOICE:147] [PKG_ORDER.PROCESS_ORDER:191] |

The edges cited per cycle are one example per package pair; the cycles themselves are package-level, as listed in `dependencies.json` [CUST_MGMT.CHK_CREDIT:167].

## Tables touched

| Table / view | Operation | Unit | Line | Via |
|--------------|-----------|------|------|-----|
| `ORDERS` | UPDATE | `CUST_MGMT.MERGE_CUST` | 22 | STATIC |
| `INVOICES` | UPDATE | `CUST_MGMT.MERGE_CUST` | 26 | STATIC |
| `CUSTOMERS` | UPDATE | `CUST_MGMT.MERGE_CUST` | 30 | STATIC |
| `CUSTOMERS` | SELECT | `CUST_MGMT.CREATE_CUSTOMER` | 51 | STATIC |
| `CUSTOMERS` | INSERT | `CUST_MGMT.CREATE_CUSTOMER` | 70 | STATIC |
| `CUSTOMERS` | UPDATE | `CUST_MGMT.UPD_CREDIT_LIMIT` | 86 | STATIC |
| `CUSTOMERS` | UPDATE | `CUST_MGMT.BLOCK_CUSTOMER` | 101 | STATIC |
| `ORDERS` | UPDATE | `CUST_MGMT.BLOCK_CUSTOMER` | 107 | STATIC |
| `CUSTOMERS` | UPDATE | `CUST_MGMT.UNBLOCK_CUSTOMER` | 120 | STATIC |
| `CUSTOMERS` | SELECT | `CUST_MGMT.GET_CUST_TYPE` | 136 | STATIC |
| `CUSTOMERS` | SELECT | `CUST_MGMT.CHK_CREDIT` | 156 | STATIC |
| `INVOICES` | SELECT | `CUST_MGMT.GET_BALANCE#2` | 195 | STATIC |
| `INVOICES` | SELECT | `CUST_MGMT.GET_BALANCE#2` | 202 | STATIC |
| `PAYMENTS` | SELECT | `CUST_MGMT.GET_BALANCE#2` | 202 | STATIC |
| `CUSTOMERS` | SELECT | `CUST_MGMT.GET_CUST_ATTR` | 216 | DYNAMIC_LITERAL |
| `V_OPEN_INVOICES` | SELECT | `CUST_MGMT.CHK_OVERDUE_CUSTOMERS` | 233 | STATIC |

The `CUSTOMERS` read in `CUST_MGMT.GET_CUST_ATTR` is DYNAMIC_LITERAL: the table name is a literal inside the dynamic SQL text, but the column is built at runtime from `P_COL` [CUST_MGMT.GET_CUST_ATTR:216].
`V_OPEN_INVOICES` reads `INVOICES` and `CUSTOMERS` [V_OPEN_INVOICES:12].
Indirect writes through `UTIL_LOG.LOG_MSG` go to `AUDIT_LOG` [UTIL_LOG.LOG_MSG:72].

### Triggers fired

| Unit | Statement line | Trigger | What the trigger writes |
|------|----------------|---------|-------------------------|
| `CUST_MGMT.MERGE_CUST` | 30 | `TRG_CUST_BIU` | `:NEW` columns of `CUSTOMERS`; `CUST_HIST` only when `CREDIT_LIMIT` is in the SET list, which it is not here [TRG_CUST_BIU:12-24] [CUST_MGMT.MERGE_CUST:30-32] |
| `CUST_MGMT.CREATE_CUSTOMER` | 70 | `TRG_CUST_BIU` | `:NEW` columns `CREATED_DT`, `CUST_NAME`, `UPD_DT`, `UPD_BY` of `CUSTOMERS`; no `CUST_HIST` row on INSERT [TRG_CUST_BIU:5-19] |
| `CUST_MGMT.UPD_CREDIT_LIMIT` | 86 | `TRG_CUST_BIU` | `:NEW` columns of `CUSTOMERS`, and an INSERT into `CUST_HIST` when the limit changes [TRG_CUST_BIU:12-19] |
| `CUST_MGMT.BLOCK_CUSTOMER` | 101 | `TRG_CUST_BIU` | `:NEW` columns of `CUSTOMERS`, and `CREDIT_LIMIT` set to 0 because the new status is `'B'`; no `CUST_HIST` row because `CREDIT_LIMIT` is not in the SET list [TRG_CUST_BIU:12-24] [CUST_MGMT.BLOCK_CUSTOMER:101-104] |
| `CUST_MGMT.UNBLOCK_CUSTOMER` | 120 | `TRG_CUST_BIU` | `:NEW` columns `CUST_NAME`, `UPD_DT`, `UPD_BY` of `CUSTOMERS`; no `CUST_HIST` row [TRG_CUST_BIU:12-17] [CUST_MGMT.UNBLOCK_CUSTOMER:120-124] |

`TRG_CUST_BIU` is a BEFORE INSERT OR UPDATE row trigger on `CUSTOMERS` [TRG_CUST_BIU:1-3].
On every row it upper-cases and trims `CUST_NAME` and sets `UPD_DT` and `UPD_BY` [TRG_CUST_BIU:12-14].
On INSERT it sets `CREATED_DT` and takes a `SEQ_CUSTOMERS` value only when `CUST_ID` is NULL, which never happens for `CUST_MGMT.CREATE_CUSTOMER` because it supplies the id [TRG_CUST_BIU:5-10] [CUST_MGMT.CREATE_CUSTOMER:68-72].
Its `CUST_HIST` insert is TRIGGER_DML in the caller's transaction, so it is undone by a caller rollback (unlike the `AUDIT_LOG` lines) [TRG_CUST_BIU:17-20].
In `CUST_MGMT.UPD_CREDIT_LIMIT` on a customer with status `'B'`, the trigger records `P_LIMIT` as the new limit in `CUST_HIST` and then sets the stored `CREDIT_LIMIT` to 0 [TRG_CUST_BIU:17-24] [CUST_MGMT.UPD_CREDIT_LIMIT:86-89].
The writes of `CUST_MGMT.MERGE_CUST` to `ORDERS` and `INVOICES` and of `CUST_MGMT.BLOCK_CUSTOMER` to `ORDERS` have no FIRES_TRIGGER edge in the metadata [CUST_MGMT.MERGE_CUST:22-28] [CUST_MGMT.BLOCK_CUSTOMER:107-110].

## Side effects and risks

### Transaction control

- `CUST_MGMT.BLOCK_CUSTOMER` ends with `COMMIT`: it commits its own two updates and all uncommitted work of the caller's transaction, and the caller can no longer roll any of it back [CUST_MGMT.BLOCK_CUSTOMER:113].
- Through `CUST_MGMT.CHK_OVERDUE_CUSTOMERS`, that `COMMIT` runs once per blocked customer inside the cursor loop [CUST_MGMT.CHK_OVERDUE_CUSTOMERS:236-241].
- No other unit of the package commits, rolls back or sets a savepoint; their changes stay open until the caller commits [CUST_MGMT(body):1-244].
- The log lines from `UTIL_LOG.LOG_MSG` are committed in an autonomous transaction and survive a rollback by the caller [UTIL_LOG.LOG_MSG:63] [UTIL_LOG.LOG_MSG:82].

### Package state

| Variable | Visibility | Constant | Written by | Read by |
|----------|------------|----------|------------|---------|
| `CUST_MGMT.V_MAX_LIMIT` | PRIVATE | yes | declaration only, value 250000 [CUST_MGMT.V_MAX_LIMIT:16] | `CUST_MGMT.UPD_CREDIT_LIMIT` [CUST_MGMT.UPD_CREDIT_LIMIT:82] |

`CUST_MGMT.V_MAX_LIMIT` is a constant, so the package holds no state that changes between calls [CUST_MGMT.V_MAX_LIMIT:16].
`CUST_MGMT.CREATE_CUSTOMER` changes the session state of another package, `UTIL_LOG.G_MODULE`, through `UTIL_LOG.SET_CTX` [CUST_MGMT.CREATE_CUSTOMER:46] [UTIL_LOG.SET_CTX:28].

### Dynamic SQL

- `CUST_MGMT.GET_CUST_ATTR` concatenates `P_COL` into the select list of an `EXECUTE IMMEDIATE` statement [CUST_MGMT.GET_CUST_ATTR:216].
- The column name or expression is built at runtime, so `table_usage.json` sees only the literal table `CUSTOMERS` and not which column is read [CUST_MGMT.GET_CUST_ATTR:216].
- `P_COL` is not validated before it is concatenated, so any SQL expression the caller passes becomes part of the statement [CUST_MGMT.GET_CUST_ATTR:212-218].
- Only `P_CUST_ID` is passed as a bind variable [CUST_MGMT.GET_CUST_ATTR:218].

### Hardcoded values

| Unit | Line | Literal | Meaning |
|------|------|---------|---------|
| `CUST_MGMT.V_MAX_LIMIT` | 16 | 250000, upper bound for `P_LIMIT` in `CUST_MGMT.UPD_CREDIT_LIMIT` | Unknown: needs human input |
| `CUST_MGMT.MERGE_CUST` | 31 | `'C'` written to `STATUS` | Unknown: needs human input |
| `CUST_MGMT.CREATE_CUSTOMER` | 60-61 | `'W'` gets limit 20000 | Unknown: needs human input |
| `CUST_MGMT.CREATE_CUSTOMER` | 62 | `'G'` gets limit NULL | Unknown: needs human input |
| `CUST_MGMT.CREATE_CUSTOMER` | 65 | 2500, limit for all other types | Unknown: needs human input |
| `CUST_MGMT.CREATE_CUSTOMER` | 72 | `'R'`, default `CUST_TYPE` | Unknown: needs human input |
| `CUST_MGMT.CREATE_CUSTOMER` | 73 | `'BE'`, default `COUNTRY_CD`; `'A'`, initial `STATUS` | Unknown: needs human input |
| `CUST_MGMT.UPD_CREDIT_LIMIT` | 89 | `'C'`, status excluded from the update | Unknown: needs human input |
| `CUST_MGMT.BLOCK_CUSTOMER` | 102 | `'B'` written to `STATUS` | Unknown: needs human input |
| `CUST_MGMT.BLOCK_CUSTOMER` | 108 | 15 written to `ORD_STATUS` | Unknown: needs human input |
| `CUST_MGMT.BLOCK_CUSTOMER` | 110 | 10, 20, the `ORD_STATUS` values that are changed | Unknown: needs human input |
| `CUST_MGMT.UNBLOCK_CUSTOMER` | 121 | `'A'` written to `STATUS` | Unknown: needs human input |
| `CUST_MGMT.UNBLOCK_CUSTOMER` | 124 | `'B'`, only status that is unblocked | Unknown: needs human input |
| `CUST_MGMT.GET_CUST_TYPE` | 142 | `'R'` returned for a missing customer | Unknown: needs human input |
| `CUST_MGMT.CHK_CREDIT` | 159 | `'A'`, only status that can pass | Unknown: needs human input |
| `CUST_MGMT.CHK_CREDIT` | 163 | `'G'` always passes | Unknown: needs human input |
| `CUST_MGMT.CHK_CREDIT` | 169 | 1.1, multiplier on the limit | Unknown: needs human input |
| `CUST_MGMT.GET_BALANCE#2` | 198 | `'CANC'`, invoice status excluded | Unknown: needs human input |
| `CUST_MGMT.CHK_OVERDUE_CUSTOMERS` | 234 | 90, days overdue threshold | Unknown: needs human input |
| `CUST_MGMT.CHK_OVERDUE_CUSTOMERS` | 238 | `'G'` is never blocked | Unknown: needs human input |
| `CUST_MGMT.CHK_OVERDUE_CUSTOMERS` | 239 | `'AUTO: overdue invoices'`, block reason (not flagged by the parser) | Unknown: needs human input |
| `CUST_MGMT.BLOCK_CUSTOMER` | 103 | 200, length `BLOCKED_REASON` is cut to (not flagged by the parser) | Unknown: needs human input |

The check constraints on `CUSTOMERS` allow `CUST_TYPE` values `'R'`, `'W'`, `'G'` and `STATUS` values `'A'`, `'B'`, `'C'` [CUSTOMERS:15-16].
The comment at [legacy_code/tables/customers.sql:19] says `CUST_TYPE` is "R=retail W=wholesale" and does not mention `'G'`; the comment at [legacy_code/tables/customers.sql:20] says `STATUS` is "A/B" and does not mention `'C'`.
The comment at [legacy_code/tables/orders.sql:16] says `ORD_STATUS` is "10=new 20=confirmed 30=shipped 40=invoiced 90=cancelled" and does not mention 15; the constant `PKG_ORDER.ST_HOLD` has the value 15 [PKG_ORDER.ST_HOLD:5].
The comment at [CUST_MGMT(body):12] says revision 1.2 added "gov customers"; whether `'G'` means that is Unknown: needs human input.

### Other

- NO_CALLER: `CUST_MGMT.CREATE_CUSTOMER`, `CUST_MGMT.UPD_CREDIT_LIMIT`, `CUST_MGMT.UNBLOCK_CUSTOMER` and `CUST_MGMT.GET_BALANCE#1` are public and have no caller in legacy_code/; they may be called from outside the source tree [CUST_MGMT.CREATE_CUSTOMER:36] [CUST_MGMT.UPD_CREDIT_LIMIT:79] [CUST_MGMT.UNBLOCK_CUSTOMER:117] [CUST_MGMT.GET_BALANCE#1:180].
- NO_CALLER: `CUST_MGMT.MERGE_CUST` is private and has no caller in the package body, so it is unreachable [CUST_MGMT.MERGE_CUST:19].
- TRIGGER_DML: `TRG_CUST_BIU` inserts into `CUST_HIST` when `CREDIT_LIMIT` changes on an UPDATE [TRG_CUST_BIU:17-19].
- `CUST_MGMT.CREATE_CUSTOMER` checks VAT uniqueness with a `COUNT(*)` before the INSERT; no unique constraint on `VAT_NO` is declared in the table script [CUST_MGMT.CREATE_CUSTOMER:49-56] [CUSTOMERS:1-17].
- A `P_TYPE` value other than `'R'`, `'W'`, `'G'` or NULL gets limit 2500 and is then rejected at INSERT by the `CUST_TYPE` check constraint (or the column length), with the error going to the caller [CUST_MGMT.CREATE_CUSTOMER:64-73] [CUSTOMERS:15].

## Error handling

| Unit | Line | Handler / raise | Effect for the caller |
|------|------|-----------------|-----------------------|
| `CUST_MGMT.CREATE_CUSTOMER` | 55 | RAISE_APPLICATION_ERROR(-20010, 'Customer with VAT ... exists') | Raised to the caller; nothing has been inserted yet |
| `CUST_MGMT.CREATE_CUSTOMER` | 36-76 | no handler | Errors of the INSERT (for example the `CUST_TYPE` check) go to the caller |
| `CUST_MGMT.UPD_CREDIT_LIMIT` | 83 | RAISE_APPLICATION_ERROR(-20011, 'Limit too high') | Caught by the unit's own WHEN OTHERS at line 93; the caller gets no error |
| `CUST_MGMT.UPD_CREDIT_LIMIT` | 93-94 | WHEN OTHERS THEN NULL (swallow) | Every error, including -20011 and errors from the UPDATE or the trigger, is ignored; the caller sees a normal return |
| `CUST_MGMT.BLOCK_CUSTOMER` | 98-114 | no handler | Errors go to the caller before the `COMMIT` is reached |
| `CUST_MGMT.GET_CUST_TYPE` | 141-142 | WHEN NO_DATA_FOUND | Returns `'R'` |
| `CUST_MGMT.CHK_CREDIT` | 175-176 | WHEN NO_DATA_FOUND | Returns 0 |
| `CUST_MGMT.GET_CUST_ATTR` | 222-223 | WHEN OTHERS THEN RETURN NULL (swallow) | Returns NULL for any error: missing customer, invalid `P_COL`, conversion errors |

Units not listed (`CUST_MGMT.UNBLOCK_CUSTOMER`, `CUST_MGMT.GET_BALANCE#1`, `CUST_MGMT.GET_BALANCE#2`, `CUST_MGMT.CHK_OVERDUE_CUSTOMERS`, `CUST_MGMT.MERGE_CUST`) have no exception section, so errors go to the caller [CUST_MGMT(body):1-244].

## Open questions

1. What is the business purpose of the package, and of each rule below? Unknown: needs human input [CUST_MGMT(body):5].
2. The comment at [CUST_MGMT(body):59] says "default limit: 5000, wholesale 20000", but the code sets 2500 for the default case [CUST_MGMT.CREATE_CUSTOMER:65]. The `CUSTOMERS` column default is 5000 [CUSTOMERS:8]. Which value is intended?
3. Is the NULL credit limit for type `'G'` intended to mean "no limit"? `CUST_MGMT.CHK_CREDIT` passes a NULL limit [CUST_MGMT.CREATE_CUSTOMER:62-63] [CUST_MGMT.CHK_CREDIT:169].
4. The comment at [CUST_MGMT(spec):20] says `CUST_MGMT.CHK_CREDIT` "returns Y/N", but it returns 0/1 [CUST_MGMT.CHK_CREDIT:160]. Is the comment outdated?
5. What does the 1.1 multiplier on the credit limit represent? Unknown: needs human input [CUST_MGMT.CHK_CREDIT:169].
6. The comment at [CUST_MGMT(body):227] says 60 days, the code uses 90 [CUST_MGMT.CHK_OVERDUE_CUSTOMERS:234]. Which threshold is intended?
7. `CUST_MGMT.UPD_CREDIT_LIMIT` swallows its own -20011 "Limit too high" error, so a too-high limit fails silently [CUST_MGMT.UPD_CREDIT_LIMIT:83] [CUST_MGMT.UPD_CREDIT_LIMIT:93-94]. Is that known and accepted?
8. `CUST_MGMT.BLOCK_CUSTOMER` commits the caller's transaction [CUST_MGMT.BLOCK_CUSTOMER:113]. Do callers outside legacy_code/ rely on, or suffer from, this commit?
9. What do `ORD_STATUS` 10, 15 and 20 mean in `CUST_MGMT.BLOCK_CUSTOMER`? The table comment does not list 15; is it the same as `PKG_ORDER.ST_HOLD`? Unknown: needs human input [CUST_MGMT.BLOCK_CUSTOMER:108-110] [PKG_ORDER.ST_HOLD:5].
10. `CUST_MGMT.UNBLOCK_CUSTOMER` does not restore `CREDIT_LIMIT`, which `TRG_CUST_BIU` set to 0 on blocking [CUST_MGMT.UNBLOCK_CUSTOMER:120-124] [TRG_CUST_BIU:22-24]. Is that intended?
11. `CUST_MGMT.CHK_OVERDUE_CUSTOMERS` re-blocks customers that are already `'B'` and also blocks `'C'` customers that still have overdue invoices [CUST_MGMT.CHK_OVERDUE_CUSTOMERS:232-240] [V_OPEN_INVOICES:12-14]. Is that intended?
12. `CUST_MGMT.CHK_OVERDUE_CUSTOMERS` commits (via `CUST_MGMT.BLOCK_CUSTOMER`) inside an open cursor loop [CUST_MGMT.CHK_OVERDUE_CUSTOMERS:236-241]. Has this caused errors in production runs?
13. `CUST_MGMT.MERGE_CUST` is private and has no caller, but the comment at [CUST_MGMT(body):18] says it is "called from nightly batch" [CUST_MGMT.MERGE_CUST:19]. Was it called once, and can it be removed?
14. `CUST_MGMT.GET_CUST_ATTR` concatenates `P_COL` unchecked into dynamic SQL [CUST_MGMT.GET_CUST_ATTR:216]. Which callers outside legacy_code/ (the comment at [CUST_MGMT(body):211] says "reports") pass which values? The parser cannot trace dynamic SQL or outside callers [CUST_MGMT.GET_CUST_ATTR:216].
15. `CUST_MGMT.GET_BALANCE#2` excludes `'CANC'` invoices but still subtracts payments on them [CUST_MGMT.GET_BALANCE#2:198] [CUST_MGMT.GET_BALANCE#2:200-205]. Is that intended?
16. Callers of the four public units with NO_CALLER (`CUST_MGMT.CREATE_CUSTOMER`, `CUST_MGMT.UPD_CREDIT_LIMIT`, `CUST_MGMT.UNBLOCK_CUSTOMER`, `CUST_MGMT.GET_BALANCE#1`) may exist outside legacy_code/ (applications, schedulers, other schemas) [CUST_MGMT(spec):5-25]. Which ones?
17. Does `'G'` stand for the "gov customers" of the revision comment at [CUST_MGMT(body):12]? What do `'R'`, `'W'`, `'A'`, `'B'` and `'C'` mean beyond the incomplete column comments? Unknown: needs human input [CUSTOMERS:15-16].
18. Only `CUST_MGMT.CREATE_CUSTOMER` sets the `UTIL_LOG` module; the other units log under whatever module the session set last [CUST_MGMT.CREATE_CUSTOMER:46] [UTIL_LOG.SET_CTX:28]. Is the module in `AUDIT_LOG` relied on?
19. The parser does not flag the reason literal `'AUTO: overdue invoices'` and the length 200 as hardcoded values (longer strings and `SUBSTR` arguments are ignored by design) [CUST_MGMT.CHK_OVERDUE_CUSTOMERS:239] [CUST_MGMT.BLOCK_CUSTOMER:103].
