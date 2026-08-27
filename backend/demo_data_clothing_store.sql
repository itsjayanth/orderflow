-- Demo data for a clothing store (non-food vertical)
-- Exercises the same schema as demo_data_varkeys.sql with a
-- Retail / Clothing merchant instead of a restaurant, as a concrete check
-- that nothing food-specific is baked into the data model.
-- Run with: psql -U orderflow -h localhost -d orderflow -f demo_data_clothing_store.sql

-- Clean up existing demo data if any
DELETE FROM order_items WHERE order_id IN (SELECT order_id FROM orders WHERE merchant_id = '99999999-9999-9999-9999-999999999999');
DELETE FROM order_status_events WHERE order_id IN (SELECT order_id FROM orders WHERE merchant_id = '99999999-9999-9999-9999-999999999999');
DELETE FROM payment_events WHERE order_id IN (SELECT order_id FROM orders WHERE merchant_id = '99999999-9999-9999-9999-999999999999');
DELETE FROM orders WHERE merchant_id = '99999999-9999-9999-9999-999999999999';
DELETE FROM addresses WHERE merchant_id = '99999999-9999-9999-9999-999999999999';
DELETE FROM customers WHERE merchant_id = '99999999-9999-9999-9999-999999999999';
DELETE FROM items WHERE merchant_id = '99999999-9999-9999-9999-999999999999';
DELETE FROM notification_templates WHERE merchant_id = '99999999-9999-9999-9999-999999999999';
DELETE FROM whatsapp_business_accounts WHERE merchant_id = '99999999-9999-9999-9999-999999999999';
DELETE FROM merchant_payment_credentials WHERE merchant_id = '99999999-9999-9999-9999-999999999999';
DELETE FROM merchant_item_counters WHERE merchant_id = '99999999-9999-9999-9999-999999999999';
DELETE FROM merchant_customer_counters WHERE merchant_id = '99999999-9999-9999-9999-999999999999';
DELETE FROM merchant_order_counters WHERE merchant_id = '99999999-9999-9999-9999-999999999999';
DELETE FROM staff_users WHERE merchant_id = '99999999-9999-9999-9999-999999999999';
DELETE FROM merchants WHERE merchant_id = '99999999-9999-9999-9999-999999999999';

-- Create Urban Threads merchant (Retail / Clothing vertical)
INSERT INTO merchants (merchant_id, business_name, owner_contact, onboarding_status, status, created_at, updated_at, business_address_line1, business_address_line2, business_city, business_pincode, business_category, license_no)
VALUES (
    '99999999-9999-9999-9999-999999999999',
    'Urban Threads Clothing',
    '+919876509999',
    'live',
    'active',
    NOW() - INTERVAL '60 days',
    NOW(),
    '45 Commercial Street',
    'Shivaji Nagar',
    'Bangalore',
    '560001',
    'Retail / Clothing',
    'GSTIN29ABCDE1234F1Z5'
);

-- Create staff user (password: password123)
INSERT INTO staff_users (staff_user_id, merchant_id, name, email_or_phone, password_hash, role, created_at)
VALUES (
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    '99999999-9999-9999-9999-999999999999',
    'Urban Threads Admin',
    'admin@urbanthreads.example',
    '$argon2id$v=19$m=65536,t=3,p=4$x7rHyRnCzvdNjeeNOflaIA$ki3lQ156rIn86NoLB0BC0CtSv3TnkfZx8ellj99cFu4',
    'owner',
    NOW() - INTERVAL '60 days'
);

