# Package `PKG_ORDER`

| Field | Value |
|-------|-------|
| Spec | `legacy_code/packages/pkg_order.pks` lines 1-27 |
| Body | `legacy_code/packages/pkg_order.pkb` lines 1-279 |
| Source hash | `f33eac6142f77100f7d8d926f9ee89daef2d7ca9d0c39b64453b72a154b8c615` |
| Status | draft |

## Purpose

The package inserts orders into `ORDERS` and order lines into `ORDER_LINES`, changes the order status, cancels orders, and sums the line amounts of an order [PKG_ORDER.NEW_ORDER:35-54] [PKG_ORDER.ADD_LINE#2:76-95] [PKG_ORDER.SET_STATUS:98-104] [PKG_ORDER.CANCEL_ORDER:258-277] [PKG_ORDER.GET_ORDER_TOTAL:107-112]. `PKG_ORDER.PROCESS_ORDER` confirms, holds or cancels one order or a batch of orders, and can ship and invoice them through `INV_API` [PKG_ORDER.PROCESS_ORDER:120-255]. The spec declares the order status constants `PKG_ORDER.ST_NEW` to `PKG_ORDER.ST_CANCELLED` [PKG_ORDER(spec):4-9]. The business reason for the package is Unknown: needs human input.

## Public API

| Unit | Kind | Signature | Spec | Body |
|------|------|-----------|------|------|
| `PKG_ORDER.NEW_ORDER` | FUNCTION | `FUNCTION NEW_ORDER(P_CUST_ID IN NUMBER, P_REMARKS IN VARCHAR2 DEFAULT null) RETURN NUMBER` | 14 | 35-54 |
| `PKG_ORDER.ADD_LINE#1` | PROCEDURE | `PROCEDURE ADD_LINE(P_ORD_ID IN NUMBER, P_PROD_CD IN VARCHAR2, P_QTY IN NUMBER)` | 16 | 58-73 |
| `PKG_ORDER.ADD_LINE#2` | PROCEDURE | `PROCEDURE ADD_LINE(P_ORD_ID IN NUMBER, P_PROD_CD IN VARCHAR2, P_QTY IN NUMBER, P_PRICE IN NUMBER)` | 17 | 76-95 |
| `PKG_ORDER.PROCESS_ORDER` | PROCEDURE | `PROCEDURE PROCESS_ORDER(P_ORD_ID IN NUMBER DEFAULT null, P_SHIP IN BOOLEAN DEFAULT false)` | 19 | 120-255 |
| `PKG_ORDER.SET_STATUS` | PROCEDURE | `PROCEDURE SET_STATUS(P_ORD_ID IN NUMBER, P_STATUS IN NUMBER)` | 21 | 98-104 |
| `PKG_ORDER.CANCEL_ORDER` | PROCEDURE | `PROCEDURE CANCEL_ORDER(P_ORD_ID IN NUMBER, P_REASON IN VARCHAR2)` | 23 | 258-277 |
| `PKG_ORDER.GET_ORDER_TOTAL` | FUNCTION | `FUNCTION GET_ORDER_TOTAL(P_ORD_ID IN NUMBER) RETURN NUMBER` | 25 | 107-112 |

### `PKG_ORDER.NEW_ORDER`

Sets the `UTIL_LOG` module context to 'PKG_ORDER' [PKG_ORDER.NEW_ORDER:39]. Reads `CUSTOMERS.STATUS` for `P_CUST_ID` and raises -20100 when it is 'C' [PKG_ORDER.NEW_ORDER:41-44]. Takes the next value of `ORD_SEQ` and inserts a row into `ORDERS` with status `PKG_ORDER.ST_NEW`, `TOTAL_AMT` 0, `DISC_PCT` 0, `CURR_CD` 'EUR', the given remarks, and `CREATED_BY` = NVL(`UTIL_LOG.G_USER`, USER) [PKG_ORDER.NEW_ORDER:46-49]. Stores the new id in `PKG_ORDER.G_LAST_ORD_ID`, writes a 'NEW' log line and returns the id [PKG_ORDER.NEW_ORDER:51-53]. It does not commit; the insert stays in the caller's transaction [PKG_ORDER.NEW_ORDER:35-54].

### `PKG_ORDER.ADD_LINE#1`

Reads `PRODUCTS.LIST_PRICE` for UPPER(`P_PROD_CD`) where `ACTIVE_YN` = 'Y' [PKG_ORDER.ADD_LINE#1:61-65]. When `P_QTY` is 100 or more, the price is multiplied by 0.97 and rounded to 2 decimals [PKG_ORDER.ADD_LINE#1:68-70]. It then calls `PKG_ORDER.ADD_LINE#2` with that price [PKG_ORDER.ADD_LINE#1:72]. The comment at [PKG_ORDER.ADD_LINE#1:67] says "volume price break"; the code applies the 0.97 factor from quantity 100 [PKG_ORDER.ADD_LINE#1:68-69]. An unknown or inactive product raises NO_DATA_FOUND to the caller, because there is no handler [PKG_ORDER.ADD_LINE#1:58-73].

### `PKG_ORDER.ADD_LINE#2`

Reads the order status with a SELECT FOR UPDATE, which locks the `ORDERS` row until the caller commits or rolls back [PKG_ORDER.ADD_LINE#2:80]. Raises -20101 when the status is not `PKG_ORDER.ST_NEW` or `PKG_ORDER.ST_HOLD`, and -20102 when `P_QTY` is 0 or less [PKG_ORDER.ADD_LINE#2:82-87]. The new `LINE_NO` is the highest existing line number of the order plus 10 (10 for the first line) [PKG_ORDER.ADD_LINE#2:89]. Inserts the line with UPPER(`P_PROD_CD`), `P_QTY`, `P_PRICE` and `LINE_AMT` = ROUND(`P_QTY` * `P_PRICE`, 2) [PKG_ORDER.ADD_LINE#2:91-92]. The insert fires `TRG_ORDL_AIUD`, which adds the line amount to `ORDERS.TOTAL_AMT` [TRG_ORDL_AIUD:5-6]. Increments `PKG_ORDER.G_LINE_CNT` [PKG_ORDER.ADD_LINE#2:94]. It does not check that the product is active or validate `P_PRICE` [PKG_ORDER.ADD_LINE#2:76-95].

### `PKG_ORDER.PROCESS_ORDER`

Confirms, holds or cancels the order given by `P_ORD_ID`, or every order in status `PKG_ORDER.ST_NEW` when it is NULL; applies a discount from `PKG_ORDER.CALC_DISC`, checks credit with `CUST_MGMT.CHK_CREDIT`, and with `P_SHIP` TRUE ships the order and creates an invoice [PKG_ORDER.PROCESS_ORDER:120-255]. It uses a savepoint per order, swallows all errors per order, and commits every 50 orders and at the end [PKG_ORDER.PROCESS_ORDER:145] [PKG_ORDER.PROCESS_ORDER:242-253]. Full walkthrough: [PKG_ORDER.PROCESS_ORDER](pkg_order/process_order.md).

### `PKG_ORDER.SET_STATUS`

Updates `ORDERS.ORD_STATUS` to `P_STATUS` for `P_ORD_ID`, without checking the value or the current status [PKG_ORDER.SET_STATUS:100]. When no row was updated it writes a 'W' log line 'order not found' and returns normally [PKG_ORDER.SET_STATUS:101-103]. It does not commit [PKG_ORDER.SET_STATUS:98-104].

### `PKG_ORDER.CANCEL_ORDER`

Reads the order status; an unknown order raises NO_DATA_FOUND to the caller [PKG_ORDER.CANCEL_ORDER:261]. Status equal to `PKG_ORDER.ST_INVOICED` calls `INV_API.CANCEL_INVOICE_FOR_ORDER`; a status above it raises -20103 [PKG_ORDER.CANCEL_ORDER:263-269]. Any status below `PKG_ORDER.ST_INVOICED`, including `PKG_ORDER.ST_SHIPPED`, is cancelled without further checks [PKG_ORDER.CANCEL_ORDER:263-274]. The UPDATE sets status `PKG_ORDER.ST_CANCELLED` and appends ' | CANCELLED: ' and `P_REASON` to `REMARKS`, cut to 4000 characters [PKG_ORDER.CANCEL_ORDER:271-274]. A 'W' log line with the reason is written [PKG_ORDER.CANCEL_ORDER:276]. It does not commit [PKG_ORDER.CANCEL_ORDER:258-277]. `INV_API.CANCEL_INVOICE_FOR_ORDER` cancels each 'OPEN' or 'PART' invoice of the order through `INV_API.CANCEL_INVOICE`, which sets the order back to `PKG_ORDER.ST_CONFIRMED` before this procedure sets it to `PKG_ORDER.ST_CANCELLED` [INV_API.CANCEL_INVOICE_FOR_ORDER:155-160] [INV_API.CANCEL_INVOICE:147].

### `PKG_ORDER.GET_ORDER_TOTAL`

Returns SUM(`LINE_AMT`) of the order's `ORDER_LINES`, or 0 when the order has no lines or does not exist [PKG_ORDER.GET_ORDER_TOTAL:110-111]. It returns the sum of line amounts, not `ORDERS.TOTAL_AMT` [PKG_ORDER.GET_ORDER_TOTAL:110].

### Private units

| Unit | Signature | Body | Called by |
|------|-----------|------|-----------|
| `PKG_ORDER.WLOG` | `PROCEDURE WLOG(P_ACT IN VARCHAR2, P_ID IN NUMBER, P_MSG IN VARCHAR2, P_SEV IN CHAR DEFAULT 'I')` | 11-14 | `PKG_ORDER.NEW_ORDER`, `PKG_ORDER.SET_STATUS`, `PKG_ORDER.PROCESS_ORDER`, `PKG_ORDER.CANCEL_ORDER` |
| `PKG_ORDER.CALC_DISC` | `FUNCTION CALC_DISC(P_CUST_TYPE IN CHAR, P_AMT IN NUMBER) RETURN NUMBER` | 18-32 | `PKG_ORDER.PROCESS_ORDER` |

`PKG_ORDER.WLOG` passes its arguments to `UTIL_LOG.LOG_MSG`, with `P_ID` converted by TO_CHAR [PKG_ORDER.WLOG:13]. `UTIL_LOG.LOG_MSG` is an autonomous transaction that commits its own insert and swallows its own errors, so log lines survive a rollback by the caller and a logging error never reaches the caller [UTIL_LOG.LOG_MSG:63] [UTIL_LOG.LOG_MSG:82-85].

`PKG_ORDER.CALC_DISC` returns a percentage: 7.5 when `P_AMT` is above 25000, 5 when it is above 10000, otherwise 0, plus 2 when `P_CUST_TYPE` is 'W' [PKG_ORDER.CALC_DISC:21-31]. The maximum return value is 9.5 [PKG_ORDER.CALC_DISC:21-29]. The comment at [PKG_ORDER(body):17] says "discount: 5% above 10k, 10% for wholesale"; the code does not agree: it gives 7.5 above 25000 and adds 2, not 10, for 'W' [PKG_ORDER.CALC_DISC:21-29].

## Dependencies

### Calls out

| From unit | To | Kind | Line |
|-----------|----|------|------|
| `PKG_ORDER.WLOG` | `UTIL_LOG.LOG_MSG` | CALL | 13 |
| `PKG_ORDER.NEW_ORDER` | `UTIL_LOG.SET_CTX` | CALL | 39 |
| `PKG_ORDER.NEW_ORDER` | `ORD_SEQ` | SEQUENCE_USE | 46 |
| `PKG_ORDER.NEW_ORDER` | `UTIL_LOG.G_USER` | VARIABLE_REF | 49 |
| `PKG_ORDER.NEW_ORDER` | `PKG_ORDER.WLOG` | CALL | 52 |
| `PKG_ORDER.ADD_LINE#1` | `PKG_ORDER.ADD_LINE#2` | CALL | 72 |
| `PKG_ORDER.ADD_LINE#2` | `TRG_ORDL_AIUD` | FIRES_TRIGGER | 91 |
| `PKG_ORDER.SET_STATUS` | `PKG_ORDER.WLOG` | CALL | 102 |
| `PKG_ORDER.PROCESS_ORDER` | `UTIL_LOG.SET_CTX` | CALL | 140 |
| `PKG_ORDER.PROCESS_ORDER` | `PKG_ORDER.WLOG` | CALL | 141, 148, 156, 173, 186, 219, 221, 234, 254 |
| `PKG_ORDER.PROCESS_ORDER` | `PKG_ORDER.SET_STATUS` | CALL | 172, 175, 185, 233 |
| `PKG_ORDER.PROCESS_ORDER` | `PKG_ORDER.CALC_DISC` | CALL | 177 |
| `PKG_ORDER.PROCESS_ORDER` | `CUST_MGMT.CHK_CREDIT` | CALL | 191 |
| `PKG_ORDER.PROCESS_ORDER` | `UTIL_LOG.ADD_WORKDAYS` | CALL | 210 |
| `PKG_ORDER.PROCESS_ORDER` | `INV_API.CREATE_INVOICE#1` | CALL | 214 |
| `PKG_ORDER.PROCESS_ORDER` | `UTIL_LOG.LOG_ERR` | CALL | 249 |
| `PKG_ORDER.CANCEL_ORDER` | `INV_API.CANCEL_INVOICE_FOR_ORDER` | CALL | 265 |
| `PKG_ORDER.CANCEL_ORDER` | `PKG_ORDER.WLOG` | CALL | 276 |

### Called by

| Caller | Unit called | Line |
|--------|-------------|------|
| `INV_API.CREATE_INVOICE#2` | `PKG_ORDER.SET_STATUS` (CALL) and `PKG_ORDER.ST_INVOICED` (VARIABLE_REF) | 119 |
| `INV_API.CANCEL_INVOICE` | `PKG_ORDER.SET_STATUS` (CALL) and `PKG_ORDER.ST_CONFIRMED` (VARIABLE_REF) | 147 |
| `PKG_ORDER.PROCESS_ORDER` | `PKG_ORDER.SET_STATUS`, `PKG_ORDER.CALC_DISC`, `PKG_ORDER.WLOG` (see Calls out) | 172, 177, 141 |
| `PKG_ORDER.ADD_LINE#1` | `PKG_ORDER.ADD_LINE#2` | 72 |
| `PKG_ORDER.NEW_ORDER` | `PKG_ORDER.WLOG` | 52 |
| `PKG_ORDER.SET_STATUS` | `PKG_ORDER.WLOG` | 102 |
| `PKG_ORDER.CANCEL_ORDER` | `PKG_ORDER.WLOG` | 276 |

`PKG_ORDER.NEW_ORDER`, `PKG_ORDER.ADD_LINE#1`, `PKG_ORDER.PROCESS_ORDER`, `PKG_ORDER.CANCEL_ORDER` and `PKG_ORDER.GET_ORDER_TOTAL` have no caller in legacy_code/ (`NO_CALLER`) [PKG_ORDER.NEW_ORDER:35] [PKG_ORDER.ADD_LINE#1:58] [PKG_ORDER.PROCESS_ORDER:120] [PKG_ORDER.CANCEL_ORDER:258] [PKG_ORDER.GET_ORDER_TOTAL:107]. Callers outside the source tree cannot be seen [PKG_ORDER.PROCESS_ORDER:120].

### Package cycles

1. `PKG_ORDER` -> `INV_API` -> `PKG_ORDER` [PKG_ORDER.PROCESS_ORDER:214] [PKG_ORDER.CANCEL_ORDER:265] [INV_API.CREATE_INVOICE#2:119] [INV_API.CANCEL_INVOICE:147]
2. `PKG_ORDER` -> `CUST_MGMT` -> `INV_API` -> `PKG_ORDER` [PKG_ORDER.PROCESS_ORDER:191] [CUST_MGMT.CHK_CREDIT:167] [INV_API.CREATE_INVOICE#2:119]
3. `PKG_ORDER` -> `UTIL_LOG` -> `INV_API` -> `PKG_ORDER` [PKG_ORDER.WLOG:13] [UTIL_LOG.HOUSEKEEPING:165] [INV_API.CANCEL_INVOICE:147]
4. `PKG_ORDER` -> `CUST_MGMT` -> `UTIL_LOG` -> `INV_API` -> `PKG_ORDER` [PKG_ORDER.PROCESS_ORDER:191] [CUST_MGMT.CREATE_CUSTOMER:46] [UTIL_LOG.HOUSEKEEPING:165] [INV_API.CREATE_INVOICE#2:119]

## Tables touched

| Table / view | Operation | Unit | Line | Via |
|--------------|-----------|------|------|-----|
| `CUSTOMERS` | SELECT | `PKG_ORDER.NEW_ORDER` | 41 | STATIC |
| `ORDERS` | INSERT | `PKG_ORDER.NEW_ORDER` | 48 | STATIC |
| `PRODUCTS` | SELECT | `PKG_ORDER.ADD_LINE#1` | 63 | STATIC |
| `ORDERS` | SELECT | `PKG_ORDER.ADD_LINE#2` | 80 | STATIC |
| `ORDER_LINES` | SELECT | `PKG_ORDER.ADD_LINE#2` | 89 | STATIC |
| `ORDER_LINES` | INSERT | `PKG_ORDER.ADD_LINE#2` | 91 | STATIC |
| `ORDERS` | UPDATE | `PKG_ORDER.SET_STATUS` | 100 | STATIC |
| `ORDER_LINES` | SELECT | `PKG_ORDER.GET_ORDER_TOTAL` | 110 | STATIC |
| `ORDERS` | SELECT | `PKG_ORDER.PROCESS_ORDER` | 124 | STATIC |
| `CUSTOMERS` | SELECT | `PKG_ORDER.PROCESS_ORDER` | 124 | STATIC |
| `ORDER_LINES` | SELECT | `PKG_ORDER.PROCESS_ORDER` | 152 | STATIC |
| `ORDERS` | UPDATE | `PKG_ORDER.PROCESS_ORDER` | 158 | STATIC |
| `ORDER_LINES` | SELECT | `PKG_ORDER.PROCESS_ORDER` | 166 | STATIC |
| `PRODUCTS` | SELECT | `PKG_ORDER.PROCESS_ORDER` | 166 | STATIC |
| `ORDERS` | UPDATE | `PKG_ORDER.PROCESS_ORDER` | 194 | STATIC |
| `ORDERS` | UPDATE | `PKG_ORDER.PROCESS_ORDER` | 202 | STATIC |
| `ORDERS` | UPDATE | `PKG_ORDER.PROCESS_ORDER` | 208 | STATIC |
| `ORDERS` | UPDATE | `PKG_ORDER.PROCESS_ORDER` | 227 | STATIC |
| `ORDERS` | SELECT | `PKG_ORDER.CANCEL_ORDER` | 261 | STATIC |
| `ORDERS` | UPDATE | `PKG_ORDER.CANCEL_ORDER` | 271 | STATIC |

No access is via DYNAMIC_LITERAL [PKG_ORDER(body):1-279]. Through calls into `INV_API`, `PKG_ORDER.PROCESS_ORDER` and `PKG_ORDER.CANCEL_ORDER` also write `INVOICES` [INV_API.CREATE_INVOICE#2:113] [INV_API.CANCEL_INVOICE:144].

### Triggers fired

| Unit | Statement line | Trigger | What the trigger writes |
|------|----------------|---------|-------------------------|
| `PKG_ORDER.ADD_LINE#2` | 91 | `TRG_ORDL_AIUD` | UPDATE `ORDERS` set `TOTAL_AMT` = NVL(`TOTAL_AMT`, 0) + the new `LINE_AMT` for the line's order (insert branch); `TRIGGER_DML` flags at lines 6, 8 and 10 [TRG_ORDL_AIUD:5-6] [TRG_ORDL_AIUD:8] [TRG_ORDL_AIUD:10] |

The `ORDERS` updates in this package fire no trigger: `objects.json` has triggers only on `CUSTOMERS`, `ORDER_LINES` and `PAYMENTS` [TRG_CUST_BIU:1-2] [TRG_ORDL_AIUD:1-2] [TRG_PAY_AIR:1-2].

## Side effects and risks

### Transaction control

`PKG_ORDER.PROCESS_ORDER` is the only unit with transaction control [PKG_ORDER.PROCESS_ORDER:145-253]. It sets savepoint `SP_ORD` for each order and rolls back to it when the invoice fails or any error occurs, which undoes only that order's uncommitted writes [PKG_ORDER.PROCESS_ORDER:145] [PKG_ORDER.PROCESS_ORDER:217] [PKG_ORDER.PROCESS_ORDER:247]. The COMMIT every 50 orders and the COMMIT after the loop commit the caller's whole open transaction, including work done before the call; the final COMMIT runs even when no order was selected [PKG_ORDER.PROCESS_ORDER:242-244] [PKG_ORDER.PROCESS_ORDER:253]. A caller cannot roll back what `PKG_ORDER.PROCESS_ORDER` did [PKG_ORDER.PROCESS_ORDER:253]. The other units do not commit or roll back, so their writes stay in the caller's transaction [PKG_ORDER.NEW_ORDER:35-54] [PKG_ORDER.ADD_LINE#2:76-95] [PKG_ORDER.SET_STATUS:98-104] [PKG_ORDER.CANCEL_ORDER:258-277]. Log lines written through `PKG_ORDER.WLOG` are committed by the autonomous transaction in `UTIL_LOG.LOG_MSG` and survive any rollback by the caller [PKG_ORDER.WLOG:13] [UTIL_LOG.LOG_MSG:63] [UTIL_LOG.LOG_MSG:82].

### Package state

| Variable | Visibility | Constant | Written by | Read by |
|----------|------------|----------|------------|---------|
| `PKG_ORDER.ST_NEW` (10) | PUBLIC | yes | - [PKG_ORDER.ST_NEW:4] | `PKG_ORDER.NEW_ORDER` [PKG_ORDER.NEW_ORDER:49], `PKG_ORDER.ADD_LINE#2` [PKG_ORDER.ADD_LINE#2:82], `PKG_ORDER.PROCESS_ORDER` [PKG_ORDER.PROCESS_ORDER:126] [PKG_ORDER.PROCESS_ORDER:147] |
| `PKG_ORDER.ST_HOLD` (15) | PUBLIC | yes | - [PKG_ORDER.ST_HOLD:5] | `PKG_ORDER.ADD_LINE#2` [PKG_ORDER.ADD_LINE#2:82], `PKG_ORDER.PROCESS_ORDER` [PKG_ORDER.PROCESS_ORDER:147] [PKG_ORDER.PROCESS_ORDER:172] [PKG_ORDER.PROCESS_ORDER:175] [PKG_ORDER.PROCESS_ORDER:185] [PKG_ORDER.PROCESS_ORDER:233] |
| `PKG_ORDER.ST_CONFIRMED` (20) | PUBLIC | yes | - [PKG_ORDER.ST_CONFIRMED:6] | `PKG_ORDER.PROCESS_ORDER` [PKG_ORDER.PROCESS_ORDER:195] [PKG_ORDER.PROCESS_ORDER:228], `INV_API.CANCEL_INVOICE` [INV_API.CANCEL_INVOICE:147] |
| `PKG_ORDER.ST_SHIPPED` (30) | PUBLIC | yes | - [PKG_ORDER.ST_SHIPPED:7] | `PKG_ORDER.PROCESS_ORDER` [PKG_ORDER.PROCESS_ORDER:203] [PKG_ORDER.PROCESS_ORDER:209] |
| `PKG_ORDER.ST_INVOICED` (40) | PUBLIC | yes | - [PKG_ORDER.ST_INVOICED:8] | `PKG_ORDER.CANCEL_ORDER` [PKG_ORDER.CANCEL_ORDER:263-264], `INV_API.CREATE_INVOICE#2` [INV_API.CREATE_INVOICE#2:119] |
| `PKG_ORDER.ST_CANCELLED` (90) | PUBLIC | yes | - [PKG_ORDER.ST_CANCELLED:9] | `PKG_ORDER.PROCESS_ORDER` [PKG_ORDER.PROCESS_ORDER:159], `PKG_ORDER.CANCEL_ORDER` [PKG_ORDER.CANCEL_ORDER:272] |
| `PKG_ORDER.G_LAST_ORD_ID` | PUBLIC | no | `PKG_ORDER.NEW_ORDER` [PKG_ORDER.NEW_ORDER:51] | no reader in legacy_code/ [PKG_ORDER.G_LAST_ORD_ID:12] |
| `PKG_ORDER.G_LINE_CNT` | PRIVATE | no | `PKG_ORDER.ADD_LINE#2` [PKG_ORDER.ADD_LINE#2:94] | `PKG_ORDER.ADD_LINE#2` only, to increment it [PKG_ORDER.ADD_LINE#2:94] |
| `PKG_ORDER.G_DISC_CACHE` | PRIVATE | no | no writer in legacy_code/ [PKG_ORDER.G_DISC_CACHE:8] | no reader in legacy_code/ [PKG_ORDER.G_DISC_CACHE:8] |

The three non-constant variables keep their value for the whole database session, between calls [PKG_ORDER.G_LAST_ORD_ID:12] [PKG_ORDER.G_LINE_CNT:7] [PKG_ORDER.G_DISC_CACHE:8]. `PKG_ORDER.G_LAST_ORD_ID` is in the spec, so any code in the session can read or change it; it keeps the id of the last order created by `PKG_ORDER.NEW_ORDER` in the session, also when that insert is later rolled back [PKG_ORDER.G_LAST_ORD_ID:12] [PKG_ORDER.NEW_ORDER:51]. The comment at [PKG_ORDER(spec):11] says "last order created in this session"; the code agrees, with the rollback caveat above [PKG_ORDER.NEW_ORDER:51]. `PKG_ORDER.G_LINE_CNT` starts at 0 and counts lines inserted by `PKG_ORDER.ADD_LINE#2` in the session, including lines later rolled back [PKG_ORDER.G_LINE_CNT:7] [PKG_ORDER.ADD_LINE#2:94]. `PKG_ORDER.G_DISC_CACHE` is declared but never read or written in legacy_code/ [PKG_ORDER.G_DISC_CACHE:8]. `PKG_ORDER.NEW_ORDER` reads `UTIL_LOG.G_USER`, which is package state of `UTIL_LOG` [PKG_ORDER.NEW_ORDER:49].

### Dynamic SQL

None found in metadata.

### Hardcoded values

| Unit | Line | Literal | Used in |
|------|------|---------|---------|
| `PKG_ORDER.ST_NEW` | 4 | 10 | status constant [PKG_ORDER.ST_NEW:4] |
| `PKG_ORDER.ST_HOLD` | 5 | 15 | status constant [PKG_ORDER.ST_HOLD:5] |
| `PKG_ORDER.ST_CONFIRMED` | 6 | 20 | status constant [PKG_ORDER.ST_CONFIRMED:6] |
| `PKG_ORDER.ST_SHIPPED` | 7 | 30 | status constant [PKG_ORDER.ST_SHIPPED:7] |
| `PKG_ORDER.ST_INVOICED` | 8 | 40 | status constant [PKG_ORDER.ST_INVOICED:8] |
| `PKG_ORDER.ST_CANCELLED` | 9 | 90 | status constant [PKG_ORDER.ST_CANCELLED:9] |
| `PKG_ORDER.CALC_DISC` | 21, 22 | 25000, 7.5 | amount threshold and percentage |
| `PKG_ORDER.CALC_DISC` | 23, 24 | 10000, 5 | amount threshold and percentage |
| `PKG_ORDER.CALC_DISC` | 27, 28 | 'W', 2 | customer type and added percentage |
| `PKG_ORDER.NEW_ORDER` | 42 | 'C' | customer status that raises -20100 |
| `PKG_ORDER.NEW_ORDER` | 49 | 'EUR' | `CURR_CD` of a new order |
| `PKG_ORDER.ADD_LINE#1` | 65 | 'Y' | `ACTIVE_YN` filter |
| `PKG_ORDER.ADD_LINE#1` | 68, 69 | 100, 0.97 | quantity threshold and price factor |
| `PKG_ORDER.ADD_LINE#2` | 89 | 10 | line number step |
| `PKG_ORDER.PROCESS_ORDER` | 138 | 25 | minimum order total |
| `PKG_ORDER.PROCESS_ORDER` | 169 | 'N' | `ACTIVE_YN` filter |
| `PKG_ORDER.PROCESS_ORDER` | 174 | 'B' | customer status that puts the order on hold |
| `PKG_ORDER.PROCESS_ORDER` | 180 | 15 | discount cap |
| `PKG_ORDER.PROCESS_ORDER` | 182 | 50 | discount approval threshold |
| `PKG_ORDER.PROCESS_ORDER` | 201 | 'BE' | `COUNTRY_CD` with same-day `SHIP_DT` |
| `PKG_ORDER.PROCESS_ORDER` | 225 | 'G' | customer type confirmed despite failed credit check |
| `PKG_ORDER.PROCESS_ORDER` | 242 | 50 | commit interval |

The meaning of every value in this table, including the status codes, is Unknown: needs human input. The comment at [legacy_code/tables/orders.sql:16] says "10=new 20=confirmed 30=shipped 40=invoiced 90=cancelled"; it has no entry for 15 (`PKG_ORDER.ST_HOLD`) [PKG_ORDER.ST_HOLD:5]. The comment at [legacy_code/tables/orders.sql:17] says "only EUR supported"; `PKG_ORDER.NEW_ORDER` always inserts 'EUR' [PKG_ORDER.NEW_ORDER:49]. The comment at [PKG_ORDER(spec):3] says "order statuses" above the six constants [PKG_ORDER(spec):4-9].

### Other

- `NO_CALLER`: `PKG_ORDER.NEW_ORDER`, `PKG_ORDER.ADD_LINE#1`, `PKG_ORDER.PROCESS_ORDER`, `PKG_ORDER.CANCEL_ORDER` and `PKG_ORDER.GET_ORDER_TOTAL` have no caller in legacy_code/ [PKG_ORDER.NEW_ORDER:35] [PKG_ORDER.ADD_LINE#1:58] [PKG_ORDER.PROCESS_ORDER:120] [PKG_ORDER.CANCEL_ORDER:258] [PKG_ORDER.GET_ORDER_TOTAL:107].
- `TRIGGER_DML`: `TRG_ORDL_AIUD` updates `ORDERS.TOTAL_AMT` on every insert, update or delete of `ORDER_LINES`; in this package only the insert in `PKG_ORDER.ADD_LINE#2` fires it [TRG_ORDL_AIUD:5-10] [PKG_ORDER.ADD_LINE#2:91].
- `ORDERS.TOTAL_AMT` is written by three parties: 0 on insert, the trigger adding gross line amounts, and `PKG_ORDER.PROCESS_ORDER` overwriting it with the discounted net amount [PKG_ORDER.NEW_ORDER:48-49] [TRG_ORDL_AIUD:6] [PKG_ORDER.PROCESS_ORDER:194-198].
- Unreachable branch: in `PKG_ORDER.PROCESS_ORDER` the discount is capped at 15 and then compared with "> 50", so lines 183-186 cannot run [PKG_ORDER.PROCESS_ORDER:180-186].
- `PKG_ORDER.ADD_LINE#2` holds a row lock on the order (FOR UPDATE) until the caller ends the transaction [PKG_ORDER.ADD_LINE#2:80].
- The comments at [PKG_ORDER(body):3-5] give a change history (2010, 2013, 2014) that cannot be checked against the code [PKG_ORDER(body):3-5].

## Error handling

| Unit | Line | Handler / raise | Effect for the caller |
|------|------|-----------------|-----------------------|
| `PKG_ORDER.NEW_ORDER` | 41 | NO_DATA_FOUND, no handler | Raised to the caller when `P_CUST_ID` does not exist [PKG_ORDER.NEW_ORDER:41] |
| `PKG_ORDER.NEW_ORDER` | 43 | RAISE_APPLICATION_ERROR(-20100, 'customer closed') | Raised when the customer status is 'C'; no order is inserted [PKG_ORDER.NEW_ORDER:42-44] |
| `PKG_ORDER.ADD_LINE#1` | 61 | NO_DATA_FOUND, no handler | Raised when the product does not exist or `ACTIVE_YN` is not 'Y' [PKG_ORDER.ADD_LINE#1:61-65] |
| `PKG_ORDER.ADD_LINE#2` | 80 | NO_DATA_FOUND, no handler | Raised when the order does not exist [PKG_ORDER.ADD_LINE#2:80] |
| `PKG_ORDER.ADD_LINE#2` | 83 | RAISE_APPLICATION_ERROR(-20101, 'order ... not editable') | Raised when the status is not `PKG_ORDER.ST_NEW` or `PKG_ORDER.ST_HOLD` [PKG_ORDER.ADD_LINE#2:82-84] |
| `PKG_ORDER.ADD_LINE#2` | 86 | RAISE_APPLICATION_ERROR(-20102, 'qty must be > 0') | Raised when `P_QTY` is 0 or less [PKG_ORDER.ADD_LINE#2:85-87] |
| `PKG_ORDER.SET_STATUS` | 101-102 | SQL%ROWCOUNT = 0, warning log only | No error is raised; the caller cannot tell that no row was updated [PKG_ORDER.SET_STATUS:101-103] |
| `PKG_ORDER.GET_ORDER_TOTAL` | 111 | NVL(..., 0) | Returns 0 for an unknown order or an order without lines [PKG_ORDER.GET_ORDER_TOTAL:110-111] |
| `PKG_ORDER.PROCESS_ORDER` | 246-249 | WHEN OTHERS without RAISE (`WHEN_OTHERS_SWALLOW`) | Rolls back to `SP_ORD`, logs through `UTIL_LOG.LOG_ERR`, continues with the next order; the caller gets a normal return and no error indicator [PKG_ORDER.PROCESS_ORDER:245-250] |
| `PKG_ORDER.PROCESS_ORDER` | 216-219 | NULL from `INV_API.CREATE_INVOICE#1` | Rolls back the order to `SP_ORD` and logs 'invoice failed'; the caller is not told [PKG_ORDER.PROCESS_ORDER:216-219] |
| `PKG_ORDER.CANCEL_ORDER` | 261 | NO_DATA_FOUND, no handler | Raised when the order does not exist [PKG_ORDER.CANCEL_ORDER:261] |
| `PKG_ORDER.CANCEL_ORDER` | 265 | Errors from `INV_API.CANCEL_INVOICE`, no handler | -20200 'Invoice has payments' from `INV_API.CANCEL_INVOICE` reaches the caller, and the UPDATE at line 271 is not reached [PKG_ORDER.CANCEL_ORDER:265] [INV_API.CANCEL_INVOICE:140-142] |
| `PKG_ORDER.CANCEL_ORDER` | 267 | RAISE_APPLICATION_ERROR(-20103, 'cannot cancel order in status ...') | Raised for a status above `PKG_ORDER.ST_INVOICED`, including `PKG_ORDER.ST_CANCELLED` [PKG_ORDER.CANCEL_ORDER:263-268] |

## Open questions

1. The business purpose of the package is Unknown: needs human input [PKG_ORDER(body):1]
2. The meaning of the status codes 10, 15, 20, 30, 40, 90 (the column comment on `ORDERS.ORD_STATUS` does not list 15) is Unknown: needs human input [PKG_ORDER(spec):4-9] [legacy_code/tables/orders.sql:16]
3. The meaning of the hardcoded values in "Hardcoded values" (thresholds 25000, 10000, 100, 25, 15, 50; factors 7.5, 5, 2, 0.97; codes 'C', 'W', 'B', 'G', 'Y', 'N', 'BE', 'EUR') is Unknown: needs human input [PKG_ORDER.CALC_DISC:21-28] [PKG_ORDER.ADD_LINE#1:68-69] [PKG_ORDER.PROCESS_ORDER:138-242]
4. The comment at body line 17 ("5% above 10k, 10% for wholesale") contradicts `PKG_ORDER.CALC_DISC` (7.5 above 25000, 5 above 10000, plus 2 for 'W'); which is correct? [PKG_ORDER(body):17] [PKG_ORDER.CALC_DISC:21-29]
5. The comment "government never on hold" contradicts `PKG_ORDER.PROCESS_ORDER`, which can put a 'G' customer's order on hold for inactive products or customer status 'B' [PKG_ORDER.PROCESS_ORDER:171-175] [PKG_ORDER.PROCESS_ORDER:226]
6. The approval branch (discount > 50) cannot be reached after the cap at 15, and the cap itself has no effect because `PKG_ORDER.CALC_DISC` returns at most 9.5; is this intended? Unknown: needs human input [PKG_ORDER.PROCESS_ORDER:180-186]
7. Batch mode selects only `PKG_ORDER.ST_NEW` orders while the loop also accepts `PKG_ORDER.ST_HOLD`; is a held order expected to be reprocessed only on explicit request? Unknown: needs human input [PKG_ORDER.PROCESS_ORDER:126] [PKG_ORDER.PROCESS_ORDER:147]
8. A 'G' customer whose credit check fails is confirmed but never shipped or invoiced, even with `P_SHIP` TRUE; is that intended? Unknown: needs human input [PKG_ORDER.PROCESS_ORDER:225-231]
9. `PKG_ORDER.PROCESS_ORDER` commits the caller's transaction; callers outside legacy_code/ (scheduler, application) cannot be seen, so who depends on this is Unknown: needs human input [PKG_ORDER.PROCESS_ORDER:243] [PKG_ORDER.PROCESS_ORDER:253]
10. Five public units have no caller in legacy_code/; whether they are called from outside the source tree (applications, jobs, other schemas; a parser limitation) is Unknown: needs human input [PKG_ORDER.NEW_ORDER:35] [PKG_ORDER.ADD_LINE#1:58] [PKG_ORDER.GET_ORDER_TOTAL:107] [PKG_ORDER.CANCEL_ORDER:258] [PKG_ORDER.PROCESS_ORDER:120]
11. `PKG_ORDER.G_DISC_CACHE` is never read or written, and `PKG_ORDER.G_LAST_ORD_ID` has no reader in legacy_code/; are they read outside the source tree? Unknown: needs human input [PKG_ORDER.G_DISC_CACHE:8] [PKG_ORDER.G_LAST_ORD_ID:12]
12. `ORDERS.TOTAL_AMT` is the discounted net amount after `PKG_ORDER.PROCESS_ORDER`, but `TRG_ORDL_AIUD` adjusts it with gross line amounts and `PKG_ORDER.GET_ORDER_TOTAL` returns the gross sum; which value is authoritative? Unknown: needs human input [PKG_ORDER.PROCESS_ORDER:197] [TRG_ORDL_AIUD:6] [PKG_ORDER.GET_ORDER_TOTAL:110]
13. `PKG_ORDER.CANCEL_ORDER` cancels an order in status `PKG_ORDER.ST_SHIPPED` without any check, and `PKG_ORDER.SET_STATUS` accepts any status value; is that intended? Unknown: needs human input [PKG_ORDER.CANCEL_ORDER:263-274] [PKG_ORDER.SET_STATUS:100]
14. The comment at body line 207 says "export: ship next business day"; `UTIL_LOG.ADD_WORKDAYS` skips only days named SAT or SUN, which depends on the session date language and ignores holidays [PKG_ORDER.PROCESS_ORDER:207-210] [UTIL_LOG.ADD_WORKDAYS:113-119]
15. Calls from `UTIL_LOG` into `INV_API` (cycles 3 and 4) were taken from `dependencies.json` and not traced further in this doc [UTIL_LOG.HOUSEKEEPING:165]
