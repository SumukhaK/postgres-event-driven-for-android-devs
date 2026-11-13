---
title: Counting, summing, and grouping
part: Part 1 · SQL and Postgres
summary: Aggregates, GROUP BY, HAVING, CTEs and window functions, to answer "how many" and "how much".
---

**An aggregate function squeezes many rows into one answer, such as a count or a sum. `GROUP BY` does that once per group.**

In this chapter, we will learn:

- `count`, `sum`, `avg`, `min`, and `max`
- `GROUP BY`: one answer per group
- `WHERE` versus `HAVING`, and why both exist
- `WITH` (CTEs): naming a step so a long query reads top to bottom
- Window functions: a running total without losing any rows

Let's get started.

## One answer from many rows

The manual puts it simply: "An aggregate function computes a single result from multiple input rows." The common ones are `count`, `sum`, `avg`, `min` and `max`.

```sql
SELECT count(*)                AS orders,
       sum(total)              AS revenue,
       round(avg(total), 2)    AS average_order,
       max(total)              AS biggest,
       min(total)              AS smallest
FROM orders;
```

Seven orders, and one single row of answers. `count(*)` counts rows. `count(column)` counts only the rows where that column is **not NULL**. This difference is important, and we use it below.

!!! android "Android parallel"
    In Kotlin you would write `orders.sumOf { it.total }` after loading the whole list into memory. In SQL, the database does the sum next to the data and sends you one number. For a million orders, that is the difference between a quick answer and an out-of-memory crash.

## GROUP BY: one answer per group

"How many orders per status?" means: split the rows into groups by `status`, then aggregate each group.

```sql
SELECT status, count(*) AS orders, sum(total) AS revenue
FROM orders
GROUP BY status
ORDER BY status;
```

Press Play to see the groups form.

```tables
{"intro":"GROUP BY status puts rows with the same status in one bucket.",
 "tables":[{"name":"orders","columns":["id","status","total"],"rows":[[1,"delivered","55.00"],[2,"delivered","85.00"],[3,"paid","90.00"],[4,"cancelled","25.00"],[5,"placed","60.00"],[6,"placed","40.00"],[7,"placed","35.00"]]}],
 "steps":[
  {"text":"Seven orders, in the order they were saved."},
  {"hl":{"0":[0,1]},"dim":{"0":[2,3,4,5,6]},"text":"Group 'delivered': 2 orders. 55 + 85 = 140."},
  {"hl":{"0":[4,5,6]},"dim":{"0":[0,1,2,3]},"text":"Group 'placed': 3 orders. 60 + 40 + 35 = 135."},
  {"hl":{"0":[2,3]},"dim":{"0":[0,1,4,5,6]},"text":"'paid' has 1 order (90) and 'cancelled' has 1 order (25). The result has 4 rows, one per group."}]}
```

The rule: every column in `SELECT` must be either in `GROUP BY` or inside an aggregate. Otherwise, Postgres has no single value to show for the group, and it refuses.

### Counting with a LEFT JOIN: count(*) versus count(column)

Let's count orders per customer, including customers with none:

```sql
SELECT c.name,
       count(*)    AS wrong_count,
       count(o.id) AS orders
FROM customers AS c
LEFT JOIN orders AS o ON o.customer_id = c.id
GROUP BY c.id
ORDER BY c.id;
```

Look at Divya. `count(*)` says `1`, because the `LEFT JOIN` made one row for her, full of `NULL`s. `count(o.id)` says `0`, because it skips `NULL`. When you count the right side of a `LEFT JOIN`, count a column of that table.

(We wrote `GROUP BY c.id` and still selected `c.name`. This works because `id` is the primary key, so each group has exactly one name.)

## WHERE versus HAVING

Both filter. The manual states the difference clearly: "WHERE selects input rows before groups and aggregates are computed ... whereas HAVING selects group rows after groups and aggregates are computed."

So: `WHERE` filters **rows** going into the groups. `HAVING` filters **groups** coming out. Aggregates are allowed only in `HAVING`.

"Which customers have spent more than ₹100, not counting cancelled orders?"

```sql
SELECT c.name, count(*) AS orders, sum(o.total) AS spent
FROM orders AS o
JOIN customers AS c ON c.id = o.customer_id
WHERE o.status <> 'cancelled'
GROUP BY c.id
HAVING sum(o.total) > 100
ORDER BY spent DESC;
```

Asha (₹180) and Ravi (₹125) appear. Meera's only order was cancelled, and Kiran spent only ₹60.

