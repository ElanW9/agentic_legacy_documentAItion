-- customer credit overview
CREATE OR REPLACE VIEW cust_balance_v AS
SELECT c.cust_id,
       c.cust_name,
       c.credit_limit,
       NVL(SUM(o.open_amt), 0)                  open_amt,
       c.credit_limit - NVL(SUM(o.open_amt), 0) avail_credit
  FROM customers c
  LEFT JOIN v_open_invoices o ON o.cust_id = c.cust_id
 GROUP BY c.cust_id, c.cust_name, c.credit_limit;
