---
title: Changing data: UPDATE, DELETE, and upsert
part: Part 1 · SQL and Postgres
summary: Change and remove rows safely, get results back with RETURNING, and insert-or-update in one step.
---

**`UPDATE` changes existing rows, `DELETE` removes them, and `INSERT ... ON CONFLICT` adds a row or updates it if it already exists. Always say which rows with `WHERE`.**

In this chapter, we will learn:

- How `UPDATE` and `DELETE` find the rows to change
- Why forgetting `WHERE` is the classic disaster
- How `RETURNING` gives you the changed rows back
- What `ON DELETE CASCADE` really does
- How upsert works: insert or update in one atomic step

Let's get started.

## A safe way to practise: BEGIN and ROLLBACK

In this chapter we will change the ChaiPoint data. But the next chapters need the data the way it was. So every example below sits inside a **transaction** that we cancel at the end:

```text
BEGIN;        -- start a bundle of changes
...           -- do things
ROLLBACK;     -- throw the bundle away, as if nothing happened
```

The PostgreSQL tutorial describes a transaction as one that "bundles multiple steps into a single, all-or-nothing operation", and says that with `ROLLBACK` "all our updates so far will be canceled". We study transactions properly in chapter 8. For now, treat `BEGIN ... ROLLBACK` as an undo button. It is also a habit worth keeping when you run a risky statement on a real database.

## UPDATE: change existing rows

The shape is: which table, what to set, which rows.

```sql
BEGIN;
UPDATE products SET price = 22.00 WHERE id = 1;
SELECT id, name, price FROM products WHERE id = 1;
ROLLBACK;
```

Inside the transaction, the select shows the new price, `22.00`. After `ROLLBACK`, the price is `20.00` again.

You can set a value **from the old value**. This is how you reduce stock:

```sql
BEGIN;
UPDATE products SET stock = stock - 2 WHERE id = 1 AND stock >= 2;
SELECT stock FROM products WHERE id = 1;
ROLLBACK;
```

Two things to notice. `stock = stock - 2` is calculated by the database, on the current value. And `AND stock >= 2` is a guard: if there is not enough stock, **zero rows match** and nothing changes.

The manual says that after an `UPDATE`, the command returns `UPDATE count`, where the count is the number of rows updated, and "if count is 0, no rows were updated by the query (this is not considered an error)". So a failed guard is silent. Your code must look at the count.

!!! android "Android parallel"
    Room's `@Update` can "optionally return an `Int` value indicating the number of rows that were updated successfully". Same idea. In Python, you will read `cursor.rowcount` and treat `0` as "nothing happened".

### The disaster: UPDATE without WHERE

```sql
BEGIN;
UPDATE products SET is_active = false;
SELECT count(*) AS inactive FROM products WHERE NOT is_active;
ROLLBACK;
```

We forgot `WHERE`, so **every** row changed: the count is 6, all products. Postgres does not ask "are you sure?". On a real database, this is how people lose a Friday evening. Two habits help: run a `SELECT` with the same `WHERE` first, and run risky changes inside `BEGIN`, check, then `COMMIT` or `ROLLBACK`.

Press Play to see how `WHERE` decides which rows are touched.

```tables
{"intro":"UPDATE products SET stock = stock - 2 WHERE id = 1",
 "tables":[{"name":"products","columns":["id","name","price","stock"],"rows":[[1,"Masala chai","20.00",200],[2,"Filter coffee","25.00",150],[3,"Samosa","15.00",120]]}],
 "steps":[
  {"text":"Three rows before the change."},
  {"hl":{"0":[0]},"dim":{"0":[1,2]},"text":"WHERE id = 1 picks one row. The other rows are not touched."},
  {"hl":{"0":[0]},"dim":{"0":[1,2]},"text":"The database reads the current stock (200), calculates 200 - 2, and writes 198. Only this row changes."}]}
```

## RETURNING: get the changed rows back

Often you change a row **and** want to see the result. Without `RETURNING` you would run a second query. The manual says `RETURNING` "avoids performing an extra database query to collect the data, and is especially valuable when it would otherwise be difficult to identify the modified rows reliably."

```sql
BEGIN;
UPDATE products SET stock = stock - 1 WHERE id = 2 RETURNING id, name, stock;
ROLLBACK;
```

It works with `INSERT` and `DELETE` too. A very common use is to get the generated `id` of a new row:

```sql
BEGIN;
INSERT INTO products (name, price, stock) VALUES ('Jaggery tea', 22.00, 40) RETURNING id;
ROLLBACK;
```

!!! android "Android parallel"
    In Room, `@Insert` can return the new `rowId` as a `Long`. In Postgres you write `RETURNING id`, and you can return any columns you like, not only the id.

## DELETE: remove rows

```sql
BEGIN;
DELETE FROM orders WHERE id = 4 RETURNING id, status;
SELECT count(*) AS items_left FROM order_items WHERE order_id = 4;
ROLLBACK;
```

