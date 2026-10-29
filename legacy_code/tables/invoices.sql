CREATE TABLE invoices (
  inv_id        NUMBER(12)    NOT NULL,
  inv_no        VARCHAR2(20)  NOT NULL,
  ord_id        NUMBER(12),
  cust_id       NUMBER(10)    NOT NULL,
  inv_dt        DATE          NOT NULL,
  due_dt        DATE,
  net_amt       NUMBER(12,2),
  vat_amt       NUMBER(12,2),
  gross_amt     NUMBER(12,2),
  paid_amt      NUMBER(12,2)  DEFAULT 0,
  inv_status    VARCHAR2(4)   DEFAULT 'OPEN' NOT NULL,
  reminder_cnt  NUMBER(2)     DEFAULT 0,
  CONSTRAINT invoices_pk PRIMARY KEY (inv_id),
  CONSTRAINT invoices_no_uk UNIQUE (inv_no),
  CONSTRAINT inv_ord_fk FOREIGN KEY (ord_id) REFERENCES orders (ord_id),
  CONSTRAINT inv_cust_fk FOREIGN KEY (cust_id) REFERENCES customers (cust_id),
  CONSTRAINT inv_status_ck CHECK (inv_status IN ('OPEN','PART','PAID','CANC'))
);
