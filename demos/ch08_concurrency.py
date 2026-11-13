"""Chapter 8 demos: two real database sessions, driven step by step.

Run:  COURSE_DSN=postgresql://course:course@localhost:5432/course_test python demos/ch08_concurrency.py
Needs the ChaiPoint tables from chapter 2 and `pip install "psycopg[binary]"`.
Every demo resets the stock first, so you can run it as often as you like.
"""
import os
import threading
import time

import psycopg

DSN = os.environ.get("COURSE_DSN", "postgresql://course:course@localhost:5432/course_test")


def reset(stock: int = 200) -> None:
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute("UPDATE products SET stock = %s WHERE id = 1", (stock,))


def stock_now() -> int:
    with psycopg.connect(DSN, autocommit=True) as c:
        return c.execute("SELECT stock FROM products WHERE id = 1").fetchone()[0]


def demo_lost_update() -> None:
    print("== 1. Read in Python, write back (BROKEN) ==")
    reset()
    a_read, b_done = threading.Event(), threading.Event()

    def order_a():
        with psycopg.connect(DSN) as c:
            stock = c.execute("SELECT stock FROM products WHERE id = 1").fetchone()[0]
            print(f"A read stock = {stock}")
            a_read.set()
            b_done.wait()                     # A is slow: B finishes first
            c.execute("UPDATE products SET stock = %s WHERE id = 1", (stock - 2,))
            print(f"A wrote {stock - 2}")

    def order_b():
        a_read.wait()
        with psycopg.connect(DSN) as c:
            stock = c.execute("SELECT stock FROM products WHERE id = 1").fetchone()[0]
            print(f"B read stock = {stock}")
            c.execute("UPDATE products SET stock = %s WHERE id = 1", (stock - 2,))
            print(f"B wrote {stock - 2}")
        b_done.set()

    ts = [threading.Thread(target=order_a), threading.Thread(target=order_b)]
    [t.start() for t in ts]; [t.join() for t in ts]
    print(f"final stock = {stock_now()}   (two orders of 2 should leave 196)\n")


def demo_atomic_update() -> None:
    print("== 2. Let the database do the arithmetic ==")
    reset()

    def order():
        with psycopg.connect(DSN) as c:
            c.execute("UPDATE products SET stock = stock - 2 WHERE id = 1")

    ts = [threading.Thread(target=order) for _ in range(2)]
    [t.start() for t in ts]; [t.join() for t in ts]
    print(f"final stock = {stock_now()}\n")


def demo_for_update() -> None:
    print("== 3. SELECT ... FOR UPDATE makes the second session wait ==")
    reset()
    a_locked, a_may_commit = threading.Event(), threading.Event()
    t0 = time.time()

    def order_a():
        with psycopg.connect(DSN) as c:
            stock = c.execute("SELECT stock FROM products WHERE id = 1 FOR UPDATE").fetchone()[0]
            print(f"[{time.time()-t0:4.1f}s] A locked the row, stock = {stock}")
            a_locked.set()
            a_may_commit.wait()
            c.execute("UPDATE products SET stock = %s WHERE id = 1", (stock - 2,))
        print(f"[{time.time()-t0:4.1f}s] A committed {stock - 2}")

    def order_b():
        a_locked.wait()
        with psycopg.connect(DSN) as c:
            print(f"[{time.time()-t0:4.1f}s] B asks for the same row ...")
            stock = c.execute("SELECT stock FROM products WHERE id = 1 FOR UPDATE").fetchone()[0]
            print(f"[{time.time()-t0:4.1f}s] B got the row, stock = {stock}")
            c.execute("UPDATE products SET stock = %s WHERE id = 1", (stock - 2,))
        print(f"[{time.time()-t0:4.1f}s] B committed {stock - 2}")

    ta, tb = threading.Thread(target=order_a), threading.Thread(target=order_b)
    ta.start(); tb.start()
    time.sleep(1.5)                            # B is blocked during this time
    a_may_commit.set()
    ta.join(); tb.join()
    print(f"final stock = {stock_now()}\n")


def demo_isolation(level: str) -> None:
    print(f"== 4. Isolation level: {level} ==")
    reset()
    with psycopg.connect(DSN) as b:
        b.execute(f"SET TRANSACTION ISOLATION LEVEL {level}")
        first = b.execute("SELECT stock FROM products WHERE id = 1").fetchone()[0]
        print(f"B first read   : {first}")
        with psycopg.connect(DSN, autocommit=True) as a:
            a.execute("UPDATE products SET stock = 150 WHERE id = 1")
        print("A committed stock = 150 in between")
        second = b.execute("SELECT stock FROM products WHERE id = 1").fetchone()[0]
        print(f"B second read  : {second}")
        try:
            b.execute("UPDATE products SET stock = stock - 2 WHERE id = 1")
            print("B update worked")
        except psycopg.errors.SerializationFailure as e:
            print(f"B update failed: {type(e).__name__}: {e.diag.message_primary}")
    print()


def demo_guard() -> None:
    print("== 6. A guard in the UPDATE: only 3 in stock, two orders of 2 arrive together ==")
    reset(3)
    results = {}
    start = threading.Barrier(2)

    def order(name):
        with psycopg.connect(DSN) as c:
            start.wait()
            cur = c.execute("UPDATE products SET stock = stock - 2 WHERE id = 1 AND stock >= 2")
            results[name] = cur.rowcount

    ts = [threading.Thread(target=order, args=(n,)) for n in ("A", "B")]
    [t.start() for t in ts]; [t.join() for t in ts]
    print(f"rows updated: A = {results['A']}, B = {results['B']}  (1 = order accepted, 0 = refused)")
    print(f"final stock = {stock_now()}\n")


def demo_deadlock() -> None:
    print("== 5. Deadlock: two sessions lock rows in opposite order ==")
    reset()
    a_has_1, b_has_2 = threading.Event(), threading.Event()
    results = {}

    def worker(name, first, second, mine, theirs):
        try:
            with psycopg.connect(DSN) as c:
                c.execute("UPDATE products SET stock = stock WHERE id = %s", (first,))
                mine.set(); theirs.wait()
                c.execute("UPDATE products SET stock = stock WHERE id = %s", (second,))
            results[name] = "committed"
        except psycopg.errors.DeadlockDetected as e:
            results[name] = f"aborted: {e.diag.message_primary}"

    ts = [threading.Thread(target=worker, args=("A", 1, 2, a_has_1, b_has_2)),
          threading.Thread(target=worker, args=("B", 2, 1, b_has_2, a_has_1))]
    [t.start() for t in ts]; [t.join() for t in ts]
    for k in sorted(results):
        print(f"{k}: {results[k]}")
    print()


if __name__ == "__main__":
    demo_lost_update()
    demo_atomic_update()
    demo_for_update()
    demo_isolation("READ COMMITTED")
    demo_isolation("REPEATABLE READ")
    demo_guard()
    demo_deadlock()
    reset()
