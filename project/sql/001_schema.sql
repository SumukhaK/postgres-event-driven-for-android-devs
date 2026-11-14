-- ChaiPoint schema (the tables from chapter 2).
CREATE TABLE products (
    id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name      text          NOT NULL,
    price     numeric(8,2)  NOT NULL CHECK (price > 0),
    stock     integer       NOT NULL DEFAULT 0 CHECK (stock >= 0),
    is_active boolean       NOT NULL DEFAULT true
);

CREATE TABLE customers (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name       text        NOT NULL,
    phone      text        NOT NULL UNIQUE,
    city       text        NOT NULL DEFAULT 'Bengaluru',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE orders (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id bigint        NOT NULL REFERENCES customers (id),
    status      text          NOT NULL DEFAULT 'placed'
                CHECK (status IN ('placed', 'paid', 'cancelled', 'delivered')),
    total       numeric(10,2) NOT NULL DEFAULT 0,
    placed_at   timestamptz   NOT NULL DEFAULT now()
);

CREATE TABLE order_items (
    order_id   bigint        NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
    product_id bigint        NOT NULL REFERENCES products (id),
    quantity   integer       NOT NULL CHECK (quantity > 0),
    unit_price numeric(8,2)  NOT NULL,
    PRIMARY KEY (order_id, product_id)
);

CREATE INDEX order_items_product_idx ON order_items (product_id);
CREATE INDEX orders_customer_time_idx ON orders (customer_id, placed_at DESC);
