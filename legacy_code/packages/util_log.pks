CREATE OR REPLACE PACKAGE util_log AS
  -- Utility package. Logging + misc helpers.

  g_module   VARCHAR2(30) := 'UNKNOWN';
  g_user     VARCHAR2(30);
  g_debug    BOOLEAN := FALSE;

  c_sev_info  CONSTANT CHAR(1) := 'I';
  c_sev_warn  CONSTANT CHAR(1) := 'W';
  c_sev_err   CONSTANT CHAR(1) := 'E';

  PROCEDURE set_ctx(p_module IN VARCHAR2, p_user IN VARCHAR2 DEFAULT NULL);

  PROCEDURE log_msg(p_action IN VARCHAR2,
                    p_obj_id IN VARCHAR2,
                    p_msg    IN VARCHAR2,
                    p_sev    IN CHAR DEFAULT 'I');

  PROCEDURE log_err(p_action IN VARCHAR2, p_obj_id IN VARCHAR2);

  PROCEDURE dbg(p_msg IN VARCHAR2);

  FUNCTION get_param(p_name IN VARCHAR2) RETURN VARCHAR2;
  FUNCTION get_param_num(p_name IN VARCHAR2, p_default IN NUMBER) RETURN NUMBER;

  FUNCTION is_workday(p_dt IN DATE) RETURN BOOLEAN;
  FUNCTION add_workdays(p_dt IN DATE, p_days IN NUMBER) RETURN DATE;

  FUNCTION fmt_amt(p_amt IN NUMBER) RETURN VARCHAR2;

  -- archiving
  PROCEDURE archive_rows(p_tab IN VARCHAR2, p_date_col IN VARCHAR2, p_days IN NUMBER);
  PROCEDURE housekeeping;

END util_log;
/
