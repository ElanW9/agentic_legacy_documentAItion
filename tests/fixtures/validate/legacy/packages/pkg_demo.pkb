CREATE OR REPLACE PACKAGE BODY pkg_demo AS

  PROCEDURE set_status(p_id IN NUMBER, p_status IN VARCHAR2) IS
  BEGIN
    UPDATE demo_items SET status = p_status WHERE item_id = p_id;
    g_count := g_count + 1;
    COMMIT;
  END set_status;

  FUNCTION get_qty(p_id IN NUMBER) RETURN NUMBER IS
    l_qty NUMBER;
  BEGIN
    SELECT qty INTO l_qty FROM demo_items WHERE item_id = p_id;
    RETURN l_qty;
  EXCEPTION
    WHEN OTHERS THEN
      RETURN NULL;
  END get_qty;

  PROCEDURE add_qty(p_id IN NUMBER) IS
  BEGIN
    add_qty(p_id, 1);
  END add_qty;

  PROCEDURE add_qty(p_id IN NUMBER, p_qty IN NUMBER) IS
  BEGIN
    UPDATE demo_items SET qty = qty + p_qty WHERE item_id = p_id;
  END add_qty;

END pkg_demo;
/
