# `CUST_MGMT.CHK_CREDIT`

| Field | Value |
|-------|-------|
| Package doc | [cust_mgmt](../cust_mgmt.md) |
| Kind | FUNCTION |
| Visibility | PUBLIC |
| Spec | `legacy_code/packages/cust_mgmt.pks` line 21 |
| Body | `legacy_code/packages/cust_mgmt.pkb` lines 147-177 |

```sql
FUNCTION CHK_CREDIT(P_CUST_ID IN NUMBER, P_AMT IN NUMBER) RETURN NUMBER
```

## Purpose

The function returns 1 or 0 depending on the customer's status, type, credit limit and open amount plus `P_AMT` [CUST_MGMT.CHK_CREDIT:147-177].
The comment at [CUST_MGMT(body):146] says "check if customer can place order of P_AMT"; the only caller in legacy_code/ uses it that way, comparing the result with 1 [PKG_ORDER.PROCESS_ORDER:191-193].
The business rule behind the check is Unknown: needs human input.

## Parameters

| Name | Mode | Type | Default | Used for |
|------|------|------|---------|----------|
| `P_CUST_ID` | IN | NUMBER | - | Selects the `CUSTOMERS` row and is passed to `INV_API.GET_OPEN_AMT` [CUST_MGMT.CHK_CREDIT:157] [CUST_MGMT.CHK_CREDIT:167] |
| `P_AMT` | IN | NUMBER | - | Added to the open amount before the comparison with the limit [CUST_MGMT.CHK_CREDIT:169] |
| return | - | NUMBER | - | 1 or 0; see the walkthrough [CUST_MGMT.CHK_CREDIT:159-176] |

The comment at [CUST_MGMT(spec):20] says the function "returns Y/N"; the code returns the numbers 1 and 0, so the comment does not match the code [CUST_MGMT.CHK_CREDIT:160] [CUST_MGMT.CHK_CREDIT:164].

## Logic walkthrough

1. Read `CREDIT_LIMIT`, `STATUS` and `CUST_TYPE` of the customer [CUST_MGMT.CHK_CREDIT:154-157].
2. If `STATUS` is not `'A'`, return 0 [CUST_MGMT.CHK_CREDIT:159-161].
3. If `CUST_TYPE` is `'G'`, return 1, without looking at the limit or the open amount [CUST_MGMT.CHK_CREDIT:163-165].
4. Get the open amount from `INV_API.GET_OPEN_AMT`, which sums `OPEN_AMT` from `V_OPEN_INVOICES` and `TOTAL_AMT` of `ORDERS` with `ORD_STATUS` 20 or 30 [CUST_MGMT.CHK_CREDIT:167] [INV_API.GET_OPEN_AMT:208-218].
5. If the limit is NULL, or open amount plus `P_AMT` is at most `CREDIT_LIMIT * 1.1`, return 1; otherwise return 0 [CUST_MGMT.CHK_CREDIT:169-173].
6. If the customer does not exist (`NO_DATA_FOUND` from step 1), return 0 [CUST_MGMT.CHK_CREDIT:174-176].

A NULL `P_AMT` makes the comparison in step 5 not true, so the function returns 0 unless the limit is NULL [CUST_MGMT.CHK_CREDIT:169-172].
A blocked customer has status `'B'` and therefore always gets 0 at step 2 [CUST_MGMT.CHK_CREDIT:159-160].

## Dependencies

| Direction | Unit / object | Kind | Line |
|-----------|---------------|------|------|
| calls | `INV_API.GET_OPEN_AMT` | CALL | 167 |
| called by | `PKG_ORDER.PROCESS_ORDER` | CALL | 191 |

## Tables touched

| Table / view | Operation | Line | Via |
|--------------|-----------|------|-----|
| `CUSTOMERS` | SELECT | 156 | STATIC |

`INV_API.GET_OPEN_AMT` reads `V_OPEN_INVOICES` and `ORDERS`; those reads are attributed to that unit, not to this one [INV_API.GET_OPEN_AMT:210] [INV_API.GET_OPEN_AMT:216].
No triggers are fired: the function only reads [CUST_MGMT.CHK_CREDIT:154-157].

## Side effects and risks

- No writes, no transaction control [CUST_MGMT.CHK_CREDIT:147-177].
- Hardcoded values: `'A'` at line 159, `'G'` at line 163, 1.1 at line 169 [CUST_MGMT.CHK_CREDIT:159-169]; their meaning is Unknown: needs human input.
- This package and `INV_API` call each other, which forms the package cycle `CUST_MGMT` -> `INV_API` -> `CUST_MGMT` [CUST_MGMT.CHK_CREDIT:167] [INV_API.CALC_VAT:59].

## Error handling

| Line | Handler / raise | Effect for the caller |
|------|-----------------|-----------------------|
| 175-176 | WHEN NO_DATA_FOUND | Returns 0 for a missing customer |
| 147-177 | no other handler | Any other error, also from `INV_API.GET_OPEN_AMT`, goes to the caller |

## Open questions

1. What does the factor 1.1 on the credit limit represent? Unknown: needs human input [CUST_MGMT.CHK_CREDIT:169].
2. Why does type `'G'` always pass? Unknown: needs human input [CUST_MGMT.CHK_CREDIT:163-165].
3. Is the spec comment "returns Y/N" outdated, given that the function returns 1/0 [CUST_MGMT.CHK_CREDIT:160]?
