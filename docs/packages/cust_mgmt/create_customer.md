# `CUST_MGMT.CREATE_CUSTOMER`

| Field | Value |
|-------|-------|
| Package doc | [cust_mgmt](../cust_mgmt.md) |
| Kind | PROCEDURE |
| Visibility | PUBLIC |
| Spec | `legacy_code/packages/cust_mgmt.pks` lines 5-10 |
| Body | `legacy_code/packages/cust_mgmt.pkb` lines 36-76 |

```sql
PROCEDURE CREATE_CUSTOMER(P_NAME IN VARCHAR2, P_TYPE IN CHAR, P_VAT IN VARCHAR2, P_EMAIL IN VARCHAR2, P_CTRY IN VARCHAR2, P_CUST_ID OUT NUMBER)
```

## Purpose

The procedure inserts one `CUSTOMERS` row with a new id from `SEQ_CUSTOMERS`, after a duplicate check on the VAT number, and returns the id in `P_CUST_ID` [CUST_MGMT.CREATE_CUSTOMER:36-76].
The business rules behind the defaults are Unknown: needs human input.

## Parameters

| Name | Mode | Type | Default | Used for |
|------|------|------|---------|----------|
| `P_NAME` | IN | VARCHAR2 | - | Inserted as `CUST_NAME`; `TRG_CUST_BIU` upper-cases and trims it [CUST_MGMT.CREATE_CUSTOMER:72] [TRG_CUST_BIU:12] |
| `P_TYPE` | IN | CHAR | - | Chooses the credit limit; inserted as `NVL(P_TYPE, 'R')` [CUST_MGMT.CREATE_CUSTOMER:60-66] [CUST_MGMT.CREATE_CUSTOMER:72] |
| `P_VAT` | IN | VARCHAR2 | - | Duplicate check and `VAT_NO`, upper-cased with spaces removed [CUST_MGMT.CREATE_CUSTOMER:48-57] [CUST_MGMT.CREATE_CUSTOMER:72] |
| `P_EMAIL` | IN | VARCHAR2 | - | Inserted lower-cased as `EMAIL` [CUST_MGMT.CREATE_CUSTOMER:73] |
| `P_CTRY` | IN | VARCHAR2 | - | Inserted as `NVL(P_CTRY, 'BE')` into `COUNTRY_CD` [CUST_MGMT.CREATE_CUSTOMER:73] |
| `P_CUST_ID` | OUT | NUMBER | - | Receives `SEQ_CUSTOMERS.NEXTVAL`; used as `CUST_ID` and as the log object id [CUST_MGMT.CREATE_CUSTOMER:68] [CUST_MGMT.CREATE_CUSTOMER:72] [CUST_MGMT.CREATE_CUSTOMER:75] |

## Logic walkthrough

1. Call `UTIL_LOG.SET_CTX('CUST_MGMT')`, which sets the session variable `UTIL_LOG.G_MODULE` [CUST_MGMT.CREATE_CUSTOMER:46] [UTIL_LOG.SET_CTX:28].
2. If `P_VAT` is not NULL, count `CUSTOMERS` rows with the same normalised `VAT_NO`; if any exist, raise `-20010` [CUST_MGMT.CREATE_CUSTOMER:48-57].
3. Credit limit: 20000 when `P_TYPE` is `'W'`, NULL when it is `'G'`, 2500 in every other case, NULL included [CUST_MGMT.CREATE_CUSTOMER:60-66].
4. The comment at [CUST_MGMT.CREATE_CUSTOMER:59] says "default limit: 5000, wholesale 20000"; the code uses 2500 as the default, so the comment does not match the code [CUST_MGMT.CREATE_CUSTOMER:65].
5. Take `SEQ_CUSTOMERS.NEXTVAL` into `P_CUST_ID` [CUST_MGMT.CREATE_CUSTOMER:68].
6. Insert the row with `STATUS` `'A'` and the limit from step 3 [CUST_MGMT.CREATE_CUSTOMER:70-73].
7. `TRG_CUST_BIU` fires: `CUST_ID` is already set so the trigger does not take a sequence value; it sets `CREATED_DT`, `UPD_DT`, `UPD_BY` and upper-cases `CUST_NAME` [TRG_CUST_BIU:5-14].
8. Call `UTIL_LOG.LOG_MSG('CREATE', ...)` [CUST_MGMT.CREATE_CUSTOMER:75].

## Dependencies

| Direction | Unit / object | Kind | Line |
|-----------|---------------|------|------|
| calls | `UTIL_LOG.SET_CTX` | CALL | 46 |
| calls | `SEQ_CUSTOMERS` | SEQUENCE_USE | 68 |
| calls | `TRG_CUST_BIU` | FIRES_TRIGGER | 70 |
| calls | `UTIL_LOG.LOG_MSG` | CALL | 75 |

There is no caller in legacy_code/ [CUST_MGMT.CREATE_CUSTOMER:36].

## Tables touched

| Table / view | Operation | Line | Via |
|--------------|-----------|------|-----|
| `CUSTOMERS` | SELECT | 51 | STATIC |
| `CUSTOMERS` | INSERT | 70 | STATIC |

`TRG_CUST_BIU` writes only `:NEW` columns on INSERT; its `CUST_HIST` insert is limited to UPDATE [TRG_CUST_BIU:5-19].
`UTIL_LOG.LOG_MSG` inserts into `AUDIT_LOG` in an autonomous transaction [UTIL_LOG.LOG_MSG:63] [UTIL_LOG.LOG_MSG:72].

## Side effects and risks

- No COMMIT: the new row stays uncommitted until the caller commits [CUST_MGMT.CREATE_CUSTOMER:36-76].
- The "customer created" log line is committed on its own and survives a rollback by the caller [CUST_MGMT.CREATE_CUSTOMER:75] [UTIL_LOG.LOG_MSG:82].
- `UTIL_LOG.G_MODULE` keeps the value `'CUST_MGMT'` for the rest of the session, also for logging by other packages [UTIL_LOG.SET_CTX:28].
- The duplicate check is a `COUNT(*)` before the INSERT; the table script declares no unique constraint on `VAT_NO` [CUST_MGMT.CREATE_CUSTOMER:49-56] [CUSTOMERS:14-16].
- Hardcoded values: `'W'`, 20000, `'G'`, 2500, `'R'`, `'BE'`, `'A'` at lines 60-73 [CUST_MGMT.CREATE_CUSTOMER:60-73]; their meaning is Unknown: needs human input.
- No caller in legacy_code/; it may be called from outside the source tree [CUST_MGMT.CREATE_CUSTOMER:36].

## Error handling

| Line | Handler / raise | Effect for the caller |
|------|-----------------|-----------------------|
| 55 | RAISE_APPLICATION_ERROR(-20010, 'Customer with VAT ... exists') | Raised to the caller before any insert |
| 36-76 | no exception section | Errors from the INSERT, for example the `CUST_TYPE` check constraint for a `P_TYPE` other than R/W/G, go to the caller [CUSTOMERS:15] |

## Open questions

1. Which default credit limit is intended: 2500 in the code, 5000 in the comment and in the column default [CUST_MGMT.CREATE_CUSTOMER:59-65] [CUSTOMERS:8]?
2. Does a NULL limit for type `'G'` mean "no limit"? Unknown: needs human input [CUST_MGMT.CREATE_CUSTOMER:62-63].
3. Who calls this procedure from outside legacy_code/ [CUST_MGMT.CREATE_CUSTOMER:36]?
