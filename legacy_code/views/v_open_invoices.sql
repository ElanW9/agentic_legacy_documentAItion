CREATE OR REPLACE VIEW v_open_invoices AS
SELECT i.inv_id,
       i.inv_no,
       i.cust_id,
       c.cust_name,
       i.inv_dt,
       i.due_dt,
       i.gross_amt,
       i.paid_amt,
       i.gross_amt - NVL(i.paid_amt, 0) AS open_amt,
       TRUNC(SYSDATE) - i.due_dt        AS days_overdue
  FROM invoices i, customers c
 WHERE i.cust_id = c.cust_id
   AND i.inv_status IN ('OPEN', 'PART');
