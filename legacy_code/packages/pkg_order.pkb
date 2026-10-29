create or replace package body pkg_order is

  -- 2010 bvh: rewrite of ORD_PROC (old package dropped)
  -- 2013 bvh: batch mode in process_order
  -- 2014 kv : export shipping

  g_line_cnt    pls_integer := 0;
  g_disc_cache  number;

  ----------------------------------------------------------------------------
  procedure wlog(p_act in varchar2, p_id in number, p_msg in varchar2, p_sev in char default 'I') is
  begin
    util_log.log_msg(p_act, to_char(p_id), p_msg, p_sev);
  end wlog;

  ----------------------------------------------------------------------------
  -- discount: 5% above 10k, 10% for wholesale
  function calc_disc(p_cust_type in char, p_amt in number) return number is
    l_pct number := 0;
  begin
    if p_amt > 25000 then
      l_pct := 7.5;
    elsif p_amt > 10000 then
      l_pct := 5;
    end if;

    if p_cust_type = 'W' then
      l_pct := l_pct + 2;
    end if;

    return l_pct;
  end calc_disc;

  ----------------------------------------------------------------------------
  function new_order(p_cust_id in number, p_remarks in varchar2 default null) return number is
    l_id  orders.ord_id%type;
    l_st  customers.status%type;
  begin
    util_log.set_ctx('PKG_ORDER');

    select status into l_st from customers where cust_id = p_cust_id;
    if l_st = 'C' then
      raise_application_error(-20100, 'customer closed');
    end if;

    select ord_seq.nextval into l_id from dual;

    insert into orders (ord_id, cust_id, ord_dt, ord_status, total_amt, disc_pct, curr_cd, remarks, created_by)
    values (l_id, p_cust_id, sysdate, st_new, 0, 0, 'EUR', p_remarks, nvl(util_log.g_user, user));

    g_last_ord_id := l_id;
    wlog('NEW', l_id, 'cust ' || p_cust_id);
    return l_id;
  end new_order;

  ----------------------------------------------------------------------------
  -- price from catalogue
  procedure add_line(p_ord_id in number, p_prod_cd in varchar2, p_qty in number) is
    l_price products.list_price%type;
  begin
    select list_price
      into l_price
      from products
     where prod_cd = upper(p_prod_cd)
       and active_yn = 'Y';

    -- volume price break
    if p_qty >= 100 then
      l_price := round(l_price * 0.97, 2);
    end if;

    add_line(p_ord_id, p_prod_cd, p_qty, l_price);
  end add_line;

  ----------------------------------------------------------------------------
  procedure add_line(p_ord_id in number, p_prod_cd in varchar2, p_qty in number, p_price in number) is
    l_line  order_lines.line_no%type;
    l_st    orders.ord_status%type;
  begin
    select ord_status into l_st from orders where ord_id = p_ord_id for update;

    if l_st not in (st_new, st_hold) then
      raise_application_error(-20101, 'order ' || p_ord_id || ' not editable');
    end if;
    if p_qty <= 0 then
      raise_application_error(-20102, 'qty must be > 0');
    end if;

    select nvl(max(line_no), 0) + 10 into l_line from order_lines where ord_id = p_ord_id;

    insert into order_lines (ord_id, line_no, prod_cd, qty, unit_price, line_amt)
    values (p_ord_id, l_line, upper(p_prod_cd), p_qty, p_price, round(p_qty * p_price, 2));

    g_line_cnt := g_line_cnt + 1;
  end add_line;

  ----------------------------------------------------------------------------
  procedure set_status(p_ord_id in number, p_status in number) is
  begin
    update orders set ord_status = p_status where ord_id = p_ord_id;
    if sql%rowcount = 0 then
      wlog('SET_STATUS', p_ord_id, 'order not found', 'W');
    end if;
  end set_status;

  ----------------------------------------------------------------------------
  function get_order_total(p_ord_id in number) return number is
    l_tot number;
  begin
    select sum(line_amt) into l_tot from order_lines where ord_id = p_ord_id;
    return nvl(l_tot, 0);
  end get_order_total;

  ----------------------------------------------------------------------------
  /*
   * process_order
   * confirms order(s): credit check, discount, optional shipping + invoice.
   * if p_ord_id is null all NEW orders are processed (batch).
   */
  procedure process_order(p_ord_id in number default null, p_ship in boolean default false) is
    cursor c_ord is
      select o.ord_id, o.cust_id, o.ord_status, o.ord_dt,
             c.cust_type, c.status cust_status, c.country_cd
        from orders o, customers c
       where o.cust_id = c.cust_id
         and (o.ord_id = p_ord_id or (p_ord_id is null and o.ord_status = st_new))
       order by o.ord_dt;

    l_tot       number;
    l_disc      number;
    l_net       number;
    l_lines     pls_integer;
    l_inactive  pls_integer;
    l_ok        number;
    l_inv_id    number;
    l_err_cnt   pls_integer := 0;
    l_done_cnt  pls_integer := 0;
    l_min_amt   number := 25;
  begin
    util_log.set_ctx('PKG_ORDER');
    wlog('PROCESS', p_ord_id, 'start');

    for r in c_ord loop
      begin
        savepoint sp_ord;

        if r.ord_status not in (st_new, st_hold) then
          wlog('PROCESS', r.ord_id, 'skipped, status ' || r.ord_status, 'W');
        else
          select count(*), nvl(sum(line_amt), 0)
            into l_lines, l_tot
            from order_lines
           where ord_id = r.ord_id;

          if l_lines = 0 then
            wlog('PROCESS', r.ord_id, 'no lines', 'W');
          elsif l_tot < l_min_amt then
            update orders
               set ord_status = st_cancelled,
                   remarks = 'MIN AMOUNT'
             where ord_id = r.ord_id;
          else
            -- inactive products on the order?
            select count(*)
              into l_inactive
              from order_lines l, products p
             where l.prod_cd = p.prod_cd
               and l.ord_id = r.ord_id
               and p.active_yn = 'N';

            if l_inactive > 0 then
              set_status(r.ord_id, st_hold);
              wlog('PROCESS', r.ord_id, l_inactive || ' inactive product(s)', 'W');
            elsif r.cust_status = 'B' then
              set_status(r.ord_id, st_hold);
            else
              l_disc := calc_disc(r.cust_type, l_tot);

              -- cap discount
              l_disc := least(l_disc, 15);

              if l_disc > 50 then
                -- needs manager approval
                l_disc := 0;
                set_status(r.ord_id, st_hold);
                wlog('PROCESS', r.ord_id, 'discount needs approval', 'W');
              end if;

              l_net := round(l_tot * (1 - l_disc / 100), 2);

              l_ok := cust_mgmt.chk_credit(r.cust_id, l_net);

              if l_ok = 1 then
                update orders
                   set ord_status = st_confirmed,
                       disc_pct = l_disc,
                       total_amt = l_net
                 where ord_id = r.ord_id;

                if p_ship then
                  if r.country_cd = 'BE' or r.country_cd is null then
                    update orders
                       set ord_status = st_shipped,
                           ship_dt = sysdate
                     where ord_id = r.ord_id;
                  else
                    -- export: ship next business day
                    update orders
                       set ord_status = st_shipped,
                           ship_dt = util_log.add_workdays(trunc(sysdate), 1)
                     where ord_id = r.ord_id;
                  end if;

                  l_inv_id := inv_api.create_invoice(r.ord_id);

                  if l_inv_id is null then
                    rollback to sp_ord;
                    l_err_cnt := l_err_cnt + 1;
                    wlog('PROCESS', r.ord_id, 'invoice failed', 'E');
                  else
                    wlog('PROCESS', r.ord_id, 'shipped+invoiced ' || l_inv_id);
                  end if;
                end if;
              else
                if r.cust_type = 'G' then
                  -- government never on hold
                  update orders
                     set ord_status = st_confirmed,
                         disc_pct = l_disc,
                         total_amt = l_net
                   where ord_id = r.ord_id;
                else
                  set_status(r.ord_id, st_hold);
                  wlog('PROCESS', r.ord_id, 'credit check failed', 'W');
                end if;
              end if;
            end if;
          end if;
        end if;

        l_done_cnt := l_done_cnt + 1;
        if mod(l_done_cnt, 50) = 0 then
          commit;
        end if;
      exception
        when others then
          rollback to sp_ord;
          l_err_cnt := l_err_cnt + 1;
          util_log.log_err('PROCESS', to_char(r.ord_id));
      end;
    end loop;

    commit;
    wlog('PROCESS', p_ord_id, 'done, ' || l_done_cnt || ' processed, ' || l_err_cnt || ' errors');
  end process_order;

  ----------------------------------------------------------------------------
  procedure cancel_order(p_ord_id in number, p_reason in varchar2) is
    l_st orders.ord_status%type;
  begin
    select ord_status into l_st from orders where ord_id = p_ord_id;

    if l_st >= st_invoiced then
      if l_st = st_invoiced then
        inv_api.cancel_invoice_for_order(p_ord_id);
      else
        raise_application_error(-20103, 'cannot cancel order in status ' || l_st);
      end if;
    end if;

    update orders
       set ord_status = st_cancelled,
           remarks = substr(remarks || ' | CANCELLED: ' || p_reason, 1, 4000)
     where ord_id = p_ord_id;

    wlog('CANCEL', p_ord_id, p_reason, 'W');
  end cancel_order;

end pkg_order;
/
