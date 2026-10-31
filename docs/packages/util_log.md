# Package `UTIL_LOG`

| Field | Value |
|-------|-------|
| Spec | `legacy_code/packages/util_log.pks` lines 1-35 |
| Body | `legacy_code/packages/util_log.pkb` lines 1-168 |
| Source hash | `d44fc2f3d3ec73c27bbf4349e0f6b47af262ee799294ce2582dc78d57a8a48e6` |
| Status | draft |

## Purpose

The comment at [UTIL_LOG(spec):2] says "Utility package. Logging + misc helpers."; the code agrees that the package mixes several kinds of units [UTIL_LOG(spec):12-33]. It writes log lines to `AUDIT_LOG` in an autonomous transaction [UTIL_LOG.LOG_MSG:59-86] [UTIL_LOG.LOG_ERR:89-92], keeps a per-session logging context in package variables [UTIL_LOG.SET_CTX:26-32], reads values from `APP_PARAMS` [UTIL_LOG.GET_PARAM:35-46] [UTIL_LOG.GET_PARAM_NUM:49-55], and offers date and number helpers [UTIL_LOG.IS_WORKDAY:103-106] [UTIL_LOG.ADD_WORKDAYS:109-120] [UTIL_LOG.FMT_AMT:123-126]. It also copies and deletes rows of a table named at runtime with dynamic SQL and commits [UTIL_LOG.ARCHIVE_ROWS:130-155], and runs a fixed sequence of archiving and `INV_API.SEND_REMINDERS` [UTIL_LOG.HOUSEKEEPING:159-166]. Why these units sit in one package, and the business reason for the package: Unknown: needs human input.

## Public API

| Unit | Kind | Signature | Spec | Body |
|------|------|-----------|------|------|
| `UTIL_LOG.SET_CTX` | PROCEDURE | `PROCEDURE SET_CTX(P_MODULE IN VARCHAR2, P_USER IN VARCHAR2 DEFAULT NULL)` | 12 | 26-32 |
| `UTIL_LOG.LOG_MSG` | PROCEDURE | `PROCEDURE LOG_MSG(P_ACTION IN VARCHAR2, P_OBJ_ID IN VARCHAR2, P_MSG IN VARCHAR2, P_SEV IN CHAR DEFAULT 'I')` | 14-17 | 59-86 |
| `UTIL_LOG.LOG_ERR` | PROCEDURE | `PROCEDURE LOG_ERR(P_ACTION IN VARCHAR2, P_OBJ_ID IN VARCHAR2)` | 19 | 89-92 |
| `UTIL_LOG.DBG` | PROCEDURE | `PROCEDURE DBG(P_MSG IN VARCHAR2)` | 21 | 95-100 |
| `UTIL_LOG.GET_PARAM` | FUNCTION | `FUNCTION GET_PARAM(P_NAME IN VARCHAR2) RETURN VARCHAR2` | 23 | 35-46 |
| `UTIL_LOG.GET_PARAM_NUM` | FUNCTION | `FUNCTION GET_PARAM_NUM(P_NAME IN VARCHAR2, P_DEFAULT IN NUMBER) RETURN NUMBER` | 24 | 49-55 |
| `UTIL_LOG.IS_WORKDAY` | FUNCTION | `FUNCTION IS_WORKDAY(P_DT IN DATE) RETURN BOOLEAN` | 26 | 103-106 |
| `UTIL_LOG.ADD_WORKDAYS` | FUNCTION | `FUNCTION ADD_WORKDAYS(P_DT IN DATE, P_DAYS IN NUMBER) RETURN DATE` | 27 | 109-120 |
| `UTIL_LOG.FMT_AMT` | FUNCTION | `FUNCTION FMT_AMT(P_AMT IN NUMBER) RETURN VARCHAR2` | 29 | 123-126 |
| `UTIL_LOG.ARCHIVE_ROWS` | PROCEDURE | `PROCEDURE ARCHIVE_ROWS(P_TAB IN VARCHAR2, P_DATE_COL IN VARCHAR2, P_DAYS IN NUMBER)` | 32 | 130-155 |
| `UTIL_LOG.HOUSEKEEPING` | PROCEDURE | `PROCEDURE HOUSEKEEPING` | 33 | 159-166 |

### `UTIL_LOG.SET_CTX`

Sets `UTIL_LOG.G_MODULE` to the first 30 characters of `P_MODULE` in uppercase [UTIL_LOG.SET_CTX:28]. A NULL `P_MODULE` sets `UTIL_LOG.G_MODULE` to NULL [UTIL_LOG.SET_CTX:28]. `UTIL_LOG.G_USER` is set to the first 30 characters of `P_USER` only when `P_USER` is not NULL; otherwise the previous value stays in place for the session [UTIL_LOG.SET_CTX:29-31]. Both values are read later by `UTIL_LOG.LOG_MSG` and `UTIL_LOG.DBG`, and `UTIL_LOG.G_USER` also by other packages (see "Package state") [UTIL_LOG.LOG_MSG:75-79] [UTIL_LOG.DBG:98].

### `UTIL_LOG.LOG_MSG`

