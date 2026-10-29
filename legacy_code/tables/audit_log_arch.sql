-- same layout as audit_log + arch_dt (must stay in sync!)
CREATE TABLE audit_log_arch (
  log_id   NUMBER(15),
  log_ts   TIMESTAMP,
  module   VARCHAR2(30),
  action   VARCHAR2(30),
  obj_id   VARCHAR2(50),
  msg      VARCHAR2(4000),
  usr      VARCHAR2(30),
  sev      CHAR(1),
  arch_dt  DATE
);
