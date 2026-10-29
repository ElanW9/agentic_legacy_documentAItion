CREATE OR REPLACE TRIGGER trg_cust_biu
BEFORE INSERT OR UPDATE ON customers
FOR EACH ROW
BEGIN
  IF INSERTING THEN
    IF :NEW.cust_id IS NULL THEN
      :NEW.cust_id := seq_customers.NEXTVAL;
    END IF;
    :NEW.created_dt := SYSDATE;
  END IF;

  :NEW.cust_name := UPPER(TRIM(:NEW.cust_name));
  :NEW.upd_dt    := SYSDATE;
  :NEW.upd_by    := NVL(SYS_CONTEXT('USERENV', 'CLIENT_IDENTIFIER'), USER);

  -- keep history of credit limit
  IF UPDATING('CREDIT_LIMIT') AND NVL(:OLD.credit_limit, -1) <> NVL(:NEW.credit_limit, -1) THEN
    INSERT INTO cust_hist (cust_id, chg_dt, old_limit, new_limit, chg_by)
    VALUES (:NEW.cust_id, SYSDATE, :OLD.credit_limit, :NEW.credit_limit, :NEW.upd_by);
  END IF;

  IF :NEW.status = 'B' THEN
    :NEW.credit_limit := 0;
  END IF;
END;
/