Inserts one row into `AUDIT_LOG` in an autonomous transaction when the severity level of `P_SEV` is at least the session log level, then commits only that autonomous transaction; any error is swallowed [UTIL_LOG.LOG_MSG:63-86]. Full walkthrough: [log_msg](util_log/log_msg.md).

### `UTIL_LOG.LOG_ERR`

Calls `UTIL_LOG.LOG_MSG` with `P_ACTION`, `P_OBJ_ID`, the text `SQLERRM || ' ' || DBMS_UTILITY.FORMAT_ERROR_BACKTRACE` as the message, and severity `UTIL_LOG.C_SEV_ERR` [UTIL_LOG.LOG_ERR:91]. `SQLERRM` and the backtrace describe the error being handled at the moment of the call, so the message only carries an error when `UTIL_LOG.LOG_ERR` is called from inside an exception handler [UTIL_LOG.LOG_ERR:91]. The only caller in legacy_code/ calls it from a `WHEN OTHERS` handler [PKG_ORDER.PROCESS_ORDER:246-249]. It inherits the behaviour of `UTIL_LOG.LOG_MSG`: it never raises and does not touch the caller's transaction [UTIL_LOG.LOG_MSG:63] [UTIL_LOG.LOG_MSG:83-85].

### `UTIL_LOG.DBG`

When `UTIL_LOG.G_DEBUG` is TRUE, writes a line with the current time (format `'HH24:MI:SS.FF3'`), `UTIL_LOG.G_MODULE` and `P_MSG` to `DBMS_OUTPUT.PUT_LINE`; otherwise it does nothing [UTIL_LOG.DBG:97-99]. No unit in legacy_code/ sets `UTIL_LOG.G_DEBUG`, so the output branch is only reached when code outside legacy_code/ sets it to TRUE in the session (see "Package state") [UTIL_LOG.DBG:97] [UTIL_LOG.G_DEBUG:6].

### `UTIL_LOG.GET_PARAM`

Returns `APP_PARAMS.PARAM_VAL` for the row whose `PARAM_NAME` equals `UPPER(P_NAME)` [UTIL_LOG.GET_PARAM:38-42]. When no row matches it returns NULL [UTIL_LOG.GET_PARAM:44-45]. `PARAM_NAME` is the primary key of `APP_PARAMS`, so at most one row can match [APP_PARAMS:4].

### `UTIL_LOG.GET_PARAM_NUM`

Returns `TO_NUMBER` of `UTIL_LOG.GET_PARAM(P_NAME)`, or `P_DEFAULT` when that value is NULL [UTIL_LOG.GET_PARAM_NUM:51]. When the stored value cannot be converted to a number, the `VALUE_ERROR` handler returns `P_DEFAULT` [UTIL_LOG.GET_PARAM_NUM:52-54].

### `UTIL_LOG.IS_WORKDAY`

Returns TRUE unless `TO_CHAR(P_DT, 'DY')` is `'SAT'` or `'SUN'` [UTIL_LOG.IS_WORKDAY:105]. The day abbreviation produced by `TO_CHAR` depends on the session's date language, which the parser cannot see; with a date language whose abbreviations differ from `'SAT'`/`'SUN'`, every date counts as a workday [UTIL_LOG.IS_WORKDAY:105]. Holidays are not checked [UTIL_LOG.IS_WORKDAY:103-106]. For a NULL `P_DT` the expression is NULL, so the function returns NULL [UTIL_LOG.IS_WORKDAY:105].

### `UTIL_LOG.ADD_WORKDAYS`

Starting from `P_DT`, adds one calendar day at a time and counts the days for which `UTIL_LOG.IS_WORKDAY` is TRUE, until the count reaches `P_DAYS`; it returns the date reached [UTIL_LOG.ADD_WORKDAYS:110-119]. The time-of-day part of `P_DT` is kept, because only whole days are added [UTIL_LOG.ADD_WORKDAYS:114]. When `P_DAYS` is zero, negative or NULL the loop does not run and `P_DT` is returned unchanged [UTIL_LOG.ADD_WORKDAYS:113]. A fractional `P_DAYS` is rounded up in effect, because the loop runs while the count is below `P_DAYS` [UTIL_LOG.ADD_WORKDAYS:113-117]. When `P_DT` is NULL and `P_DAYS` is positive, `V_DT` stays NULL, the workday test never succeeds and the loop never ends [UTIL_LOG.ADD_WORKDAYS:113-118].

### `UTIL_LOG.FMT_AMT`

Returns `P_AMT` (NULL treated as 0) formatted with the mask `'FM999G999G990D00'` and the fixed numeric characters `','` as decimal separator and `'.'` as group separator, so 1234.5 becomes `1.234,50` [UTIL_LOG.FMT_AMT:125]. The mask has room for nine integer digits; Oracle returns a string of `#` characters for a value that does not fit [UTIL_LOG.FMT_AMT:125].

### `UTIL_LOG.ARCHIVE_ROWS`

Copies rows older than `P_DAYS` days (by the column named in `P_DATE_COL`) from the table named in `P_TAB` into the table with the same name plus `_ARCH`, deletes them from the source table, and then either commits or rolls back the whole transaction, with dynamic SQL [UTIL_LOG.ARCHIVE_ROWS:130-155]. Full walkthrough: [archive_rows](util_log/archive_rows.md).

