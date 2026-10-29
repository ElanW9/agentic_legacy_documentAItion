# `PKG_ORDER.PROCESS_ORDER`

| Field | Value |
|-------|-------|
| Package doc | [pkg_order](../pkg_order.md) |
| Kind | PROCEDURE |
| Visibility | PUBLIC |
| Spec | `legacy_code/packages/pkg_order.pks` line 19 |
| Body | `legacy_code/packages/pkg_order.pkb` lines 120-255 |

```sql
PROCEDURE PROCESS_ORDER(P_ORD_ID IN NUMBER DEFAULT null, P_SHIP IN BOOLEAN DEFAULT false)
```

## Purpose

The procedure loops over one order (when `P_ORD_ID` is given) or over all orders in status `PKG_ORDER.ST_NEW` (when it is NULL), and for each order either skips it, cancels it, puts it on hold, or confirms it with a discount and a credit check [PKG_ORDER.PROCESS_ORDER:121-127] [PKG_ORDER.PROCESS_ORDER:143-239]. With `P_SHIP` TRUE, a confirmed order is also set to shipped and an invoice is created through `INV_API.CREATE_INVOICE#1` [PKG_ORDER.PROCESS_ORDER:200-223]. It commits every 50 processed orders and always at the end [PKG_ORDER.PROCESS_ORDER:241-244] [PKG_ORDER.PROCESS_ORDER:253]. The business reason for the procedure and for its rules is Unknown: needs human input.

## Parameters

| Name | Mode | Type | Default | Used for |
|------|------|------|---------|----------|
| `P_ORD_ID` | IN | NUMBER | null | Cursor filter: that order in any status, or, when NULL, every order in status `PKG_ORDER.ST_NEW`; also passed to the start and end log calls [PKG_ORDER.PROCESS_ORDER:126] [PKG_ORDER.PROCESS_ORDER:141] [PKG_ORDER.PROCESS_ORDER:254] |
| `P_SHIP` | IN | BOOLEAN | false | When TRUE, a confirmed order is set to `PKG_ORDER.ST_SHIPPED` and invoiced [PKG_ORDER.PROCESS_ORDER:200-223] |

## Logic walkthrough

