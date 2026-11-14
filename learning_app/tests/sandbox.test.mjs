import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import "fake-indexeddb/auto";
import { test } from "node:test";
import { PGlite } from "@electric-sql/pglite";

const seedSql = await readFile(new URL("../static/seed.sql", import.meta.url), "utf8");

test("ChaiPoint seed supports the course's stock and join queries", async () => {
  const dataDir = `idb://postgres-lab-test-${crypto.randomUUID()}`;
  let db = await PGlite.create(dataDir);
  try {
    await db.exec(seedSql);
    const products = await db.query("SELECT name, stock FROM products ORDER BY id LIMIT 2");
    assert.deepEqual(products.rows, [
      { name: "Masala Chai", stock: 200 },
      { name: "Filter Coffee", stock: 80 },
    ]);

    const updated = await db.query(
      "UPDATE products SET stock = stock - 2 WHERE id = 1 AND stock >= 2 RETURNING stock",
    );
    assert.equal(updated.rows[0].stock, 198);

    const joined = await db.query(
      "SELECT customers.name, count(orders.id)::int AS orders FROM customers LEFT JOIN orders ON orders.customer_id = customers.id GROUP BY customers.name ORDER BY customers.name",
    );
    assert.equal(joined.rows.length, 3);
    await assert.rejects(db.query("SELECT missing_column FROM products"));
    await db.close();
    db = await PGlite.create(dataDir);
    const reopened = await db.query("SELECT stock FROM products WHERE id = 1");
    assert.equal(reopened.rows[0].stock, 198);
  } finally {
    if (!db.closed) await db.close();
  }
});