### `UTIL_LOG.HOUSEKEEPING`

Runs three steps in order [UTIL_LOG.HOUSEKEEPING:159-166]:

1. `UTIL_LOG.SET_CTX('HOUSEKEEPING', 'BATCH')`, which leaves `UTIL_LOG.G_MODULE` = `'HOUSEKEEPING'` and `UTIL_LOG.G_USER` = `'BATCH'` in the session after the procedure returns [UTIL_LOG.HOUSEKEEPING:161].
2. `UTIL_LOG.ARCHIVE_ROWS('AUDIT_LOG', 'LOG_TS', ...)` with the number of days from `UTIL_LOG.GET_PARAM_NUM('AUDIT_KEEP_DAYS', 90)` [UTIL_LOG.HOUSEKEEPING:162]. The seed data stores `'90'` for this parameter [legacy_code/tables/app_params.sql:9].
3. `INV_API.SEND_REMINDERS` [UTIL_LOG.HOUSEKEEPING:165], which has its own COMMIT [INV_API.SEND_REMINDERS:243].

The comment at [UTIL_LOG.HOUSEKEEPING:163] says "orders archive disabled 2013, see ticket 4471", and line 164 is a commented-out call that would archive `ORDERS` by `ORD_DT` with 730 days; it is not executed [UTIL_LOG.HOUSEKEEPING:163-164]. The comment at [UTIL_LOG(body):158] says "nightly job"; there is no caller in legacy_code/ to confirm it [UTIL_LOG.HOUSEKEEPING:159]. When `UTIL_LOG.ARCHIVE_ROWS` raises, `INV_API.SEND_REMINDERS` is not reached; when it ends with its count-mismatch branch it returns normally and the reminders still run [UTIL_LOG.HOUSEKEEPING:162-165] [UTIL_LOG.ARCHIVE_ROWS:147-150].

### Private units

| Unit | Signature | Body | Called by |
|------|-----------|------|-----------|
| `UTIL_LOG.LVL` | `FUNCTION LVL(P_SEV IN CHAR) RETURN NUMBER` | 16-23 | `UTIL_LOG.LOG_MSG` [UTIL_LOG.LOG_MSG:71] |

`UTIL_LOG.LVL` maps `'E'` to 3, `'W'` to 2 and every other value, NULL included, to 1 [UTIL_LOG.LVL:18-22]. The meaning of these levels: Unknown: needs human input.

## Dependencies

### Calls out

| From unit | To | Kind | Line |
|-----------|----|------|------|
| `UTIL_LOG.GET_PARAM_NUM` | `UTIL_LOG.GET_PARAM` | CALL | 51 |
| `UTIL_LOG.LOG_MSG` | `UTIL_LOG.GET_PARAM_NUM` | CALL | 66 |
| `UTIL_LOG.LOG_MSG` | `UTIL_LOG.LVL` | CALL | 71 |
| `UTIL_LOG.LOG_MSG` | `AUDIT_LOG_SEQ` | SEQUENCE_USE | 73 |
| `UTIL_LOG.LOG_ERR` | `UTIL_LOG.LOG_MSG` | CALL | 91 |
| `UTIL_LOG.LOG_ERR` | `DBMS_UTILITY.FORMAT_ERROR_BACKTRACE` | EXTERNAL_CALL | 91 |
| `UTIL_LOG.DBG` | `DBMS_OUTPUT.PUT_LINE` | EXTERNAL_CALL | 98 |
| `UTIL_LOG.ADD_WORKDAYS` | `UTIL_LOG.IS_WORKDAY` | CALL | 115 |
| `UTIL_LOG.ARCHIVE_ROWS` | `UTIL_LOG.DBG` | CALL | 136 |
| `UTIL_LOG.ARCHIVE_ROWS` | `UTIL_LOG.LOG_MSG` | CALL | 149 |
| `UTIL_LOG.ARCHIVE_ROWS` | `UTIL_LOG.LOG_MSG` | CALL | 154 |
| `UTIL_LOG.HOUSEKEEPING` | `UTIL_LOG.SET_CTX` | CALL | 161 |
| `UTIL_LOG.HOUSEKEEPING` | `UTIL_LOG.ARCHIVE_ROWS` | CALL | 162 |
| `UTIL_LOG.HOUSEKEEPING` | `UTIL_LOG.GET_PARAM_NUM` | CALL | 162 |
| `UTIL_LOG.HOUSEKEEPING` | `INV_API.SEND_REMINDERS` | CALL | 165 |

### Called by

