---
title: Indexes and EXPLAIN: why some queries are slow
part: Part 1 · SQL and Postgres
summary: What an index is, how to read EXPLAIN, and when an index helps or does not.
---

**An index is a sorted shortcut the database keeps next to a table, so it can find rows without reading every row. `EXPLAIN` shows you which route a query will take.**

In this chapter, we will learn:

- Why a query that is fast with 7 rows can be slow with 200,000
- What an index is, using the book-index analogy
- How to read `EXPLAIN` and `EXPLAIN ANALYZE`
- The cost of indexes, and when an index does not help
- Multicolumn indexes, for the queries a real app runs all the time

Let's get started.

## The problem: scanning everything

ChaiPoint has 7 orders. Any query is instant. Real apps have millions. Let's make a bigger table to feel the problem. This creates 200,000 fake orders for 5,000 customers. It is a separate table, so our ChaiPoint data stays as it was.

```sql
CREATE TABLE big_orders AS
SELECT g AS id,
       (g % 5000) + 1 AS customer_id,
       (ARRAY['placed','paid','delivered','cancelled'])[1 + (g % 4)] AS status,
       (g % 500)::numeric(8,2) AS total,
       now() - (g || ' minutes')::interval AS placed_at
FROM generate_series(1, 200000) AS g;

ALTER TABLE big_orders ADD PRIMARY KEY (id);
ANALYZE big_orders;
```

(`ANALYZE` makes Postgres collect statistics about the table. The planner uses them to choose a route.)

Now ask for one customer's orders:

```sql
SELECT * FROM big_orders WHERE customer_id = 42;
```

It returns 40 rows. But how did Postgres find them? To see, put `EXPLAIN ANALYZE` in front.

## EXPLAIN: ask the database how it will do it

The manual says that "PostgreSQL devises a query plan for each query it receives", and `EXPLAIN` prints that plan. With `ANALYZE`, "EXPLAIN actually executes the query, and then displays the true row counts and true run time".

```sql
EXPLAIN ANALYZE SELECT * FROM big_orders WHERE customer_id = 42;
```

On my test machine (Postgres 16, 200,000 rows), the answer was:

```text
Seq Scan on big_orders  (cost=0.00..3972.00 rows=40 width=28) (actual time=0.011..10.988 rows=40 loops=1)
  Filter: (customer_id = 42)
  Rows Removed by Filter: 199960
Planning Time: 0.169 ms
Execution Time: 11.011 ms
```

Your numbers will differ. The shape is what matters:

- **`Seq Scan`**: a sequential scan. Postgres read the whole table, row by row.
- **`Rows Removed by Filter: 199960`**: it looked at 200,000 rows to keep 40. That is the waste.
- **`cost=0.00..3972.00`**: the planner's estimate, in "arbitrary units", not milliseconds. The manual says the cost numbers "are expressed in arbitrary units; so they are unlikely to match up" with the real time. The first number is the start-up cost, the second is the total.
- **`actual time` and `Execution Time`**: the real time, in milliseconds.

!!! warning "EXPLAIN ANALYZE really runs the query"
    For an `UPDATE` or `DELETE`, this changes data. The manual's advice is to "roll the command back afterwards": `BEGIN; EXPLAIN ANALYZE UPDATE ...; ROLLBACK;`. Plain `EXPLAIN` (without `ANALYZE`) only plans, and runs nothing.

## What an index is

Think of the index at the back of a book. If you want "transactions", you do not read all 500 pages. You look in the index, which is sorted, and it says "pages 112 and 340".

A database index works the same way. The manual's introduction puts it this way: without preparation "the system would have to scan the entire table, row by row", but with an index it "might only have to walk a few levels deep into a search tree". The default kind in Postgres is the **B-tree**.