1. Sets the logging context to `'PKG_ORDER'` through `UTIL_LOG.SET_CTX` and writes a 'start' log line [PKG_ORDER.PROCESS_ORDER:140-141].
2. Cursor `C_ORD` joins `ORDERS` with `CUSTOMERS` on `CUST_ID` and selects the order given by `P_ORD_ID`, or, when `P_ORD_ID` is NULL, every order with status `PKG_ORDER.ST_NEW`, ordered by `ORD_DT` [PKG_ORDER.PROCESS_ORDER:121-127]. An order whose customer row is missing is not selected, because the join is an inner join [PKG_ORDER.PROCESS_ORDER:124-125]. In batch mode an order in status `PKG_ORDER.ST_HOLD` is not selected, although the loop body accepts that status [PKG_ORDER.PROCESS_ORDER:126] [PKG_ORDER.PROCESS_ORDER:147].
3. For each order, an inner block sets savepoint `SP_ORD` [PKG_ORDER.PROCESS_ORDER:144-145].
4. An order whose status is not `PKG_ORDER.ST_NEW` or `PKG_ORDER.ST_HOLD` is skipped with a 'W' log line [PKG_ORDER.PROCESS_ORDER:147-148].
5. Otherwise the procedure counts the order lines and sums `LINE_AMT` from `ORDER_LINES` [PKG_ORDER.PROCESS_ORDER:150-153].
6. No lines: a 'W' log line is written and the order is not changed [PKG_ORDER.PROCESS_ORDER:155-156].
7. Line total below `l_min_amt` (25): the order is set to `PKG_ORDER.ST_CANCELLED` and `REMARKS` is overwritten with 'MIN AMOUNT' by a direct UPDATE, not through `PKG_ORDER.SET_STATUS` [PKG_ORDER.PROCESS_ORDER:138] [PKG_ORDER.PROCESS_ORDER:157-161].
8. Otherwise the procedure counts the order's lines whose product has `ACTIVE_YN` = 'N' [PKG_ORDER.PROCESS_ORDER:164-169]. If there is at least one, the order is set to `PKG_ORDER.ST_HOLD` through `PKG_ORDER.SET_STATUS` and a 'W' line is logged [PKG_ORDER.PROCESS_ORDER:171-173].
9. Customer status 'B': the order is set to `PKG_ORDER.ST_HOLD`, without a log line from this procedure [PKG_ORDER.PROCESS_ORDER:174-175].
10. Otherwise the discount percentage comes from `PKG_ORDER.CALC_DISC` on the line total and the customer type, and is capped at 15 with LEAST [PKG_ORDER.PROCESS_ORDER:177-180]. `PKG_ORDER.CALC_DISC` returns at most 9.5 (7.5 plus 2), so the cap does not change the value [PKG_ORDER.CALC_DISC:21-31].
11. If the discount is above 50, it is set to 0, the order is set to `PKG_ORDER.ST_HOLD` and a 'W' line is logged [PKG_ORDER.PROCESS_ORDER:182-187]. After the cap at line 180 the discount is at most 15, so this branch cannot be reached [PKG_ORDER.PROCESS_ORDER:180-182].
12. The net amount is the line total minus the discount percentage, rounded to 2 decimals [PKG_ORDER.PROCESS_ORDER:189].
13. `CUST_MGMT.CHK_CREDIT` is called with the customer and the net amount [PKG_ORDER.PROCESS_ORDER:191]. When it returns 1, the order is set to `PKG_ORDER.ST_CONFIRMED` with `DISC_PCT` and `TOTAL_AMT` set to the discount and the net amount [PKG_ORDER.PROCESS_ORDER:193-198].
14. With `P_SHIP` TRUE, the order is set to `PKG_ORDER.ST_SHIPPED` [PKG_ORDER.PROCESS_ORDER:200-212]. `SHIP_DT` is SYSDATE when `COUNTRY_CD` is 'BE' or NULL, and otherwise `UTIL_LOG.ADD_WORKDAYS(TRUNC(SYSDATE), 1)` [PKG_ORDER.PROCESS_ORDER:201-211]. `UTIL_LOG.ADD_WORKDAYS` moves forward one day at a time and counts only days whose day name is not SAT or SUN [UTIL_LOG.ADD_WORKDAYS:113-119].
15. Still with `P_SHIP` TRUE, `INV_API.CREATE_INVOICE#1` is called for the order [PKG_ORDER.PROCESS_ORDER:214]. When it returns NULL, the procedure rolls back to `SP_ORD`, increments the error count and logs 'invoice failed' with severity 'E' [PKG_ORDER.PROCESS_ORDER:216-219]. Otherwise it logs the invoice id [PKG_ORDER.PROCESS_ORDER:220-221].
16. When `CUST_MGMT.CHK_CREDIT` returns anything other than 1 (including NULL) and the customer type is 'G', the order is confirmed with discount and net amount, but not shipped or invoiced even when `P_SHIP` is TRUE [PKG_ORDER.PROCESS_ORDER:224-231]. For every other customer type the order is set to `PKG_ORDER.ST_HOLD` and 'credit check failed' is logged [PKG_ORDER.PROCESS_ORDER:232-234].
17. Every order that leaves the inner block without an exception, including skipped orders, orders without lines and orders whose invoice failed, increments `l_done_cnt` [PKG_ORDER.PROCESS_ORDER:241]. Every 50th such order triggers a COMMIT [PKG_ORDER.PROCESS_ORDER:242-244].
18. Any exception in the inner block is caught by WHEN OTHERS: rollback to `SP_ORD`, error count plus one, and `UTIL_LOG.LOG_ERR` with the order id; the loop continues with the next order [PKG_ORDER.PROCESS_ORDER:245-250].
19. After the loop the procedure commits and logs the processed and error counts [PKG_ORDER.PROCESS_ORDER:253-254].

## Dependencies

