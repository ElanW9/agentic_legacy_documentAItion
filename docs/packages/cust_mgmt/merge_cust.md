# `CUST_MGMT.MERGE_CUST`

| Field | Value |
|-------|-------|
| Package doc | [cust_mgmt](../cust_mgmt.md) |
| Kind | PROCEDURE |
| Visibility | PRIVATE |
| Spec | none (private) |
| Body | `legacy_code/packages/cust_mgmt.pkb` lines 19-33 |

```sql
PROCEDURE MERGE_CUST(P_FROM IN NUMBER, P_TO IN NUMBER)
```

## Purpose

The procedure moves `ORDERS` and `INVOICES` from customer `P_FROM` to customer `P_TO` and sets the status of `P_FROM` to `'C'` [CUST_MGMT.MERGE_CUST:19-33].
The comment at [CUST_MGMT(body):18] says "merge duplicate customers (called from nightly batch)"; the unit is private and nothing in the package calls it, so the code cannot be reached and the "called from" part does not match the code [CUST_MGMT.MERGE_CUST:19].

## Parameters

| Name | Mode | Type | Default | Used for |
|------|------|------|---------|----------|
| `P_FROM` | IN | NUMBER | - | Customer whose orders and invoices are moved and whose status is set to `'C'` [CUST_MGMT.MERGE_CUST:24] [CUST_MGMT.MERGE_CUST:28] [CUST_MGMT.MERGE_CUST:32] |
| `P_TO` | IN | NUMBER | - | New `CUST_ID` on the moved rows [CUST_MGMT.MERGE_CUST:23] [CUST_MGMT.MERGE_CUST:27] |

## Logic walkthrough

1. Update `ORDERS`: `CUST_ID` = `P_TO` where `CUST_ID` = `P_FROM` [CUST_MGMT.MERGE_CUST:22-24].
2. Update `INVOICES`: `CUST_ID` = `P_TO` where `CUST_ID` = `P_FROM` [CUST_MGMT.MERGE_CUST:26-28].
3. Update `CUSTOMERS`: `STATUS` = `'C'` where `CUST_ID` = `P_FROM` [CUST_MGMT.MERGE_CUST:30-32].
4. `TRG_CUST_BIU` fires on step 3 and sets `UPD_DT`, `UPD_BY` and the upper-cased `CUST_NAME`; it writes no `CUST_HIST` row because `CREDIT_LIMIT` is not in the SET list [TRG_CUST_BIU:12-17].

There is no check that `P_TO` exists, no COMMIT and no log call [CUST_MGMT.MERGE_CUST:19-33].

## Dependencies

| Direction | Unit / object | Kind | Line |
|-----------|---------------|------|------|
| calls | `TRG_CUST_BIU` | FIRES_TRIGGER | 30 |

There is no caller in legacy_code/, and as a PRIVATE unit it cannot be called from outside the package [CUST_MGMT.MERGE_CUST:19].

## Tables touched

| Table / view | Operation | Line | Via |
|--------------|-----------|------|-----|
| `ORDERS` | UPDATE | 22 | STATIC |
| `INVOICES` | UPDATE | 26 | STATIC |
| `CUSTOMERS` | UPDATE | 30 | STATIC |

The metadata has no FIRES_TRIGGER edge for the `ORDERS` and `INVOICES` updates [CUST_MGMT.MERGE_CUST:22-28].

## Side effects and risks

- NO_CALLER: private and unreachable; the code never runs as the package stands [CUST_MGMT.MERGE_CUST:19].
- Hardcoded value `'C'` at line 31 [CUST_MGMT.MERGE_CUST:31]; its meaning is Unknown: needs human input.
- If it were called, its updates would stay in the caller's transaction, as it has no transaction control [CUST_MGMT.MERGE_CUST:19-33].

## Error handling

| Line | Handler / raise | Effect for the caller |
|------|-----------------|-----------------------|
| 19-33 | no exception section | Errors would go to the caller |

## Open questions

1. Was this procedure ever called by a nightly batch, as the comment at [CUST_MGMT(body):18] says, and can it be removed [CUST_MGMT.MERGE_CUST:19]?
2. What does status `'C'` mean? Unknown: needs human input [CUST_MGMT.MERGE_CUST:31].
