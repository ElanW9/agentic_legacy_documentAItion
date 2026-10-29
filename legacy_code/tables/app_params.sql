CREATE TABLE app_params (
  param_name  VARCHAR2(30)   NOT NULL,
  param_val   VARCHAR2(200),
  CONSTRAINT app_params_pk PRIMARY KEY (param_name)
);

INSERT INTO app_params (param_name, param_val) VALUES ('VAT_RATE', '21');
INSERT INTO app_params (param_name, param_val) VALUES ('LOG_LEVEL', '1');
INSERT INTO app_params (param_name, param_val) VALUES ('AUDIT_KEEP_DAYS', '90');
INSERT INTO app_params (param_name, param_val) VALUES ('MIN_ORDER_AMT', '50');
COMMIT;