-- Create items (Shirts, Trousers, Shoes, Accessories -- no food semantics)
INSERT INTO items (item_id, merchant_id, item_number, category, name, price, is_available, created_at, updated_at)
VALUES
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb01', '99999999-9999-9999-9999-999999999999', 1, 'Shirts', 'Classic White Shirt', 1299.00, true, NOW() - INTERVAL '55 days', NOW()),
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb02', '99999999-9999-9999-9999-999999999999', 2, 'Shirts', 'Blue Denim Shirt', 1499.00, true, NOW() - INTERVAL '55 days', NOW()),
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb03', '99999999-9999-9999-9999-999999999999', 3, 'Shirts', 'Checked Flannel Shirt', 1199.00, true, NOW() - INTERVAL '55 days', NOW()),
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb04', '99999999-9999-9999-9999-999999999999', 4, 'Shirts', 'Black Polo Shirt', 899.00, true, NOW() - INTERVAL '55 days', NOW()),

    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb05', '99999999-9999-9999-9999-999999999999', 5, 'Trousers', 'Slim Fit Chinos', 1799.00, true, NOW() - INTERVAL '55 days', NOW()),
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb06', '99999999-9999-9999-9999-999999999999', 6, 'Trousers', 'Formal Black Trousers', 1999.00, true, NOW() - INTERVAL '55 days', NOW()),
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb07', '99999999-9999-9999-9999-999999999999', 7, 'Trousers', 'Cargo Trousers', 1699.00, true, NOW() - INTERVAL '55 days', NOW()),
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb08', '99999999-9999-9999-9999-999999999999', 8, 'Trousers', 'Grey Track Pants', 999.00, true, NOW() - INTERVAL '55 days', NOW()),

    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb09', '99999999-9999-9999-9999-999999999999', 9, 'Shoes', 'Running Sneakers', 2999.00, true, NOW() - INTERVAL '55 days', NOW()),
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb10', '99999999-9999-9999-9999-999999999999', 10, 'Shoes', 'Leather Formal Shoes', 3499.00, true, NOW() - INTERVAL '55 days', NOW()),
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb11', '99999999-9999-9999-9999-999999999999', 11, 'Shoes', 'Canvas Casuals', 1499.00, true, NOW() - INTERVAL '55 days', NOW()),
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb12', '99999999-9999-9999-9999-999999999999', 12, 'Shoes', 'Sports Sandals', 899.00, true, NOW() - INTERVAL '55 days', NOW()),

    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb13', '99999999-9999-9999-9999-999999999999', 13, 'Accessories', 'Leather Belt', 699.00, true, NOW() - INTERVAL '55 days', NOW()),
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb14', '99999999-9999-9999-9999-999999999999', 14, 'Accessories', 'Analog Wrist Watch', 2499.00, true, NOW() - INTERVAL '55 days', NOW()),
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb15', '99999999-9999-9999-9999-999999999999', 15, 'Accessories', 'Canvas Backpack', 1899.00, true, NOW() - INTERVAL '55 days', NOW()),
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb16', '99999999-9999-9999-9999-999999999999', 16, 'Accessories', 'Aviator Sunglasses', 1299.00, true, NOW() - INTERVAL '55 days', NOW());

INSERT INTO merchant_item_counters (merchant_id, next_item_number)
VALUES ('99999999-9999-9999-9999-999999999999', 17);

-- Create customers
INSERT INTO customers (customer_id, merchant_id, customer_number, whatsapp_number, display_name, first_seen_at, last_order_at, is_active)
VALUES
    ('cccccccc-cccc-cccc-cccc-cccccccccc01', '99999999-9999-9999-9999-999999999999', 1, '+919812345601', 'Ananya Iyer', NOW() - INTERVAL '40 days', NOW() - INTERVAL '2 days', true),
    ('cccccccc-cccc-cccc-cccc-cccccccccc02', '99999999-9999-9999-9999-999999999999', 2, '+919812345602', 'Rohit Malhotra', NOW() - INTERVAL '35 days', NOW() - INTERVAL '40 minutes', true),
    ('cccccccc-cccc-cccc-cccc-cccccccccc03', '99999999-9999-9999-9999-999999999999', 3, '+919812345603', 'Fatima Sheikh', NOW() - INTERVAL '20 days', NOW() - INTERVAL '10 minutes', true),
    ('cccccccc-cccc-cccc-cccc-cccccccccc04', '99999999-9999-9999-9999-999999999999', 4, '+919812345604', 'Karan Mehta', NOW() - INTERVAL '15 days', NOW() - INTERVAL '80 minutes', true),
    ('cccccccc-cccc-cccc-cccc-cccccccccc05', '99999999-9999-9999-9999-999999999999', 5, '+919812345605', 'Divya Nair', NOW() - INTERVAL '10 days', NOW() - INTERVAL '6 days', true);

