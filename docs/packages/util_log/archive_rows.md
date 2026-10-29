# `UTIL_LOG.ARCHIVE_ROWS`

| Field | Value |
|-------|-------|
| Package doc | [util_log](../util_log.md) |
| Kind | PROCEDURE |
| Visibility | PUBLIC |
| Spec | `legacy_code/packages/util_log.pks` line 32 |
| Body | `legacy_code/packages/util_log.pkb` lines 130-155 |

```sql
PROCEDURE ARCHIVE_ROWS(P_TAB IN VARCHAR2, P_DATE_COL IN VARCHAR2, P_DAYS IN NUMBER)
```

## Purpose

Copies the rows of a table named at runtime whose date column is older than `P_DAYS` days into the table with the same name plus `_ARCH`, deletes them from the source table, and commits, or rolls back when the copied and deleted counts differ [UTIL_LOG.ARCHIVE_ROWS:130-155]. The comment at [UTIL_LOG(body):129] says "moves rows older than p_days to <table>_ARCH"; the code agrees, with the age measured on the column named in `P_DATE_COL` and the archive row getting SYSDATE as an extra last column [UTIL_LOG.ARCHIVE_ROWS:138-139]. Which tables are meant to be archived this way: Unknown: needs human input.

## Parameters

| Name | Mode | Type | Default | Used for |
|------|------|------|---------|----------|
| `P_TAB` | IN | VARCHAR2 | - | trimmed and uppercased into `V_TAB` (max 30 characters), then concatenated as source table name and, with `_ARCH`, as archive table name [UTIL_LOG.ARCHIVE_ROWS:132] [UTIL_LOG.ARCHIVE_ROWS:138] [UTIL_LOG.ARCHIVE_ROWS:143] |
| `P_DATE_COL` | IN | VARCHAR2 | - | concatenated unchanged as the column compared with the cut-off date [UTIL_LOG.ARCHIVE_ROWS:139] [UTIL_LOG.ARCHIVE_ROWS:143] |
| `P_DAYS` | IN | NUMBER | - | bound as `:d`; cut-off is `SYSDATE - P_DAYS` [UTIL_LOG.ARCHIVE_ROWS:140] [UTIL_LOG.ARCHIVE_ROWS:144] |

## Logic walkthrough

1. `V_TAB` is set to `UPPER(TRIM(P_TAB))` in the declaration; a value longer than 30 characters raises `VALUE_ERROR` to the caller before any statement runs [UTIL_LOG.ARCHIVE_ROWS:132].
2. `UTIL_LOG.DBG` writes `'archive '` and the table name to `DBMS_OUTPUT` when `UTIL_LOG.G_DEBUG` is TRUE [UTIL_LOG.ARCHIVE_ROWS:136] [UTIL_LOG.DBG:97-99].
3. Dynamic `INSERT INTO <V_TAB>_ARCH SELECT t.*, SYSDATE FROM <V_TAB> t WHERE t.<P_DATE_COL> < SYSDATE - :d`; the row count goes to `V_INS` [UTIL_LOG.ARCHIVE_ROWS:138-141].
4. Dynamic `DELETE FROM <V_TAB> WHERE <P_DATE_COL> < SYSDATE - :d`; the row count goes to `V_DEL` [UTIL_LOG.ARCHIVE_ROWS:143-145]. SYSDATE is evaluated again in this second statement, so the cut-off can differ from step 3 [UTIL_LOG.ARCHIVE_ROWS:139] [UTIL_LOG.ARCHIVE_ROWS:143].
5. If `V_DEL` differs from `V_INS`: ROLLBACK of the whole session transaction, a log row with action `'ARCHIVE'`, the table name, `'count mismatch <ins>/<del>'` and severity `UTIL_LOG.C_SEV_ERR`, then RETURN without an exception [UTIL_LOG.ARCHIVE_ROWS:147-151].
6. Otherwise COMMIT of the whole session transaction, then a log row `'<n> rows archived'` with the default severity [UTIL_LOG.ARCHIVE_ROWS:153-154].

## Dependencies

