create or replace package pkg_order is

  -- order statuses
  st_new        constant number := 10;
  st_hold       constant number := 15;
  st_confirmed  constant number := 20;
  st_shipped    constant number := 30;
  st_invoiced   constant number := 40;
  st_cancelled  constant number := 90;

  -- last order created in this session
  g_last_ord_id number;

  function new_order(p_cust_id in number, p_remarks in varchar2 default null) return number;

  procedure add_line(p_ord_id in number, p_prod_cd in varchar2, p_qty in number);
  procedure add_line(p_ord_id in number, p_prod_cd in varchar2, p_qty in number, p_price in number);

  procedure process_order(p_ord_id in number default null, p_ship in boolean default false);

  procedure set_status(p_ord_id in number, p_status in number);

  procedure cancel_order(p_ord_id in number, p_reason in varchar2);

  function get_order_total(p_ord_id in number) return number;

end pkg_order;
/