INSERT INTO merchant_customer_counters (merchant_id, next_customer_number)
VALUES ('99999999-9999-9999-9999-999999999999', 6);

-- Create addresses
INSERT INTO addresses (address_id, merchant_id, customer_id, label, line1, line2, city, pincode, is_default, created_at)
VALUES
    ('dddddddd-dddd-dddd-dddd-dddddddddd01', '99999999-9999-9999-9999-999999999999', 'cccccccc-cccc-cccc-cccc-cccccccccc01', 'Home', 'Flat 12B, Lake View Apartments', 'Indiranagar 100ft Road', 'Bangalore', '560038', true, NOW() - INTERVAL '40 days'),
    ('dddddddd-dddd-dddd-dddd-dddddddddd02', '99999999-9999-9999-9999-999999999999', 'cccccccc-cccc-cccc-cccc-cccccccccc02', 'Home', '18 ITPL Main Road', 'Whitefield', 'Bangalore', '560066', true, NOW() - INTERVAL '35 days'),
    ('dddddddd-dddd-dddd-dddd-dddddddddd03', '99999999-9999-9999-9999-999999999999', 'cccccccc-cccc-cccc-cccc-cccccccccc03', 'Home', 'House No 7, 9th Main', 'Jayanagar 3rd Block', 'Bangalore', '560011', true, NOW() - INTERVAL '20 days'),
    ('dddddddd-dddd-dddd-dddd-dddddddddd04', '99999999-9999-9999-9999-999999999999', 'cccccccc-cccc-cccc-cccc-cccccccccc04', 'Home', 'Sapphire Residency C-604', 'Malleswaram', 'Bangalore', '560003', true, NOW() - INTERVAL '15 days'),
    ('dddddddd-dddd-dddd-dddd-dddddddddd05', '99999999-9999-9999-9999-999999999999', 'cccccccc-cccc-cccc-cccc-cccccccccc05', 'Home', 'Prestige Tech Park Road', 'Electronic City', 'Bangalore', '560100', true, NOW() - INTERVAL '10 days');

-- Create orders (mix of fulfillment states, including at least one "processing")
-- Order 1: Completed order, paid online
INSERT INTO orders (order_id, merchant_id, customer_id, order_number, order_type, delivery_address_id, payment_method, payment_status, fulfillment_status, subtotal, total, currency, placed_at, paid_at, ready_at, completed_at, created_at, updated_at)
VALUES (
    'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee01',
    '99999999-9999-9999-9999-999999999999',
    'cccccccc-cccc-cccc-cccc-cccccccccc01',
    1,
    'delivery',
    'dddddddd-dddd-dddd-dddd-dddddddddd01',
    'online',
    'paid',
    'completed',
    3098.00,
    3098.00,
    'INR',
    NOW() - INTERVAL '4 days 2 hours',
    NOW() - INTERVAL '4 days 2 hours',
    NOW() - INTERVAL '4 days 1 hour 30 minutes',
    NOW() - INTERVAL '4 days 1 hour',
    NOW() - INTERVAL '4 days 2 hours',
    NOW() - INTERVAL '4 days 1 hour'
);

INSERT INTO order_items (order_item_id, order_id, item_id, name_snapshot, price_snapshot, quantity, line_total)
VALUES
    ('ffffffff-ffff-ffff-ffff-ffffffffff01', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee01', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb01', 'Classic White Shirt', 1299.00, 1, 1299.00),
    ('ffffffff-ffff-ffff-ffff-ffffffffff02', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee01', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb05', 'Slim Fit Chinos', 1799.00, 1, 1799.00);

