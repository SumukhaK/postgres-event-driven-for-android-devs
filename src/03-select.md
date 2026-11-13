---
title: Asking questions with SELECT
part: Part 1 · SQL and Postgres
summary: SELECT, WHERE, ORDER BY, LIMIT, pagination, NULL, and text search with LIKE.
---

**`SELECT` reads rows from a table. You say which columns you want, which rows you want, and in which order. The database finds them.**

In this chapter, we will learn:

- How to read columns and rows with `SELECT ... FROM`
- How to filter rows with `WHERE`
- How to sort with `ORDER BY` and take a few rows with `LIMIT`
- How to build "page 2" of a list the safe way
- Why `NULL` behaves strangely, and how to handle it
- How to search text with `LIKE` and `ILIKE`

Let's get started.

## The same query you already write in Room

In your DAO you have written this many times:

```kotlin
@Query("SELECT * FROM products WHERE price >= :min ORDER BY price")
fun expensive(min: Double): Flow<List<Product>>
```

The part inside the quotes is plain SQL. Postgres understands exactly the same sentence. So this chapter is mostly about knowing the sentence **well**, instead of copying it.

!!! android "Android parallel"
    `@Query("...")` in Room is just SQL in a string. Everything in this chapter works inside your `@Dao` too, because SQLite speaks almost the same SQL. The `:min` placeholder is Room's way to pass a value. On the Python side, we will pass values safely in chapter 9.

## Reading everything, then only what you need

The smallest query:

```sql
SELECT * FROM products;
```

`*` means "all columns". It is fine for exploring in `psql`. In real code, **name the columns you need**. It is faster and it does not break when someone adds a column later.

```sql
SELECT name, price FROM products;
```

You can also calculate while you read. Here we add 5% on top of the price, and round to two decimals:

```sql
SELECT name, price, round(price * 1.05, 2) AS price_with_tax
FROM products;
```

`AS price_with_tax` gives the new column a name. It is the same as `@ColumnInfo(name = ...)` for the result.

## Filtering rows with WHERE

`WHERE` keeps only the rows where the condition is true. Press Play to see it work row by row.

```tables
{"intro":"WHERE price >= 25 checks every row. Rows that fail are dropped from the result.",
 "tables":[{"name":"products","columns":["id","name","price","stock"],"rows":[[1,"Masala chai","20.00",200],[2,"Filter coffee","25.00",150],[3,"Samosa","15.00",120],[4,"Bun maska","30.00",80],[5,"Veg sandwich","60.00",50],[6,"Lemon tea","18.00",0]]}],
 "steps":[
  {"text":"The whole table has 6 rows."},
  {"hl":{"0":[1,3,4]},"dim":{"0":[0,2,5]},"text":"WHERE price >= 25: Filter coffee (25), Bun maska (30) and Veg sandwich (60) pass. The others are dimmed: they are not in the result."}]}
```

```sql
SELECT name, price FROM products WHERE price >= 25;
```

Conditions can be joined with `AND` and `OR`, and grouped with brackets:

```sql
SELECT name, price, stock
FROM products
WHERE stock > 0 AND price < 30;
```

Two shortcuts you will use all the time:

```sql
SELECT name FROM products WHERE id IN (1, 3, 5);

SELECT name, price FROM products WHERE price BETWEEN 20 AND 30;
```

`BETWEEN 20 AND 30` includes both ends, 20 and 30.

## Sorting with ORDER BY

Without `ORDER BY`, Postgres gives you rows in **no promised order**. It may look sorted today and be different tomorrow. If order matters, always say it.

```sql
SELECT name, price FROM products ORDER BY price DESC, name;
```

`DESC` is high to low. The default is `ASC` (low to high). After the comma, `name` breaks ties.

## Taking a few rows with LIMIT

```sql
SELECT name, price FROM products ORDER BY price DESC LIMIT 3;
```

The three most expensive items. Notice that `LIMIT` comes with `ORDER BY`.

!!! warning "LIMIT without ORDER BY"
    The PostgreSQL manual says that when you use `LIMIT` without `ORDER BY`, "you will get an unpredictable subset of the query's rows". So "the first 3 rows" means nothing until you say what "first" means.

## Pagination: the part every app needs

Your Android app shows a list and loads more as you scroll. You may have used Paging 3. On the server, there are two ways to give "the next page".

