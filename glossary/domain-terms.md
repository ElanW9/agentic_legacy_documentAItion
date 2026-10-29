# Domain terms

**Stub.** Everything below is **unconfirmed**. It was pre-filled from names and values seen in `legacy_code/` (step 1 inspection, `docs/repo-plan.md`). The "probable meaning" of an abbreviation is a reading of the name, not a fact, so docs must not rely on it. A domain expert confirms or corrects each entry and then changes its status to `confirmed`.

## Abbreviations

| Abbr | Probable meaning | Seen in | Status |
|------|------------------|---------|--------|
| `cust` | customer | `CUST_MGMT`, `CUST_HIST`, `CUSTOMERS.CUST_ID` | unconfirmed |
| `ord` | order | `ORD_SEQ`, `ORDERS.ORD_ID`, `ORD_SUMMARY_V` | unconfirmed |
| `ordl` | order line | `TRG_ORDL_AIUD`, `ORDL_ORD_FK` | unconfirmed |
| `inv` | invoice | `INV_API`, `INV_SEQ`, `INVOICES.INV_NO` | unconfirmed |
| `pay` | payment | `PAY_ID_SEQ`, `PAYMENTS.PAY_METHOD`, `TRG_PAY_AIR` | unconfirmed |
| `prod` | product | `ORDER_LINES.PROD_CD`, `PRODUCTS.PROD_CD` | unconfirmed |
| `amt` | amount | `NET_AMT`, `GROSS_AMT`, `PAID_AMT`, `UTIL_LOG.FMT_AMT` | unconfirmed |
| `dt` | date | `INV_DT`, `DUE_DT`, `ARCH_DT`, `INV_API.GET_DUE_DT` | unconfirmed |
| `ts` | timestamp | `AUDIT_LOG.LOG_TS` (type `TIMESTAMP`) | unconfirmed |
| `cd` | code | `COUNTRY_CD`, `CURR_CD`, `PROD_CD` | unconfirmed |
| `no` | number (identifier shown to people) | `INVOICES.INV_NO`, `CUSTOMERS.VAT_NO`, `ORDER_LINES.LINE_NO` | unconfirmed |
| `disc` | discount | `ORDERS.DISC_PCT`, `PKG_ORDER.CALC_DISC` | unconfirmed |
| `pct` | percentage | `ORDERS.DISC_PCT` | unconfirmed |
| `vat` | value added tax | `INVOICES.VAT_AMT`, `PRODUCTS.VAT_CAT`, `INV_API.CALC_VAT` | unconfirmed |
| `cat` | category | `PRODUCTS.VAT_CAT` | unconfirmed |
| `curr` | currency | `ORDERS.CURR_CD` | unconfirmed |
| `ctry` | country | parameter `P_CTRY` in `CUST_MGMT.CREATE_CUSTOMER` | unconfirmed |
| `st` | status | constants `PKG_ORDER.ST_*` | unconfirmed |
| `chk` | check | `CUST_MGMT.CHK_CREDIT`, `CUST_MGMT.CHK_OVERDUE_CUSTOMERS` | unconfirmed |
| `upd` | update, updated | `CUST_MGMT.UPD_CREDIT_LIMIT`, `CUSTOMERS.UPD_DT`, `CUSTOMERS.UPD_BY` | unconfirmed |
| `chg` | change | `CUST_HIST.CHG_DT`, `CUST_HIST.CHG_BY` | unconfirmed |
| `hist` | history | `CUST_HIST` | unconfirmed |
| `arch` | archive | `AUDIT_LOG_ARCH`, `AUDIT_LOG_ARCH.ARCH_DT` | unconfirmed |
| `ovd` | overdue | cursor `C_OVD` in `CUST_MGMT.CHK_OVERDUE_CUSTOMERS` | unconfirmed |
| `ref` | reference | `PAYMENTS.REF_TXT` | unconfirmed |
| `sev` | severity | `AUDIT_LOG.SEV`, `UTIL_LOG.C_SEV_*` | unconfirmed |
| `usr` | user | `AUDIT_LOG.USR` | unconfirmed |
| `obj` | object | `AUDIT_LOG.OBJ_ID` | unconfirmed |
| `msg` | message | `AUDIT_LOG.MSG`, `UTIL_LOG.LOG_MSG` | unconfirmed |
| `cnt` | count | `INVOICES.REMINDER_CNT`, `PKG_ORDER.G_LINE_CNT` | unconfirmed |
| `descr` | description | `PRODUCTS.DESCR` | unconfirmed |
| `val` | value | `APP_PARAMS.PARAM_VAL` | unconfirmed |
| `yn` | yes/no flag | `PRODUCTS.ACTIVE_YN` | unconfirmed |
| `lvl` | level | `UTIL_LOG.LVL`, `UTIL_LOG.G_LOG_LEVEL` | unconfirmed |

## Code values

What each source says about a coded column. Sources disagree in places. Where they do, the docs report the code's behaviour and add an open question. They never pick a meaning.

### `CUSTOMERS.STATUS`

| Value | Stated meaning | Where the value appears | Status |
|-------|----------------|-------------------------|--------|
| `A` | the comment says `A/B` with no meaning | check constraint [CUSTOMERS:16]; comment [legacy_code/tables/customers.sql:20]; set by [CUST_MGMT.UNBLOCK_CUSTOMER:121] | unconfirmed |
| `B` | as above | set by [CUST_MGMT.BLOCK_CUSTOMER:102]; tested in [TRG_CUST_BIU:22] [PKG_ORDER.PROCESS_ORDER:174] | unconfirmed |
| `C` | not mentioned in the comment | check constraint [CUSTOMERS:16]; set by [CUST_MGMT.MERGE_CUST:31] | unconfirmed |