| Caller | Unit called | Line |
|--------|-------------|------|
| `CUST_MGMT.CREATE_CUSTOMER` | `UTIL_LOG.SET_CTX` | 46 |
| `CUST_MGMT.CREATE_CUSTOMER` | `UTIL_LOG.LOG_MSG` | 75 |
| `CUST_MGMT.UPD_CREDIT_LIMIT` | `UTIL_LOG.LOG_MSG` | 91 |
| `CUST_MGMT.BLOCK_CUSTOMER` | `UTIL_LOG.LOG_MSG` | 112 |
| `CUST_MGMT.UNBLOCK_CUSTOMER` | `UTIL_LOG.LOG_MSG` | 126 |
| `INV_API.GET_DUE_DT` | `UTIL_LOG.ADD_WORKDAYS` | 41 |
| `INV_API.CALC_VAT` | `UTIL_LOG.GET_PARAM_NUM` | 56 |
| `INV_API.CREATE_INVOICE#2` | `UTIL_LOG.LOG_MSG` | 95 |
| `INV_API.CREATE_INVOICE#2` | `UTIL_LOG.LOG_MSG` | 121 |
| `INV_API.CREATE_INVOICE#2` | `UTIL_LOG.FMT_AMT` | 122 |
| `INV_API.CANCEL_INVOICE` | `UTIL_LOG.LOG_MSG` | 149 |
| `INV_API.REGISTER_PAYMENT` | `UTIL_LOG.SET_CTX` | 170 |
| `INV_API.REGISTER_PAYMENT` | `UTIL_LOG.G_USER` (VARIABLE_REF) | 182 |
| `INV_API.REGISTER_PAYMENT` | `UTIL_LOG.LOG_MSG` | 188 |
| `INV_API.REGISTER_PAYMENT` | `UTIL_LOG.FMT_AMT` | 189 |
| `INV_API.SEND_REMINDERS` | `UTIL_LOG.LOG_MSG` | 234 |
| `INV_API.SEND_REMINDERS` | `UTIL_LOG.FMT_AMT` | 235 |
| `PKG_ORDER.WLOG` | `UTIL_LOG.LOG_MSG` | 13 |
| `PKG_ORDER.NEW_ORDER` | `UTIL_LOG.SET_CTX` | 39 |
| `PKG_ORDER.NEW_ORDER` | `UTIL_LOG.G_USER` (VARIABLE_REF) | 49 |
| `PKG_ORDER.PROCESS_ORDER` | `UTIL_LOG.SET_CTX` | 140 |
| `PKG_ORDER.PROCESS_ORDER` | `UTIL_LOG.ADD_WORKDAYS` | 210 |
| `PKG_ORDER.PROCESS_ORDER` | `UTIL_LOG.LOG_ERR` | 249 |
| `UTIL_LOG.GET_PARAM_NUM` | `UTIL_LOG.GET_PARAM` | 51 |
| `UTIL_LOG.LOG_MSG` | `UTIL_LOG.GET_PARAM_NUM` | 66 |
| `UTIL_LOG.LOG_MSG` | `UTIL_LOG.LVL` | 71 |
| `UTIL_LOG.LOG_ERR` | `UTIL_LOG.LOG_MSG` | 91 |
| `UTIL_LOG.ADD_WORKDAYS` | `UTIL_LOG.IS_WORKDAY` | 115 |
| `UTIL_LOG.ARCHIVE_ROWS` | `UTIL_LOG.DBG` | 136 |
| `UTIL_LOG.ARCHIVE_ROWS` | `UTIL_LOG.LOG_MSG` | 149 |
| `UTIL_LOG.ARCHIVE_ROWS` | `UTIL_LOG.LOG_MSG` | 154 |
| `UTIL_LOG.HOUSEKEEPING` | `UTIL_LOG.SET_CTX` | 161 |
| `UTIL_LOG.HOUSEKEEPING` | `UTIL_LOG.ARCHIVE_ROWS` | 162 |
| `UTIL_LOG.HOUSEKEEPING` | `UTIL_LOG.GET_PARAM_NUM` | 162 |

`UTIL_LOG.HOUSEKEEPING` has no caller in legacy_code/ [UTIL_LOG.HOUSEKEEPING:159]. `UTIL_LOG.DBG`, `UTIL_LOG.IS_WORKDAY` and `UTIL_LOG.GET_PARAM` are called only from inside `UTIL_LOG` [UTIL_LOG.ARCHIVE_ROWS:136] [UTIL_LOG.ADD_WORKDAYS:115] [UTIL_LOG.GET_PARAM_NUM:51]. Callers outside legacy_code/ cannot be seen [UTIL_LOG(spec):12-33].

### Package cycles

`UTIL_LOG` takes part in four package cycles in `dependencies.json`, all through `UTIL_LOG.HOUSEKEEPING` calling `INV_API.SEND_REMINDERS` [UTIL_LOG.HOUSEKEEPING:165]:

- `INV_API` -> `UTIL_LOG` [UTIL_LOG.HOUSEKEEPING:165] [INV_API.SEND_REMINDERS:234]
- `CUST_MGMT` -> `UTIL_LOG` -> `INV_API` [UTIL_LOG.HOUSEKEEPING:165] [CUST_MGMT.CREATE_CUSTOMER:75]
- `INV_API` -> `PKG_ORDER` -> `UTIL_LOG` [UTIL_LOG.HOUSEKEEPING:165] [PKG_ORDER.WLOG:13]
- `CUST_MGMT` -> `UTIL_LOG` -> `INV_API` -> `PKG_ORDER` [UTIL_LOG.HOUSEKEEPING:165] [PKG_ORDER.WLOG:13]

