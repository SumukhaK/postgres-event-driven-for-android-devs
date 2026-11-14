---
title: FastAPI and Postgres: connecting safely
part: Part 2 · Python and Postgres
summary: A connection pool, safe parameters, one transaction per request, and a real order endpoint with tests.
---

**A backend talks to Postgres through a small pool of reusable connections, passes values separately from the SQL, and wraps each request's changes in one transaction.**

In this chapter, we will learn:

- Why you do not open a new connection for every request
- How to set up a connection pool in FastAPI with `lifespan`
- Why you never build SQL with string formatting (SQL injection)
- How psycopg 3 handles transactions
- How to write the "place an order" endpoint from the lessons of chapter 8
- How to test it against a real Postgres

Let's get started.

## The code for this chapter

Everything below is real code from the course repository, in the `project/` folder. It has 13 tests, and they pass on Postgres 16. The chapter shows the important parts. You can read the rest in the repository.

```text
project/
  sql/001_schema.sql     the tables from chapter 2 (plus two indexes)
  sql/002_seed.sql       the sample customers and products
  app/settings.py        configuration, read from environment variables
  app/db.py              the pool, and a retry helper
  app/orders.py          the business rules: place an order
  app/main.py            the web layer: routes, validation, error answers
  tests/                 13 tests against a real database
```

Notice the split. `main.py` knows about HTTP. `orders.py` knows about orders and SQL, and nothing about HTTP. `db.py` knows about connections. If you have used clean architecture on Android, this is the same: a screen layer, a domain layer, a data layer.

!!! android "Android parallel"
    `main.py` is your Fragment or Composable (it takes input and shows output). `orders.py` is your use case or repository (the rules). `db.py` is your `Room.databaseBuilder(...)`. One more difference: on Android, Room opens the database once for the whole app. On a server, hundreds of requests need the database at the same time, and that is what the pool is for.

## Why a pool?

Opening a connection to Postgres takes time: a network trip, a login, and a new server process on the other side. The psycopg manual says: "Because the time to establish a new connection can be relatively long, keeping connections open can reduce latency." So we open a few connections once, and lend them out.

```flow
{"width":720,"height":240,"intro":"Many requests share a few connections.",
 "nodes":[
  {"id":"r1","label":"Request 1","x":10,"y":10,"kind":"phone","w":120},
  {"id":"r2","label":"Request 2","x":10,"y":90,"kind":"phone","w":120},
  {"id":"r3","label":"Request 3","x":10,"y":170,"kind":"phone","w":120},
  {"id":"p","label":"Pool","sub":"2 connections open","x":280,"y":90,"kind":"queue","w":150},
  {"id":"db","label":"PostgreSQL","x":560,"y":90,"kind":"db","w":140}],
 "edges":[{"from":"r1","to":"p"},{"from":"r2","to":"p"},{"from":"r3","to":"p","dashed":true,"label":"waits"},{"from":"p","to":"db","label":"2 at a time"}],
 "steps":[
  {"edges":[0],"nodes":["r1","p"],"labels":["borrow"],"text":"Request 1 borrows a connection from the pool. No new connection is opened."},
  {"edges":[1,3],"nodes":["r2","db"],"labels":["borrow","SQL"],"text":"Request 2 borrows the second one. Both run SQL on the database at the same time."},
  {"edges":[2],"nodes":["r3"],"labels":["queue"],"text":"Request 3 arrives. All connections are busy, so it waits in line. It is not refused."},
  {"nodes":["p"],"text":"When Request 1 finishes, its connection goes back to the pool and Request 3 gets it. The database never sees more than 2 connections."}]}
```

The manual describes the same behaviour: the pool "manages a certain amount of connections (between min_size and max_size). If the pool has a connection ready in its state, it is served immediately to the connection() caller, otherwise the caller is put in a queue and is served a connection as soon as it's available."

This also protects Postgres. It has a limit on concurrent connections (`max_connections`), and a pool keeps your app under it.

## Setting up the pool in FastAPI

```python
# app/db.py
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

def make_pool(open_now: bool = False) -> ConnectionPool:
    return ConnectionPool(
        settings.DATABASE_URL,
        min_size=settings.POOL_MIN_SIZE,
        max_size=settings.POOL_MAX_SIZE,
        kwargs={"row_factory": dict_row},     # rows come back as dicts: row["price"]
        open=open_now,
    )
```