### `CUSTOMERS.CUST_TYPE`

| Value | Stated meaning | Where the value appears | Status |
|-------|----------------|-------------------------|--------|
| `R` | retail (comment) | check constraint [CUSTOMERS:15]; comment [legacy_code/tables/customers.sql:19] | unconfirmed |
| `W` | wholesale (comment) | as above; tested in [PKG_ORDER.CALC_DISC:27] | unconfirmed |
| `G` | not mentioned in the comment | check constraint [CUSTOMERS:15]; tested in [PKG_ORDER.PROCESS_ORDER:225] | unconfirmed |

### `ORDERS.ORD_STATUS`

| Value | Stated meaning | Where the value appears | Status |
|-------|----------------|-------------------------|--------|
| `10` | new (comment, constant `ST_NEW`, view text `NEW`) | [legacy_code/tables/orders.sql:16] [PKG_ORDER.ST_NEW:4] [ORD_SUMMARY_V:5] | unconfirmed |
| `15` | hold (constant `ST_HOLD`, view text `HOLD`); not in the comment | [PKG_ORDER.ST_HOLD:5] [ORD_SUMMARY_V:5]; set by [CUST_MGMT.BLOCK_CUSTOMER:108] | unconfirmed |
| `20` | confirmed | [legacy_code/tables/orders.sql:16] [PKG_ORDER.ST_CONFIRMED:6] [ORD_SUMMARY_V:5] | unconfirmed |
| `30` | shipped | [legacy_code/tables/orders.sql:16] [PKG_ORDER.ST_SHIPPED:7] [ORD_SUMMARY_V:5] | unconfirmed |
| `40` | invoiced | [legacy_code/tables/orders.sql:16] [PKG_ORDER.ST_INVOICED:8] [ORD_SUMMARY_V:6] | unconfirmed |
| `50` | none: no comment, constant or view text | set by [TRG_PAY_AIR:17]; shown as `UNKNOWN` by [ORD_SUMMARY_V:5-6] | unconfirmed |
| `90` | cancelled | [legacy_code/tables/orders.sql:16] [PKG_ORDER.ST_CANCELLED:9] [ORD_SUMMARY_V:6] | unconfirmed |

### `INVOICES.INV_STATUS`

| Value | Stated meaning | Where the value appears | Status |
|-------|----------------|-------------------------|--------|
| `OPEN` | none stated | check constraint [INVOICES:18]; default [INVOICES:12]; set by [INV_API.CREATE_INVOICE#2:117] | unconfirmed |
| `PART` | none stated | set by [TRG_PAY_AIR:19]; read by [V_OPEN_INVOICES:14] | unconfirmed |
| `PAID` | none stated | set by [TRG_PAY_AIR:15] | unconfirmed |
| `CANC` | none stated | set by [INV_API.CANCEL_INVOICE:144] | unconfirmed |

### `PAYMENTS.PAY_METHOD`

| Value | Stated meaning | Where the value appears | Status |
|-------|----------------|-------------------------|--------|
| `BT` | bank transfer (comment) | comment [legacy_code/tables/payments.sql:13]; parameter default [INV_API.REGISTER_PAYMENT:166] | unconfirmed |
| `CC` | credit card (comment) | comment [legacy_code/tables/payments.sql:13]; allowed by [INV_API.REGISTER_PAYMENT:177] | unconfirmed |
| `CA` | not mentioned in the comment | allowed by [INV_API.REGISTER_PAYMENT:177]; amount check at [INV_API.REGISTER_PAYMENT:193] | unconfirmed |

### `AUDIT_LOG.SEV`

| Value | Stated meaning | Where the value appears | Status |
|-------|----------------|-------------------------|--------|
| `I` | info (constant name `C_SEV_INFO`) | [UTIL_LOG.C_SEV_INFO:8] | unconfirmed |
| `W` | warning (constant name `C_SEV_WARN`) | [UTIL_LOG.C_SEV_WARN:9]; level 2 in [UTIL_LOG.LVL:20] | unconfirmed |
| `E` | error (constant name `C_SEV_ERR`) | [UTIL_LOG.C_SEV_ERR:10]; level 3 in [UTIL_LOG.LVL:19] | unconfirmed |

## Business terms

Candidate terms taken from object names. Definitions: Unknown: needs human input.

| Term | Objects | Definition | Status |
|------|---------|------------|--------|
| customer | `CUSTOMERS`, `CUST_MGMT` | Unknown: needs human input | unconfirmed |
| credit limit | `CUSTOMERS.CREDIT_LIMIT`, `CUST_MGMT.UPD_CREDIT_LIMIT`, `CUST_MGMT.CHK_CREDIT` | Unknown: needs human input | unconfirmed |
| blocked customer | `CUSTOMERS.BLOCKED_REASON`, `CUST_MGMT.BLOCK_CUSTOMER` | Unknown: needs human input | unconfirmed |
| order, order line | `ORDERS`, `ORDER_LINES`, `PKG_ORDER` | Unknown: needs human input | unconfirmed |
| invoice | `INVOICES`, `INV_API` | Unknown: needs human input | unconfirmed |
| payment | `PAYMENTS`, `INV_API.REGISTER_PAYMENT` | Unknown: needs human input | unconfirmed |
| reminder | `INVOICES.REMINDER_CNT`, `INV_API.SEND_REMINDERS` | Unknown: needs human input | unconfirmed |
| VAT category | `PRODUCTS.VAT_CAT` | Unknown: needs human input | unconfirmed |
| application parameter | `APP_PARAMS`, `UTIL_LOG.GET_PARAM` | Unknown: needs human input | unconfirmed |