The order of names within each cycle is copied from `dependencies.json`; the edges between the other packages are documented in their own package docs [UTIL_LOG.HOUSEKEEPING:165].

## Tables touched

| Table / view | Operation | Unit | Line | Via |
|--------------|-----------|------|------|-----|
| `APP_PARAMS` | SELECT | `UTIL_LOG.GET_PARAM` | 40 | STATIC |
| `AUDIT_LOG` | INSERT | `UTIL_LOG.LOG_MSG` | 72 | STATIC |

`UTIL_LOG.ARCHIVE_ROWS` also reads, inserts and deletes through dynamic SQL with runtime table names; those accesses are not in `table_usage.json` and are listed under "Dynamic SQL" [UTIL_LOG.ARCHIVE_ROWS:138-144].

### Triggers fired

None found in metadata.

`objects.json` has no trigger on `AUDIT_LOG`, `AUDIT_LOG_ARCH` or `APP_PARAMS` [AUDIT_LOG:1-11] [AUDIT_LOG_ARCH:2-12]. Triggers on tables that callers outside legacy_code/ pass to `UTIL_LOG.ARCHIVE_ROWS` cannot be determined, because the parser does not follow dynamic SQL [UTIL_LOG.ARCHIVE_ROWS:140-144].

## Side effects and risks

### Transaction control

- `UTIL_LOG.LOG_MSG` runs as an autonomous transaction [UTIL_LOG.LOG_MSG:63]. Its COMMIT commits only its own `AUDIT_LOG` insert, and it commits even when no row was inserted [UTIL_LOG.LOG_MSG:71-82]. The log row survives a later rollback by the caller, and the caller's open work is neither committed nor rolled back [UTIL_LOG.LOG_MSG:63] [UTIL_LOG.LOG_MSG:82]. Its ROLLBACK in the `WHEN OTHERS` handler undoes only the autonomous transaction [UTIL_LOG.LOG_MSG:84-85]. `UTIL_LOG.LOG_ERR` has the same effect because it only calls `UTIL_LOG.LOG_MSG` [UTIL_LOG.LOG_ERR:91].
- `UTIL_LOG.ARCHIVE_ROWS` is not autonomous [UTIL_LOG.ARCHIVE_ROWS:130-135]. Its COMMIT commits everything the caller had open in the session, together with the archive copy and delete [UTIL_LOG.ARCHIVE_ROWS:153]. Its ROLLBACK on a count mismatch undoes everything the caller had open, not only the archive statements, and the caller is not told: the procedure returns normally [UTIL_LOG.ARCHIVE_ROWS:147-150].
- `UTIL_LOG.HOUSEKEEPING` therefore commits through `UTIL_LOG.ARCHIVE_ROWS` and again through `INV_API.SEND_REMINDERS` [UTIL_LOG.HOUSEKEEPING:162-165] [INV_API.SEND_REMINDERS:243].

### Package state

All variables keep their value between calls for the life of the database session [UTIL_LOG(spec):4-10] [UTIL_LOG(body):12-13]. The spec variables are visible to, and can be changed by, any code in the session, also outside legacy_code/ [UTIL_LOG(spec):4-6].

| Variable | Visibility | Constant | Written by | Read by |
|----------|------------|----------|------------|---------|
| `UTIL_LOG.G_MODULE` | PUBLIC | no | `UTIL_LOG.SET_CTX` [UTIL_LOG.SET_CTX:28]; initial `'UNKNOWN'` [UTIL_LOG.G_MODULE:4] | `UTIL_LOG.LOG_MSG` [UTIL_LOG.LOG_MSG:75], `UTIL_LOG.DBG` [UTIL_LOG.DBG:98] |
| `UTIL_LOG.G_USER` | PUBLIC | no | `UTIL_LOG.SET_CTX` [UTIL_LOG.SET_CTX:30]; initial NULL [UTIL_LOG.G_USER:5] | `UTIL_LOG.LOG_MSG` [UTIL_LOG.LOG_MSG:79], `INV_API.REGISTER_PAYMENT` [INV_API.REGISTER_PAYMENT:182], `PKG_ORDER.NEW_ORDER` [PKG_ORDER.NEW_ORDER:49] |
| `UTIL_LOG.G_DEBUG` | PUBLIC | no | no writer in legacy_code/; initial FALSE [UTIL_LOG.G_DEBUG:6] | `UTIL_LOG.DBG` [UTIL_LOG.DBG:97] |
| `UTIL_LOG.C_SEV_INFO` | PUBLIC | yes | value `'I'` [UTIL_LOG.C_SEV_INFO:8] | no reader in legacy_code/ [UTIL_LOG.C_SEV_INFO:8] |
| `UTIL_LOG.C_SEV_WARN` | PUBLIC | yes | value `'W'` [UTIL_LOG.C_SEV_WARN:9] | no reader in legacy_code/ [UTIL_LOG.C_SEV_WARN:9] |
| `UTIL_LOG.C_SEV_ERR` | PUBLIC | yes | value `'E'` [UTIL_LOG.C_SEV_ERR:10] | `UTIL_LOG.LOG_ERR` [UTIL_LOG.LOG_ERR:91], `UTIL_LOG.ARCHIVE_ROWS` [UTIL_LOG.ARCHIVE_ROWS:149] |
| `UTIL_LOG.G_LOG_LEVEL` | PRIVATE | no | `UTIL_LOG.LOG_MSG`, once per session [UTIL_LOG.LOG_MSG:65-66]; initial NULL [UTIL_LOG.G_LOG_LEVEL:12] | `UTIL_LOG.LOG_MSG` [UTIL_LOG.LOG_MSG:65] [UTIL_LOG.LOG_MSG:71] |
| `UTIL_LOG.G_CALL_CNT` | PRIVATE | no | `UTIL_LOG.LOG_MSG` [UTIL_LOG.LOG_MSG:69]; initial 0 [UTIL_LOG.G_CALL_CNT:13] | only its own increment [UTIL_LOG.LOG_MSG:69] |

