create table order_lines (
  ord_id      number(12)     not null,
  line_no     number(5)      not null,
  prod_cd     varchar2(20)   not null,
  qty         number(10,2)   not null,
  unit_price  number(10,2),
  line_amt    number(12,2),
  constraint order_lines_pk primary key (ord_id, line_no),
  constraint ordl_ord_fk foreign key (ord_id) references orders (ord_id),
  constraint ordl_prod_fk foreign key (prod_cd) references products (prod_cd)
);
