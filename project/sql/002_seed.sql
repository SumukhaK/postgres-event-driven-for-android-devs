-- Sample data. Safe to run on an empty schema.
INSERT INTO customers (name, phone, city) VALUES
    ('Asha',  '9000000001', 'Bengaluru'),
    ('Ravi',  '9000000002', 'Bengaluru'),
    ('Meera', '9000000003', 'Mysuru'),
    ('Kiran', '9000000004', 'Bengaluru'),
    ('Divya', '9000000005', 'Chennai');

INSERT INTO products (name, price, stock) VALUES
    ('Masala chai',    20.00, 200),
    ('Filter coffee',  25.00, 150),
    ('Samosa',         15.00, 120),
    ('Bun maska',      30.00,  80),
    ('Veg sandwich',   60.00,  50),
    ('Lemon tea',      18.00,   0);
