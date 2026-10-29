CREATE OR REPLACE PACKAGE BODY util_log AS
/*
  UTIL_LOG
  2006-03  jvd   created
  2008-11  jvd   debug output
  2011-09  pk    archive_rows
  2015-02  tm    log level from app_params

  NOTE: all logging goes to LOG_TABLE, see install script
*/

  g_log_level  NUMBER := NULL;
  g_call_cnt   PLS_INTEGER := 0;

  ---------------------------------------------------------------------------
  FUNCTION lvl(p_sev IN CHAR) RETURN NUMBER IS
  BEGIN
    RETURN CASE p_sev
             WHEN 'E' THEN 3
             WHEN 'W' THEN 2
             ELSE 1
           END;
  END lvl;

  ---------------------------------------------------------------------------
  PROCEDURE set_ctx(p_module IN VARCHAR2, p_user IN VARCHAR2 DEFAULT NULL) IS
  BEGIN
    g_module := SUBSTR(UPPER(p_module), 1, 30);
    IF p_user IS NOT NULL THEN
      g_user := SUBSTR(p_user, 1, 30);
    END IF;
  END set_ctx;

  ---------------------------------------------------------------------------
  FUNCTION get_param(p_name IN VARCHAR2) RETURN VARCHAR2 IS
    v_val app_params.param_val%TYPE;
  BEGIN
    SELECT param_val
      INTO v_val
      FROM app_params
     WHERE param_name = UPPER(p_name);
    RETURN v_val;
  EXCEPTION
    WHEN NO_DATA_FOUND THEN
      RETURN NULL;
  END get_param;

  ---------------------------------------------------------------------------
  FUNCTION get_param_num(p_name IN VARCHAR2, p_default IN NUMBER) RETURN NUMBER IS
  BEGIN
    RETURN NVL(TO_NUMBER(get_param(p_name)), p_default);
  EXCEPTION
    WHEN VALUE_ERROR THEN
      RETURN p_default;
  END get_param_num;

  ---------------------------------------------------------------------------
  -- writes a line to the audit table. never fails.
  PROCEDURE log_msg(p_action IN VARCHAR2,
                    p_obj_id IN VARCHAR2,
                    p_msg    IN VARCHAR2,
                    p_sev    IN CHAR DEFAULT 'I') IS
    PRAGMA AUTONOMOUS_TRANSACTION;
  BEGIN
    IF g_log_level IS NULL THEN
      g_log_level := get_param_num('LOG_LEVEL', 1);
    END IF;

    g_call_cnt := g_call_cnt + 1;

    IF lvl(p_sev) >= g_log_level THEN
      INSERT INTO audit_log (log_id, log_ts, module, action, obj_id, msg, usr, sev)
      VALUES (audit_log_seq.NEXTVAL,
              SYSTIMESTAMP,
              g_module,
              SUBSTR(p_action, 1, 30),
              SUBSTR(p_obj_id, 1, 50),
              SUBSTR(p_msg, 1, 4000),
              NVL(g_user, USER),
              p_sev);
    END IF;
    COMMIT;
  EXCEPTION
    WHEN OTHERS THEN
      ROLLBACK;
  END log_msg;

  ---------------------------------------------------------------------------
  PROCEDURE log_err(p_action IN VARCHAR2, p_obj_id IN VARCHAR2) IS
  BEGIN
    log_msg(p_action, p_obj_id, SQLERRM || ' ' || DBMS_UTILITY.FORMAT_ERROR_BACKTRACE, c_sev_err);
  END log_err;

  ---------------------------------------------------------------------------
  PROCEDURE dbg(p_msg IN VARCHAR2) IS
  BEGIN
    IF g_debug THEN
      DBMS_OUTPUT.PUT_LINE(TO_CHAR(SYSTIMESTAMP, 'HH24:MI:SS.FF3') || ' ' || g_module || ' ' || p_msg);
    END IF;
  END dbg;

  ---------------------------------------------------------------------------
  FUNCTION is_workday(p_dt IN DATE) RETURN BOOLEAN IS
  BEGIN
    RETURN TO_CHAR(p_dt, 'DY') NOT IN ('SAT', 'SUN');
  END is_workday;

  ---------------------------------------------------------------------------
  FUNCTION add_workdays(p_dt IN DATE, p_days IN NUMBER) RETURN DATE IS
    v_dt  DATE   := p_dt;
    v_n   NUMBER := 0;
  BEGIN
    WHILE v_n < p_days LOOP
      v_dt := v_dt + 1;
      IF is_workday(v_dt) THEN
        v_n := v_n + 1;
      END IF;
    END LOOP;
    RETURN v_dt;
  END add_workdays;

  ---------------------------------------------------------------------------
  FUNCTION fmt_amt(p_amt IN NUMBER) RETURN VARCHAR2 IS
  BEGIN
    RETURN TO_CHAR(NVL(p_amt, 0), 'FM999G999G990D00', 'NLS_NUMERIC_CHARACTERS='',.''');
  END fmt_amt;

  ---------------------------------------------------------------------------
  -- moves rows older than p_days to <table>_ARCH
  PROCEDURE archive_rows(p_tab IN VARCHAR2, p_date_col IN VARCHAR2, p_days IN NUMBER) IS
    v_sql  VARCHAR2(2000);
    v_tab  VARCHAR2(30) := UPPER(TRIM(p_tab));
    v_ins  NUMBER;
    v_del  NUMBER;
  BEGIN
    dbg('archive ' || v_tab);

    v_sql := 'INSERT INTO ' || v_tab || '_ARCH SELECT t.*, SYSDATE FROM ' || v_tab ||
             ' t WHERE t.' || p_date_col || ' < SYSDATE - :d';
    EXECUTE IMMEDIATE v_sql USING p_days;
    v_ins := SQL%ROWCOUNT;

    v_sql := 'DELETE FROM ' || v_tab || ' WHERE ' || p_date_col || ' < SYSDATE - :d';
    EXECUTE IMMEDIATE v_sql USING p_days;
    v_del := SQL%ROWCOUNT;

    IF v_del <> v_ins THEN
      ROLLBACK;
      log_msg('ARCHIVE', v_tab, 'count mismatch ' || v_ins || '/' || v_del, c_sev_err);
      RETURN;
    END IF;

    COMMIT;
    log_msg('ARCHIVE', v_tab, v_ins || ' rows archived');
  END archive_rows;

  ---------------------------------------------------------------------------
  -- nightly job
  PROCEDURE housekeeping IS
  BEGIN
    set_ctx('HOUSEKEEPING', 'BATCH');
    archive_rows('AUDIT_LOG', 'LOG_TS', get_param_num('AUDIT_KEEP_DAYS', 90));
    -- orders archive disabled 2013, see ticket 4471
    -- archive_rows('ORDERS', 'ORD_DT', 730);
    inv_api.send_reminders;
  END housekeeping;

END util_log;
/
