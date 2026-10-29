-- credit limit history (filled by trigger)
CREATE TABLE cust_hist (
  cust_id    NUMBER(10),
  chg_dt     DATE,
  old_limit  NUMBER(12,2),
  new_limit  NUMBER(12,2),
  chg_by     VARCHAR2(30)
);
