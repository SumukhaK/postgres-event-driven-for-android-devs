import threading
from decimal import Decimal

import psycopg
import pytest
from fastapi.testclient import TestClient

from app import db as appdb
from app.main import app
from app.orders import Item, OutOfStock, place_order


@pytest.fixture
def client():
    with TestClient(app) as c:      # `with` runs the lifespan: pool opens and closes
        yield c


def test_products_use_keyset_pagination(client):
    first = client.get("/products", params={"limit": 3}).json()
    assert [p["id"] for p in first["items"]] == [1, 2, 3]
    assert first["next_after"] == 3
    second = client.get("/products", params={"after": 3, "limit": 3}).json()
    assert [p["id"] for p in second["items"]] == [4, 5, 6] and second["next_after"] == 6


def test_unknown_product_is_404(client):
    assert client.get("/products/999").status_code == 404


def test_order_takes_stock_and_saves_lines(client, db):
    r = client.post("/orders", json={"customer_id": 1, "items": [
        {"product_id": 1, "quantity": 2}, {"product_id": 3, "quantity": 1}]})
    assert r.status_code == 201
    assert Decimal(str(r.json()["total"])) == Decimal("55.00")        # 2 x 20 + 1 x 15
    assert db.execute("SELECT stock FROM products WHERE id = 1").fetchone()["stock"] == 198
    lines = db.execute("SELECT product_id, quantity FROM order_items ORDER BY product_id").fetchall()
    assert [(l["product_id"], l["quantity"]) for l in lines] == [(1, 2), (3, 1)]
    assert db.execute("SELECT total FROM orders").fetchone()["total"] == Decimal("55.00")


def test_out_of_stock_is_409_and_changes_nothing(client, db):
    # product 1 is fine, product 6 (Lemon tea) has no stock: the whole order must be undone
    r = client.post("/orders", json={"customer_id": 1, "items": [
        {"product_id": 1, "quantity": 2}, {"product_id": 6, "quantity": 1}]})
    assert r.status_code == 409
    assert db.execute("SELECT stock FROM products WHERE id = 1").fetchone()["stock"] == 200
    assert db.execute("SELECT count(*) AS n FROM orders").fetchone()["n"] == 0


def test_unknown_customer_is_404(client):
    r = client.post("/orders", json={"customer_id": 999, "items": [{"product_id": 1, "quantity": 1}]})
    assert r.status_code == 404


@pytest.mark.parametrize("body", [
    {"customer_id": 1, "items": []},
    {"customer_id": 1, "items": [{"product_id": 1, "quantity": 0}]},
    {"customer_id": 1},
])
def test_bad_input_is_422(client, body):
    assert client.post("/orders", json=body).status_code == 422


def test_sql_injection_text_is_just_text(client, db):
    # the id comes from the URL; a string full of SQL is rejected as "not an integer", never executed
    assert client.get("/products/1;DROP TABLE products").status_code == 422
    assert db.execute("SELECT count(*) AS n FROM products").fetchone()["n"] == 6


def test_concurrent_orders_never_oversell(db):
    """12 requests at once for the last 5 chai: exactly 5 succeed, stock ends at 0 and never below."""
    db.execute("UPDATE products SET stock = 5 WHERE id = 1")
    pool = appdb.make_pool(open_now=True)
    results, start = [], threading.Barrier(12)

    def one_order():
        start.wait()
        try:
            appdb.run_with_retry(pool, lambda c: place_order(c, 1, [Item(1, 1)]))
            results.append("ok")
        except OutOfStock:
            results.append("sold out")

    threads = [threading.Thread(target=one_order) for _ in range(12)]
    [t.start() for t in threads]; [t.join() for t in threads]
    pool.close()
    assert results.count("ok") == 5 and results.count("sold out") == 7
    assert db.execute("SELECT stock FROM products WHERE id = 1").fetchone()["stock"] == 0
    assert db.execute("SELECT count(*) AS n FROM orders").fetchone()["n"] == 5   # the 7 refusals left no order behind


class FakePool:
    """Stands in for the pool, to test retry logic without a real deadlock."""
    def connection(self):
        class Ctx:
            def __enter__(s): return object()
            def __exit__(s, *a): return False
        return Ctx()


def test_retry_gives_up_after_the_cap():
    calls = []
    def always_deadlocks(conn):
        calls.append(1)
        raise psycopg.errors.DeadlockDetected()
    with pytest.raises(psycopg.errors.DeadlockDetected):
        appdb.run_with_retry(FakePool(), always_deadlocks, attempts=3, pause=0)
    assert len(calls) == 3                      # a hard cap, not an endless loop


def test_retry_succeeds_when_a_later_attempt_works():
    calls = []
    def flaky(conn):
        calls.append(1)
        if len(calls) < 3:
            raise psycopg.errors.SerializationFailure()
        return "done"
    assert appdb.run_with_retry(FakePool(), flaky, attempts=3, pause=0) == "done"


def test_retry_does_not_hide_real_errors():
    def broken(conn):
        raise ValueError("a bug")
    with pytest.raises(ValueError):
        appdb.run_with_retry(FakePool(), broken, attempts=3, pause=0)
