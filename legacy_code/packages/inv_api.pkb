CREATE OR REPLACE PACKAGE BODY inv_api AS
  /*
   * Invoicing API - body
   * Replaces the old INVOICE_HDR / INVOICE_DTL logic.
   *
   * 2015-04 tm  initial
   * 2016-05 tm  reverse charge
   * 2019-01 sd  cash limit
   */

  -- cached VAT rate, loaded on first use
  g_vat_rate    NUMBER;
  g_inv_prefix  VARCHAR2(10) := 'INV';

  c_tolerance   CONSTANT NUMBER := 0.05;

  ---------------------------------------------------------------------------
  FUNCTION next_inv_no(p_id IN NUMBER) RETURN VARCHAR2 IS
  BEGIN
    RETURN g_inv_prefix || TO_CHAR(SYSDATE, 'YYYY') || '-' || LPAD(p_id, 6, '0');
  END next_inv_no;

  ---------------------------------------------------------------------------
  -- recalculates paid_amt from payments. run monthly!
  PROCEDURE recalc_paid IS
  BEGIN
    UPDATE invoices i
       SET paid_amt = (SELECT NVL(SUM(p.pay_amt), 0)
                         FROM payments p
                        WHERE p.inv_id = i.inv_id);
    COMMIT;
  END recalc_paid;

  ---------------------------------------------------------------------------
  FUNCTION get_due_dt(p_cust_id IN NUMBER, p_inv_dt IN DATE) RETURN DATE IS
    v_type CHAR(1);
  BEGIN
    v_type := cust_mgmt.get_cust_type(p_cust_id);

    IF v_type = 'G' THEN
      RETURN util_log.add_workdays(p_inv_dt, 60);
    ELSIF v_type = 'W' THEN
      RETURN p_inv_dt + 45;
    ELSE
      RETURN p_inv_dt + 30;
    END IF;
  END get_due_dt;

  ---------------------------------------------------------------------------
  -- VAT: 21% for BE, 0 for intra-EU with VAT number, else 21%
  FUNCTION calc_vat(p_cust_id IN NUMBER, p_net IN NUMBER) RETURN NUMBER IS
    v_ctry  VARCHAR2(2);
    v_vat   VARCHAR2(20);
  BEGIN
    IF g_vat_rate IS NULL THEN
      g_vat_rate := util_log.get_param_num('VAT_RATE', 21);
    END IF;

    v_ctry := cust_mgmt.get_cust_attr(p_cust_id, 'COUNTRY_CD');
    v_vat  := cust_mgmt.get_cust_attr(p_cust_id, 'VAT_NO');

    IF NVL(v_ctry, 'BE') = 'BE' THEN
      RETURN ROUND(p_net * g_vat_rate / 100, 2);
    ELSIF v_ctry IN ('NL', 'FR', 'DE', 'LU') AND v_vat IS NOT NULL THEN
      RETURN 0;  -- reverse charge
    ELSE
      RETURN ROUND(p_net * g_vat_rate / 100, 2);
    END IF;
  EXCEPTION
    WHEN OTHERS THEN
      RETURN 0;
  END calc_vat;

  ---------------------------------------------------------------------------
  FUNCTION create_invoice(p_ord_id IN NUMBER) RETURN NUMBER IS
    v_ship DATE;
  BEGIN
    SELECT ship_dt INTO v_ship FROM orders WHERE ord_id = p_ord_id;
    RETURN create_invoice(p_ord_id, NVL(v_ship, SYSDATE));
  EXCEPTION
    WHEN NO_DATA_FOUND THEN
      RETURN NULL;
  END create_invoice;

  ---------------------------------------------------------------------------
  FUNCTION create_invoice(p_ord_id IN NUMBER, p_inv_dt IN DATE) RETURN NUMBER IS
    v_ord   orders%ROWTYPE;
    v_id    invoices.inv_id%TYPE;
    v_vat   NUMBER;
    v_cnt   NUMBER;
  BEGIN
    SELECT * INTO v_ord FROM orders WHERE ord_id = p_ord_id;

    IF v_ord.ord_status NOT IN (20, 30) THEN
      util_log.log_msg('CREATE_INV', p_ord_id, 'bad status ' || v_ord.ord_status, 'W');
      RETURN NULL;
    END IF;

    SELECT COUNT(*)
      INTO v_cnt
      FROM invoices
     WHERE ord_id = p_ord_id
       AND inv_status <> 'CANC';

    IF v_cnt > 0 THEN
      RETURN NULL;
    END IF;

    SELECT inv_seq.NEXTVAL INTO v_id FROM dual;

    v_vat := calc_vat(v_ord.cust_id, v_ord.total_amt);

    INSERT INTO invoices (inv_id, inv_no, ord_id, cust_id, inv_dt, due_dt,
                          net_amt, vat_amt, gross_amt, paid_amt, inv_status, reminder_cnt)
    VALUES (v_id, next_inv_no(v_id), p_ord_id, v_ord.cust_id, TRUNC(p_inv_dt),
            get_due_dt(v_ord.cust_id, TRUNC(p_inv_dt)),
            v_ord.total_amt, v_vat, v_ord.total_amt + v_vat, 0, 'OPEN', 0);

    pkg_order.set_status(p_ord_id, pkg_order.st_invoiced);

    util_log.log_msg('CREATE_INV', TO_CHAR(v_id),
                     'order ' || p_ord_id || ' amt ' || util_log.fmt_amt(v_ord.total_amt + v_vat));
    RETURN v_id;
  EXCEPTION
    WHEN NO_DATA_FOUND THEN
      RETURN NULL;
  END create_invoice;

  ---------------------------------------------------------------------------
  PROCEDURE cancel_invoice(p_inv_id IN NUMBER) IS
    v_paid  NUMBER;
    v_ord   NUMBER;
  BEGIN
    SELECT NVL(paid_amt, 0), ord_id
      INTO v_paid, v_ord
      FROM invoices
     WHERE inv_id = p_inv_id
       FOR UPDATE;

    IF v_paid > 0 THEN
      RAISE_APPLICATION_ERROR(-20200, 'Invoice has payments');
    END IF;

    UPDATE invoices SET inv_status = 'CANC' WHERE inv_id = p_inv_id;

    -- back to confirmed
    pkg_order.set_status(v_ord, pkg_order.st_confirmed);

    util_log.log_msg('CANCEL_INV', TO_CHAR(p_inv_id), NULL, 'W');
  END cancel_invoice;

  ---------------------------------------------------------------------------
  PROCEDURE cancel_invoice_for_order(p_ord_id IN NUMBER) IS
  BEGIN
    FOR r IN (SELECT inv_id
                FROM invoices
               WHERE ord_id = p_ord_id
                 AND inv_status IN ('OPEN', 'PART')) LOOP
      cancel_invoice(r.inv_id);
    END LOOP;
  END cancel_invoice_for_order;

  ---------------------------------------------------------------------------
  PROCEDURE register_payment(p_inv_id IN NUMBER,
                             p_amt    IN NUMBER,
                             p_method IN VARCHAR2 DEFAULT 'BT',
                             p_ref    IN VARCHAR2 DEFAULT NULL) IS
    v_inv invoices%ROWTYPE;
  BEGIN
    util_log.set_ctx('INV_API');

    SELECT * INTO v_inv FROM invoices WHERE inv_id = p_inv_id;

    IF v_inv.inv_status = 'CANC' THEN
      RAISE_APPLICATION_ERROR(-20201, 'Invoice cancelled');
    END IF;
    IF p_method NOT IN ('BT', 'CC', 'CA') THEN
      RAISE_APPLICATION_ERROR(-20202, 'Unknown payment method');
    END IF;

    INSERT INTO payments (pay_id, inv_id, pay_dt, pay_amt, pay_method, ref_txt, created_by)
    VALUES (pay_id_seq.NEXTVAL, p_inv_id, SYSDATE, p_amt, p_method, p_ref, NVL(util_log.g_user, USER));

    -- update invoice paid amount and status
    SELECT * INTO v_inv FROM invoices WHERE inv_id = p_inv_id;

    IF v_inv.paid_amt > v_inv.gross_amt + c_tolerance THEN
      util_log.log_msg('PAYMENT', TO_CHAR(p_inv_id),
                       'overpaid by ' || util_log.fmt_amt(v_inv.paid_amt - v_inv.gross_amt), 'W');
    END IF;

    -- cash payments above 3000 not allowed (anti money laundering)
    IF p_method = 'CA' AND p_amt > 3000 THEN
      ROLLBACK;
      RAISE_APPLICATION_ERROR(-20203, 'Cash limit exceeded');
    END IF;

    COMMIT;
  EXCEPTION
    WHEN NO_DATA_FOUND THEN
      RAISE_APPLICATION_ERROR(-20204, 'Invoice ' || p_inv_id || ' not found');
  END register_payment;

  ---------------------------------------------------------------------------
  FUNCTION get_open_amt(p_cust_id IN NUMBER) RETURN NUMBER IS
    v_amt NUMBER;
  BEGIN
    SELECT NVL(SUM(open_amt), 0)
      INTO v_amt
      FROM v_open_invoices
     WHERE cust_id = p_cust_id;

    -- add confirmed orders not yet invoiced
    SELECT v_amt + NVL(SUM(total_amt), 0)
      INTO v_amt
      FROM orders
     WHERE cust_id = p_cust_id
       AND ord_status IN (20, 30);

    RETURN v_amt;
  END get_open_amt;

  ---------------------------------------------------------------------------
  PROCEDURE send_reminders IS
    v_email VARCHAR2(200);
  BEGIN
    FOR r IN (SELECT inv_id, inv_no, cust_id, open_amt, days_overdue
                FROM v_open_invoices
               WHERE days_overdue > 14) LOOP
      v_email := cust_mgmt.get_cust_attr(r.cust_id, 'EMAIL');

      IF v_email IS NOT NULL THEN
        -- TODO: real mail sending, for now only logged
        util_log.log_msg('REMINDER', r.inv_no,
                         'to ' || v_email || ' open ' || util_log.fmt_amt(r.open_amt));

        UPDATE invoices
           SET reminder_cnt = reminder_cnt + 1
         WHERE inv_id = r.inv_id;
      END IF;
    END LOOP;

    COMMIT;

    cust_mgmt.chk_overdue_customers;
  END send_reminders;

END inv_api;
/
