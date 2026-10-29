# `UTIL_LOG.LOG_MSG`

| Field | Value |
|-------|-------|
| Package doc | [util_log](../util_log.md) |
| Kind | PROCEDURE |
| Visibility | PUBLIC |
| Spec | `legacy_code/packages/util_log.pks` lines 14-17 |
| Body | `legacy_code/packages/util_log.pkb` lines 59-86 |

```sql
PROCEDURE LOG_MSG(P_ACTION IN VARCHAR2, P_OBJ_ID IN VARCHAR2, P_MSG IN VARCHAR2, P_SEV IN CHAR DEFAULT 'I')
```

## Purpose

Writes one row to `AUDIT_LOG` in an autonomous transaction when the level of `P_SEV` reaches the session log level, and never raises an error to the caller [UTIL_LOG.LOG_MSG:63-86]. The comment at [UTIL_LOG(body):58] says "writes a line to the audit table. never fails."; the code agrees that errors are swallowed, but writes the line only when the level check passes [UTIL_LOG.LOG_MSG:71] [UTIL_LOG.LOG_MSG:83-85]. Why log rows must survive a rollback by the caller: Unknown: needs human input.

## Parameters

| Name | Mode | Type | Default | Used for |
|------|------|------|---------|----------|
| `P_ACTION` | IN | VARCHAR2 | - | first 30 characters go to `AUDIT_LOG.ACTION` [UTIL_LOG.LOG_MSG:76] |
| `P_OBJ_ID` | IN | VARCHAR2 | - | first 50 characters go to `AUDIT_LOG.OBJ_ID` [UTIL_LOG.LOG_MSG:77] |
| `P_MSG` | IN | VARCHAR2 | - | first 4000 characters go to `AUDIT_LOG.MSG` [UTIL_LOG.LOG_MSG:78] |
| `P_SEV` | IN | CHAR | `'I'` | mapped to a level by `UTIL_LOG.LVL` for the filter, and stored unchanged in `AUDIT_LOG.SEV` [UTIL_LOG.LOG_MSG:71] [UTIL_LOG.LOG_MSG:80] |

## Logic walkthrough

1. `PRAGMA AUTONOMOUS_TRANSACTION`: everything below runs in a transaction of its own, separate from the caller's [UTIL_LOG.LOG_MSG:63].
2. If `UTIL_LOG.G_LOG_LEVEL` is NULL (first call in the session, or an earlier failed load), it is loaded with `UTIL_LOG.GET_PARAM_NUM('LOG_LEVEL', 1)`, so a missing or non-numeric parameter gives level 1 [UTIL_LOG.LOG_MSG:65-67]. The seed data stores `'1'` for this parameter [legacy_code/tables/app_params.sql:8].
3. `UTIL_LOG.G_CALL_CNT` is incremented on every call that gets this far, whether or not a row is written [UTIL_LOG.LOG_MSG:69].
4. If `UTIL_LOG.LVL(P_SEV)` (3 for `'E'`, 2 for `'W'`, 1 for anything else) is at least `UTIL_LOG.G_LOG_LEVEL`, one row is inserted into `AUDIT_LOG` [UTIL_LOG.LOG_MSG:71-81] [UTIL_LOG.LVL:18-22]. The row gets `AUDIT_LOG_SEQ.NEXTVAL` as `LOG_ID`, SYSTIMESTAMP as `LOG_TS`, `UTIL_LOG.G_MODULE` as `MODULE`, the truncated parameters, `NVL(UTIL_LOG.G_USER, USER)` as `USR` and `P_SEV` as `SEV` [UTIL_LOG.LOG_MSG:72-80].
5. COMMIT, also when no row was inserted; it commits only the autonomous transaction [UTIL_LOG.LOG_MSG:82].
6. `WHEN OTHERS`: ROLLBACK of the autonomous transaction and normal return, so the error is not propagated [UTIL_LOG.LOG_MSG:83-85].

## Dependencies

