# `INV_API.CREATE_INVOICE#2`

| Field | Value |
|-------|-------|
| Package doc | [inv_api](../inv_api.md) |
| Kind | FUNCTION |
| Visibility | PUBLIC |
| Spec | `legacy_code/packages/inv_api.pks` line 8 |
| Body | `legacy_code/packages/inv_api.pkb` lines 86-127 |

```sql
FUNCTION CREATE_INVOICE(P_ORD_ID IN NUMBER, P_INV_DT IN DATE) RETURN NUMBER
```

## Purpose

Inserts one `INVOICES` row for an order in status 20 or 30 that has no invoice other than a cancelled one, sets the order to `PKG_ORDER.ST_INVOICED`, and returns the new invoice id, or NULL [INV_API.CREATE_INVOICE#2:86-127].
The business reason for the status rule is Unknown: needs human input.

## Parameters

| Name | Mode | Type | Default | Used for |
|------|------|------|---------|----------|
| `P_ORD_ID` | IN | NUMBER | - | order that is read, invoiced and set to `PKG_ORDER.ST_INVOICED` [INV_API.CREATE_INVOICE#2:92] [INV_API.CREATE_INVOICE#2:119] |
| `P_INV_DT` | IN | DATE | - | truncated to a day; becomes `INVOICES.INV_DT` and the base of `INVOICES.DUE_DT` [INV_API.CREATE_INVOICE#2:115-116] |
| return | - | NUMBER | - | the new `INVOICES.INV_ID`, or NULL when nothing was inserted [INV_API.CREATE_INVOICE#2:96] [INV_API.CREATE_INVOICE#2:106] [INV_API.CREATE_INVOICE#2:123] [INV_API.CREATE_INVOICE#2:126] |

## Logic walkthrough

1. Reads the whole `ORDERS` row; when the order does not exist, the handler at line 125 returns NULL [INV_API.CREATE_INVOICE#2:92] [INV_API.CREATE_INVOICE#2:124-126].
2. When `ORDERS.ORD_STATUS` is not 20 or 30, logs 'bad status' with severity 'W' and returns NULL [INV_API.CREATE_INVOICE#2:94-97].
3. A NULL status does not take that branch, because `NOT IN` with NULL is not true, so such an order goes on to step 4 [INV_API.CREATE_INVOICE#2:94].
4. Counts the order's invoices whose status is not 'CANC' and returns NULL, without logging, when there is at least one [INV_API.CREATE_INVOICE#2:99-107].
5. Takes the next value of `INV_SEQ` [INV_API.CREATE_INVOICE#2:109].
6. Computes the VAT with `INV_API.CALC_VAT` on `ORDERS.TOTAL_AMT`; that function returns 0 for any error [INV_API.CREATE_INVOICE#2:111] [INV_API.CALC_VAT:69-71].
7. Inserts the invoice: number from `INV_API.NEXT_INV_NO`, due date from `INV_API.GET_DUE_DT`, net = order total, gross = total plus VAT, paid 0, status 'OPEN', reminder count 0 [INV_API.CREATE_INVOICE#2:113-117].
8. Calls `PKG_ORDER.SET_STATUS` with `PKG_ORDER.ST_INVOICED` (40), which updates `ORDERS` [INV_API.CREATE_INVOICE#2:119] [PKG_ORDER.ST_INVOICED:8] [PKG_ORDER.SET_STATUS:100].
9. Logs 'CREATE_INV' with the order id and formatted gross amount, and returns the new id [INV_API.CREATE_INVOICE#2:121-123].

## Dependencies

| Direction | Unit / object | Kind | Line |
|-----------|---------------|------|------|
| calls | `UTIL_LOG.LOG_MSG` | CALL | 95 |
| calls | `INV_SEQ` | SEQUENCE_USE | 109 |
| calls | `INV_API.CALC_VAT` | CALL | 111 |
| calls | `INV_API.NEXT_INV_NO` | CALL | 115 |
| calls | `INV_API.GET_DUE_DT` | CALL | 116 |
| calls | `PKG_ORDER.SET_STATUS` | CALL | 119 |
| calls | `PKG_ORDER.ST_INVOICED` | VARIABLE_REF | 119 |
| calls | `UTIL_LOG.LOG_MSG` | CALL | 121 |
| calls | `UTIL_LOG.FMT_AMT` | CALL | 122 |
| called by | `INV_API.CREATE_INVOICE#1` | CALL | 79 |

## Tables touched

| Table / view | Operation | Line | Via |
|--------------|-----------|------|-----|
| `ORDERS` | SELECT | 92 | STATIC |
| `INVOICES` | SELECT | 101 | STATIC |
| `INVOICES` | INSERT | 113 | STATIC |

`ORDERS` is also updated through `PKG_ORDER.SET_STATUS` [PKG_ORDER.SET_STATUS:100].
No FIRES_TRIGGER edge exists for this unit [INV_API.CREATE_INVOICE#2:113].

## Side effects and risks

- The unit neither commits nor rolls back: the invoice and the order status change stay in the caller's transaction [INV_API.CREATE_INVOICE#2:113-119].
- `PKG_ORDER.PROCESS_ORDER`, through `INV_API.CREATE_INVOICE#1`, rolls back to its savepoint when NULL is returned [PKG_ORDER.PROCESS_ORDER:214-219].
- The log lines are written in an autonomous transaction and survive a rollback by the caller [UTIL_LOG.LOG_MSG:63].
- The invoice number takes its year from SYSDATE, not from `P_INV_DT` [INV_API.NEXT_INV_NO:20].
- `INV_API.CALC_VAT` reads the session-cached package variable `INV_API.G_VAT_RATE` [INV_API.CALC_VAT:55-56].
- The unit does DML, so it cannot be called from a SQL statement [INV_API.CREATE_INVOICE#2:113].
- Hardcoded values: 20, 30, 'CANC' and 'OPEN'; their meaning is Unknown: needs human input.

## Error handling

| Line | Handler / raise | Effect for the caller |
|------|-----------------|-----------------------|
| 94-96 | status check, not an exception | 'W' log line and NULL |
| 105-106 | existing invoice check, not an exception | NULL, no log line |
| 125-126 | WHEN NO_DATA_FOUND | NULL; the handler covers the whole body, also the statements after the INSERT at line 113 |

Other errors are not handled and reach the caller [INV_API.CREATE_INVOICE#2:124-126].

## Open questions

1. What do order statuses 20 and 30 mean for invoicing? Unknown: needs human input [INV_API.CREATE_INVOICE#2:94].
2. Should an order with a NULL status be invoiced [INV_API.CREATE_INVOICE#2:94]?
3. Should the duplicate-invoice case be logged like the bad-status case [INV_API.CREATE_INVOICE#2:105-106]?
4. Is a VAT amount of 0 after an error in `INV_API.CALC_VAT` acceptable on an invoice [INV_API.CALC_VAT:69-71]?
5. Should the invoice number use the year of `P_INV_DT` instead of SYSDATE [INV_API.NEXT_INV_NO:20]?