Consequences for callers:

- `UTIL_LOG.G_USER` is only overwritten when `UTIL_LOG.SET_CTX` gets a non-NULL `P_USER` [UTIL_LOG.SET_CTX:29-31]. After `UTIL_LOG.HOUSEKEEPING` the session keeps `'BATCH'` as user and `'HOUSEKEEPING'` as module until the next `UTIL_LOG.SET_CTX` [UTIL_LOG.HOUSEKEEPING:161]. That value is written into `AUDIT_LOG.USR` by `UTIL_LOG.LOG_MSG` and used by `INV_API.REGISTER_PAYMENT` and `PKG_ORDER.NEW_ORDER` [UTIL_LOG.LOG_MSG:79] [INV_API.REGISTER_PAYMENT:182] [PKG_ORDER.NEW_ORDER:49].
- `UTIL_LOG.G_LOG_LEVEL` is loaded from the `'LOG_LEVEL'` parameter the first time `UTIL_LOG.LOG_MSG` runs in a session and never reloaded, so a change in `APP_PARAMS` is not seen by sessions that already logged [UTIL_LOG.LOG_MSG:65-67].
- `UTIL_LOG.G_CALL_CNT` is incremented on every `UTIL_LOG.LOG_MSG` call, also when no row is written, and no unit in legacy_code/ reads it [UTIL_LOG.LOG_MSG:69].
- The `C_SEV_*` constants are not used as defaults: `UTIL_LOG.LOG_MSG` has its own literal default `'I'` for `P_SEV` and `UTIL_LOG.LVL` compares with literals [UTIL_LOG.LOG_MSG:62] [UTIL_LOG.LVL:19-20].

### Dynamic SQL

`UTIL_LOG.ARCHIVE_ROWS` builds two statements by concatenation and runs them with `EXECUTE IMMEDIATE` [UTIL_LOG.ARCHIVE_ROWS:138-144]:

- `INSERT INTO <P_TAB>_ARCH SELECT t.*, SYSDATE FROM <P_TAB> t WHERE t.<P_DATE_COL> < SYSDATE - :d` [UTIL_LOG.ARCHIVE_ROWS:138-140].
- `DELETE FROM <P_TAB> WHERE <P_DATE_COL> < SYSDATE - :d` [UTIL_LOG.ARCHIVE_ROWS:143-144].

The table names and the column name are built at runtime; only `P_DAYS` is passed as a bind variable [UTIL_LOG.ARCHIVE_ROWS:140] [UTIL_LOG.ARCHIVE_ROWS:144]. `table_usage.json` cannot see these accesses [UTIL_LOG.ARCHIVE_ROWS:138-144]. The only call in legacy_code/ passes `'AUDIT_LOG'` and `'LOG_TS'`, so at runtime it reads and deletes from `AUDIT_LOG` and inserts into `AUDIT_LOG_ARCH` [UTIL_LOG.HOUSEKEEPING:162]. `P_TAB` is trimmed and uppercased, but neither it nor `P_DATE_COL` is checked before it is concatenated into the statement, so any text passed in becomes part of the SQL [UTIL_LOG.ARCHIVE_ROWS:132] [UTIL_LOG.ARCHIVE_ROWS:138-143]. `SELECT t.*` relies on the archive table having the same columns in the same order plus one extra date column [UTIL_LOG.ARCHIVE_ROWS:138]; the comment at [legacy_code/tables/audit_log_arch.sql:1] says "same layout as audit_log + arch_dt (must stay in sync!)", and the current DDL of `AUDIT_LOG_ARCH` matches that (`AUDIT_LOG` columns plus `ARCH_DT`) [AUDIT_LOG_ARCH:2-12] [AUDIT_LOG:1-11].

### Hardcoded values