We deleted order 4, and its row in `order_items` is gone too, even though we never deleted it ourselves. That is the `ON DELETE CASCADE` we wrote in chapter 2: when the order goes, its items go with it.

!!! warning "CASCADE is powerful"
    Cascades save you from orphan rows, but they also delete quietly. Use them for "owned" data, like the items of one order. Do not use them for data that other parts of the app still need.

Without a cascade, Postgres protects you instead. Customer 1 has orders, so deleting that customer is refused:

```sql-error
DELETE FROM customers WHERE id = 1;
```

The error says the delete "violates foreign key constraint": rows in `orders` still point to this customer. The database will not leave an order that points to nobody.

!!! tip "Many teams do not really delete"
    Instead of `DELETE`, they add a column like `is_active` or `deleted_at` and filter on it. You can undo it, and old reports still work. Our `products` table already has `is_active` for this reason.

## Upsert: insert, or update if it already exists

Imagine a customer signs up again with a phone number we already have. We do not want an error, and we do not want a duplicate. We want: "insert; if this phone exists, update the row instead."

```sql
BEGIN;
INSERT INTO customers (name, phone, city)
VALUES ('Asha K', '9000000001', 'Mysuru')
ON CONFLICT (phone) DO UPDATE
    SET name = EXCLUDED.name,
        city = EXCLUDED.city
RETURNING id, name, city;
ROLLBACK;
```

Read it in three parts:

- `ON CONFLICT (phone)`: if the insert would break the unique rule on `phone`...
- `DO UPDATE SET ...`: ...then update the existing row instead.
- `EXCLUDED`: a special name for "the row I tried to insert". The manual says `SET` can use the existing row through the table name, and "the row proposed for insertion using the special excluded table".

The result is still customer `1` (Asha), with the new name and city. No second row.

If you want to **ignore** the duplicate instead, use `DO NOTHING`:

```sql
BEGIN;
INSERT INTO customers (name, phone) VALUES ('Another Ravi', '9000000002')
ON CONFLICT DO NOTHING;
SELECT count(*) AS customers FROM customers;
ROLLBACK;
```

The count stays at 5. For `DO NOTHING` the conflict target is optional. For `DO UPDATE` it is required, because Postgres has to know which uniqueness rule to watch.

Why not just "select first, then insert or update" in Python? Because two requests can do that at the same moment, and both see "not found". The manual guarantees the opposite for upsert: "ON CONFLICT DO UPDATE guarantees an atomic INSERT or UPDATE outcome; provided there is no independent error, one of those two outcomes is guaranteed, even under high concurrency." We will meet this problem again in chapters 8 and 12, where upsert becomes the base of safe workers.

!!! android "Android parallel"
    Room has the same idea in two forms: `@Insert(onConflict = OnConflictStrategy.REPLACE)`, and `@Upsert`, which inserts "when there's no matching row, or update[s] them if a row already exists with the same primary key". The Postgres version is more precise: you choose the uniqueness rule (`ON CONFLICT (phone)`) and exactly which columns to update.

## Summary

- `UPDATE table SET col = value WHERE ...` and `DELETE FROM table WHERE ...` both need a `WHERE`. Without it, every row changes.
- Zero matching rows is **not** an error. Check the row count.
- `RETURNING` gives you the changed rows back in the same statement, including generated ids.
- `ON DELETE CASCADE` deletes dependent rows. A plain foreign key refuses the delete.
- `INSERT ... ON CONFLICT (...) DO UPDATE` is an atomic "insert or update". `DO NOTHING` ignores duplicates.
- Wrap risky changes in `BEGIN ... ROLLBACK/COMMIT`.

!!! faq "How do I undo a DELETE I already committed?"
    You cannot, with SQL alone. After `COMMIT`, the change is permanent. This is why we practise inside `BEGIN`, and why production teams keep backups.

!!! faq "Is `stock = stock - 2` safe when two orders arrive together?"
    The single statement is safe, because the database applies it to the current value. The risky pattern is "read stock in Python, subtract, write back". We will break that pattern on purpose in chapter 8.

## Sources

- [PostgreSQL 16 manual: UPDATE](https://www.postgresql.org/docs/16/sql-update.html)
- [PostgreSQL 16 manual: INSERT (ON CONFLICT)](https://www.postgresql.org/docs/16/sql-insert.html)
- [PostgreSQL 16 manual: Returning Data from Modified Rows](https://www.postgresql.org/docs/16/dml-returning.html)
- [PostgreSQL 16 tutorial: Transactions](https://www.postgresql.org/docs/16/tutorial-transactions.html)
- [Android Developers: Access data using Room DAOs](https://developer.android.com/training/data-storage/room/accessing-data)

That's it for now. In the next chapter, we will combine tables with `JOIN`.