| Direction | Unit / object | Kind | Line |
|-----------|---------------|------|------|
| calls | `UTIL_LOG.DBG` | CALL | 136 |
| calls | `UTIL_LOG.LOG_MSG` | CALL | 149 |
| calls | `UTIL_LOG.LOG_MSG` | CALL | 154 |
| called by | `UTIL_LOG.HOUSEKEEPING` | CALL | 162 |

## Tables touched

None found in metadata.

Both statements are dynamic SQL with table and column names built at runtime, so `table_usage.json` has no access for this unit [UTIL_LOG.ARCHIVE_ROWS:138-144]. The only caller in legacy_code/ passes `'AUDIT_LOG'` and `'LOG_TS'`, which at runtime means a read and a delete on `AUDIT_LOG` and an insert into `AUDIT_LOG_ARCH` [UTIL_LOG.HOUSEKEEPING:162]. No trigger exists on `AUDIT_LOG` or `AUDIT_LOG_ARCH` in `objects.json` [AUDIT_LOG:1-11] [AUDIT_LOG_ARCH:2-12]. Triggers on other tables passed by callers outside legacy_code/ cannot be determined [UTIL_LOG.ARCHIVE_ROWS:140-144].

## Side effects and risks

- COMMIT: commits everything the caller had open in the session, together with the archive statements [UTIL_LOG.ARCHIVE_ROWS:153].
- ROLLBACK: on a count mismatch undoes everything the caller had open in the session, not only the archive statements, and the caller gets no exception [UTIL_LOG.ARCHIVE_ROWS:147-150]. The mismatch log row is still kept, because `UTIL_LOG.LOG_MSG` is autonomous [UTIL_LOG.ARCHIVE_ROWS:149] [UTIL_LOG.LOG_MSG:63].
- Dynamic SQL: table and column names come from `P_TAB` and `P_DATE_COL` without any check, so any text passed in becomes part of the executed SQL [UTIL_LOG.ARCHIVE_ROWS:138-144].
- `SELECT t.*` requires the archive table to have the source columns in the same order plus one date column at the end [UTIL_LOG.ARCHIVE_ROWS:138]. The comment at [legacy_code/tables/audit_log_arch.sql:1] says "same layout as audit_log + arch_dt (must stay in sync!)", and the current DDL matches that [AUDIT_LOG_ARCH:2-12] [AUDIT_LOG:1-11].
- Package state read through `UTIL_LOG.DBG`: `UTIL_LOG.G_DEBUG` and `UTIL_LOG.G_MODULE` [UTIL_LOG.DBG:97-98].

## Error handling

| Line | Handler / raise | Effect for the caller |
|------|-----------------|-----------------------|
| 132 | none (declaration) | `VALUE_ERROR` propagates when `P_TAB` is longer than 30 characters |
| 140 | none | an error in the insert propagates; nothing of this unit is committed |
| 144 | none | an error in the delete propagates; the rows inserted at line 140 stay uncommitted in the caller's transaction |
| 147-151 | count mismatch, ROLLBACK, RETURN | no exception; the caller's whole transaction has been rolled back |

## Open questions

1. Which tables do callers outside legacy_code/ pass, and do triggers exist on them: Unknown: needs human input [UTIL_LOG.ARCHIVE_ROWS:138-144].
2. Committing or rolling back the caller's whole transaction: intended for every caller: Unknown: needs human input [UTIL_LOG.ARCHIVE_ROWS:148] [UTIL_LOG.ARCHIVE_ROWS:153].
3. A count mismatch is only logged, not raised [UTIL_LOG.ARCHIVE_ROWS:147-151]. Is that accepted?
4. The two statements evaluate SYSDATE separately, which can make the counts differ for rows near the cut-off [UTIL_LOG.ARCHIVE_ROWS:139] [UTIL_LOG.ARCHIVE_ROWS:143]. Has that been seen in practice?
5. `P_TAB` and `P_DATE_COL` are not checked before being concatenated into SQL [UTIL_LOG.ARCHIVE_ROWS:138-143]. Who may call this procedure: Unknown: needs human input.
