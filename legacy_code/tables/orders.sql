create table orders (
  ord_id      number(12)     not null,
  cust_id     number(10)     not null,
  ord_dt      date           default sysdate,
  ord_status  number(2)      default 10 not null,
  total_amt   number(12,2),
  disc_pct    number(5,2),
  curr_cd     varchar2(3)    default 'EUR',
  ship_dt     date,
  remarks     varchar2(4000),
  created_by  varchar2(30),
  constraint orders_pk primary key (ord_id),
  constraint orders_cust_fk foreign key (cust_id) references customers (cust_id)
);

comment on column orders.ord_status is '10=new 20=confirmed 30=shipped 40=invoiced 90=cancelled';
comment on column orders.curr_cd is 'only EUR supported';
