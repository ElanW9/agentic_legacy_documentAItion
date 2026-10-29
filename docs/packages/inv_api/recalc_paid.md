# `INV_API.RECALC_PAID`

| Field | Value |
|-------|-------|
| Package doc | [inv_api](../inv_api.md) |
| Kind | PROCEDURE |
| Visibility | PRIVATE |
| Spec | none (private) |
| Body | `legacy_code/packages/inv_api.pkb` lines 25-32 |

```sql
PROCEDURE RECALC_PAID
```

## Purpose

Sets `INVOICES.PAID_AMT` of every invoice to the sum of its `PAYMENTS.PAY_AMT` and commits [INV_API.RECALC_PAID:27-31].
The unit is private and has no caller in legacy_code/, so it cannot run [INV_API.RECALC_PAID:25].

## Parameters

None found in metadata.

## Logic walkthrough

1. Updates every `INVOICES` row, without a WHERE clause on the outer UPDATE, setting `INVOICES.PAID_AMT` to the sum of the invoice's payments, or 0 when there are none [INV_API.RECALC_PAID:27-30].
2. Commits [INV_API.RECALC_PAID:31].
3. It does not change `INVOICES.INV_STATUS` [INV_API.RECALC_PAID:27-30].

## Dependencies

| Direction | Unit / object | Kind | Line |
|-----------|---------------|------|------|
| called by | no caller in legacy_code/ | NO_CALLER | 25 |

## Tables touched

| Table / view | Operation | Line | Via |
|--------------|-----------|------|-----|
| `INVOICES` | UPDATE | 27 | STATIC |
| `PAYMENTS` | SELECT | 29 | STATIC |

No FIRES_TRIGGER edge exists for this unit [INV_API.RECALC_PAID:27].

## Side effects and risks

- If it were called, the COMMIT at line 31 would also commit any uncommitted work of the caller [INV_API.RECALC_PAID:31].
- NO_CALLER: the unit is private and nothing in the package body calls it, so it is unreachable [INV_API.RECALC_PAID:25].
- The comment at [INV_API(body):24] says "recalculates paid_amt from payments. run monthly!"; the recalculation matches the code, but nothing in legacy_code/ runs it [INV_API.RECALC_PAID:25-32].

## Error handling

None found in metadata.

## Open questions

1. The comment at [INV_API(body):24] says "run monthly!"; who ran this unit, and is it still needed [INV_API.RECALC_PAID:25]?
2. Should a recalculation also reset `INVOICES.INV_STATUS`, as `TRG_PAY_AIR` does on each payment [TRG_PAY_AIR:14-20]?
