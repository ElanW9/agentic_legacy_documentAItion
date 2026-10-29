CREATE TABLE demo_items (
  item_id   NUMBER        NOT NULL,
  status    VARCHAR2(1)   DEFAULT 'N',
  qty       NUMBER,
  upd_dt    DATE,
  CONSTRAINT demo_items_pk PRIMARY KEY (item_id)
);

COMMENT ON COLUMN demo_items.status IS 'N=new';