| Value | Where | Meaning |
|-------|-------|---------|
| `'I'`, `'W'`, `'E'` | `UTIL_LOG.C_SEV_INFO`, `UTIL_LOG.C_SEV_WARN`, `UTIL_LOG.C_SEV_ERR` [UTIL_LOG(spec):8-10] | Unknown: needs human input |
| 3 for `'E'`, 2 for `'W'`, 1 otherwise | `UTIL_LOG.LVL` [UTIL_LOG.LVL:19-21] | Unknown: needs human input |
| default level 1 for `'LOG_LEVEL'` | `UTIL_LOG.LOG_MSG` [UTIL_LOG.LOG_MSG:66] | Unknown: needs human input |
| `'SAT'`, `'SUN'` | `UTIL_LOG.IS_WORKDAY` [UTIL_LOG.IS_WORKDAY:105] | non-workdays, as the code compares; whether this fits the business calendar: Unknown: needs human input |
| mask `'FM999G999G990D00'`, separators `',.'` | `UTIL_LOG.FMT_AMT` [UTIL_LOG.FMT_AMT:125] | Unknown: needs human input |
| default 90 days for `'AUDIT_KEEP_DAYS'` | `UTIL_LOG.HOUSEKEEPING` [UTIL_LOG.HOUSEKEEPING:162] | retention period according to Elan (Confluence comment, 2026-10-31), unconfirmed; reason for 90: Unknown: needs human input (see Open questions) |
| lengths 30, 50, 4000 | `UTIL_LOG.LOG_MSG` [UTIL_LOG.LOG_MSG:76-78] | match the column sizes of `AUDIT_LOG.ACTION`, `AUDIT_LOG.OBJ_ID`, `AUDIT_LOG.MSG` [AUDIT_LOG:5-7] |

### Other

- `UTIL_LOG.HOUSEKEEPING` is flagged NO_CALLER: there is no caller in legacy_code/; a scheduler or other caller outside the source tree cannot be seen [UTIL_LOG.HOUSEKEEPING:159].
- `UTIL_LOG.ADD_WORKDAYS` loops without end for a NULL `P_DT` and a positive `P_DAYS` [UTIL_LOG.ADD_WORKDAYS:113-118].
- `UTIL_LOG.LOG_MSG` truncates `P_ACTION`, `P_OBJ_ID` and `P_MSG` silently to 30, 50 and 4000 characters [UTIL_LOG.LOG_MSG:76-78].
- The comment at [UTIL_LOG(body):9] says "all logging goes to LOG_TABLE, see install script"; the code writes to `AUDIT_LOG`, and no LOG_TABLE exists in legacy_code/ [UTIL_LOG.LOG_MSG:72].
- The comment at [UTIL_LOG(body):58] says `UTIL_LOG.LOG_MSG` "writes a line to the audit table. never fails."; the code writes the line only when the severity level reaches the session log level, and swallows every error raised inside it [UTIL_LOG.LOG_MSG:71] [UTIL_LOG.LOG_MSG:83-85].

## Error handling

| Unit | Line | Handler / raise | Effect for the caller |
|------|------|-----------------|-----------------------|
| `UTIL_LOG.GET_PARAM` | 44-45 | WHEN NO_DATA_FOUND | returns NULL when the parameter does not exist; other errors propagate |
| `UTIL_LOG.GET_PARAM_NUM` | 52-54 | WHEN VALUE_ERROR | returns `P_DEFAULT` when the stored value is not numeric; other errors from `UTIL_LOG.GET_PARAM` propagate |
| `UTIL_LOG.LOG_MSG` | 83-85 | WHEN OTHERS (swallow), ROLLBACK | the caller receives nothing: no exception, the log row is lost, and the caller's transaction is untouched |
| `UTIL_LOG.ARCHIVE_ROWS` | 147-150 | count mismatch: ROLLBACK, log, RETURN | no exception; the caller's whole open transaction has been rolled back |
| `UTIL_LOG.ARCHIVE_ROWS` | 130-155 | no handler | errors from either `EXECUTE IMMEDIATE`, or `VALUE_ERROR` when `P_TAB` is longer than 30 characters, propagate to the caller |
| `UTIL_LOG.HOUSEKEEPING` | 159-166 | no handler | errors from `UTIL_LOG.ARCHIVE_ROWS` or `INV_API.SEND_REMINDERS` propagate; after an archive error the reminders do not run |

If `UTIL_LOG.LOG_MSG` fails while loading the log level, `UTIL_LOG.G_LOG_LEVEL` stays NULL and the next call tries to load it again [UTIL_LOG.LOG_MSG:65-66] [UTIL_LOG.LOG_MSG:83-85]. No unit in the package calls `RAISE_APPLICATION_ERROR` or re-raises [UTIL_LOG(body):1-168].

## Open questions