!!! tip "Filter early"
    Put as much as you can in `WHERE`. The manual notes that this is more efficient than putting the restriction in `HAVING`, "because we avoid doing the grouping and aggregate calculations for all rows that fail the WHERE check."

## A real check: do the order totals add up?

Remember we stored `total` in `orders`, and the lines in `order_items`. They should agree. Let's ask the database to check its own data:

```sql
SELECT o.id, o.total, sum(oi.quantity * oi.unit_price) AS items_total
FROM orders AS o
JOIN order_items AS oi ON oi.order_id = o.id
GROUP BY o.id
ORDER BY o.id;
```

And to list only the orders where they **disagree**, add a `HAVING`:

```sql
SELECT o.id
FROM orders AS o
JOIN order_items AS oi ON oi.order_id = o.id
GROUP BY o.id
HAVING o.total <> sum(oi.quantity * oi.unit_price);
```

It returns nothing, which is the good answer here. Queries like this are how backend developers find data bugs. In a later chapter, we will see how a double-click could break this, and how to prevent it.

## WITH: give a step a name

Long queries get hard to read. `WITH` lets you name a step and use it below, like a local variable for a query. The manual calls these "auxiliary statements", also known as Common Table Expressions (CTEs), which "can be thought of as defining temporary tables that exist just for one query".

```sql
WITH spent AS (
    SELECT customer_id, sum(total) AS spent
    FROM orders
    WHERE status <> 'cancelled'
    GROUP BY customer_id
)
SELECT c.name, s.spent
FROM spent AS s
JOIN customers AS c ON c.id = s.customer_id
ORDER BY s.spent DESC;
```

Read it top to bottom: first work out `spent` per customer, then attach names.

!!! android "Android parallel"
    A CTE is like extracting a `val` or a small function from a long Kotlin expression. Same result, much easier to read. And in a later chapter we will use a special kind, a CTE that **writes** data, because the manual allows `INSERT`, `UPDATE` and `DELETE` inside `WITH` too.

## Window functions: a total that keeps every row

`GROUP BY` collapses rows. Sometimes you want the opposite: keep every row **and** show a calculation across related rows. The manual says window functions "do not cause rows to become grouped into a single output row ... Instead, the rows retain their separate identities."

A running total of each customer's orders, in time order:

```sql
SELECT customer_id, id AS order_id, total,
       sum(total) OVER (PARTITION BY customer_id ORDER BY placed_at) AS running_total
FROM orders
ORDER BY customer_id, placed_at;
```

`PARTITION BY customer_id` restarts the calculation for each customer. `ORDER BY placed_at` inside `OVER` sets the order of the running sum. For customer 1 you see 55, then 145, then 180.

A very popular use is "the latest row per group". Here is each customer's most recent order:

```sql
SELECT customer_id, order_id, total
FROM (
    SELECT customer_id, id AS order_id, total,
           row_number() OVER (PARTITION BY customer_id ORDER BY placed_at DESC) AS rn
    FROM orders
) AS ranked
WHERE rn = 1
ORDER BY customer_id;
```

`row_number()` numbers the rows inside each customer, newest first. Keeping `rn = 1` gives the newest. We use this shape again later for "latest status of each order" in the event-driven part.

## Summary

- Aggregates (`count`, `sum`, `avg`, `min`, `max`) turn many rows into one value.
- `GROUP BY` gives one result row per group. Every selected column must be grouped or aggregated.
- `WHERE` filters rows before grouping. `HAVING` filters groups after.
- `count(*)` counts rows. `count(column)` skips `NULL`, which is what you want after a `LEFT JOIN`.
- `WITH` names a step so a long query reads in order.
- Window functions (`OVER (PARTITION BY ... ORDER BY ...)`) calculate across related rows without collapsing them.

!!! faq "When do I use a window function instead of GROUP BY?"
    If you need one row per group, use `GROUP BY`. If you need to keep every row and add a calculation next to it (a running total, a rank, "latest per group"), use a window function.

!!! faq "Is `avg` of money exact?"
    `avg` of a `numeric` column gives a `numeric` result, so there is no floating-point error. We rounded to two decimals only to make it readable.

## Sources

- [PostgreSQL 16 tutorial: Aggregate Functions](https://www.postgresql.org/docs/16/tutorial-agg.html)
- [PostgreSQL 16 tutorial: Window Functions](https://www.postgresql.org/docs/16/tutorial-window.html)
- [PostgreSQL 16 manual: WITH Queries (Common Table Expressions)](https://www.postgresql.org/docs/16/queries-with.html)

That's it for now. In the next chapter, we will make queries fast with indexes, and read the database's own explanation with `EXPLAIN`.