-- Order 2: Processing order (paid via COD, not yet collected)
INSERT INTO orders (order_id, merchant_id, customer_id, order_number, order_type, delivery_address_id, payment_method, payment_status, fulfillment_status, subtotal, total, currency, placed_at, paid_at, created_at, updated_at)
VALUES (
    'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee02',
    '99999999-9999-9999-9999-999999999999',
    'cccccccc-cccc-cccc-cccc-cccccccccc02',
    2,
    'delivery',
    'dddddddd-dddd-dddd-dddd-dddddddddd02',
    'cod',
    'cod_pending',
    'processing',
    2999.00,
    2999.00,
    'INR',
    NOW() - INTERVAL '40 minutes',
    NULL,
    NOW() - INTERVAL '40 minutes',
    NOW() - INTERVAL '15 minutes'
);

INSERT INTO order_items (order_item_id, order_id, item_id, name_snapshot, price_snapshot, quantity, line_total)
VALUES
    ('ffffffff-ffff-ffff-ffff-ffffffffff03', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee02', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb09', 'Running Sneakers', 2999.00, 1, 2999.00);

-- Order 3: New order just placed
INSERT INTO orders (order_id, merchant_id, customer_id, order_number, order_type, delivery_address_id, payment_method, payment_status, fulfillment_status, subtotal, total, currency, placed_at, paid_at, created_at, updated_at)
VALUES (
    'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee03',
    '99999999-9999-9999-9999-999999999999',
    'cccccccc-cccc-cccc-cccc-cccccccccc03',
    3,
    'pickup',
    NULL,
    'online',
    'paid',
    'new',
    1199.00,
    1199.00,
    'INR',
    NOW() - INTERVAL '10 minutes',
    NOW() - INTERVAL '10 minutes',
    NOW() - INTERVAL '10 minutes',
    NOW() - INTERVAL '10 minutes'
);

INSERT INTO order_items (order_item_id, order_id, item_id, name_snapshot, price_snapshot, quantity, line_total)
VALUES
    ('ffffffff-ffff-ffff-ffff-ffffffffff04', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee03', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb03', 'Checked Flannel Shirt', 1199.00, 1, 1199.00);

-- Order 4: Ready for pickup/delivery
INSERT INTO orders (order_id, merchant_id, customer_id, order_number, order_type, delivery_address_id, payment_method, payment_status, fulfillment_status, subtotal, total, currency, placed_at, paid_at, ready_at, created_at, updated_at)
VALUES (
    'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee04',
    '99999999-9999-9999-9999-999999999999',
    'cccccccc-cccc-cccc-cccc-cccccccccc04',
    4,
    'delivery',
    'dddddddd-dddd-dddd-dddd-dddddddddd04',
    'cod',
    'cod_pending',
    'ready',
    1998.00,
    1998.00,
    'INR',
    NOW() - INTERVAL '1 hour 20 minutes',
    NULL,
    NOW() - INTERVAL '10 minutes',
    NOW() - INTERVAL '1 hour 20 minutes',
    NOW() - INTERVAL '10 minutes'
);

INSERT INTO order_items (order_item_id, order_id, item_id, name_snapshot, price_snapshot, quantity, line_total)
VALUES
    ('ffffffff-ffff-ffff-ffff-ffffffffff05', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee04', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb13', 'Leather Belt', 699.00, 1, 699.00),
    ('ffffffff-ffff-ffff-ffff-ffffffffff06', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee04', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb16', 'Aviator Sunglasses', 1299.00, 1, 1299.00);

