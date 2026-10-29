-- install_order.sql
-- run as schema owner in SQL*Plus
-- last update: 2016 (check with DBA before running on PROD)

PROMPT === sequences ===
@@sequences/seq_customers.sql
@@sequences/ord_seq.sql
@@sequences/inv_seq.sql
@@sequences/pay_id_seq.sql
@@sequences/audit_log_seq.sql

PROMPT === tables ===
@@tables/app_params.sql
@@tables/audit_log.sql
@@tables/audit_log_arch.sql
@@tables/customers.sql
@@tables/cust_hist.sql
@@tables/products.sql
@@tables/orders.sql
@@tables/order_lines.sql
@@tables/invoices.sql
@@tables/payments.sql

PROMPT === views ===
@@views/v_open_invoices.sql
@@views/cust_balance_v.sql
@@views/ord_summary_v.sql

PROMPT === package specs ===
@@packages/util_log.pks
@@packages/cust_mgmt.pks
@@packages/pkg_order.pks
@@packages/inv_api.pks

PROMPT === package bodies ===
@@packages/util_log.pkb
@@packages/cust_mgmt.pkb
@@packages/pkg_order.pkb
@@packages/inv_api.pkb

PROMPT === triggers ===
@@triggers/trg_cust_biu.sql
@@triggers/trg_ordl_aiud.sql
@@triggers/trg_pay_air.sql

PROMPT === recompile ===
EXEC DBMS_UTILITY.COMPILE_SCHEMA(USER, FALSE);
