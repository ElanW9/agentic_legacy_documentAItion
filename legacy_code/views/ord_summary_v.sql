create or replace view ord_summary_v as
select o.ord_id,
       o.cust_id,
       o.ord_dt,
       decode(o.ord_status, 10, 'NEW', 15, 'HOLD', 20, 'CONFIRMED', 30, 'SHIPPED',
                            40, 'INVOICED', 90, 'CANCELLED', 'UNKNOWN') status_txt,
       count(l.line_no) line_cnt,
       o.total_amt,
       sum(l.line_amt)  lines_amt
  from orders o, order_lines l
 where l.ord_id(+) = o.ord_id
 group by o.ord_id, o.cust_id, o.ord_dt, o.ord_status, o.total_amt;
