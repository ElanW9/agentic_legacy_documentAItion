CREATE OR REPLACE TRIGGER trg_pay_air
AFTER INSERT ON payments
FOR EACH ROW
DECLARE
  l_gross  invoices.gross_amt%TYPE;
  l_paid   invoices.paid_amt%TYPE;
  l_ord    invoices.ord_id%TYPE;
BEGIN
  UPDATE invoices
     SET paid_amt = NVL(paid_amt, 0) + :NEW.pay_amt
   WHERE inv_id = :NEW.inv_id
  RETURNING gross_amt, paid_amt, ord_id INTO l_gross, l_paid, l_ord;

  IF l_paid >= l_gross - 0.05 THEN
    UPDATE invoices SET inv_status = 'PAID' WHERE inv_id = :NEW.inv_id;
    -- close order
    UPDATE orders SET ord_status = 50 WHERE ord_id = l_ord;
  ELSE
    UPDATE invoices SET inv_status = 'PART' WHERE inv_id = :NEW.inv_id;
  END IF;
END;
/
