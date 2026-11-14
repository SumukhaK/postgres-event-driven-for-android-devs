"""The web layer: routes, validation, and turning errors into HTTP answers."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app import db
from app.orders import CustomerNotFound, Item, OutOfStock, place_order


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = db.make_pool()
    app.state.pool.open()
    app.state.pool.wait()          # fail at start-up, not at the first request, if the DB is unreachable
    yield
    app.state.pool.close()


app = FastAPI(title="ChaiPoint API", lifespan=lifespan)


class ItemIn(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class OrderIn(BaseModel):
    customer_id: int
    items: list[ItemIn] = Field(min_length=1)


@app.get("/products")
def list_products(request: Request, after: int = 0, limit: int = Query(3, ge=1, le=100)):
    """Keyset pagination: pass the last id you saw as `after`."""
    with request.app.state.pool.connection() as conn:
        rows = conn.execute(
            "SELECT id, name, price, stock FROM products WHERE id > %s AND is_active ORDER BY id LIMIT %s",
            (after, limit),
        ).fetchall()
    return {"items": rows, "next_after": rows[-1]["id"] if len(rows) == limit else None}


@app.get("/products/{product_id}")
def get_product(product_id: int, request: Request):
    with request.app.state.pool.connection() as conn:
        row = conn.execute(
            "SELECT id, name, price, stock FROM products WHERE id = %s", (product_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(404, "product not found")
    return row


@app.post("/orders", status_code=201)
def create_order(order: OrderIn, request: Request):
    items = [Item(i.product_id, i.quantity) for i in order.items]
    try:
        return db.run_with_retry(request.app.state.pool, lambda conn: place_order(conn, order.customer_id, items))
    except OutOfStock as e:
        raise HTTPException(409, str(e))
    except CustomerNotFound:
        raise HTTPException(404, "customer not found")