The pool must be opened when the app starts and closed when it stops. FastAPI has a place for that, the **lifespan**. Its manual says the code before `yield` runs "once, before the application starts receiving requests", and the code after it runs "once, after having handled possibly many requests". It even names our use case: "a database connection pool".

```python
# app/main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = db.make_pool()
    app.state.pool.open()
    app.state.pool.wait()      # fail at start-up if the database cannot be reached
    yield
    app.state.pool.close()

app = FastAPI(title="ChaiPoint API", lifespan=lifespan)
```

`pool.wait()` is from the psycopg manual's "pool startup check": without it, a pool that cannot reach the database accepts clients and lets them "block until failing with a PoolTimeout". With `wait()`, a wrong password fails when the server starts, where you will see it, and not on the first customer's request.

!!! android "Android parallel"
    `lifespan` is like `Application.onCreate` and the end of the process: a place to create things that live for the whole app. The code after `yield` is the cleanup you wish Android gave you a reliable hook for.

### Why plain `def` and not `async def`?

The psycopg `ConnectionPool` we use is the **blocking** (thread-based) one, so our routes are plain `def` functions. FastAPI's manual says that when you declare a path operation with normal `def`, "it is run in an external threadpool that is then awaited, instead of being called directly (as it would block the server)." So many requests still run at once, each in its own thread, each borrowing its own connection. psycopg also offers `AsyncConnectionPool` for `async def` code. For a beginner, plain `def` with the normal pool is simpler and has fewer traps.

## Passing values: never build SQL as a string

This is the most important security rule in this chapter. Compare:

```python
# WRONG: SQL built from a string
conn.execute(f"SELECT * FROM products WHERE id = {product_id}")

# RIGHT: SQL and values sent separately
conn.execute("SELECT * FROM products WHERE id = %s", (product_id,))
```

The psycopg manual says: "Never use % or + to merge values", and explains that "if the variables containing the data to send to the database come from an untrusted source (such as data coming from a form on a web site) an attacker could easily craft a malformed string, either gaining access to unauthorized data or performing destructive operations on the database. This form of attack is called SQL injection". With `%s`, the manual notes that "query and the parameters are sent to the server separately", so the value can never be read as SQL, whatever it contains.

Two small details: the placeholder is `%s` for every type (numbers too), without quotes around it. And the values go in a **tuple**, even for one value: `(product_id,)`.

!!! android "Android parallel"
    This is why Room uses `:id` placeholders and not string concatenation, and why `SupportSQLiteDatabase.query(sql, args)` takes the arguments separately. The idea is the same on every platform.

We have a test for it. The id in the URL is declared as `int`, so FastAPI rejects text before any SQL runs:

```python
def test_sql_injection_text_is_just_text(client, db):
    assert client.get("/products/1;DROP TABLE products").status_code == 422
    assert db.execute("SELECT count(*) AS n FROM products").fetchone()["n"] == 6
```

## Transactions in psycopg 3

One surprise, from the psycopg manual: "by default, any database operation will start a new transaction. As a consequence, changes made by any cursor of the connection will not be visible until `commit()` is called". If you forget the commit, your insert silently disappears.

The pool makes this easy. The manual says that at the end of `with pool.connection() as conn:` the transaction "is committed (if the block is exited normally) or rolled back (if it is exited with an exception)". So the rule is:

- the block ends normally: **commit**,
- the block raises any exception: **rollback**, as if nothing happened.

Our whole "place an order" function uses this. It does many statements, and if any step raises an error, all of them are undone.

## Placing an order, with the lessons of chapter 8

Here is the heart of the chapter. It uses almost everything we have learned.

```python
# app/orders.py
def place_order(conn, customer_id, items):
    try:
        order_id = conn.execute(
            "INSERT INTO orders (customer_id) VALUES (%s) RETURNING id", (customer_id,)
        ).fetchone()["id"]
    except psycopg.errors.ForeignKeyViolation:
        raise CustomerNotFound() from None

    total = Decimal("0")
    for item in sorted(items, key=lambda i: i.product_id):
        row = conn.execute(
            "UPDATE products SET stock = stock - %s "
            "WHERE id = %s AND is_active AND stock >= %s RETURNING price",
            (item.quantity, item.product_id, item.quantity),
        ).fetchone()
        if row is None:
            raise OutOfStock(item.product_id)
        conn.execute(
            "INSERT INTO order_items (order_id, product_id, quantity, unit_price) "
            "VALUES (%s, %s, %s, %s)",
            (order_id, item.product_id, item.quantity, row["price"]),
        )
        total += row["price"] * item.quantity

    conn.execute("UPDATE orders SET total = %s WHERE id = %s", (total, order_id))
    return {"order_id": order_id, "total": total}
```

