"""Tests run against a REAL Postgres. They wipe the schema, so the database name must end in _test."""
import os
import pathlib

import psycopg
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://course:course@localhost:5432/course_test")
DSN = os.environ["DATABASE_URL"]
SQL = pathlib.Path(__file__).parent.parent / "sql"

assert DSN.split("?")[0].rstrip("/").endswith("_test"), "refusing to wipe a database whose name does not end in _test"


def apply_sql(conn, *names):
    for name in names:
        conn.execute((SQL / name).read_text())


@pytest.fixture(scope="session", autouse=True)
def schema():
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        apply_sql(conn, *sorted(p.name for p in SQL.glob("0*.sql") if p.name != "002_seed.sql"))


@pytest.fixture(autouse=True)
def fresh_data():
    """Every test starts from the same sample data."""
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("TRUNCATE order_items, orders, products, customers RESTART IDENTITY CASCADE")
        apply_sql(conn, "002_seed.sql")


@pytest.fixture
def db():
    with psycopg.connect(DSN, autocommit=True, row_factory=psycopg.rows.dict_row) as conn:
        yield conn
