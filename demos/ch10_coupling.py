"""Chapter 10 demo: what happens when the request does everything itself.

The email service here is SIMULATED (a sleep, and a switch to make it fail). Everything else is real.
Run from the project folder:  cd project && python ../demos/ch10_coupling.py
"""
import sys, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "project"))

import psycopg
from app import db
from app.orders import Item, place_order

EMAIL_DELAY = 1.0          # pretend the email provider takes one second


class EmailDown(Exception):
    pass


def send_email(order_id: int, fail: bool) -> None:
    time.sleep(EMAIL_DELAY)
    if fail:
        raise EmailDown("email provider is down")


def reset(pool):
    with pool.connection() as c:
        c.execute("TRUNCATE order_items, orders RESTART IDENTITY CASCADE")
        c.execute("UPDATE products SET stock = 200 WHERE id = 1")


def orders_and_stock(pool):
    with pool.connection() as c:
        n = c.execute("SELECT count(*) AS n FROM orders").fetchone()["n"]
        s = c.execute("SELECT stock FROM products WHERE id = 1").fetchone()["stock"]
    return n, s


def email_inside_the_transaction(pool, fail):
    with pool.connection() as conn:
        res = place_order(conn, 1, [Item(1, 2)])
        send_email(res["order_id"], fail)          # still inside the transaction
    return res


def email_after_the_commit(pool, fail):
    with pool.connection() as conn:
        res = place_order(conn, 1, [Item(1, 2)])
    send_email(res["order_id"], fail)              # transaction is already committed
    return res


if __name__ == "__main__":
    pool = db.make_pool(open_now=True)
    for name, fn in (("A. email INSIDE the transaction", email_inside_the_transaction),
                     ("B. email AFTER the commit", email_after_the_commit)):
        for fail in (False, True):
            reset(pool)
            t0 = time.time()
            try:
                fn(pool, fail)
                outcome = "request OK"
            except EmailDown as e:
                outcome = f"request FAILED ({e})"
            took = time.time() - t0
            n, stock = orders_and_stock(pool)
            print(f"{name:34} email {'down' if fail else 'up  '} -> {outcome:42} "
                  f"took {took:.1f}s | orders saved: {n} | stock: {stock}")
    reset(pool); pool.close()
