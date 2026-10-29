CREATE TABLE audit_log (
  log_id   NUMBER(15)      NOT NULL,
  log_ts   TIMESTAMP       DEFAULT SYSTIMESTAMP,
  module   VARCHAR2(30),
  action   VARCHAR2(30),
  obj_id   VARCHAR2(50),
  msg      VARCHAR2(4000),
  usr      VARCHAR2(30),
  sev      CHAR(1),
  CONSTRAINT audit_log_pk PRIMARY KEY (log_id)
);
