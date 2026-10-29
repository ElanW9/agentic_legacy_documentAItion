# Conventions

Two parts: how the docs in this repo are written (agreed), and the naming conventions observed in `legacy_code/` (**unconfirmed**, from the step 1 inspection in `docs/repo-plan.md`).

## 1. Documentation conventions

### Identifiers

Names are written in UPPERCASE, the way `metadata/objects.json` stores them.

| Object | Id | Example |
|--------|----|---------|
| Subprogram | `PACKAGE.NAME` | `PKG_ORDER.SET_STATUS` |
| Overloaded subprogram | `PACKAGE.NAME#n`, where n is the position in the package body | `PKG_ORDER.ADD_LINE#2` |
| Package variable or constant | `PACKAGE.NAME` | `PKG_ORDER.ST_HOLD` |
| Package spec or body as a whole | `PACKAGE(spec)` / `PACKAGE(body)` | `UTIL_LOG(spec)` |
| Table, view, trigger, sequence | bare name | `ORDERS`, `TRG_PAY_AIR` |

### Citations

Every claim ends with at least one citation in square brackets:

```
[ID:line]            [PKG_ORDER.SET_STATUS:100]
[ID:start-end]       [PKG_ORDER.SET_STATUS:98-104]
[path:start-end]     [legacy_code/tables/orders.sql:16]
```

- Line numbers are line numbers in the source file, not offsets within the unit. They must fall inside the range that `objects.json` gives for that id.
- Use the `path` form only for lines that belong to no object, such as `COMMENT ON` statements after a `CREATE TABLE` or seed `INSERT`s.
- Several citations go side by side: `[A:1-5] [B:9]`.

### Markers

| Marker | Use |
|--------|-----|
| `Unknown: needs human input` | Business intent, meaning of a code value, or anything else that the code does not show. Repeat it as an item under "Open questions". |
| `None found in metadata.` | A template section with nothing to report. Never delete the heading. |
| `the comment at [..] says ...` | The only way to use a source comment. Comments are not facts and may be outdated. |
| `no caller in legacy_code/` | Instead of "unused" or "dead": callers outside the source tree cannot be seen. |

### Files

| Doc | Path | Template |
|-----|------|----------|
| Package | `docs/packages/<package_lowercase>.md` | `templates/package.md` |
| Complex unit | `docs/packages/<package_lowercase>/<unit_lowercase>.md` | `templates/procedure.md` |
| Cross-package flow | `docs/flows/<flow-name>.md` | `templates/flow.md` |

## 2. Naming conventions observed in the code (unconfirmed)

These patterns were seen when reading the code. They are not enforced anywhere and every package deviates from them somewhere. Do not infer an object's role from its name alone.

### Prefixes and suffixes

| Pattern | Seen in | Probable meaning | Status |
|---------|---------|------------------|--------|
| `p_` | parameters, all packages | parameter | unconfirmed |
| `l_` | locals in `PKG_ORDER` | local variable | unconfirmed |
| `v_` / `V_` | locals in `INV_API`, `UTIL_LOG` (lowercase), `CUST_MGMT` (uppercase) | local variable | unconfirmed |
| `V_` | `CUST_MGMT.V_MAX_LIMIT`, a package-level **constant** | breaks the pattern above | unconfirmed |
| `g_` | package globals in `INV_API`, `PKG_ORDER`, `UTIL_LOG` | global (package state) | unconfirmed |
| `c_` | constants in `INV_API`, `UTIL_LOG`; cursor `C_OVD` in `CUST_MGMT` | constant, or cursor | unconfirmed |
| `st_` | `PKG_ORDER.ST_NEW` ... `ST_CANCELLED` | order status constant | unconfirmed |
| `PKG_` / `_MGMT` / `_API` / `UTIL_` | package names | no single scheme | unconfirmed |
| `V_` prefix / `_V` suffix | views `V_OPEN_INVOICES`, `CUST_BALANCE_V`, `ORD_SUMMARY_V` | view | unconfirmed |
| `SEQ_<table>` / `<abbr>_SEQ` / `<table>_SEQ` | `SEQ_CUSTOMERS`, `ORD_SEQ`, `INV_SEQ`, `PAY_ID_SEQ`, `AUDIT_LOG_SEQ` | sequence | unconfirmed |
| `TRG_<abbr>_<timing><events>` | `TRG_CUST_BIU`, `TRG_ORDL_AIUD`, `TRG_PAY_AIR` | trigger | unconfirmed |
| `_PK`, `_FK`, `_UK`, `_CK` | constraint names, e.g. `INV_ORD_FK`, `INVOICES_NO_UK` | primary key, foreign key, unique key, check | unconfirmed |
| `_YN` | `PRODUCTS.ACTIVE_YN` | Y/N flag | unconfirmed |
| `_ARCH`, `_HIST` | `AUDIT_LOG_ARCH`, `CUST_HIST` | archive copy, history | unconfirmed |

### Trigger name suffix

The letters after the abbreviation match the trigger's timing and events in `objects.json` for all three triggers. Use the metadata, not the name.

| Letters | Probable meaning | Example | Matches metadata |
|---------|------------------|---------|------------------|
| `B` / `A` | BEFORE / AFTER | `TRG_CUST_BIU` | yes |
| `I`, `U`, `D` | INSERT, UPDATE, DELETE | `TRG_ORDL_AIUD` | yes |
| `R` | row-level | `TRG_PAY_AIR` | yes |

### Code style per package

| Package | Keyword case | Indent | Notes |
|---------|--------------|--------|-------|
| `CUST_MGMT` | UPPERCASE everything | 3 spaces | Toad-style headers |
| `PKG_ORDER` | lowercase everything | 2 spaces | |
| `INV_API` | UPPERCASE keywords, lowercase names | 2 spaces | |
| `UTIL_LOG` | UPPERCASE keywords, lowercase names | 2 spaces | |