| Direction | Unit / object | Kind | Line |
|-----------|---------------|------|------|
| calls | `UTIL_LOG.SET_CTX` | CALL | 140 |
| calls | `PKG_ORDER.WLOG` | CALL | 141, 148, 156, 173, 186, 219, 221, 234, 254 |
| calls | `PKG_ORDER.SET_STATUS` | CALL | 172, 175, 185, 233 |
| calls | `PKG_ORDER.CALC_DISC` | CALL | 177 |
| calls | `CUST_MGMT.CHK_CREDIT` | CALL | 191 |
| calls | `UTIL_LOG.ADD_WORKDAYS` | CALL | 210 |
| calls | `INV_API.CREATE_INVOICE#1` | CALL | 214 |
| calls | `UTIL_LOG.LOG_ERR` | CALL | 249 |

The `NO_CALLER` flag in `risk_flags.json` says there is no caller in legacy_code/ [PKG_ORDER.PROCESS_ORDER:120].

## Tables touched

| Table / view | Operation | Line | Via |
|--------------|-----------|------|-----|
| `ORDERS` | SELECT | 124 | STATIC |
| `CUSTOMERS` | SELECT | 124 | STATIC |
| `ORDER_LINES` | SELECT | 152 | STATIC |
| `ORDERS` | UPDATE | 158 | STATIC |
| `ORDER_LINES` | SELECT | 166 | STATIC |
| `PRODUCTS` | SELECT | 166 | STATIC |
| `ORDERS` | UPDATE | 194 | STATIC |
| `ORDERS` | UPDATE | 202 | STATIC |
| `ORDERS` | UPDATE | 208 | STATIC |
| `ORDERS` | UPDATE | 227 | STATIC |

