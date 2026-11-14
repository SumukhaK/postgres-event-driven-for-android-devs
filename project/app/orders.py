"""Business logic for placing an order. No web code here, only SQL and rules."""
from dataclasses import dataclass
from decimal import Decimal

import psycopg


class OutOfStock(Exception):
    def __init__(self, product_id: int):
        super().__init__(f"not enough stock for product {product_id}")
        self.product_id = product_id


class CustomerNotFound(Exception):
    pass


@dataclass
class Item:
    product_id: int
    quantity: int


def place_order(conn: psycopg.Connection, customer_id: int, items: list[Item]) -> dict:
    """Create an order and take stock, all inside the caller's transaction.

    Products are handled in ascending id order. Every request locks rows in the same
    order, so two orders can never deadlock each other (chapter 8)."""
    try:
        order_id = conn.execute(
            "INSERT INTO orders (customer_id) VALUES (%s) RETURNING id", (customer_id,)
        ).fetchone()["id"]
    except psycopg.errors.ForeignKeyViolation:
        raise CustomerNotFound() from None

    total = Decimal("0")
    for item in sorted(items, key=lambda i: i.product_id):
        # One statement: check, subtract, and read the price. The guard stops negative stock.
        row = conn.execute(
            "UPDATE products SET stock = stock - %s "
            "WHERE id = %s AND is_active AND stock >= %s RETURNING price",
            (item.quantity, item.product_id, item.quantity),
        ).fetchone()
        if row is None:
            raise OutOfStock(item.product_id)   # the caller's block rolls everything back
        conn.execute(
            "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
            (order_id, item.product_id, item.quantity, row["price"]),
        )
        total += row["price"] * item.quantity

    conn.execute("UPDATE orders SET total = %s WHERE id = %s", (total, order_id))
    return {"order_id": order_id, "total": total}
