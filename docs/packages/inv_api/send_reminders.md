# `INV_API.SEND_REMINDERS`

| Field | Value |
|-------|-------|
| Package doc | [inv_api](../inv_api.md) |
| Kind | PROCEDURE |
| Visibility | PUBLIC |
| Spec | `legacy_code/packages/inv_api.pks` line 22 |
| Body | `legacy_code/packages/inv_api.pkb` lines 224-246 |

```sql
PROCEDURE SEND_REMINDERS
```

## Purpose

Logs a reminder line and increments `INVOICES.REMINDER_CNT` for every open or partly paid invoice more than 14 days overdue whose customer has an email, commits, and then calls `CUST_MGMT.CHK_OVERDUE_CUSTOMERS` [INV_API.SEND_REMINDERS:224-246].
The business reason for the 14-day threshold is Unknown: needs human input.

## Parameters

None found in metadata.

## Logic walkthrough

1. Loops over `V_OPEN_INVOICES` rows with `V_OPEN_INVOICES.DAYS_OVERDUE` above 14 [INV_API.SEND_REMINDERS:227-229].
2. `V_OPEN_INVOICES` holds invoices with status 'OPEN' or 'PART', and computes days overdue as today minus the due date [V_OPEN_INVOICES:11-14].
3. Reads the customer's 'EMAIL' through `CUST_MGMT.GET_CUST_ATTR`, which returns NULL on any error [INV_API.SEND_REMINDERS:230] [CUST_MGMT.GET_CUST_ATTR:221-223].
4. When the email is not NULL, logs a 'REMINDER' line with the invoice number, email and open amount, and adds 1 to `INVOICES.REMINDER_CNT` [INV_API.SEND_REMINDERS:232-240].
5. The comment at [INV_API.SEND_REMINDERS:233] says "TODO: real mail sending, for now only logged"; the code agrees, as nothing but `UTIL_LOG.LOG_MSG` is called [INV_API.SEND_REMINDERS:234-235].
6. Commits after the loop [INV_API.SEND_REMINDERS:243].
7. Calls `CUST_MGMT.CHK_OVERDUE_CUSTOMERS` after the commit [INV_API.SEND_REMINDERS:245].

## Dependencies

| Direction | Unit / object | Kind | Line |
|-----------|---------------|------|------|
| calls | `CUST_MGMT.GET_CUST_ATTR` | CALL | 230 |
| calls | `UTIL_LOG.LOG_MSG` | CALL | 234 |
| calls | `UTIL_LOG.FMT_AMT` | CALL | 235 |
| calls | `CUST_MGMT.CHK_OVERDUE_CUSTOMERS` | CALL | 245 |
| called by | `UTIL_LOG.HOUSEKEEPING` | CALL | 165 |

## Tables touched

| Table / view | Operation | Line | Via |
|--------------|-----------|------|-----|
| `V_OPEN_INVOICES` | SELECT | 228 | STATIC |
| `INVOICES` | UPDATE | 237 | STATIC |

`CUSTOMERS` is read through dynamic SQL in `CUST_MGMT.GET_CUST_ATTR`, which table_usage cannot see for this unit [CUST_MGMT.GET_CUST_ATTR:216].
No FIRES_TRIGGER edge exists for this unit [INV_API.SEND_REMINDERS:237].

## Side effects and risks

- The COMMIT at line 243 commits all reminder-count increments and any uncommitted work of the caller [INV_API.SEND_REMINDERS:243].
- The writes made by `CUST_MGMT.CHK_OVERDUE_CUSTOMERS` happen after that COMMIT and are not committed by this unit [INV_API.SEND_REMINDERS:245].
- The reminder log lines are written in an autonomous transaction, so they survive even if the increment or the COMMIT does not happen [UTIL_LOG.LOG_MSG:63] [INV_API.SEND_REMINDERS:234-239].
- Every run adds 1 again for every invoice still overdue, and `INVOICES.REMINDER_CNT` is NUMBER(2) [INV_API.SEND_REMINDERS:237-239] [INVOICES:13].
- Hardcoded value 14; its meaning is Unknown: needs human input.

## Error handling

| Line | Handler / raise | Effect for the caller |
|------|-----------------|-----------------------|
| 224-246 | no handler | any error reaches the caller; an error in the loop comes before the COMMIT, so the increments made so far are not committed by this unit |

## Open questions

1. What does the 14-day threshold mean? Unknown: needs human input [INV_API.SEND_REMINDERS:229].
2. Is the missing mail sending, noted in the TODO comment, still open [INV_API.SEND_REMINDERS:233]?
3. What should happen when `INVOICES.REMINDER_CNT` reaches the NUMBER(2) limit [INVOICES:13]?
4. Should the COMMIT also cover the work of `CUST_MGMT.CHK_OVERDUE_CUSTOMERS` [INV_API.SEND_REMINDERS:243-245]?
