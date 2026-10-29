create table products (
  prod_cd     varchar2(20)   not null,
  descr       varchar2(200),
  list_price  number(10,2)   not null,
  active_yn   char(1)        default 'Y',
  vat_cat     varchar2(2),
  constraint products_pk primary key (prod_cd)
);