1. Business purpose of the package and why logging, parameters, date helpers, formatting, archiving and housekeeping sit together: Unknown: needs human input [UTIL_LOG(spec):2].
2. Meaning of the severity codes `'I'`/`'W'`/`'E'` and of the levels 1/2/3 that `UTIL_LOG.LVL` maps them to, and of the `'LOG_LEVEL'` parameter values: Unknown: needs human input [UTIL_LOG.LVL:18-22] [UTIL_LOG.LOG_MSG:66-71].
3. The comment at [UTIL_LOG(body):9] names LOG_TABLE as the log destination, but the code writes to `AUDIT_LOG` [UTIL_LOG.LOG_MSG:72]. Is the comment outdated?
4. The comment at [UTIL_LOG(body):58] says "never fails"; rows below the log level are not written and every error is swallowed, so a failed log write is invisible [UTIL_LOG.LOG_MSG:71] [UTIL_LOG.LOG_MSG:83-85]. Is silent loss of log rows accepted?
5. `UTIL_LOG.HOUSEKEEPING` has no caller in legacy_code/; the comment at [UTIL_LOG(body):158] says "nightly job". Which scheduler or external caller runs it [UTIL_LOG.HOUSEKEEPING:159]? Elan (Confluence comment, 2026-10-31) says it runs every night at 02:00 as scheduler job HK_NIGHTLY [UTIL_LOG.HOUSEKEEPING:159]; no scheduler job is in legacy_code/ to confirm it.
6. Which tables do callers outside legacy_code/ pass to `UTIL_LOG.ARCHIVE_ROWS`? Its dynamic SQL is not in `table_usage.json`, and the literal `'AUDIT_LOG'` argument is not traced by the parser (docs/extraction-limitations.md) [UTIL_LOG.ARCHIVE_ROWS:138-144] [UTIL_LOG.HOUSEKEEPING:162].
7. `UTIL_LOG.ARCHIVE_ROWS` commits or rolls back the caller's whole transaction [UTIL_LOG.ARCHIVE_ROWS:147-153]. Is that intended for every caller: Unknown: needs human input [UTIL_LOG.ARCHIVE_ROWS:148] [UTIL_LOG.ARCHIVE_ROWS:153].
8. On a count mismatch `UTIL_LOG.ARCHIVE_ROWS` rolls back and returns without an exception, so the caller cannot tell it failed [UTIL_LOG.ARCHIVE_ROWS:147-150]. The insert and the delete each evaluate SYSDATE separately, so rows that cross the cut-off between the two statements can cause a mismatch [UTIL_LOG.ARCHIVE_ROWS:138-143]. Is this behaviour known and accepted?
9. `P_TAB` and `P_DATE_COL` are concatenated into SQL without a check [UTIL_LOG.ARCHIVE_ROWS:138-143]. Who may call `UTIL_LOG.ARCHIVE_ROWS` with which values: Unknown: needs human input.
10. No unit in legacy_code/ sets `UTIL_LOG.G_DEBUG` [UTIL_LOG.DBG:97]. Who sets it, if anyone: Unknown: needs human input.
11. `UTIL_LOG.G_CALL_CNT` is written but never read in legacy_code/ [UTIL_LOG.LOG_MSG:69]. Its purpose: Unknown: needs human input.
12. `UTIL_LOG.G_LOG_LEVEL` is cached for the session, so a change to `'LOG_LEVEL'` only affects new sessions [UTIL_LOG.LOG_MSG:65-67]. Is that intended?
13. `UTIL_LOG.SET_CTX` keeps the previous `UTIL_LOG.G_USER` when `P_USER` is NULL, so `'BATCH'` from `UTIL_LOG.HOUSEKEEPING` stays in the session and is used by `INV_API.REGISTER_PAYMENT` and `PKG_ORDER.NEW_ORDER` [UTIL_LOG.SET_CTX:29-31] [UTIL_LOG.HOUSEKEEPING:161]. Is that intended?
14. `UTIL_LOG.IS_WORKDAY` depends on the session's date language, which the parser cannot see (docs/extraction-limitations.md, runtime facts), and ignores holidays [UTIL_LOG.IS_WORKDAY:105]. Which calendar should count as workdays: Unknown: needs human input.
15. `UTIL_LOG.ADD_WORKDAYS` never ends for a NULL `P_DT` with a positive `P_DAYS` [UTIL_LOG.ADD_WORKDAYS:113-118]. Can callers pass a NULL date?
16. Why `UTIL_LOG.FMT_AMT` fixes `','` as decimal and `'.'` as group separator, and what happens to amounts above the mask's nine integer digits: Unknown: needs human input [UTIL_LOG.FMT_AMT:125].
17. Reason for the default of 90 days for `'AUDIT_KEEP_DAYS'`: Unknown: needs human input [UTIL_LOG.HOUSEKEEPING:162]. Elan (Confluence comment, 2026-10-31) says the 90 days is the retention period [UTIL_LOG.HOUSEKEEPING:162], and Elan (Confluence reply, 2026-10-31) says this is confirmed by retention policy RP-12; neither is in legacy_code/. The code archives `AUDIT_LOG` rows older than that number of days [UTIL_LOG.ARCHIVE_ROWS:138-143].
18. The comment at [UTIL_LOG.HOUSEKEEPING:163] says the orders archive was disabled in 2013 (ticket 4471); the commented-out call would need an archive table for `ORDERS` that does not exist in legacy_code/ [UTIL_LOG.HOUSEKEEPING:164]. Can the commented code be treated as obsolete?
19. `UTIL_LOG.LOG_ERR` only logs a meaningful error from inside an exception handler [UTIL_LOG.LOG_ERR:91]. Do callers outside legacy_code/ call it elsewhere?
20. The `C_SEV_*` constants exist but `UTIL_LOG.C_SEV_INFO` and `UTIL_LOG.C_SEV_WARN` have no reader in legacy_code/ [UTIL_LOG(spec):8-10]. Are they used by code outside legacy_code/?
