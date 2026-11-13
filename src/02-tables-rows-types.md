---
title: Tables, rows, and types: designing the ChaiPoint database
part: Part 1 · SQL and Postgres
summary: CREATE TABLE, data types, keys, constraints, and your first INSERT.
---

**A table is a named grid with fixed columns, and the database refuses any row that breaks the rules you wrote for it.**

In this chapter, we will learn:

- How to create a table with `CREATE TABLE`
- The data types you will use every day
- What a primary key is and why every table needs one
- How constraints (`NOT NULL`, `UNIQUE`, `CHECK`) protect your data
- How to add rows with `INSERT`

Let's get started.

## From @Entity to CREATE TABLE

In Room, you write a class and Room creates the table:

```kotlin
@Entity(tableName = "products")
data class Product(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val name: String,
    val price: Double,
    val stock: Int,
)
```

On a server, you write the table yourself, in SQL:

```sql
CREATE TABLE products (
    id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name      text          NOT NULL,
    price     numeric(8,2)  NOT NULL CHECK (price > 0),
    stock     integer       NOT NULL DEFAULT 0 CHECK (stock >= 0),
    is_active boolean       NOT NULL DEFAULT true
);
```

Read it line by line. Each line is: **column name, type, rules**.

!!! android "Android parallel"
    `@PrimaryKey(autoGenerate = true)` becomes `GENERATED ALWAYS AS IDENTITY PRIMARY KEY`. Both say: "the database picks the id for me." In Room you also had `@ColumnInfo(defaultValue = ...)` and `NOT NULL` from Kotlin's non-null types. In SQL you write these rules explicitly.

## The types you will use every day

| Type | Use it for | Kotlin cousin |
|---|---|---|
| `integer`, `bigint` | whole numbers, ids, counts | `Int`, `Long` |
| `numeric(8,2)` | **money**, exact decimals | `BigDecimal` (never `Double`) |
| `text` | any string | `String` |
| `boolean` | true or false | `Boolean` |
| `timestamptz` | a moment in time, with time zone | `Instant` |
| `date` | a calendar date | `LocalDate` |
| `uuid` | a random unique id | `UUID` |
| `jsonb` | a JSON document you can query | a `Map` or a data class as JSON |

!!! warning "Never store money as a float"
    `0.1 + 0.2` in floating point is `0.30000000000000004`. Use `numeric` (or whole paise in an `integer`). The books of a shop must add up exactly.

## Keys and constraints: the bouncers of your data

A **constraint** is a rule the database checks on every write. If a row breaks the rule, the write fails and nothing changes.

- `PRIMARY KEY`: unique and not null. It identifies one row.
- `NOT NULL`: this column must have a value.
- `UNIQUE`: no two rows may have the same value here.
- `CHECK (...)`: any condition you can write, such as `price > 0`.
- `DEFAULT`: the value used when you do not give one.
- `REFERENCES` (foreign key): points to a row in another table. We use it in chapter 5.

Let's create the rest of ChaiPoint's tables:

```sql
CREATE TABLE customers (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name       text        NOT NULL,
    phone      text        NOT NULL UNIQUE,
    city       text        NOT NULL DEFAULT 'Bengaluru',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE orders (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id bigint       NOT NULL REFERENCES customers (id),
    status      text         NOT NULL DEFAULT 'placed'
                CHECK (status IN ('placed', 'paid', 'cancelled', 'delivered')),
    total       numeric(10,2) NOT NULL DEFAULT 0,
    placed_at   timestamptz  NOT NULL DEFAULT now()
);

CREATE TABLE order_items (
    order_id   bigint        NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
    product_id bigint        NOT NULL REFERENCES products (id),
    quantity   integer       NOT NULL CHECK (quantity > 0),
    unit_price numeric(8,2)  NOT NULL,
    PRIMARY KEY (order_id, product_id)
);
```

Here is the whole picture. Press Play to see how the tables point at each other.

```flow
{"width":720,"height":260,"intro":"Arrows mean 'has a reference to'.",
 "nodes":[
  {"id":"c","label":"customers","sub":"id, name, phone","x":10,"y":100,"kind":"db","w":150},
  {"id":"o","label":"orders","sub":"id, customer_id, status","x":250,"y":100,"kind":"db","w":170},
  {"id":"i","label":"order_items","sub":"order_id, product_id, quantity","x":500,"y":20,"kind":"db","w":200},
  {"id":"p","label":"products","sub":"id, name, price, stock","x":500,"y":180,"kind":"db","w":200}],
 "edges":[{"from":"o","to":"c","label":"customer_id"},{"from":"i","to":"o","label":"order_id"},{"from":"i","to":"p","label":"product_id"}],
 "steps":[
  {"nodes":["c"],"text":"A customer is a person. One row per person."},
  {"nodes":["o","c"],"edges":[0],"text":"An order belongs to exactly one customer. The column customer_id points to customers.id."},
  {"nodes":["i","o"],"edges":[1],"text":"An order has many items. Each item row points back to its order."},
  {"nodes":["i","p"],"edges":[2],"text":"And each item points to the product that was bought. order_items sits between orders and products."}]}
```

