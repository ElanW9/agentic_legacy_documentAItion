CREATE TABLE customers (
  cust_id        NUMBER(10)      NOT NULL,
  cust_name      VARCHAR2(100)   NOT NULL,
  cust_type      CHAR(1)         DEFAULT 'R' NOT NULL,
  vat_no         VARCHAR2(20),
  email          VARCHAR2(200),
  country_cd     VARCHAR2(2)     DEFAULT 'BE',
  credit_limit   NUMBER(12,2)    DEFAULT 5000,
  status         CHAR(1)         DEFAULT 'A' NOT NULL,
  blocked_reason VARCHAR2(200),
  created_dt     DATE            DEFAULT SYSDATE,
  upd_dt         DATE,
  upd_by         VARCHAR2(30),
  CONSTRAINT customers_pk PRIMARY KEY (cust_id),
  CONSTRAINT cust_type_ck CHECK (cust_type IN ('R','W','G')),
  CONSTRAINT cust_status_ck CHECK (status IN ('A','B','C'))
);

COMMENT ON COLUMN customers.cust_type IS 'R=retail W=wholesale';
COMMENT ON COLUMN customers.status IS 'A/B';
