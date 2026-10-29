CREATE OR REPLACE PACKAGE pkg_demo AS
  -- writes to OLD_ITEMS as well (outdated)
  g_count NUMBER := 0;
  PROCEDURE set_status(p_id IN NUMBER, p_status IN VARCHAR2);
  FUNCTION get_qty(p_id IN NUMBER) RETURN NUMBER;
  PROCEDURE add_qty(p_id IN NUMBER);
  PROCEDURE add_qty(p_id IN NUMBER, p_qty IN NUMBER);
END pkg_demo;
/