### Way 1: LIMIT and OFFSET

```sql
SELECT id, name FROM products ORDER BY id LIMIT 3 OFFSET 3;
```

`OFFSET 3` skips three rows, then `LIMIT 3` takes three. Easy to read. But the manual warns: "The rows skipped by an OFFSET clause still have to be computed inside the server; therefore a large OFFSET might be inefficient." Page 1000 is slower than page 1. Also, if a new row is inserted while the user scrolls, an item can appear twice or be missed.

### Way 2: keyset pagination ("seek")

Instead of "skip N rows", say "give me the rows after the last one I saw":

```sql
SELECT id, name FROM products WHERE id > 3 ORDER BY id LIMIT 3;
```

The app remembers the last `id` it received (3) and sends it back as the cursor. Postgres jumps straight to it, using the index on `id` (chapter 7). New rows do not shift the pages.

!!! android "Android parallel"
    This is exactly the idea of `nextKey` in Paging 3's `PagingSource.load()`. Your API gets `?after=3&limit=3`, not `?page=2`. Use `OFFSET` for small admin screens, and keyset for feeds and big lists.

## NULL: "I don't know"

`NULL` is not zero and not an empty string. It means **unknown or missing**. The rule that surprises everyone: any normal comparison with `NULL` gives `NULL`, not true or false. The manual says `7 = NULL` yields null, and: "Do not write expression = NULL because NULL is not 'equal to' NULL."

```sql
SELECT NULL = NULL AS equal,
       NULL IS NULL AS is_null,
       1 IS DISTINCT FROM NULL AS differs,
       NULL IS NOT DISTINCT FROM NULL AS same;
```

Read the result carefully: `equal` is empty (NULL), but `is_null` is `true`. Use `IS NULL` and `IS NOT NULL` to test. Use `IS DISTINCT FROM` when you want NULL to act like a normal value in a comparison.

!!! android "Android parallel"
    Kotlin has `String?` and the compiler makes you handle `null`. SQL has no compiler for it. If a column can be `NULL` and you write `WHERE col = 'x'`, rows with `NULL` silently disappear. This is why we declared most ChaiPoint columns `NOT NULL` in chapter 2.

## Searching text

`LIKE` matches a pattern. In it, `%` means "any number of characters" and `_` means "exactly one character". And, the manual says, "LIKE pattern matching always covers the entire string", so to find text **anywhere** inside, put `%` on both sides.

```sql
SELECT name FROM products WHERE name LIKE 'S%';

SELECT name FROM products WHERE name ILIKE '%CHAI%';
```

`ILIKE` is the case-insensitive version. The first finds names starting with `S` (Samosa). The second finds `Masala chai` even though we typed `CHAI`.

One more useful word, `DISTINCT`, removes duplicates:

```sql
SELECT DISTINCT city FROM customers ORDER BY city;
```

## Summary

- `SELECT columns FROM table WHERE condition ORDER BY ... LIMIT n` is the shape of most queries.
- Name your columns instead of `*` in real code.
- No `ORDER BY` means no promised order. `LIMIT` needs an `ORDER BY` to mean anything.
- For "next page", prefer keyset (`WHERE id > last_seen`) over a big `OFFSET`.
- `NULL` is "unknown". Test it with `IS NULL`, never `= NULL`.
- `LIKE` is case-sensitive, `ILIKE` is not. `%` is any text, `_` is one character.

!!! faq "Is SQL case-sensitive?"
    Keywords (`SELECT`, `where`) are not. Text values are: `'Samosa'` and `'samosa'` are different strings, unless you use `ILIKE` or `lower()`.

!!! faq "Why not just use SELECT * everywhere?"
    It sends more data than you need, and it can break your code when the table changes. Naming columns is a small habit with a big payoff.

## Sources

- [PostgreSQL 16 manual: LIMIT and OFFSET](https://www.postgresql.org/docs/16/queries-limit.html)
- [PostgreSQL 16 manual: Comparison Functions and Operators (NULL, IS DISTINCT FROM)](https://www.postgresql.org/docs/16/functions-comparison.html)
- [PostgreSQL 16 manual: Pattern Matching (LIKE, ILIKE)](https://www.postgresql.org/docs/16/functions-matching.html)

That's it for now. In the next chapter, we will change data: `UPDATE`, `DELETE`, and upsert.