```flow
{"width":720,"height":230,"intro":"Without an index, the database reads every row. With one, it jumps.",
 "nodes":[
  {"id":"q","label":"Query","sub":"customer_id = 42","x":10,"y":90,"kind":"app","w":140},
  {"id":"i","label":"Index","sub":"sorted by customer_id","x":290,"y":20,"kind":"queue","w":170},
  {"id":"t","label":"Table","sub":"200,000 rows","x":290,"y":160,"kind":"db","w":170},
  {"id":"r","label":"Result","sub":"40 rows","x":560,"y":90,"kind":"phone","w":130}],
 "edges":[{"from":"q","to":"t","label":"no index: read all"},{"from":"q","to":"i","label":"look up 42"},{"from":"i","to":"t","label":"go to these pages"},{"from":"t","to":"r"}],
 "steps":[
  {"edges":[0],"nodes":["t"],"labels":["200,000"],"text":"Without an index the database has only one way: read every row of the table and check each one."},
  {"edges":[1],"nodes":["i"],"labels":["42?"],"text":"With an index, the database first looks in the small sorted index for 42."},
  {"edges":[2],"nodes":["t"],"labels":["40 pages"],"text":"The index points to exactly where the 40 matching rows live. Only those pages of the table are read."},
  {"edges":[3],"nodes":["r"],"labels":["40 rows"],"text":"The result is the same. The work is far smaller."}]}
```

!!! android "Android parallel"
    In Room you have `@Entity(indices = [Index("customer_id")])`, and the same advice applies: index the columns you filter or join on. It is the same B-tree idea in SQLite, only the scale is different.

Create one:

```sql
CREATE INDEX big_orders_customer_idx ON big_orders (customer_id);
ANALYZE big_orders;
```

```sql
EXPLAIN ANALYZE SELECT * FROM big_orders WHERE customer_id = 42;
```

```text
Bitmap Heap Scan on big_orders  (cost=4.60..145.32 rows=40 width=28) (actual time=0.028..0.083 rows=40 loops=1)
  Recheck Cond: (customer_id = 42)
  Heap Blocks: exact=40
  ->  Bitmap Index Scan on big_orders_customer_idx  (cost=0.00..4.59 rows=40 width=0) (actual time=0.019..0.019 rows=40 loops=1)
        Index Cond: (customer_id = 42)
Planning Time: 0.163 ms
Execution Time: 0.109 ms
```

From **11 ms to 0.1 ms**, about a hundred times faster, on the same data. Notice we did not change the query. Postgres found the index and used it by itself.

You may see `Bitmap Index Scan` and `Bitmap Heap Scan` here instead of a plain `Index Scan`. The manual explains why: the planner first collects, from the index, which table pages hold matches, and then visits those pages in order. "Fetching rows separately is much more expensive than reading them sequentially, but because not all the pages of the table have to be visited, this is still cheaper than a sequential scan." For a single row (`WHERE id = 42`) you would see a plain `Index Scan`.

!!! tip "You already have some indexes"
    The manual says "PostgreSQL automatically creates a unique index when a unique constraint or primary key is defined for a table." So `id` columns, and `customers.phone` (which is `UNIQUE`), are already indexed. What you must add yourself are indexes on **foreign keys** and on columns you filter or sort on often.

## What an index can and cannot do

The manual lists what a B-tree helps with: "equality and range queries on data that can be sorted". In practice, the operators `<  <=  =  >=  >`, plus `BETWEEN`, `IN`, `IS NULL`, and `LIKE 'foo%'` (a pattern anchored at the start). It also says an index can "retrieve data in sorted order", which helps `ORDER BY`.

And what it cannot do:

- **`LIKE '%bar'`** (wildcard at the start). The manual: "not `col LIKE '%bar'`". The sorted order is no help when you do not know the first letters.
- **A calculation on the column.** We still have our index on `customer_id`, but watch what happens when we hide the column inside an expression:

```sql
EXPLAIN ANALYZE SELECT * FROM big_orders WHERE customer_id + 0 = 42;
```

The plan on my machine was a `Parallel Seq Scan` that removed 99,980 rows per worker, and took about 10 ms. The index is sorted by `customer_id`, not by `customer_id + 0`, so it cannot be used. Keep the column alone on one side of the comparison. (Postgres can index an expression too, but that is a topic for another day.)

## An index is not free

The manual says it directly: "After an index is created, the system has to keep it synchronized with the table. This adds overhead to data manipulation operations." Every `INSERT`, `UPDATE` and `DELETE` must also update every index. And indexes take space:

```sql
SELECT pg_size_pretty(pg_relation_size('big_orders'))              AS table_size,
       pg_size_pretty(pg_relation_size('big_orders_customer_idx')) AS index_size;
```