The calls to `PKG_ORDER.SET_STATUS` also update `ORDERS` [PKG_ORDER.SET_STATUS:100]. `dependencies.json` has no `FIRES_TRIGGER` edge for this unit, and `objects.json` lists no trigger on `ORDERS` [TRG_CUST_BIU:1-2] [TRG_ORDL_AIUD:1-2] [TRG_PAY_AIR:1-2]. Through `INV_API.CREATE_INVOICE#1`, the procedure also inserts into `INVOICES` and calls `PKG_ORDER.SET_STATUS` with `PKG_ORDER.ST_INVOICED` [INV_API.CREATE_INVOICE#1:79] [INV_API.CREATE_INVOICE#2:113-119].

## Side effects and risks

- COMMIT at line 243 (every 50th order) and at line 253 (always, also when no order matched) commits the whole transaction of the caller, including work the caller did before the call [PKG_ORDER.PROCESS_ORDER:243] [PKG_ORDER.PROCESS_ORDER:253].
- The cursor loop continues to fetch from `C_ORD` after the COMMIT at line 243 [PKG_ORDER.PROCESS_ORDER:143] [PKG_ORDER.PROCESS_ORDER:243].
- Savepoint `SP_ORD` is set per order; ROLLBACK TO at lines 217 and 247 undoes only the uncommitted writes made since that savepoint for the current order, including writes made by `INV_API.CREATE_INVOICE#1` and `PKG_ORDER.SET_STATUS` [PKG_ORDER.PROCESS_ORDER:145] [PKG_ORDER.PROCESS_ORDER:217] [PKG_ORDER.PROCESS_ORDER:247].
- Log lines are written by `UTIL_LOG.LOG_MSG`, which runs as an autonomous transaction and commits on its own, so they survive the ROLLBACK TO and any rollback by the caller [UTIL_LOG.LOG_MSG:63] [UTIL_LOG.LOG_MSG:82] [PKG_ORDER.WLOG:13].
- Hardcoded values in this unit: 25 [PKG_ORDER.PROCESS_ORDER:138], 'N' [PKG_ORDER.PROCESS_ORDER:169], 'B' [PKG_ORDER.PROCESS_ORDER:174], 15 [PKG_ORDER.PROCESS_ORDER:180], 50 [PKG_ORDER.PROCESS_ORDER:182], 'BE' [PKG_ORDER.PROCESS_ORDER:201], 'G' [PKG_ORDER.PROCESS_ORDER:225], 50 [PKG_ORDER.PROCESS_ORDER:242]. Also not flagged by the parser: 'MIN AMOUNT' [PKG_ORDER.PROCESS_ORDER:160] and the 1 workday [PKG_ORDER.PROCESS_ORDER:210]. Their meaning is Unknown: needs human input.
- `ORDERS.TOTAL_AMT` is set to the discounted net amount here, while trigger `TRG_ORDL_AIUD` keeps adding and subtracting line amounts on the same column [PKG_ORDER.PROCESS_ORDER:197] [TRG_ORDL_AIUD:5-10].
- The comment at [PKG_ORDER.PROCESS_ORDER:226] says "government never on hold"; the code can still set an order of a 'G' customer to `PKG_ORDER.ST_HOLD` at lines 172 and 175, before the credit check [PKG_ORDER.PROCESS_ORDER:171-175].
- The comment at [PKG_ORDER.PROCESS_ORDER:183] says "needs manager approval"; it sits in the branch that cannot be reached (step 11) [PKG_ORDER.PROCESS_ORDER:180-186].
- The comment at [PKG_ORDER.PROCESS_ORDER:207] says "export: ship next business day"; the code adds one day that is not a Saturday or Sunday by day name, and does not consider holidays [PKG_ORDER.PROCESS_ORDER:210] [UTIL_LOG.ADD_WORKDAYS:113-119].
- The comment at [PKG_ORDER(body):118] says "if p_ord_id is null all NEW orders are processed (batch)"; the cursor agrees [PKG_ORDER.PROCESS_ORDER:126].

## Error handling

| Line | Handler / raise | Effect for the caller |
|------|-----------------|-----------------------|
| 246-249 | WHEN OTHERS without RAISE (`WHEN_OTHERS_SWALLOW`) | Any error for one order is rolled back to `SP_ORD`, logged through `UTIL_LOG.LOG_ERR`, and not passed on; the caller gets a normal return with no error count or status [PKG_ORDER.PROCESS_ORDER:245-250] |
| 216-219 | NULL from `INV_API.CREATE_INVOICE#1` | Shipping and confirmation of that order are rolled back to `SP_ORD`, an 'E' line is logged; the caller is not told [PKG_ORDER.PROCESS_ORDER:216-219] |
| 140-143, 253-254 | No handler outside the inner block | An error in `UTIL_LOG.SET_CTX`, the cursor, the final COMMIT or the last log call is raised to the caller [PKG_ORDER.PROCESS_ORDER:140-143] [PKG_ORDER.PROCESS_ORDER:253-254] |

## Open questions

1. Why are orders in status `PKG_ORDER.ST_HOLD` never picked up in batch mode, while an explicit `P_ORD_ID` in that status is processed? Unknown: needs human input [PKG_ORDER.PROCESS_ORDER:126] [PKG_ORDER.PROCESS_ORDER:147]
2. The discount cap of 15 and the "> 50" approval branch have no effect with the current `PKG_ORDER.CALC_DISC` (maximum 9.5); is the approval branch expected to be reachable? Unknown: needs human input [PKG_ORDER.PROCESS_ORDER:180-186]
3. For customer type 'G' with a failed credit check the order is confirmed but never shipped or invoiced, even with `P_SHIP` TRUE; is that intended? Unknown: needs human input [PKG_ORDER.PROCESS_ORDER:225-231]
4. The meaning of the hardcoded values 25, 15, 50 (twice), 'N', 'B', 'G', 'BE' and 'MIN AMOUNT' is Unknown: needs human input [PKG_ORDER.PROCESS_ORDER:138] [PKG_ORDER.PROCESS_ORDER:160]
5. The comment "government never on hold" contradicts lines 171-175, which can put a 'G' customer's order on hold [PKG_ORDER.PROCESS_ORDER:226] [PKG_ORDER.PROCESS_ORDER:171-175]
6. The procedure commits the caller's transaction; callers outside legacy_code/ (schedulers, applications) cannot be seen, so it is unknown who relies on this [PKG_ORDER.PROCESS_ORDER:120] [PKG_ORDER.PROCESS_ORDER:253]
7. `ORDERS.TOTAL_AMT` holds the discounted net amount after confirmation, but `TRG_ORDL_AIUD` keeps adjusting it by gross line amounts, and `PKG_ORDER.GET_ORDER_TOTAL` returns the gross sum; which value is authoritative is Unknown: needs human input [PKG_ORDER.PROCESS_ORDER:197] [TRG_ORDL_AIUD:5-10] [PKG_ORDER.GET_ORDER_TOTAL:110-111]
