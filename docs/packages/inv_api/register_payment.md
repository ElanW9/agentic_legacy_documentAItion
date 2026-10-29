# `INV_API.REGISTER_PAYMENT`

| Field | Value |
|-------|-------|
| Package doc | [inv_api](../inv_api.md) |
| Kind | PROCEDURE |
| Visibility | PUBLIC |
| Spec | `legacy_code/packages/inv_api.pks` line 13-16 |
| Body | `legacy_code/packages/inv_api.pkb` lines 164-202 |

```sql
PROCEDURE REGISTER_PAYMENT(P_INV_ID IN NUMBER, P_AMT IN NUMBER, P_METHOD IN VARCHAR2 DEFAULT 'BT', P_REF IN VARCHAR2 DEFAULT NULL)
```

## Purpose

Inserts one `PAYMENTS` row for an invoice, which makes `TRG_PAY_AIR` update the invoice and possibly the order, and then commits, or rolls back and raises for a cash payment above 3000 [INV_API.REGISTER_PAYMENT:164-202].
The business reason for the checks is Unknown: needs human input.

## Parameters

| Name | Mode | Type | Default | Used for |
|------|------|------|---------|----------|
| `P_INV_ID` | IN | NUMBER | - | invoice that is read and that the payment row points to [INV_API.REGISTER_PAYMENT:172] [INV_API.REGISTER_PAYMENT:182] |
| `P_AMT` | IN | NUMBER | - | `PAYMENTS.PAY_AMT`, and compared with 3000 for method 'CA' [INV_API.REGISTER_PAYMENT:182] [INV_API.REGISTER_PAYMENT:193] |
| `P_METHOD` | IN | VARCHAR2 | 'BT' | must be 'BT', 'CC' or 'CA'; stored in `PAYMENTS.PAY_METHOD` [INV_API.REGISTER_PAYMENT:177] [INV_API.REGISTER_PAYMENT:182] |
| `P_REF` | IN | VARCHAR2 | NULL | stored in `PAYMENTS.REF_TXT` [INV_API.REGISTER_PAYMENT:182] |

## Logic walkthrough

1. Calls `UTIL_LOG.SET_CTX` with 'INV_API', which sets the `UTIL_LOG` module for the rest of the session [INV_API.REGISTER_PAYMENT:170] [UTIL_LOG.SET_CTX:28].
2. Reads the whole `INVOICES` row; when it does not exist, NO_DATA_FOUND goes to the handler at line 200 [INV_API.REGISTER_PAYMENT:172] [INV_API.REGISTER_PAYMENT:199-201].
3. Raises -20201 'Invoice cancelled' when `INVOICES.INV_STATUS` is 'CANC' [INV_API.REGISTER_PAYMENT:174-176].
4. Raises -20202 'Unknown payment method' when `P_METHOD` is not 'BT', 'CC' or 'CA'; a NULL method passes, because `NOT IN` with NULL is not true [INV_API.REGISTER_PAYMENT:177-179].
5. Inserts into `PAYMENTS` with an id from `PAY_ID_SEQ`, SYSDATE, `P_AMT`, `P_METHOD`, `P_REF`, and `UTIL_LOG.G_USER` or USER as creator [INV_API.REGISTER_PAYMENT:181-182].
6. `TRG_PAY_AIR` fires for that row: it adds the amount to `INVOICES.PAID_AMT`, sets the invoice to 'PAID' (and the order to status 50) when paid is at least gross minus 0.05, else to 'PART' [TRG_PAY_AIR:9-20].
7. Re-reads the invoice and, when `INVOICES.PAID_AMT` exceeds `INVOICES.GROSS_AMT` plus `INV_API.C_TOLERANCE`, logs an 'overpaid by' warning [INV_API.REGISTER_PAYMENT:185-190].
8. The comment at [INV_API.REGISTER_PAYMENT:184] says "update invoice paid amount and status"; the unit itself only re-reads the invoice, and the update is done by the trigger in step 6 [INV_API.REGISTER_PAYMENT:185].
9. When `P_METHOD` is 'CA' and `P_AMT` is above 3000, it rolls back the whole transaction and raises -20203 'Cash limit exceeded' [INV_API.REGISTER_PAYMENT:193-196].
10. Otherwise it commits [INV_API.REGISTER_PAYMENT:198].

## Dependencies