!!! android "Android parallel"
    `REFERENCES` is Room's `@ForeignKey`. `ON DELETE CASCADE` is the same option in `@ForeignKey(onDelete = CASCADE)`. And `order_items` is the "junction table" you made for a many-to-many relation.

## Adding rows with INSERT

```sql
INSERT INTO customers (name, phone, city) VALUES
    ('Asha',  '9000000001', 'Bengaluru'),
    ('Ravi',  '9000000002', 'Bengaluru'),
    ('Meera', '9000000003', 'Mysuru'),
    ('Kiran', '9000000004', 'Bengaluru'),
    ('Divya', '9000000005', 'Chennai');

INSERT INTO products (name, price, stock) VALUES
    ('Masala chai',    20.00, 200),
    ('Filter coffee',  25.00, 150),
    ('Samosa',         15.00, 120),
    ('Bun maska',      30.00,  80),
    ('Veg sandwich',   60.00,  50),
    ('Lemon tea',      18.00,   0);
```

We did not give `id` or `created_at`. The database filled them: `id` from the identity counter, `created_at` from `now()`. Let's look:

```sql
SELECT id, name, price, stock FROM products;
```

Press Play to see how a row enters the table.

```tables
{"intro":"INSERT adds a row at the end. The id is chosen by Postgres.",
 "tables":[{"name":"products","columns":["id","name","price","stock"],"rows":[[1,"Masala chai","20.00",200],[2,"Filter coffee","25.00",150],[3,"Samosa","15.00",120],[4,"Bun maska","30.00",80]]}],
 "steps":[
  {"text":"Four rows are already in the table."},
  {"add":{"0":[3]},"text":"INSERT INTO products (name, price, stock) VALUES ('Bun maska', 30.00, 80). We gave three values. The id 4 came from the identity counter."}]}
```

Now let's break a rule on purpose. The database should refuse.

```sql-error
INSERT INTO products (name, price, stock) VALUES ('Free chai', 0, 10);
```

Postgres answers with `violates check constraint "products_price_check"`. The row is **not** saved. This is the point: bad data is stopped at the door, even if a bug in your Python code forgets to check.

```sql-error
INSERT INTO customers (name, phone) VALUES ('Another Asha', '9000000001');
```

The phone number is `UNIQUE`, so the second `9000000001` is refused.

Finally, some orders, so later chapters have data to ask questions about:

```sql
INSERT INTO orders (customer_id, status, total, placed_at) VALUES
    (1, 'delivered', 55.00, now() - interval '6 days'),
    (2, 'delivered', 85.00, now() - interval '5 days'),
    (1, 'paid',      90.00, now() - interval '3 days'),
    (3, 'cancelled', 25.00, now() - interval '3 days'),
    (4, 'placed',    60.00, now() - interval '1 day'),
    (2, 'placed',    40.00, now() - interval '2 hours'),
    (1, 'placed',    35.00, now() - interval '1 hour');

INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
    (1, 1, 2, 20.00), (1, 3, 1, 15.00),
    (2, 2, 1, 25.00), (2, 5, 1, 60.00),
    (3, 4, 3, 30.00),
    (4, 2, 1, 25.00),
    (5, 5, 1, 60.00),
    (6, 1, 2, 20.00),
    (7, 3, 1, 15.00), (7, 1, 1, 20.00);
```

## Summary

- `CREATE TABLE` lists columns, each with a type and rules.
- Use `numeric` for money, `text` for strings, `timestamptz` for moments.
- Constraints (`PRIMARY KEY`, `NOT NULL`, `UNIQUE`, `CHECK`, `REFERENCES`) make the database refuse bad data.
- `INSERT INTO table (columns) VALUES (...)` adds rows. Columns you skip get their `DEFAULT`.

!!! faq "Why not just validate in Python?"
    Do both. Python gives friendly error messages. The database is the last line of defence, and it protects you from every bug, every script, and every future service that writes to the same table.

!!! faq "What is the difference between `varchar(50)` and `text`?"
    In Postgres, nearly none for speed. `text` is simpler. Use a `CHECK (length(name) <= 50)` if you need a limit.

That's it for now. In the next chapter, we will ask the database questions with `SELECT`.