On my machine: a 12 MB table and a 1.4 MB index. The manual also warns that "creating an index on a large table can take a long time", and that by default writes (`INSERT`, `UPDATE`, `DELETE`) are blocked on that table until the build finishes. On a busy production table, read the `CREATE INDEX` page of the manual first.

So the rule is not "index everything". It is: **index what your slow, frequent queries use, then check with `EXPLAIN` that it helped.**

Another honest point: a column with only a few different values, like our `status` with four values, is a weak candidate. A query for `status = 'paid'` still returns a quarter of the table (50,000 rows). On my machine, even with an index on `status`, the time only went from about 18 ms to about 12 ms, and most of the time was spent returning all those rows. Indexes shine when the query picks out **few rows from many**.

## Multicolumn indexes: matching what your screens really ask

Your app screen "my last 5 orders" asks: orders of **one customer**, **newest first**, **limit 5**. An index on both columns, in this order, fits that exactly:

```sql
CREATE INDEX big_orders_cust_time_idx ON big_orders (customer_id, placed_at DESC);
ANALYZE big_orders;
```

```sql
EXPLAIN ANALYZE
SELECT * FROM big_orders WHERE customer_id = 42 ORDER BY placed_at DESC LIMIT 5;
```

```text
Limit  (cost=0.42..21.00 rows=5 width=27) (actual time=0.026..0.035 rows=5 loops=1)
  ->  Index Scan using big_orders_cust_time_idx on big_orders  (cost=0.42..165.09 rows=40 width=27) (actual time=0.026..0.031 rows=5 loops=1)
        Index Cond: (customer_id = 42)
Execution Time: 0.049 ms
```

There is no `Sort` step at all: the index already holds the rows in the right order, so Postgres reads the first 5 entries and stops. The manual's rule for multicolumn indexes: it is "most efficient when there are constraints on the leading (leftmost) columns". So put the column you compare with `=` first, and the column you sort by next. The manual also advises using them "sparingly": "indexes with more than three columns are unlikely to be helpful unless the usage of the table is extremely stylized."

This is also the index that makes the keyset pagination of chapter 3 fast.

Clean up our experiment table:

```sql
DROP TABLE big_orders;
```

## Summary

- Without an index, Postgres reads the whole table (`Seq Scan`). With a fitting index, it jumps to the rows.
- `EXPLAIN` shows the plan, `EXPLAIN ANALYZE` runs the query and shows real times. Wrap data-changing statements in `BEGIN ... ROLLBACK`.
- Cost numbers are the planner's estimates in arbitrary units, `actual time` is in milliseconds.
- Primary keys and `UNIQUE` columns are indexed automatically. Add indexes for foreign keys and for columns you often filter or sort by.
- Indexes cost space and slow down writes. They do not help for `LIKE '%x'`, for calculations on the column, or when the query returns most of the table.
- For "latest N of something", a multicolumn index (equality column first, then the sort column) removes the sort entirely.

!!! faq "Why did Postgres not use my index?"
    Run `EXPLAIN` and read the reason. Common causes: the table is tiny (the manual says that on a table of one disk page "you'll nearly always get a sequential scan plan whether indexes are available or not"), the query returns most of the table, the column is wrapped in a function, or the statistics are old (run `ANALYZE`).

!!! faq "Can I trust EXPLAIN on my laptop for production?"
    Be careful. The manual warns that "results on a toy-sized table cannot be assumed to apply to large tables". Test with realistic amounts of data, like we did here.

## Sources

- [PostgreSQL 16 manual: Using EXPLAIN](https://www.postgresql.org/docs/16/using-explain.html)
- [PostgreSQL 16 manual: Indexes, Introduction](https://www.postgresql.org/docs/16/indexes-intro.html)
- [PostgreSQL 16 manual: Index Types (B-tree)](https://www.postgresql.org/docs/16/indexes-types.html)
- [PostgreSQL 16 manual: Multicolumn Indexes](https://www.postgresql.org/docs/16/indexes-multicolumn.html)
- [PostgreSQL 16 manual: Unique Indexes](https://www.postgresql.org/docs/16/indexes-unique.html)

That's it for now. In the next chapter, we will see what happens when many people use the database at the same time: transactions, isolation, and locks.