-- Order 5: Completed order from a few days ago
INSERT INTO orders (order_id, merchant_id, customer_id, order_number, order_type, delivery_address_id, payment_method, payment_status, fulfillment_status, subtotal, total, currency, placed_at, paid_at, ready_at, completed_at, created_at, updated_at)
VALUES (
    'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee05',
    '99999999-9999-9999-9999-999999999999',
    'cccccccc-cccc-cccc-cccc-cccccccccc05',
    5,
    'delivery',
    'dddddddd-dddd-dddd-dddd-dddddddddd05',
    'online',
    'paid',
    'completed',
    5398.00,
    5398.00,
    'INR',
    NOW() - INTERVAL '6 days 5 hours',
    NOW() - INTERVAL '6 days 5 hours',
    NOW() - INTERVAL '6 days 4 hours 30 minutes',
    NOW() - INTERVAL '6 days 4 hours',
    NOW() - INTERVAL '6 days 5 hours',
    NOW() - INTERVAL '6 days 4 hours'
);

INSERT INTO order_items (order_item_id, order_id, item_id, name_snapshot, price_snapshot, quantity, line_total)
VALUES
    ('ffffffff-ffff-ffff-ffff-ffffffffff07', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee05', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb10', 'Leather Formal Shoes', 3499.00, 1, 3499.00),
    ('ffffffff-ffff-ffff-ffff-ffffffffff08', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee05', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb15', 'Canvas Backpack', 1899.00, 1, 1899.00);

-- Order 6: Cancelled order (customer abandoned payment)
INSERT INTO orders (order_id, merchant_id, customer_id, order_number, order_type, delivery_address_id, payment_method, payment_status, fulfillment_status, subtotal, total, currency, placed_at, paid_at, created_at, updated_at)
VALUES (
    'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee06',
    '99999999-9999-9999-9999-999999999999',
    'cccccccc-cccc-cccc-cccc-cccccccccc01',
    6,
    'pickup',
    NULL,
    'online',
    'cancelled',
    'cancelled',
    999.00,
    999.00,
    'INR',
    NOW() - INTERVAL '2 days 3 hours',
    NULL,
    NOW() - INTERVAL '2 days 3 hours',
    NOW() - INTERVAL '2 days 2 hours'
);

INSERT INTO order_items (order_item_id, order_id, item_id, name_snapshot, price_snapshot, quantity, line_total)
VALUES
    ('ffffffff-ffff-ffff-ffff-ffffffffff09', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee06', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb08', 'Grey Track Pants', 999.00, 1, 999.00);

INSERT INTO merchant_order_counters (merchant_id, next_order_number)
VALUES ('99999999-9999-9999-9999-999999999999', 7);

-- Add notification templates
INSERT INTO notification_templates (template_id, merchant_id, notification_kind, template_name, language_code, body, is_active, updated_at)
VALUES
    ('00000000-0000-0000-0000-000000000001', '99999999-9999-9999-9999-999999999999', 'order_confirmed', 'order_confirmed_template', 'en', 'Hi {{customer_name}}! Your order #{{order_number}} at {{business_name}} has been confirmed. Total: Rs {{total}}.', true, NOW()),
    ('00000000-0000-0000-0000-000000000002', '99999999-9999-9999-9999-999999999999', 'order_ready', 'order_ready_template', 'en', 'Your order #{{order_number}} at {{business_name}} is ready for pickup/delivery!', true, NOW()),
    ('00000000-0000-0000-0000-000000000003', '99999999-9999-9999-9999-999999999999', 'order_completed', 'order_completed_template', 'en', 'Thank you for shopping with {{business_name}}! Your order #{{order_number}} is complete.', true, NOW());

-- Summary
SELECT
    'Demo data for Urban Threads Clothing created successfully!' as status,
    (SELECT COUNT(*) FROM items WHERE merchant_id = '99999999-9999-9999-9999-999999999999') as items,
    (SELECT COUNT(*) FROM customers WHERE merchant_id = '99999999-9999-9999-9999-999999999999') as customers,
    (SELECT COUNT(*) FROM orders WHERE merchant_id = '99999999-9999-9999-9999-999999999999') as orders,
    (SELECT COUNT(*) FROM addresses WHERE merchant_id = '99999999-9999-9999-9999-999999999999') as addresses;
