# `CUST_MGMT.BLOCK_CUSTOMER`

| Field | Value |
|-------|-------|
| Package doc | [cust_mgmt](../cust_mgmt.md) |
| Kind | PROCEDURE |
| Visibility | PUBLIC |
| Spec | `legacy_code/packages/cust_mgmt.pks` line 14 |
| Body | `legacy_code/packages/cust_mgmt.pkb` lines 98-114 |

```sql
PROCEDURE BLOCK_CUSTOMER(P_CUST_ID IN NUMBER, P_REASON IN VARCHAR2)
```

## Purpose

The procedure sets a customer's `STATUS` to `'B'`, changes the `ORD_STATUS` of some of the customer's orders to 15, writes a log line and commits [CUST_MGMT.BLOCK_CUSTOMER:98-114].
Why a customer is blocked and what the status values mean is Unknown: needs human input.

## Parameters

| Name | Mode | Type | Default | Used for |
|------|------|------|---------|----------|
| `P_CUST_ID` | IN | NUMBER | - | Selects the `CUSTOMERS` row and the `ORDERS` rows; also logged as the object id [CUST_MGMT.BLOCK_CUSTOMER:104] [CUST_MGMT.BLOCK_CUSTOMER:109] [CUST_MGMT.BLOCK_CUSTOMER:112] |
| `P_REASON` | IN | VARCHAR2 | - | First 200 characters stored in `BLOCKED_REASON`; passed in full as the log message [CUST_MGMT.BLOCK_CUSTOMER:103] [CUST_MGMT.BLOCK_CUSTOMER:112] |

## Logic walkthrough

1. Update `CUSTOMERS`: `STATUS` = `'B'`, `BLOCKED_REASON` = `SUBSTR(P_REASON, 1, 200)` for `CUST_ID` = `P_CUST_ID`, whatever the current status [CUST_MGMT.BLOCK_CUSTOMER:101-104].
2. `TRG_CUST_BIU` fires on that row: it upper-cases `CUST_NAME`, sets `UPD_DT` and `UPD_BY`, and sets `CREDIT_LIMIT` to 0 because the new status is `'B'` [TRG_CUST_BIU:12-14] [TRG_CUST_BIU:22-24].
3. The trigger does not insert into `CUST_HIST`, because that branch requires `UPDATING('CREDIT_LIMIT')` and the SET list of step 1 does not name `CREDIT_LIMIT` [TRG_CUST_BIU:17] [CUST_MGMT.BLOCK_CUSTOMER:102-103].
4. Update `ORDERS`: `ORD_STATUS` = 15 for the customer's orders with `ORD_STATUS` 10 or 20 [CUST_MGMT.BLOCK_CUSTOMER:107-110].
5. The comment at [CUST_MGMT.BLOCK_CUSTOMER:106] says "put open orders on hold"; the code changes statuses 10 and 20 to 15, and whether that is "on hold" is Unknown: needs human input.
6. Call `UTIL_LOG.LOG_MSG` with action `'BLOCK'`, the customer id, `P_REASON` and severity `'W'` [CUST_MGMT.BLOCK_CUSTOMER:112].
7. `COMMIT` [CUST_MGMT.BLOCK_CUSTOMER:113].

No step checks that the customer exists; with no matching rows, steps 6 and 7 still run [CUST_MGMT.BLOCK_CUSTOMER:101-113].

## Dependencies

| Direction | Unit / object | Kind | Line |
|-----------|---------------|------|------|
| calls | `TRG_CUST_BIU` | FIRES_TRIGGER | 101 |
| calls | `UTIL_LOG.LOG_MSG` | CALL | 112 |
| called by | `CUST_MGMT.CHK_OVERDUE_CUSTOMERS` | CALL | 239 |

## Tables touched

| Table / view | Operation | Line | Via |
|--------------|-----------|------|-----|
| `CUSTOMERS` | UPDATE | 101 | STATIC |
| `ORDERS` | UPDATE | 107 | STATIC |

`TRG_CUST_BIU` writes `:NEW` columns of the same `CUSTOMERS` row, including `CREDIT_LIMIT` = 0 [TRG_CUST_BIU:12-24].
`UTIL_LOG.LOG_MSG` inserts into `AUDIT_LOG` in an autonomous transaction [UTIL_LOG.LOG_MSG:63] [UTIL_LOG.LOG_MSG:72].
The metadata has no FIRES_TRIGGER edge for the `ORDERS` update [CUST_MGMT.BLOCK_CUSTOMER:107].

## Side effects and risks

- COMMIT: the `COMMIT` at line 113 commits the two updates and all other uncommitted work of the caller's transaction; the caller cannot roll any of it back afterwards [CUST_MGMT.BLOCK_CUSTOMER:113].
- When called from `CUST_MGMT.CHK_OVERDUE_CUSTOMERS`, the commit runs once per customer, inside its open cursor loop [CUST_MGMT.CHK_OVERDUE_CUSTOMERS:236-241].
- The `AUDIT_LOG` line is committed separately and survives even if the commit at line 113 is never reached [UTIL_LOG.LOG_MSG:63] [UTIL_LOG.LOG_MSG:82].
- Hardcoded values: `'B'` at line 102, 15 at line 108, 10 and 20 at line 110, 200 at line 103 [CUST_MGMT.BLOCK_CUSTOMER:102-110]; their meaning is Unknown: needs human input.
- Blocking leaves `CREDIT_LIMIT` at 0 (set by the trigger); `CUST_MGMT.UNBLOCK_CUSTOMER` does not restore it [TRG_CUST_BIU:22-24] [CUST_MGMT.UNBLOCK_CUSTOMER:120-124].

## Error handling

| Line | Handler / raise | Effect for the caller |
|------|-----------------|-----------------------|
| 98-114 | no exception section | An error in either UPDATE goes to the caller before the `COMMIT`; the caller decides whether to roll back |
| 112 | `UTIL_LOG.LOG_MSG` swallows its own errors | A logging failure does not stop the commit [UTIL_LOG.LOG_MSG:83-85] |

## Open questions

1. What do status `'B'` and `ORD_STATUS` 10, 15 and 20 mean? Unknown: needs human input [CUST_MGMT.BLOCK_CUSTOMER:102] [CUST_MGMT.BLOCK_CUSTOMER:108-110].
2. Do callers outside legacy_code/ expect their open work to be committed by this procedure [CUST_MGMT.BLOCK_CUSTOMER:113]?
3. Should blocking a customer that is already `'B'` or `'C'` be possible? The UPDATE has no status filter [CUST_MGMT.BLOCK_CUSTOMER:101-104].
4. Is the credit limit of 0 left after unblocking intended [TRG_CUST_BIU:22-24]?
