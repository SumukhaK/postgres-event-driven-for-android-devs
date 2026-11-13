---
title: JOINs: combining tables
part: Part 1 · SQL and Postgres
summary: INNER and LEFT JOIN, aliases, three-table queries, and the mistakes that hide rows.
---

**A `JOIN` glues rows from two tables together, using a rule you write in `ON`, usually "this foreign key equals that primary key".**

In this chapter, we will learn:

- Why data is split into many tables, and how `JOIN` puts it back together
- `INNER JOIN` and `LEFT JOIN`, and when each one is right
- Table aliases, to keep queries short
- Joining three tables to build a readable order list
- Two classic mistakes: the filter in the wrong place, and rows that multiply

Let's get started.

## Why do we need joins at all?

In chapter 2 we split the data: an order stores only `customer_id`, not the customer's name. The name lives once, in `customers`. If Asha changes her name, we update one row, not 50 orders.

But now, to show "Asha ordered ₹55", we need both tables. That is what `JOIN` does. We have been preparing for it since chapter 2: the `REFERENCES` arrows are the join paths.

!!! android "Android parallel"
    In Room you wrote the same thing when a screen needed data from two entities. The Room guide shows a `@Query` that uses `JOIN ... ON` across tables, and even a query that returns a `Map<User, List<Book>>`. The SQL inside is exactly what we write here.

## INNER JOIN: only the rows that match

```sql
SELECT o.id AS order_id, c.name, o.status, o.total
FROM orders AS o
JOIN customers AS c ON c.id = o.customer_id
ORDER BY o.id;
```

Read it like a sentence: "take each order, find the customer whose `id` equals the order's `customer_id`, and show them side by side."

`orders AS o` and `customers AS c` are **aliases**: short names for the tables. They save typing, and they make clear which table each column comes from (`o.id` is the order's id, `c.id` is the customer's).

`JOIN` alone means `INNER JOIN`. The manual says "INNER is the default". An inner join keeps a row only when a match is found on both sides. Press Play to watch the matching.

```tables
{"intro":"JOIN customers c ON c.id = o.customer_id",
 "tables":[
  {"name":"customers","columns":["id","name"],"rows":[[1,"Asha"],[2,"Ravi"],[5,"Divya"]]},
  {"name":"orders","columns":["id","customer_id","total"],"rows":[[1,1,"55.00"],[2,2,"85.00"],[3,1,"90.00"]]}],
 "steps":[
  {"text":"Two tables. Orders point at customers through customer_id."},
  {"links":[[1,0,0,0],[1,1,0,1],[1,2,0,0]],"hl":{"0":[0,1],"1":[0,1,2]},"text":"For each order, Postgres finds the customer with the same id. Orders 1 and 3 belong to Asha, order 2 to Ravi."},
  {"links":[[1,0,0,0],[1,1,0,1],[1,2,0,0]],"hl":{"0":[0,1],"1":[0,1,2]},"dim":{"0":[2]},"text":"Divya has no order, so she has no partner. In an INNER JOIN she does not appear in the result at all."}]}
```

## Three tables: a readable order list

A join result is just a table, so you can join again. Here is every line of every order, with names instead of ids:

```sql
SELECT o.id AS order_id,
       c.name AS customer,
       p.name AS product,
       oi.quantity,
       oi.unit_price
FROM order_items AS oi
JOIN orders    AS o ON o.id = oi.order_id
JOIN products  AS p ON p.id = oi.product_id
JOIN customers AS c ON c.id = o.customer_id
ORDER BY o.id, p.id;
```

Each `JOIN ... ON ...` follows one arrow of the diagram from chapter 2. Start from the table in the middle (`order_items`), and walk outwards.

Notice that order 1 appears **twice**, once per item. A join gives one result row for every matching pair. This is correct, but it matters for totals: if you add up `o.total` over this result, order 1's total is counted twice. In chapter 6 we use `GROUP BY` to fix this properly.

## LEFT JOIN: keep everything from the left table