Read it with the earlier chapters in mind:

1. `INSERT ... RETURNING id` (chapter 4) gives us the new order's id without a second query.
2. The `UPDATE ... WHERE stock >= %s` (chapter 8, Fix 2) is the guard. It checks and subtracts in **one statement**, so two requests cannot both take the last chai. `RETURNING price` reads the price in the same step. The price we charge is the price at that moment, and we store it in `unit_price`, so old orders never change when a price changes later.
3. `row is None` means the guard stopped us (chapter 4: zero rows is not an error, so we check). We raise `OutOfStock`. The exception leaves the `with pool.connection()` block, so **everything rolls back**: the order row, and the stock we already took from earlier items.
4. Items are sorted by product id first. Every request locks product rows in the same order, which is the manual's own cure for deadlocks, from chapter 8: "acquire locks on multiple objects in a consistent order."
5. A `ForeignKeyViolation` (chapter 2's `REFERENCES`) means the customer does not exist. We turn it into a clear error instead of a crash.

### The retry helper, with a hard cap

In chapter 8 we promised: retries, with a limit. Here it is.

```python
# app/db.py
RETRYABLE = (psycopg.errors.DeadlockDetected, psycopg.errors.SerializationFailure)

def run_with_retry(pool, work, attempts=settings.MAX_ATTEMPTS, pause=0.05):
    for attempt in range(1, attempts + 1):
        try:
            with pool.connection() as conn:     # commit on success, rollback on exception
                return work(conn)
        except RETRYABLE:
            if attempt == attempts:
                raise                           # out of tries: tell the caller
            time.sleep(pause * attempt)
```

Only the two "just run it again" errors are retried. A `ValueError` from a bug, or `OutOfStock`, goes straight out, because running it again would not change the answer. After the last attempt, the error is raised to the caller. There is no loop that can run forever. There are tests for all three cases: it gives up after the cap, it succeeds on a later attempt, and it does not hide real bugs.

### The web layer

```python
# app/main.py
@app.post("/orders", status_code=201)
def create_order(order: OrderIn, request: Request):
    items = [Item(i.product_id, i.quantity) for i in order.items]
    try:
        return db.run_with_retry(request.app.state.pool,
                                 lambda conn: place_order(conn, order.customer_id, items))
    except OutOfStock as e:
        raise HTTPException(409, str(e))
    except CustomerNotFound:
        raise HTTPException(404, "customer not found")
```

`OrderIn` is a Pydantic model: `quantity: int = Field(gt=0)` and `items: list[...] = Field(min_length=1)`. FastAPI checks the JSON before our code runs. It is your Kotlin `data class` plus input validation. The HTTP codes: `201` created, `409` conflict (not enough stock), `404` unknown customer, `422` invalid input.

## Does it really work? Run it

These are real outputs from the running server (`uvicorn app.main:app`), against the seed data.

```text
$ curl "localhost:8000/products?limit=3"
{"items":[{"id":1,"name":"Masala chai","price":20.0,"stock":200},
          {"id":2,"name":"Filter coffee","price":25.0,"stock":150},
          {"id":3,"name":"Samosa","price":15.0,"stock":120}],"next_after":3}

$ curl "localhost:8000/products?after=3&limit=3"        # the keyset page from chapter 3
{"items":[{"id":4,...},{"id":5,...},{"id":6,"name":"Lemon tea","price":18.0,"stock":0}],"next_after":6}

$ curl -X POST localhost:8000/orders -H 'content-type: application/json' \
       -d '{"customer_id":1,"items":[{"product_id":1,"quantity":2},{"product_id":3,"quantity":1}]}'
{"order_id":1,"total":55.0}

$ curl -X POST localhost:8000/orders ... -d '{"customer_id":1,"items":[{"product_id":6,"quantity":1}]}'
{"detail":"not enough stock for product 6"}        <- HTTP 409

$ curl -X POST localhost:8000/orders ... -d '{... "quantity":0 ...}'
{"detail":[{"type":"greater_than","loc":["body","items",0,"quantity"],"msg":"Input should be greater than 0", ...}]}     <- HTTP 422
```

After the successful order, stock for Masala chai went from 200 to 198 and Samosa from 120 to 119.

!!! warning "Look at the prices: `20.0`"
    In the database, `price` is `numeric`, exact. But the JSON answer shows `20.0`, a plain JSON number, which most clients read as a floating-point value. For display that is fine. If your app does **arithmetic** on money, send whole paise as an integer (`2000`), or the price as a string (`"20.00"`), and do the same in your Kotlin code. Never let `Double` into money maths.

## The tests

The tests run against a real Postgres, not a fake. A fake database would not catch the bugs we care about (locks, constraints, races). The setup file wipes and rebuilds the schema, so for safety it **refuses to run unless the database name ends in `_test`**. Each test starts from the same sample data.

The most important one repeats chapter 8's experiment at the API level: 12 orders for the last 5 chai, all at the same instant, from 12 threads.

```python
def test_concurrent_orders_never_oversell(db):
    db.execute("UPDATE products SET stock = 5 WHERE id = 1")
    ...                      # 12 threads, released together by a Barrier
    assert results.count("ok") == 5 and results.count("sold out") == 7
    assert stock == 0        # never below zero
    assert order_count == 5  # the 7 refusals left no order behind
```

Does the test really catch the bug? I checked, by breaking the code on purpose: I removed `AND stock >= %s` from the `UPDATE`, and ran the tests again. Two tests failed, including this one. Then I put the guard back, and all 13 passed. A test that has never failed has not proven anything, so this check matters.

!!! tip "Try it yourself"
    ```bash
    cd project
    pip install -r requirements.txt
    createdb chaipoint_test            # or use the Docker Postgres from chapter 0
    DATABASE_URL=postgresql://user:pass@localhost:5432/chaipoint_test pytest -q
    ```
    Then comment out the guard in `app/orders.py` and watch two tests fail.

## Summary

- Use a **connection pool**, opened and closed in FastAPI's `lifespan`. Call `pool.wait()` so a bad configuration fails at start-up.
- With the blocking pool, write routes as plain `def`. FastAPI runs them in a threadpool.
- **Never** merge values into SQL with f-strings, `%` or `+`. Pass them as the second argument: `execute("... %s", (value,))`. That is the defence against SQL injection.
- `with pool.connection() as conn:` commits on a normal exit and rolls back on an exception. One request, one transaction.
- Put the rules in a function that knows nothing about HTTP, and turn errors into HTTP codes in the web layer.
- Retry only deadlocks and serialization failures, with a hard cap.
- Test against a real Postgres, and check that a test fails when the code is wrong.

!!! faq "Should I use an ORM like SQLAlchemy instead?"
    Many teams do, and it is a fine choice for a big app. In this course we write the SQL ourselves, because the point is to learn what the database actually does. Everything you learn here carries over to an ORM, and helps you read the SQL it generates.

!!! faq "How big should the pool be?"
    Small. The PostgreSQL manual says the server starts "a new process for each connection", and that `max_connections`, the limit on concurrent connections, "is typically 100" by default. Many app instances with big pools can use up that limit. Start with something like 5 to 10 per app instance, measure, and change it with the `POOL_MAX_SIZE` setting. We do not claim a magic number here.

## Sources

- [psycopg 3 docs: Connection pools](https://www.psycopg.org/psycopg3/docs/advanced/pool.html)
- [psycopg 3 docs: Passing parameters to SQL queries](https://www.psycopg.org/psycopg3/docs/basic/params.html)
- [psycopg 3 docs: Transactions management](https://www.psycopg.org/psycopg3/docs/basic/transactions.html)
- [FastAPI: Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)
- [FastAPI: Concurrency and async / await](https://fastapi.tiangolo.com/async/)
- [PostgreSQL 16 manual: Explicit Locking (deadlocks)](https://www.postgresql.org/docs/16/explicit-locking.html)
- [PostgreSQL 16 manual: Architectural Fundamentals (a process per connection)](https://www.postgresql.org/docs/16/tutorial-arch.html)
- [PostgreSQL 16 manual: Connections and Authentication (max_connections)](https://www.postgresql.org/docs/16/runtime-config-connection.html)
- The code and tests: the `project/` folder of the course repository.

That's it for now. Part 2 is done. In Part 3, we make the backend event-driven. In the next chapter, we will learn what an "event" is and why it is useful.
