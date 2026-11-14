"""Connection pool and a retry helper."""
import time
from typing import Callable, TypeVar

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app import settings

T = TypeVar("T")

# Errors that mean "nothing is wrong with your code, just run the transaction again".
RETRYABLE = (psycopg.errors.DeadlockDetected, psycopg.errors.SerializationFailure)


def make_pool(open_now: bool = False) -> ConnectionPool:
    return ConnectionPool(
        settings.DATABASE_URL,
        min_size=settings.POOL_MIN_SIZE,
        max_size=settings.POOL_MAX_SIZE,
        kwargs={"row_factory": dict_row},
        open=open_now,
    )


def run_with_retry(pool: ConnectionPool, work: Callable[[psycopg.Connection], T],
                   attempts: int = settings.MAX_ATTEMPTS, pause: float = 0.05) -> T:
    """Run `work(conn)` in one transaction. Retry the WHOLE transaction on a deadlock or
    serialization failure, at most `attempts` times, then let the error out."""
    for attempt in range(1, attempts + 1):
        try:
            with pool.connection() as conn:     # commits on success, rolls back on exception
                return work(conn)
        except RETRYABLE:
            if attempt == attempts:
                raise
            time.sleep(pause * attempt)
    raise AssertionError("unreachable")