What if we want **all customers**, including those who have not ordered yet? An inner join drops them. A `LEFT JOIN` keeps them.

The manual describes it exactly: "for each row in T1 that does not satisfy the join condition with any row in T2, a joined row is added with null values in columns of T2." So the left table never loses a row.

```sql
SELECT c.name, o.id AS order_id
FROM customers AS c
LEFT JOIN orders AS o ON o.customer_id = c.id
ORDER BY c.id, o.id;
```

Divya now appears, with an empty (`NULL`) `order_id`. This `NULL` is the one from chapter 3: it means "no matching order".

That gives us a very useful trick: **find rows that have no partner**. Keep the `NULL` rows only:

```sql
SELECT c.name
FROM customers AS c
LEFT JOIN orders AS o ON o.customer_id = c.id
WHERE o.id IS NULL;
```

Customers who never ordered. We test `IS NULL` because `= NULL` never works. The same trick finds products nobody has bought:

```sql
SELECT p.name
FROM products AS p
LEFT JOIN order_items AS oi ON oi.product_id = p.id
WHERE oi.product_id IS NULL;
```

The answer is `Lemon tea`. It has no stock either, so it makes sense.

!!! tip "Which one do I need?"
    Ask: "If there is no match, should the left row still appear?" If yes, `LEFT JOIN`. If no, plain `JOIN`. `RIGHT JOIN` is the same as `LEFT JOIN` with the tables swapped, so most people only write `LEFT`.

## Mistake 1: the filter that quietly turns LEFT into INNER

We want all customers, and next to them, only their **paid** orders. Compare these two:

```sql
SELECT c.name, o.id AS order_id
FROM customers AS c
LEFT JOIN orders AS o ON o.customer_id = c.id AND o.status = 'paid'
ORDER BY c.id;
```

```sql
SELECT c.name, o.id AS order_id
FROM customers AS c
LEFT JOIN orders AS o ON o.customer_id = c.id
WHERE o.status = 'paid'
ORDER BY c.id;
```

The first returns all five customers, and only Asha has an `order_id` (her paid order). The second returns **only Asha**. Why? `WHERE` runs after the join. For customers with no match, `o.status` is `NULL`, and `NULL = 'paid'` is not true, so those rows are thrown away. You wrote a `LEFT JOIN`, but the `WHERE` made it behave like an inner join.

The rule: a condition about the **right** table that should not remove left rows goes into `ON`, not into `WHERE`.

## Mistake 2: forgetting the ON condition

A join without a proper `ON` pairs every row with every row. Five customers and seven orders give 35 rows of nonsense. Always join on the key, and check the row count of your result against what you expect.

## Summary

- Data is split across tables. `JOIN ... ON a.fk = b.pk` puts it back together.
- `JOIN` (inner) keeps matches only. `LEFT JOIN` keeps every row of the left table, and fills the right side with `NULL` when nothing matches.
- Use aliases (`orders AS o`) so queries stay short and clear.
- `LEFT JOIN ... WHERE right.id IS NULL` finds rows that have no partner.
- A join gives one row per matching pair, so a parent row repeats for each child.
- Put right-table conditions in `ON`, not `WHERE`, when you must keep left rows.

!!! faq "Is a JOIN slow?"
    Not by itself. Joins on indexed keys are what databases are built for. The primary keys already have indexes, and chapter 7 shows how to check the rest with `EXPLAIN`.

!!! faq "Should I join in SQL or in my Python code?"
    In SQL. The database can do it with indexes and send you only the result. Looping in Python and calling the database once per row is the "N+1 problem", and it is slow.

## Sources

- [PostgreSQL 16 manual: Table Expressions (joined tables)](https://www.postgresql.org/docs/16/queries-table-expressions.html)
- [Android Developers: Access data using Room DAOs (queries over multiple tables)](https://developer.android.com/training/data-storage/room/accessing-data)

That's it for now. In the next chapter, we will count, sum, and group.
