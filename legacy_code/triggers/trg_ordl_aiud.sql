create or replace trigger trg_ordl_aiud
after insert or update or delete on order_lines
for each row
begin
  if inserting then
    update orders set total_amt = nvl(total_amt, 0) + :new.line_amt where ord_id = :new.ord_id;
  elsif updating then
    update orders set total_amt = nvl(total_amt, 0) - :old.line_amt + :new.line_amt where ord_id = :new.ord_id;
  else
    update orders set total_amt = nvl(total_amt, 0) - :old.line_amt where ord_id = :old.ord_id;
  end if;
end;
/