| Direction | Unit / object | Kind | Line |
|-----------|---------------|------|------|
| calls | `UTIL_LOG.SET_CTX` | CALL | 170 |
| calls | `TRG_PAY_AIR` | FIRES_TRIGGER | 181 |
| calls | `PAY_ID_SEQ` | SEQUENCE_USE | 182 |
| calls | `UTIL_LOG.G_USER` | VARIABLE_REF | 182 |
| calls | `UTIL_LOG.LOG_MSG` | CALL | 188 |
| calls | `UTIL_LOG.FMT_AMT` | CALL | 189 |

The unit has no caller in legacy_code/; it may be called from outside the source tree [INV_API.REGISTER_PAYMENT:164].

## Tables touched

| Table / view | Operation | Line | Via |
|--------------|-----------|------|-----|
| `INVOICES` | SELECT | 172 | STATIC |
| `PAYMENTS` | INSERT | 181 | STATIC |
| `INVOICES` | SELECT | 185 | STATIC |

The INSERT at line 181 fires `TRG_PAY_AIR`, which updates `INVOICES` (paid amount and status) and `ORDERS` (status 50) [INV_API.REGISTER_PAYMENT:181] [TRG_PAY_AIR:9-19].

## Side effects and risks

- COMMIT at line 198 commits the payment, the trigger's updates and any uncommitted work the caller did before the call [INV_API.REGISTER_PAYMENT:198].
- ROLLBACK at line 194 undoes the payment, the trigger's updates and all uncommitted work of the caller, then raises -20203 [INV_API.REGISTER_PAYMENT:194-195].
- The cash-limit check comes after the INSERT, so the trigger has already run when it rolls back [INV_API.REGISTER_PAYMENT:181-196].
- The 'overpaid by' warning is written by `UTIL_LOG.LOG_MSG` in an autonomous transaction, so it stays in `AUDIT_LOG` even when the cash-limit ROLLBACK follows [UTIL_LOG.LOG_MSG:63] [INV_API.REGISTER_PAYMENT:188-194].
- The comment at [INV_API.REGISTER_PAYMENT:192] says "cash payments above 3000 not allowed (anti money laundering)"; the code checks each payment alone, not a total, and states no currency [INV_API.REGISTER_PAYMENT:193].
- The unit does not check `P_AMT` for NULL, zero or a negative value, and accepts payments on 'PAID' or 'PART' invoices [INV_API.REGISTER_PAYMENT:174-182].
- It reads the package variable `UTIL_LOG.G_USER` and changes the `UTIL_LOG` module context for the session [INV_API.REGISTER_PAYMENT:170] [INV_API.REGISTER_PAYMENT:182].
- Hardcoded values: 'CANC', 'BT', 'CC', 'CA' and 3000; their meaning is Unknown: needs human input.

## Error handling

| Line | Handler / raise | Effect for the caller |
|------|-----------------|-----------------------|
| 175 | RAISE_APPLICATION_ERROR(-20201) 'Invoice cancelled' | raised before any write |
| 178 | RAISE_APPLICATION_ERROR(-20202) 'Unknown payment method' | raised before any write |
| 194-195 | ROLLBACK, then RAISE_APPLICATION_ERROR(-20203) 'Cash limit exceeded' | caller's whole transaction is undone, then the error is raised |
| 200-201 | WHEN NO_DATA_FOUND, RAISE_APPLICATION_ERROR(-20204) | an unknown invoice becomes -20204 'Invoice <id> not found' |

Other errors, such as a NULL `P_AMT` violating the NOT NULL column, are not handled and reach the caller unchanged [INV_API.REGISTER_PAYMENT:181-182] [PAYMENTS:5].

## Open questions

1. Which external system calls this unit, given there is no caller in legacy_code/ [INV_API.REGISTER_PAYMENT:164]?
2. Should the cash-limit check run before the INSERT, without rolling back the caller's whole transaction [INV_API.REGISTER_PAYMENT:181-196]?
3. What does method 'CA' mean? The column comment at [legacy_code/tables/payments.sql:13] lists only 'BT' and 'CC'. Unknown: needs human input.
4. What do the cash limit 3000 and its currency mean? Unknown: needs human input [INV_API.REGISTER_PAYMENT:193].
5. Is the missing validation of `P_AMT` (NULL, zero, negative) handled elsewhere [INV_API.REGISTER_PAYMENT:177-182]?
6. Is it intended that the paid amount and status are updated by `TRG_PAY_AIR` rather than by this unit, as the comment at [INV_API.REGISTER_PAYMENT:184] suggests [TRG_PAY_AIR:9-20]?
7. What does order status 50, set by `TRG_PAY_AIR`, mean? Unknown: needs human input [TRG_PAY_AIR:17].