| Direction | Unit / object | Kind | Line |
|-----------|---------------|------|------|
| calls | `UTIL_LOG.GET_PARAM_NUM` | CALL | 66 |
| calls | `UTIL_LOG.LVL` | CALL | 71 |
| calls | `AUDIT_LOG_SEQ` | SEQUENCE_USE | 73 |
| called by | `CUST_MGMT.CREATE_CUSTOMER` | CALL | 75 |
| called by | `CUST_MGMT.UPD_CREDIT_LIMIT` | CALL | 91 |
| called by | `CUST_MGMT.BLOCK_CUSTOMER` | CALL | 112 |
| called by | `CUST_MGMT.UNBLOCK_CUSTOMER` | CALL | 126 |
| called by | `INV_API.CREATE_INVOICE#2` | CALL | 95 |
| called by | `INV_API.CREATE_INVOICE#2` | CALL | 121 |
| called by | `INV_API.CANCEL_INVOICE` | CALL | 149 |
| called by | `INV_API.REGISTER_PAYMENT` | CALL | 188 |
| called by | `INV_API.SEND_REMINDERS` | CALL | 234 |
| called by | `PKG_ORDER.WLOG` | CALL | 13 |
| called by | `UTIL_LOG.LOG_ERR` | CALL | 91 |
| called by | `UTIL_LOG.ARCHIVE_ROWS` | CALL | 149 |
| called by | `UTIL_LOG.ARCHIVE_ROWS` | CALL | 154 |

## Tables touched

| Table / view | Operation | Line | Via |
|--------------|-----------|------|-----|
| `AUDIT_LOG` | INSERT | 72 | STATIC |

`APP_PARAMS` is read indirectly through `UTIL_LOG.GET_PARAM_NUM` and `UTIL_LOG.GET_PARAM` [UTIL_LOG.LOG_MSG:66] [UTIL_LOG.GET_PARAM:38-41]. No trigger exists on `AUDIT_LOG` in `objects.json`, and there is no FIRES_TRIGGER edge for this unit [AUDIT_LOG:1-11].

## Side effects and risks

- Autonomous transaction: the inserted log row is committed on its own and survives a rollback by the caller; the caller's open work is neither committed nor rolled back by the COMMIT or the ROLLBACK here [UTIL_LOG.LOG_MSG:63] [UTIL_LOG.LOG_MSG:82] [UTIL_LOG.LOG_MSG:85].
- Package state read: `UTIL_LOG.G_LOG_LEVEL`, `UTIL_LOG.G_CALL_CNT`, `UTIL_LOG.G_MODULE`, `UTIL_LOG.G_USER` [UTIL_LOG.LOG_MSG:65] [UTIL_LOG.LOG_MSG:69] [UTIL_LOG.LOG_MSG:75] [UTIL_LOG.LOG_MSG:79].
- Package state written: `UTIL_LOG.G_LOG_LEVEL` once per session and `UTIL_LOG.G_CALL_CNT` on every call; both persist between calls in the session [UTIL_LOG.LOG_MSG:66] [UTIL_LOG.LOG_MSG:69]. A change to the `'LOG_LEVEL'` parameter is not seen by a session that already loaded the level [UTIL_LOG.LOG_MSG:65-67].
- The values in `MODULE` and `USR` come from whatever `UTIL_LOG.SET_CTX` (or other code in the session) last set, which can be a value left over from an earlier call [UTIL_LOG.LOG_MSG:75] [UTIL_LOG.LOG_MSG:79] [UTIL_LOG.SET_CTX:28-31].
- Text longer than the column sizes is cut off without notice [UTIL_LOG.LOG_MSG:76-78].
- Hardcoded default level 1 for `'LOG_LEVEL'` [UTIL_LOG.LOG_MSG:66]; its meaning: Unknown: needs human input.

## Error handling

| Line | Handler / raise | Effect for the caller |
|------|-----------------|-----------------------|
| 83-85 | WHEN OTHERS, ROLLBACK, no RAISE | the caller receives nothing: no exception, the log row is lost, the caller's transaction is untouched |

An error while loading the level (line 66) also lands in this handler and leaves `UTIL_LOG.G_LOG_LEVEL` NULL, so the next call tries again [UTIL_LOG.LOG_MSG:65-66] [UTIL_LOG.LOG_MSG:83-85].

## Open questions

1. Meaning of the severity codes and levels, and of the default level 1: Unknown: needs human input [UTIL_LOG.LOG_MSG:66-71] [UTIL_LOG.LVL:18-22].
2. Why log rows must survive the caller's rollback: Unknown: needs human input [UTIL_LOG.LOG_MSG:63].
3. Every error is swallowed, so a failed log write is invisible to the caller [UTIL_LOG.LOG_MSG:83-85]. Is that accepted?
4. `UTIL_LOG.G_CALL_CNT` is incremented but never read in legacy_code/ [UTIL_LOG.LOG_MSG:69]. Is it read from outside legacy_code/?
