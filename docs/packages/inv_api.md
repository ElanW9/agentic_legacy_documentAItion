# Package `INV_API`

| Field | Value |
|-------|-------|
| Spec | `legacy_code/packages/inv_api.pks` lines 1-24 |
| Body | `legacy_code/packages/inv_api.pkb` lines 1-248 |
| Source hash | `af29cc787e6fe6d3d728cbb3fb2d41fafc8f38fc7868291e09b784baa60cdbbf` |
| Status | draft |

## Purpose

`INV_API` inserts invoices for orders, cancels invoices, inserts payments, computes a VAT amount and a due date, sums a customer's open amount, and increments a reminder counter on overdue invoices [INV_API.CREATE_INVOICE#2:86-127] [INV_API.CANCEL_INVOICE:130-150] [INV_API.REGISTER_PAYMENT:164-202] [INV_API.CALC_VAT:51-72] [INV_API.GET_DUE_DT:35-47] [INV_API.GET_OPEN_AMT:205-221] [INV_API.SEND_REMINDERS:224-246].
The comment at [INV_API(spec):2-5] says "Invoicing API"; the units above are consistent with that label, but the business reason the package exists is Unknown: needs human input.

## Public API

| Unit | Kind | Signature | Spec | Body |
|------|------|-----------|------|------|
| `INV_API.CREATE_INVOICE#1` | FUNCTION | `FUNCTION CREATE_INVOICE(P_ORD_ID IN NUMBER) RETURN NUMBER` | 7 | 75-83 |
| `INV_API.CREATE_INVOICE#2` | FUNCTION | `FUNCTION CREATE_INVOICE(P_ORD_ID IN NUMBER, P_INV_DT IN DATE) RETURN NUMBER` | 8 | 86-127 |
| `INV_API.CANCEL_INVOICE` | PROCEDURE | `PROCEDURE CANCEL_INVOICE(P_INV_ID IN NUMBER)` | 10 | 130-150 |
| `INV_API.CANCEL_INVOICE_FOR_ORDER` | PROCEDURE | `PROCEDURE CANCEL_INVOICE_FOR_ORDER(P_ORD_ID IN NUMBER)` | 11 | 153-161 |
| `INV_API.REGISTER_PAYMENT` | PROCEDURE | `PROCEDURE REGISTER_PAYMENT(P_INV_ID IN NUMBER, P_AMT IN NUMBER, P_METHOD IN VARCHAR2 DEFAULT 'BT', P_REF IN VARCHAR2 DEFAULT NULL)` | 13-16 | 164-202 |
| `INV_API.GET_OPEN_AMT` | FUNCTION | `FUNCTION GET_OPEN_AMT(P_CUST_ID IN NUMBER) RETURN NUMBER` | 18 | 205-221 |
| `INV_API.CALC_VAT` | FUNCTION | `FUNCTION CALC_VAT(P_CUST_ID IN NUMBER, P_NET IN NUMBER) RETURN NUMBER` | 20 | 51-72 |
| `INV_API.SEND_REMINDERS` | PROCEDURE | `PROCEDURE SEND_REMINDERS` | 22 | 224-246 |

### `INV_API.CREATE_INVOICE#1`

