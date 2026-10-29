CREATE OR REPLACE PACKAGE inv_api AS
  /*
   * Invoicing API
   * T. Maes, 2015
   */

  FUNCTION create_invoice(p_ord_id IN NUMBER) RETURN NUMBER;
  FUNCTION create_invoice(p_ord_id IN NUMBER, p_inv_dt IN DATE) RETURN NUMBER;

  PROCEDURE cancel_invoice(p_inv_id IN NUMBER);
  PROCEDURE cancel_invoice_for_order(p_ord_id IN NUMBER);

  PROCEDURE register_payment(p_inv_id IN NUMBER,
                             p_amt    IN NUMBER,
                             p_method IN VARCHAR2 DEFAULT 'BT',
                             p_ref    IN VARCHAR2 DEFAULT NULL);

  FUNCTION get_open_amt(p_cust_id IN NUMBER) RETURN NUMBER;

  FUNCTION calc_vat(p_cust_id IN NUMBER, p_net IN NUMBER) RETURN NUMBER;

  PROCEDURE send_reminders;

END inv_api;
/