Reads `ORDERS.SHIP_DT` for `P_ORD_ID` and calls `INV_API.CREATE_INVOICE#2` with that date, or with SYSDATE when the ship date is NULL [INV_API.CREATE_INVOICE#1:78-79].
When the order does not exist, the NO_DATA_FOUND handler returns NULL [INV_API.CREATE_INVOICE#1:80-82].
Otherwise it returns whatever `INV_API.CREATE_INVOICE#2` returns [INV_API.CREATE_INVOICE#1:79].

### `INV_API.CREATE_INVOICE#2`

Details: [create_invoice_2.md](inv_api/create_invoice_2.md).
It returns NULL without inserting when the order is missing, when `ORDERS.ORD_STATUS` is not 20 or 30, or when the order already has an invoice whose status is not 'CANC' [INV_API.CREATE_INVOICE#2:92-107] [INV_API.CREATE_INVOICE#2:124-126].
Otherwise it inserts one `INVOICES` row with status 'OPEN', sets the order status to `PKG_ORDER.ST_INVOICED`, logs, and returns the new `INVOICES.INV_ID` [INV_API.CREATE_INVOICE#2:109-123].
It does not commit [INV_API.CREATE_INVOICE#2:86-127].

### `INV_API.CANCEL_INVOICE`

Reads `INVOICES.PAID_AMT` and `INVOICES.ORD_ID` for `P_INV_ID` with FOR UPDATE, which locks the invoice row until the caller ends the transaction [INV_API.CANCEL_INVOICE:134-138].
When the paid amount (NULL counted as 0) is above 0 it raises -20200 'Invoice has payments' [INV_API.CANCEL_INVOICE:140-142].
Otherwise it sets `INVOICES.INV_STATUS` to 'CANC', whatever the current status is [INV_API.CANCEL_INVOICE:144].
It then calls `PKG_ORDER.SET_STATUS` with `PKG_ORDER.ST_CONFIRMED` for the invoice's order and logs with severity 'W' [INV_API.CANCEL_INVOICE:147-149].
The comment at [INV_API.CANCEL_INVOICE:146] says "back to confirmed"; the code agrees, since `PKG_ORDER.ST_CONFIRMED` is declared as 20 [PKG_ORDER.ST_CONFIRMED:6].
It does not commit and has no exception handler, so NO_DATA_FOUND for an unknown invoice reaches the caller [INV_API.CANCEL_INVOICE:130-150].

### `INV_API.CANCEL_INVOICE_FOR_ORDER`

Loops over the invoices of `P_ORD_ID` whose status is 'OPEN' or 'PART' and calls `INV_API.CANCEL_INVOICE` for each [INV_API.CANCEL_INVOICE_FOR_ORDER:155-160].
It has no exception handler: when one invoice raises -20200, the loop stops, the error reaches the caller, and invoices cancelled earlier in the loop stay cancelled in the caller's open transaction [INV_API.CANCEL_INVOICE_FOR_ORDER:153-161] [INV_API.CANCEL_INVOICE:140-142].
It does not commit [INV_API.CANCEL_INVOICE_FOR_ORDER:153-161].

### `INV_API.REGISTER_PAYMENT`

Details: [register_payment.md](inv_api/register_payment.md).
It validates the invoice and `P_METHOD`, inserts a `PAYMENTS` row (which fires `TRG_PAY_AIR`), logs a warning when the invoice is overpaid, and then either rolls back and raises -20203 for a cash payment above 3000 or commits [INV_API.REGISTER_PAYMENT:170-198].
Both the COMMIT and the ROLLBACK act on the caller's whole transaction [INV_API.REGISTER_PAYMENT:194] [INV_API.REGISTER_PAYMENT:198].
It has no caller in legacy_code/ [INV_API.REGISTER_PAYMENT:164].

### `INV_API.GET_OPEN_AMT`

Sums `V_OPEN_INVOICES.OPEN_AMT` for `P_CUST_ID` (0 when there are none) [INV_API.GET_OPEN_AMT:208-211].
It adds the sum of `ORDERS.TOTAL_AMT` of the customer's orders with `ORDERS.ORD_STATUS` 20 or 30, and returns the total [INV_API.GET_OPEN_AMT:214-220].
The values 20 and 30 are the values of `PKG_ORDER.ST_CONFIRMED` and `PKG_ORDER.ST_SHIPPED`, but the code uses the literals [INV_API.GET_OPEN_AMT:218] [PKG_ORDER.ST_CONFIRMED:6] [PKG_ORDER.ST_SHIPPED:7].
The comment at [INV_API.GET_OPEN_AMT:213] says "add confirmed orders not yet invoiced"; the code also adds orders in status 30, which the comment does not mention [INV_API.GET_OPEN_AMT:218].
`V_OPEN_INVOICES` only returns invoices with status 'OPEN' or 'PART' that join to a `CUSTOMERS` row, with `OPEN_AMT` computed as gross minus paid [V_OPEN_INVOICES:10-14].
It has no exception handler and does not write [INV_API.GET_OPEN_AMT:205-221].

### `INV_API.CALC_VAT`

On the first call in a session where `INV_API.G_VAT_RATE` is NULL, it loads it with `UTIL_LOG.GET_PARAM_NUM` for 'VAT_RATE', default 21 [INV_API.CALC_VAT:55-57].
It reads the customer's 'COUNTRY_CD' and 'VAT_NO' through `CUST_MGMT.GET_CUST_ATTR` [INV_API.CALC_VAT:59-60].
It returns `ROUND(P_NET * rate / 100, 2)` when the country is 'BE' or NULL [INV_API.CALC_VAT:62-63].
It returns 0 when the country is 'NL', 'FR', 'DE' or 'LU' and the VAT number is not NULL [INV_API.CALC_VAT:64-65].
For any other country it returns the same rounded amount as for 'BE' [INV_API.CALC_VAT:66-67].
A WHEN OTHERS handler returns 0 for any error, so the caller cannot tell an error from a zero-VAT result [INV_API.CALC_VAT:69-71].
The comment at [INV_API(body):50] says "21% for BE, 0 for intra-EU with VAT number, else 21%"; the code uses the `APP_PARAMS` value, which is 21 only when the parameter is 21, missing or not numeric, and its country list has four codes [INV_API.CALC_VAT:56] [UTIL_LOG.GET_PARAM_NUM:51-54] [INV_API.CALC_VAT:64].
The comment at [INV_API.CALC_VAT:65] says "reverse charge"; what that means for the business is Unknown: needs human input.

### `INV_API.SEND_REMINDERS`

Details: [send_reminders.md](inv_api/send_reminders.md).
For each row of `V_OPEN_INVOICES` with `V_OPEN_INVOICES.DAYS_OVERDUE` above 14 whose customer has a non-NULL email, it logs a 'REMINDER' line and adds 1 to `INVOICES.REMINDER_CNT` [INV_API.SEND_REMINDERS:227-241].
It then commits and calls `CUST_MGMT.CHK_OVERDUE_CUSTOMERS` [INV_API.SEND_REMINDERS:243-245].
The comment at [INV_API.SEND_REMINDERS:233] says "TODO: real mail sending, for now only logged"; the code agrees: no mail is sent, only `UTIL_LOG.LOG_MSG` is called [INV_API.SEND_REMINDERS:234-235].

### Private units

| Unit | Signature | Body | Called by |
|------|-----------|------|-----------|
| `INV_API.NEXT_INV_NO` | `FUNCTION NEXT_INV_NO(P_ID IN NUMBER) RETURN VARCHAR2` | 18-21 | `INV_API.CREATE_INVOICE#2` [INV_API.CREATE_INVOICE#2:115] |
| `INV_API.RECALC_PAID` | `PROCEDURE RECALC_PAID` | 25-32 | no caller in legacy_code/ [INV_API.RECALC_PAID:25] |
| `INV_API.GET_DUE_DT` | `FUNCTION GET_DUE_DT(P_CUST_ID IN NUMBER, P_INV_DT IN DATE) RETURN DATE` | 35-47 | `INV_API.CREATE_INVOICE#2` [INV_API.CREATE_INVOICE#2:116] |

`INV_API.NEXT_INV_NO` returns `INV_API.G_INV_PREFIX`, the year of SYSDATE, '-', and `P_ID` left-padded with '0' to 6 characters [INV_API.NEXT_INV_NO:20].
The year comes from SYSDATE, not from the invoice date passed to `INV_API.CREATE_INVOICE#2` [INV_API.NEXT_INV_NO:20] [INV_API.CREATE_INVOICE#2:115].

`INV_API.RECALC_PAID` sets `INVOICES.PAID_AMT` of every invoice to the sum of its `PAYMENTS.PAY_AMT` (0 when none) and commits [INV_API.RECALC_PAID:27-31].
Details: [recalc_paid.md](inv_api/recalc_paid.md).

`INV_API.GET_DUE_DT` gets the customer type from `CUST_MGMT.GET_CUST_TYPE` [INV_API.GET_DUE_DT:38].
For type 'G' it returns `UTIL_LOG.ADD_WORKDAYS` of the date and 60, for type 'W' the date plus 45, and for any other type the date plus 30 [INV_API.GET_DUE_DT:40-46].
`UTIL_LOG.ADD_WORKDAYS` counts only days that are not Saturday or Sunday [UTIL_LOG.ADD_WORKDAYS:113-118].
`CUST_MGMT.GET_CUST_TYPE` returns 'R' when the customer does not exist, so an unknown customer gets the 30-day branch [CUST_MGMT.GET_CUST_TYPE:140-142] [INV_API.GET_DUE_DT:44-45].
The comment at [legacy_code/tables/customers.sql:19] says "R=retail W=wholesale" and does not mention 'G'; the meaning of the customer types is Unknown: needs human input.

## Dependencies

### Calls out

| From unit | To | Kind | Line |
|-----------|----|------|------|
| `INV_API.GET_DUE_DT` | `CUST_MGMT.GET_CUST_TYPE` | CALL | 38 |
| `INV_API.GET_DUE_DT` | `UTIL_LOG.ADD_WORKDAYS` | CALL | 41 |
| `INV_API.CALC_VAT` | `UTIL_LOG.GET_PARAM_NUM` | CALL | 56 |
| `INV_API.CALC_VAT` | `CUST_MGMT.GET_CUST_ATTR` | CALL | 59 |
| `INV_API.CALC_VAT` | `CUST_MGMT.GET_CUST_ATTR` | CALL | 60 |
| `INV_API.CREATE_INVOICE#1` | `INV_API.CREATE_INVOICE#2` | CALL | 79 |
| `INV_API.CREATE_INVOICE#2` | `UTIL_LOG.LOG_MSG` | CALL | 95 |
| `INV_API.CREATE_INVOICE#2` | `INV_SEQ` | SEQUENCE_USE | 109 |
| `INV_API.CREATE_INVOICE#2` | `INV_API.CALC_VAT` | CALL | 111 |
| `INV_API.CREATE_INVOICE#2` | `INV_API.NEXT_INV_NO` | CALL | 115 |
| `INV_API.CREATE_INVOICE#2` | `INV_API.GET_DUE_DT` | CALL | 116 |
| `INV_API.CREATE_INVOICE#2` | `PKG_ORDER.SET_STATUS` | CALL | 119 |
| `INV_API.CREATE_INVOICE#2` | `PKG_ORDER.ST_INVOICED` | VARIABLE_REF | 119 |
| `INV_API.CREATE_INVOICE#2` | `UTIL_LOG.LOG_MSG` | CALL | 121 |
| `INV_API.CREATE_INVOICE#2` | `UTIL_LOG.FMT_AMT` | CALL | 122 |
| `INV_API.CANCEL_INVOICE` | `PKG_ORDER.SET_STATUS` | CALL | 147 |
| `INV_API.CANCEL_INVOICE` | `PKG_ORDER.ST_CONFIRMED` | VARIABLE_REF | 147 |
| `INV_API.CANCEL_INVOICE` | `UTIL_LOG.LOG_MSG` | CALL | 149 |
| `INV_API.CANCEL_INVOICE_FOR_ORDER` | `INV_API.CANCEL_INVOICE` | CALL | 159 |
| `INV_API.REGISTER_PAYMENT` | `UTIL_LOG.SET_CTX` | CALL | 170 |
| `INV_API.REGISTER_PAYMENT` | `TRG_PAY_AIR` | FIRES_TRIGGER | 181 |
| `INV_API.REGISTER_PAYMENT` | `PAY_ID_SEQ` | SEQUENCE_USE | 182 |
| `INV_API.REGISTER_PAYMENT` | `UTIL_LOG.G_USER` | VARIABLE_REF | 182 |
| `INV_API.REGISTER_PAYMENT` | `UTIL_LOG.LOG_MSG` | CALL | 188 |
| `INV_API.REGISTER_PAYMENT` | `UTIL_LOG.FMT_AMT` | CALL | 189 |
| `INV_API.SEND_REMINDERS` | `CUST_MGMT.GET_CUST_ATTR` | CALL | 230 |
| `INV_API.SEND_REMINDERS` | `UTIL_LOG.LOG_MSG` | CALL | 234 |
| `INV_API.SEND_REMINDERS` | `UTIL_LOG.FMT_AMT` | CALL | 235 |
| `INV_API.SEND_REMINDERS` | `CUST_MGMT.CHK_OVERDUE_CUSTOMERS` | CALL | 245 |

### Called by

| Caller | Unit called | Line |
|--------|-------------|------|
| `INV_API.CREATE_INVOICE#1` | `INV_API.CREATE_INVOICE#2` | 79 |
| `INV_API.CREATE_INVOICE#2` | `INV_API.CALC_VAT` | 111 |
| `INV_API.CREATE_INVOICE#2` | `INV_API.NEXT_INV_NO` | 115 |
| `INV_API.CREATE_INVOICE#2` | `INV_API.GET_DUE_DT` | 116 |
| `INV_API.CANCEL_INVOICE_FOR_ORDER` | `INV_API.CANCEL_INVOICE` | 159 |
| `CUST_MGMT.CHK_CREDIT` | `INV_API.GET_OPEN_AMT` | 167 |
| `UTIL_LOG.HOUSEKEEPING` | `INV_API.SEND_REMINDERS` | 165 |
| `PKG_ORDER.PROCESS_ORDER` | `INV_API.CREATE_INVOICE#1` | 214 |
| `PKG_ORDER.CANCEL_ORDER` | `INV_API.CANCEL_INVOICE_FOR_ORDER` | 265 |

`INV_API.REGISTER_PAYMENT` and `INV_API.RECALC_PAID` have no caller in legacy_code/ [INV_API.REGISTER_PAYMENT:164] [INV_API.RECALC_PAID:25].
Callers outside legacy_code/ (schedulers, applications, other schemas) cannot be seen by the parser, so this list may be incomplete for the public units [INV_API(spec):7-22].

### Package cycles

| Cycle (as listed in dependencies.json) | Edges that close it |
|----------------------------------------|---------------------|
| CUST_MGMT, INV_API | [INV_API.CALC_VAT:59] [CUST_MGMT.CHK_CREDIT:167] |
| INV_API, PKG_ORDER | [INV_API.CREATE_INVOICE#2:119] [PKG_ORDER.PROCESS_ORDER:214] |
| INV_API, UTIL_LOG | [INV_API.CALC_VAT:56] [UTIL_LOG.HOUSEKEEPING:165] |
| CUST_MGMT, INV_API, PKG_ORDER | [CUST_MGMT.CHK_CREDIT:167] [INV_API.CREATE_INVOICE#2:119] [PKG_ORDER.PROCESS_ORDER:191] |
| CUST_MGMT, UTIL_LOG, INV_API | [CUST_MGMT.UNBLOCK_CUSTOMER:126] [UTIL_LOG.HOUSEKEEPING:165] [INV_API.CALC_VAT:59] |
| INV_API, PKG_ORDER, UTIL_LOG | [INV_API.CREATE_INVOICE#2:119] [PKG_ORDER.PROCESS_ORDER:140] [UTIL_LOG.HOUSEKEEPING:165] |
| CUST_MGMT, UTIL_LOG, INV_API, PKG_ORDER | [CUST_MGMT.UNBLOCK_CUSTOMER:126] [UTIL_LOG.HOUSEKEEPING:165] [INV_API.CREATE_INVOICE#2:119] [PKG_ORDER.PROCESS_ORDER:191] |

## Tables touched

| Table / view | Operation | Unit | Line | Via |
|--------------|-----------|------|------|-----|
| `INVOICES` | UPDATE | `INV_API.RECALC_PAID` | 27 | STATIC |
| `PAYMENTS` | SELECT | `INV_API.RECALC_PAID` | 29 | STATIC |
| `ORDERS` | SELECT | `INV_API.CREATE_INVOICE#1` | 78 | STATIC |
| `ORDERS` | SELECT | `INV_API.CREATE_INVOICE#2` | 92 | STATIC |
| `INVOICES` | SELECT | `INV_API.CREATE_INVOICE#2` | 101 | STATIC |
| `INVOICES` | INSERT | `INV_API.CREATE_INVOICE#2` | 113 | STATIC |
| `INVOICES` | SELECT | `INV_API.CANCEL_INVOICE` | 136 | STATIC |
| `INVOICES` | UPDATE | `INV_API.CANCEL_INVOICE` | 144 | STATIC |
| `INVOICES` | SELECT | `INV_API.CANCEL_INVOICE_FOR_ORDER` | 156 | STATIC |
| `INVOICES` | SELECT | `INV_API.REGISTER_PAYMENT` | 172 | STATIC |
| `PAYMENTS` | INSERT | `INV_API.REGISTER_PAYMENT` | 181 | STATIC |
| `INVOICES` | SELECT | `INV_API.REGISTER_PAYMENT` | 185 | STATIC |
| `V_OPEN_INVOICES` | SELECT | `INV_API.GET_OPEN_AMT` | 210 | STATIC |
| `ORDERS` | SELECT | `INV_API.GET_OPEN_AMT` | 216 | STATIC |
| `V_OPEN_INVOICES` | SELECT | `INV_API.SEND_REMINDERS` | 228 | STATIC |
| `INVOICES` | UPDATE | `INV_API.SEND_REMINDERS` | 237 | STATIC |

No access is via DYNAMIC_LITERAL [INV_API(body):1-248].
`V_OPEN_INVOICES` reads `INVOICES` and `CUSTOMERS` [V_OPEN_INVOICES:12].
`CUSTOMERS` is also read through dynamic SQL in `CUST_MGMT.GET_CUST_ATTR`, which `INV_API.CALC_VAT` and `INV_API.SEND_REMINDERS` call; that read is not in table_usage for this package (see Dynamic SQL) [CUST_MGMT.GET_CUST_ATTR:216].
`PKG_ORDER.SET_STATUS`, called by `INV_API.CREATE_INVOICE#2` and `INV_API.CANCEL_INVOICE`, updates `ORDERS` [PKG_ORDER.SET_STATUS:100] [INV_API.CREATE_INVOICE#2:119] [INV_API.CANCEL_INVOICE:147].
`UTIL_LOG.LOG_MSG` inserts into `AUDIT_LOG` in an autonomous transaction [UTIL_LOG.LOG_MSG:63-82].

### Triggers fired

| Unit | Statement line | Trigger | What the trigger writes |
|------|----------------|---------|-------------------------|
| `INV_API.REGISTER_PAYMENT` | 181 | `TRG_PAY_AIR` | `INVOICES`: adds the payment to `INVOICES.PAID_AMT`, then sets `INVOICES.INV_STATUS` to 'PAID' when paid is at least gross minus 0.05, else to 'PART'; `ORDERS`: sets `ORDERS.ORD_STATUS` to 50 for the invoice's order in the 'PAID' case [TRG_PAY_AIR:9-20] |

`TRG_PAY_AIR` is an AFTER INSERT row-level trigger on `PAYMENTS`, so it fires for every payment row inserted at line 181 [TRG_PAY_AIR:1-3] [INV_API.REGISTER_PAYMENT:181-182].
The comment at [TRG_PAY_AIR:16] says "close order"; the meaning of status 50 is Unknown: needs human input, and `PKG_ORDER` declares no constant with value 50 [PKG_ORDER(spec):3-9].
No `INV_API` write to `INVOICES` or `ORDERS` has a FIRES_TRIGGER edge [INV_API(body):1-248].

## Side effects and risks

### Transaction control

- `INV_API.REGISTER_PAYMENT` commits at line 198: this commits the payment, the `TRG_PAY_AIR` updates of `INVOICES` and `ORDERS`, and any uncommitted work the caller did before the call [INV_API.REGISTER_PAYMENT:198].
- `INV_API.REGISTER_PAYMENT` rolls back at line 194 for a cash payment above 3000: this undoes the payment, the trigger's updates, and all uncommitted work of the caller, not only this payment, and then raises -20203 [INV_API.REGISTER_PAYMENT:193-195].
- The cash-limit check runs after the INSERT, so the trigger has already run when the ROLLBACK happens [INV_API.REGISTER_PAYMENT:181-196].
- `INV_API.SEND_REMINDERS` commits at line 243: this commits all `INVOICES.REMINDER_CNT` increments and any uncommitted work of the caller [INV_API.SEND_REMINDERS:243].
- `CUST_MGMT.CHK_OVERDUE_CUSTOMERS` runs after that COMMIT, so its writes are not committed by `INV_API.SEND_REMINDERS` [INV_API.SEND_REMINDERS:243-245].
- `INV_API.RECALC_PAID` commits at line 31, which would also commit the caller's work, but it has no caller in legacy_code/ [INV_API.RECALC_PAID:31].
- `INV_API.CREATE_INVOICE#1`, `INV_API.CREATE_INVOICE#2`, `INV_API.CANCEL_INVOICE` and `INV_API.CANCEL_INVOICE_FOR_ORDER` neither commit nor roll back: their writes stay in the caller's transaction [INV_API.CREATE_INVOICE#2:113-119] [INV_API.CANCEL_INVOICE:144-147] [INV_API.CANCEL_INVOICE_FOR_ORDER:155-160].
- `PKG_ORDER.PROCESS_ORDER` rolls back to its savepoint when `INV_API.CREATE_INVOICE#1` returns NULL [PKG_ORDER.PROCESS_ORDER:214-219].
- Every log line written through `UTIL_LOG.LOG_MSG` is committed in an autonomous transaction, so it survives a rollback by the caller, including the 'overpaid' warning written just before the cash-limit ROLLBACK [UTIL_LOG.LOG_MSG:63] [INV_API.REGISTER_PAYMENT:187-194].

### Package state

| Variable | Visibility | Constant | Written by | Read by |
|----------|------------|----------|------------|---------|
| `INV_API.G_VAT_RATE` | PRIVATE | no | `INV_API.CALC_VAT` [INV_API.CALC_VAT:56] | `INV_API.CALC_VAT` [INV_API.CALC_VAT:55] [INV_API.CALC_VAT:63] [INV_API.CALC_VAT:67] |
| `INV_API.G_INV_PREFIX` | PRIVATE | no | no unit; only the declaration default 'INV' [INV_API.G_INV_PREFIX:13] | `INV_API.NEXT_INV_NO` [INV_API.NEXT_INV_NO:20] |
| `INV_API.C_TOLERANCE` | PRIVATE | yes | declaration only, 0.05 [INV_API.C_TOLERANCE:15] | `INV_API.REGISTER_PAYMENT` [INV_API.REGISTER_PAYMENT:187] |

`INV_API.G_VAT_RATE` is loaded once and then kept for the database session: a change to the 'VAT_RATE' row in `APP_PARAMS` is not seen by a session that has already called `INV_API.CALC_VAT` [INV_API.G_VAT_RATE:12] [INV_API.CALC_VAT:55-57].
`INV_API.G_INV_PREFIX` is not a constant but no unit assigns it, so it keeps 'INV' for the session [INV_API.G_INV_PREFIX:13].
`INV_API.REGISTER_PAYMENT` reads the package variable `UTIL_LOG.G_USER` for `PAYMENTS.CREATED_BY`, falling back to USER when it is NULL [INV_API.REGISTER_PAYMENT:182].
`INV_API.REGISTER_PAYMENT` calls `UTIL_LOG.SET_CTX` with 'INV_API', which sets the `UTIL_LOG` module for the rest of the session and leaves `UTIL_LOG.G_USER` unchanged [INV_API.REGISTER_PAYMENT:170] [UTIL_LOG.SET_CTX:28-31].

### Dynamic SQL

`INV_API` itself contains no dynamic SQL [INV_API(body):1-248].
`INV_API.CALC_VAT` and `INV_API.SEND_REMINDERS` call `CUST_MGMT.GET_CUST_ATTR` with the column names 'COUNTRY_CD', 'VAT_NO' and 'EMAIL', and that function builds its SELECT on `CUSTOMERS` at runtime by concatenating the column name [INV_API.CALC_VAT:59-60] [INV_API.SEND_REMINDERS:230] [CUST_MGMT.GET_CUST_ATTR:216-218].
table_usage cannot see this read of `CUSTOMERS` [CUST_MGMT.GET_CUST_ATTR:216].
`CUST_MGMT.GET_CUST_ATTR` returns NULL for any error, so `INV_API.CALC_VAT` treats a failed country lookup as 'BE' and `INV_API.SEND_REMINDERS` skips the invoice [CUST_MGMT.GET_CUST_ATTR:221-223] [INV_API.CALC_VAT:62] [INV_API.SEND_REMINDERS:232].

### Hardcoded values

| Unit | Line | Value | What the code does with it | Meaning |
|------|------|-------|----------------------------|---------|
| `INV_API.C_TOLERANCE` | 15 | 0.05 | overpayment warning threshold in `INV_API.REGISTER_PAYMENT` | Unknown: needs human input |
| `INV_API.G_INV_PREFIX` | 13 | 'INV' | prefix of `INVOICES.INV_NO` | Unknown: needs human input |
| `INV_API.NEXT_INV_NO` | 20 | 'YYYY', '-', 6, '0' | year format, separator and padding of the invoice number; '-' is not flagged by the parser, the others are excluded by its rules | Unknown: needs human input |
| `INV_API.GET_DUE_DT` | 40-45 | 'G', 60, 'W', 45, 30 | customer type and number of days to the due date | Unknown: needs human input |
| `INV_API.CALC_VAT` | 56 | 21 | default VAT rate when 'VAT_RATE' is missing or not numeric | Unknown: needs human input |
| `INV_API.CALC_VAT` | 62-64 | 'BE', 'NL', 'FR', 'DE', 'LU' | country codes that select the VAT branch | Unknown: needs human input |
| `INV_API.CREATE_INVOICE#2` | 94 | 20, 30 | order statuses that may be invoiced | Unknown: needs human input |
| `INV_API.CREATE_INVOICE#2` | 103 | 'CANC' | invoice status ignored by the duplicate check | Unknown: needs human input |
| `INV_API.CREATE_INVOICE#2` | 117 | 'OPEN' | status of a new invoice | Unknown: needs human input |
| `INV_API.CANCEL_INVOICE` | 144 | 'CANC' | status set on cancel | Unknown: needs human input |
| `INV_API.CANCEL_INVOICE_FOR_ORDER` | 158 | 'OPEN', 'PART' | invoice statuses that get cancelled | Unknown: needs human input |
| `INV_API.REGISTER_PAYMENT` | 174 | 'CANC' | invoice status that is refused | Unknown: needs human input |
| `INV_API.REGISTER_PAYMENT` | 177 | 'BT', 'CC', 'CA' | accepted payment methods | Unknown: needs human input |
| `INV_API.REGISTER_PAYMENT` | 193 | 'CA', 3000 | cash limit per payment | Unknown: needs human input |
| `INV_API.GET_OPEN_AMT` | 218 | 20, 30 | order statuses added to the open amount | Unknown: needs human input |
| `INV_API.SEND_REMINDERS` | 229 | 14 | minimum days overdue for a reminder | Unknown: needs human input |

The invoice statuses used here are the four values allowed by the `INVOICES` check constraint [INVOICES:18].
The comment at [legacy_code/tables/payments.sql:13] says "BT=bank transfer, CC=credit card" and does not mention 'CA', which `INV_API.REGISTER_PAYMENT` accepts [INV_API.REGISTER_PAYMENT:177].
The comment at [INV_API.REGISTER_PAYMENT:192] says "cash payments above 3000 not allowed (anti money laundering)"; the code checks each payment on its own, not a total per invoice or customer, and the currency is not stated in the code [INV_API.REGISTER_PAYMENT:193].

### Other

- NO_CALLER: `INV_API.RECALC_PAID` is private and nothing in the body calls it, so it cannot run [INV_API.RECALC_PAID:25].
- The comment at [INV_API(body):24] says "run monthly!"; no caller exists in legacy_code/ and, being private, it cannot be called from outside the package [INV_API(body):24-25].
- NO_CALLER: `INV_API.REGISTER_PAYMENT` is public and has no caller in legacy_code/; it may be called from outside the source tree [INV_API.REGISTER_PAYMENT:164].
- TRIGGER_DML: the insert into `PAYMENTS` makes `TRG_PAY_AIR` update `INVOICES` and `ORDERS` (see Triggers fired) [TRG_PAY_AIR:9-19].
- `INV_API.NEXT_INV_NO` pads `P_ID` with LPAD to 6 characters; LPAD truncates longer values, so ids above 999999 give a truncated number [INV_API.NEXT_INV_NO:20].
- `INV_SEQ` has no MAXVALUE, and `INVOICES.INV_NO` has a unique key, so a truncated number could collide with an existing one [INV_SEQ:1-5] [INVOICES:15].
- `INVOICES.REMINDER_CNT` is NUMBER(2), and `INV_API.SEND_REMINDERS` adds 1 on every run without an upper bound [INVOICES:13] [INV_API.SEND_REMINDERS:237-239].
- `INV_API.CREATE_INVOICE#2` lets an order with a NULL `ORDERS.ORD_STATUS` through the status check, because `NOT IN` with NULL is not true [INV_API.CREATE_INVOICE#2:94].
- `INV_API.CREATE_INVOICE#2` performs DML, so neither overload can be called from a SQL statement [INV_API.CREATE_INVOICE#2:113-119].

## Error handling

| Unit | Line | Handler / raise | Effect for the caller |
|------|------|-----------------|-----------------------|
| `INV_API.CALC_VAT` | 70-71 | WHEN OTHERS, no RAISE | returns 0 instead of the error; `INV_API.CREATE_INVOICE#2` then stores a VAT amount of 0 |
| `INV_API.CREATE_INVOICE#1` | 81-82 | WHEN NO_DATA_FOUND | returns NULL when the order does not exist |
| `INV_API.CREATE_INVOICE#2` | 94-96 | status check, not an exception | logs a 'W' line and returns NULL |
| `INV_API.CREATE_INVOICE#2` | 105-106 | existing invoice check, not an exception | returns NULL without logging |
| `INV_API.CREATE_INVOICE#2` | 125-126 | WHEN NO_DATA_FOUND | returns NULL; the handler covers the whole body, including the statements after the INSERT |
| `INV_API.CANCEL_INVOICE` | 141 | RAISE_APPLICATION_ERROR(-20200) 'Invoice has payments' | raised to the caller; nothing is undone by the unit |
| `INV_API.CANCEL_INVOICE` | 134-138 | no handler | NO_DATA_FOUND for an unknown invoice reaches the caller |
| `INV_API.CANCEL_INVOICE_FOR_ORDER` | 159 | no handler | -20200 or any other error from `INV_API.CANCEL_INVOICE` reaches the caller; earlier cancellations in the loop are not undone |
| `INV_API.REGISTER_PAYMENT` | 175 | RAISE_APPLICATION_ERROR(-20201) 'Invoice cancelled' | raised before any write |
| `INV_API.REGISTER_PAYMENT` | 178 | RAISE_APPLICATION_ERROR(-20202) 'Unknown payment method' | raised before any write; a NULL method is not rejected because `NOT IN` with NULL is not true |
| `INV_API.REGISTER_PAYMENT` | 194-195 | ROLLBACK, then RAISE_APPLICATION_ERROR(-20203) 'Cash limit exceeded' | caller's whole transaction is rolled back, then the error is raised |
| `INV_API.REGISTER_PAYMENT` | 200-201 | WHEN NO_DATA_FOUND, RAISE_APPLICATION_ERROR(-20204) | an unknown invoice becomes -20204 'Invoice <id> not found' |
| `INV_API.GET_DUE_DT` | 35-47 | no handler | errors reach `INV_API.CREATE_INVOICE#2` |
| `INV_API.GET_OPEN_AMT` | 205-221 | no handler | errors reach the caller |
| `INV_API.SEND_REMINDERS` | 224-246 | no handler | an error in the loop reaches the caller before the COMMIT at line 243; increments made so far are not committed by the unit |

## Open questions

1. What is the business purpose of `INV_API`? The comment at [INV_API(spec):3] only says "Invoicing API". Unknown: needs human input.
2. What do the hardcoded values listed under "Hardcoded values" mean (order statuses 20 and 30, invoice statuses, customer types 'G' and 'W', the 60/45/30 day terms, the 14-day reminder threshold, the 0.05 tolerance, the 3000 cash limit and its currency)? Unknown: needs human input [INV_API.GET_DUE_DT:40-45] [INV_API.REGISTER_PAYMENT:193] [INV_API.SEND_REMINDERS:229].
3. The comment at [INV_API(body):50] says "0 for intra-EU with VAT number", but the code gives 0 only for 'NL', 'FR', 'DE' and 'LU'; are other EU countries meant to be included [INV_API.CALC_VAT:64]?
4. The comment at [INV_API(body):50] says the rate is 21%, but the code uses the 'VAT_RATE' parameter cached per session; is the session cache acceptable when the rate changes [INV_API.CALC_VAT:55-57]?
5. `INV_API.CALC_VAT` returns 0 on any error, which creates an invoice with zero VAT without a warning; is that intended [INV_API.CALC_VAT:69-71]?
6. What does "reverse charge" in the comment at [INV_API.CALC_VAT:65] mean for the business? Unknown: needs human input.
7. The comment at [INV_API.GET_OPEN_AMT:213] says "confirmed orders not yet invoiced", but the code also adds orders with status 30 (`PKG_ORDER.ST_SHIPPED`); which is correct [INV_API.GET_OPEN_AMT:218]?
8. The comment at [INV_API(body):24] says "run monthly!", but the unit is private and has no caller; is it still needed, and who ran it [INV_API.RECALC_PAID:25]?
9. `INV_API.REGISTER_PAYMENT` has no caller in legacy_code/; which external system calls it [INV_API.REGISTER_PAYMENT:164]?
10. The cash-limit check runs after the INSERT and its ROLLBACK undoes the caller's whole transaction; should the check run before the INSERT, without a full rollback [INV_API.REGISTER_PAYMENT:181-196]?
11. `INV_API.REGISTER_PAYMENT` accepts payment method 'CA', which the column comment at [legacy_code/tables/payments.sql:13] does not list; what does 'CA' mean [INV_API.REGISTER_PAYMENT:177]?
12. `INV_API.REGISTER_PAYMENT` does not check `P_AMT` for NULL, zero or a negative value; is that validated elsewhere [INV_API.REGISTER_PAYMENT:177-182]?
13. The comment at [INV_API.REGISTER_PAYMENT:184] says "update invoice paid amount and status", but the unit only re-reads the invoice; the update is done by `TRG_PAY_AIR` [TRG_PAY_AIR:9-20]. Is this split intended?
14. `TRG_PAY_AIR` sets `ORDERS.ORD_STATUS` to 50, a value with no constant in `PKG_ORDER`; what does 50 mean [TRG_PAY_AIR:17]?
15. `INV_API.CANCEL_INVOICE` sets the order back to `PKG_ORDER.ST_CONFIRMED` (20), even when it was called from `PKG_ORDER.CANCEL_ORDER`, which then sets the order to cancelled; is the intermediate status change intended [INV_API.CANCEL_INVOICE:147] [PKG_ORDER.CANCEL_ORDER:263-274]?
16. `INV_API.CANCEL_INVOICE` cancels an invoice in any status, including 'PAID' with a paid amount of 0 or one already 'CANC'; is a status check missing [INV_API.CANCEL_INVOICE:140-144]?
17. Invoice numbers take the year from SYSDATE, not from the invoice date, and LPAD truncates ids above 999999; is either a known issue [INV_API.NEXT_INV_NO:20]?
18. `INVOICES.REMINDER_CNT` is NUMBER(2) and grows by 1 per run of `INV_API.SEND_REMINDERS`; what should happen after 99 reminders [INVOICES:13] [INV_API.SEND_REMINDERS:237-239]?
19. Metadata gap: the hardcoded-value heuristic did not flag the literal '-' in `INV_API.NEXT_INV_NO`, although it is a string of up to 4 characters outside the excluded calls [INV_API.NEXT_INV_NO:20].
20. Parser limitation: the read of `CUSTOMERS` through dynamic SQL in `CUST_MGMT.GET_CUST_ATTR` is not in table_usage for this package [CUST_MGMT.GET_CUST_ATTR:216].
21. Parser limitation: callers outside legacy_code/ (schedulers, applications, other schemas) are not visible, so the "Called by" list may be incomplete [INV_API(spec):7-22].
22. The body comment at [INV_API(body):4] says the package "Replaces the old INVOICE_HDR / INVOICE_DTL logic"; those objects do not exist in legacy_code/. Do they still exist elsewhere? Unknown: needs human input.
