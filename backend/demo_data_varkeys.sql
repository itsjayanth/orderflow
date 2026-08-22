-- Demo data for Varkeys restaurant
-- Run with: psql -U orderflow -h localhost -d orderflow -f demo_data_varkeys.sql

-- Clean up existing demo data if any
DELETE FROM order_items WHERE order_id IN (SELECT order_id FROM orders WHERE merchant_id = '11111111-1111-1111-1111-111111111111');
DELETE FROM order_status_events WHERE order_id IN (SELECT order_id FROM orders WHERE merchant_id = '11111111-1111-1111-1111-111111111111');
DELETE FROM payment_events WHERE order_id IN (SELECT order_id FROM orders WHERE merchant_id = '11111111-1111-1111-1111-111111111111');
DELETE FROM orders WHERE merchant_id = '11111111-1111-1111-1111-111111111111';
DELETE FROM addresses WHERE merchant_id = '11111111-1111-1111-1111-111111111111';
DELETE FROM customers WHERE merchant_id = '11111111-1111-1111-1111-111111111111';
DELETE FROM menu_items WHERE merchant_id = '11111111-1111-1111-1111-111111111111';
DELETE FROM notification_templates WHERE merchant_id = '11111111-1111-1111-1111-111111111111';
DELETE FROM whatsapp_business_accounts WHERE merchant_id = '11111111-1111-1111-1111-111111111111';
DELETE FROM merchant_payment_credentials WHERE merchant_id = '11111111-1111-1111-1111-111111111111';
DELETE FROM staff_users WHERE merchant_id = '11111111-1111-1111-1111-111111111111';
DELETE FROM merchants WHERE merchant_id = '11111111-1111-1111-1111-111111111111';

-- Create Varkeys merchant
INSERT INTO merchants (merchant_id, business_name, owner_contact, onboarding_status, status, created_at, updated_at, kitchen_address_line1, kitchen_address_line2, kitchen_city, kitchen_pincode, cuisine_type, fssai_license_no)
VALUES (
    '11111111-1111-1111-1111-111111111111',
    'Varkeys Restaurant',
    '+919876543210',
    'completed',
    'active',
    NOW() - INTERVAL '90 days',
    NOW(),
    '123 MG Road',
    'Koramangala',
    'Bangalore',
    '560034',
    'South Indian, Chinese',
    'FSSAI12345678901234'
);

-- Create staff user (password: password123)
INSERT INTO staff_users (staff_user_id, merchant_id, name, email_or_phone, password_hash, role, created_at)
VALUES (
    '22222222-2222-2222-2222-222222222222',
    '11111111-1111-1111-1111-111111111111',
    'Varkeys Admin',
    'admin@varkeys.com',
    '$argon2id$v=19$m=65536,t=3,p=4$abc123def456ghi789jkl012mno345pq$uvwxyz1234567890abcdefghijklmnopqrstuvwxyz123456',
    'owner',
    NOW() - INTERVAL '90 days'
);

-- Create menu items (South Indian section)
INSERT INTO menu_items (menu_item_id, merchant_id, category, name, price, is_available, created_at, updated_at)
VALUES
    ('33333333-3333-3333-3333-333333333301', '11111111-1111-1111-1111-111111111111', 'Dosa & Crepes', 'Masala Dosa', 80.00, true, NOW() - INTERVAL '80 days', NOW()),
    ('33333333-3333-3333-3333-333333333302', '11111111-1111-1111-1111-111111111111', 'Dosa & Crepes', 'Plain Dosa', 60.00, true, NOW() - INTERVAL '80 days', NOW()),
    ('33333333-3333-3333-3333-333333333303', '11111111-1111-1111-1111-111111111111', 'Dosa & Crepes', 'Rava Masala Dosa', 90.00, true, NOW() - INTERVAL '80 days', NOW()),
    ('33333333-3333-3333-3333-333333333304', '11111111-1111-1111-1111-111111111111', 'Dosa & Crepes', 'Paneer Dosa', 110.00, true, NOW() - INTERVAL '80 days', NOW()),
    ('33333333-3333-3333-3333-333333333305', '11111111-1111-1111-1111-111111111111', 'Dosa & Crepes', 'Cheese Dosa', 100.00, true, NOW() - INTERVAL '80 days', NOW()),
    
    ('33333333-3333-3333-3333-333333333306', '11111111-1111-1111-1111-111111111111', 'Idli & Vada', 'Idli (2 pcs)', 40.00, true, NOW() - INTERVAL '80 days', NOW()),
    ('33333333-3333-3333-3333-333333333307', '11111111-1111-1111-1111-111111111111', 'Idli & Vada', 'Medu Vada (2 pcs)', 50.00, true, NOW() - INTERVAL '80 days', NOW()),
    ('33333333-3333-3333-3333-333333333308', '11111111-1111-1111-1111-111111111111', 'Idli & Vada', 'Sambar Vada (2 pcs)', 55.00, true, NOW() - INTERVAL '80 days', NOW()),
    ('33333333-3333-3333-3333-333333333309', '11111111-1111-1111-1111-111111111111', 'Idli & Vada', 'Idli Vada Combo', 70.00, true, NOW() - INTERVAL '80 days', NOW()),
    
    ('33333333-3333-3333-3333-333333333310', '11111111-1111-1111-1111-111111111111', 'Rice Items', 'Curd Rice', 60.00, true, NOW() - INTERVAL '80 days', NOW()),
    ('33333333-3333-3333-3333-333333333311', '11111111-1111-1111-1111-111111111111', 'Rice Items', 'Lemon Rice', 70.00, true, NOW() - INTERVAL '80 days', NOW()),
    ('33333333-3333-3333-3333-333333333312', '11111111-1111-1111-1111-111111111111', 'Rice Items', 'Sambar Rice', 80.00, true, NOW() - INTERVAL '80 days', NOW()),
    ('33333333-3333-3333-3333-333333333313', '11111111-1111-1111-1111-111111111111', 'Rice Items', 'Tamarind Rice', 75.00, true, NOW() - INTERVAL '80 days', NOW()),
    
    ('33333333-3333-3333-3333-333333333314', '11111111-1111-1111-1111-111111111111', 'Chinese', 'Veg Fried Rice', 120.00, true, NOW() - INTERVAL '80 days', NOW()),
    ('33333333-3333-3333-3333-333333333315', '11111111-1111-1111-1111-111111111111', 'Chinese', 'Schezwan Fried Rice', 140.00, true, NOW() - INTERVAL '80 days', NOW()),
    ('33333333-3333-3333-3333-333333333316', '11111111-1111-1111-1111-111111111111', 'Chinese', 'Veg Hakka Noodles', 130.00, true, NOW() - INTERVAL '80 days', NOW()),
    ('33333333-3333-3333-3333-333333333317', '11111111-1111-1111-1111-111111111111', 'Chinese', 'Chilli Paneer', 180.00, true, NOW() - INTERVAL '80 days', NOW()),
    ('33333333-3333-3333-3333-333333333318', '11111111-1111-1111-1111-111111111111', 'Chinese', 'Gobi Manchurian', 150.00, true, NOW() - INTERVAL '80 days', NOW()),
    
    ('33333333-3333-3333-3333-333333333319', '11111111-1111-1111-1111-111111111111', 'Beverages', 'Filter Coffee', 40.00, true, NOW() - INTERVAL '80 days', NOW()),
    ('33333333-3333-3333-3333-333333333320', '11111111-1111-1111-1111-111111111111', 'Beverages', 'Masala Tea', 30.00, true, NOW() - INTERVAL '80 days', NOW()),
    ('33333333-3333-3333-3333-333333333321', '11111111-1111-1111-1111-111111111111', 'Beverages', 'Buttermilk', 35.00, true, NOW() - INTERVAL '80 days', NOW()),
    ('33333333-3333-3333-3333-333333333322', '11111111-1111-1111-1111-111111111111', 'Beverages', 'Fresh Lime Soda', 45.00, true, NOW() - INTERVAL '80 days', NOW()),
    
    ('33333333-3333-3333-3333-333333333323', '11111111-1111-1111-1111-111111111111', 'Desserts', 'Payasam', 60.00, true, NOW() - INTERVAL '80 days', NOW()),
    ('33333333-3333-3333-3333-333333333324', '11111111-1111-1111-1111-111111111111', 'Desserts', 'Kesari', 50.00, true, NOW() - INTERVAL '80 days', NOW());

-- Create customers
INSERT INTO customers (customer_id, merchant_id, whatsapp_number, display_name, first_seen_at, last_order_at)
VALUES
    ('44444444-4444-4444-4444-444444444401', '11111111-1111-1111-1111-111111111111', '+919876501234', 'Rajesh Kumar', NOW() - INTERVAL '45 days', NOW() - INTERVAL '2 days'),
    ('44444444-4444-4444-4444-444444444402', '11111111-1111-1111-1111-111111111111', '+919876502345', 'Priya Sharma', NOW() - INTERVAL '60 days', NOW() - INTERVAL '5 days'),
    ('44444444-4444-4444-4444-444444444403', '11111111-1111-1111-1111-111111111111', '+919876503456', 'Amit Patel', NOW() - INTERVAL '30 days', NOW() - INTERVAL '1 day'),
    ('44444444-4444-4444-4444-444444444404', '11111111-1111-1111-1111-111111111111', '+919876504567', 'Sneha Reddy', NOW() - INTERVAL '20 days', NOW() - INTERVAL '7 days'),
    ('44444444-4444-4444-4444-444444444405', '11111111-1111-1111-1111-111111111111', '+919876505678', 'Vikram Singh', NOW() - INTERVAL '15 days', NOW() - INTERVAL '3 days');

-- Create addresses
INSERT INTO addresses (address_id, merchant_id, customer_id, label, line1, line2, city, pincode, is_default, created_at)
VALUES
    ('55555555-5555-5555-5555-555555555501', '11111111-1111-1111-1111-111111111111', '44444444-4444-4444-4444-444444444401', 'Home', 'Flat 301, Prestige Towers', 'HSR Layout Sector 2', 'Bangalore', '560102', true, NOW() - INTERVAL '45 days'),
    ('55555555-5555-5555-5555-555555555502', '11111111-1111-1111-1111-111111111111', '44444444-4444-4444-4444-444444444402', 'Home', '24/7 BTM Layout 1st Stage', 'Near Water Tank', 'Bangalore', '560068', true, NOW() - INTERVAL '60 days'),
    ('55555555-5555-5555-5555-555555555503', '11111111-1111-1111-1111-111111111111', '44444444-4444-4444-4444-444444444403', 'Home', 'Sobha Apartments B-402', 'Koramangala 6th Block', 'Bangalore', '560095', true, NOW() - INTERVAL '30 days'),
    ('55555555-5555-5555-5555-555555555504', '11111111-1111-1111-1111-111111111111', '44444444-4444-4444-4444-444444444404', 'Home', 'House No 45, 17th Cross', 'Jayanagar 4th Block', 'Bangalore', '560011', true, NOW() - INTERVAL '20 days'),
    ('55555555-5555-5555-5555-555555555505', '11111111-1111-1111-1111-111111111111', '44444444-4444-4444-4444-444444444405', 'Home', 'Green Meadows Villa 12', 'Sarjapur Road', 'Bangalore', '560035', true, NOW() - INTERVAL '15 days');

-- Create orders (mix of statuses)
-- Order 1: Recent completed order
INSERT INTO orders (order_id, merchant_id, customer_id, order_type, delivery_address_id, payment_method, payment_status, fulfillment_status, subtotal, total, currency, placed_at, paid_at, ready_at, completed_at, created_at, updated_at)
VALUES (
    '66666666-6666-6666-6666-666666666601',
    '11111111-1111-1111-1111-111111111111',
    '44444444-4444-4444-4444-444444444401',
    'delivery',
    '55555555-5555-5555-5555-555555555501',
    'online',
    'captured',
    'completed',
    290.00,
    290.00,
    'INR',
    NOW() - INTERVAL '2 days 2 hours',
    NOW() - INTERVAL '2 days 2 hours',
    NOW() - INTERVAL '2 days 1 hour 30 minutes',
    NOW() - INTERVAL '2 days 1 hour',
    NOW() - INTERVAL '2 days 2 hours',
    NOW() - INTERVAL '2 days 1 hour'
);

INSERT INTO order_items (order_item_id, order_id, menu_item_id, name_snapshot, price_snapshot, quantity, line_total)
VALUES
    ('77777777-7777-7777-7777-777777777701', '66666666-6666-6666-6666-666666666601', '33333333-3333-3333-3333-333333333301', 'Masala Dosa', 80.00, 2, 160.00),
    ('77777777-7777-7777-7777-777777777702', '66666666-6666-6666-6666-666666666601', '33333333-3333-3333-3333-333333333307', 'Medu Vada (2 pcs)', 50.00, 1, 50.00),
    ('77777777-7777-7777-7777-777777777703', '66666666-6666-6666-6666-666666666601', '33333333-3333-3333-3333-333333333319', 'Filter Coffee', 40.00, 2, 80.00);

-- Order 2: Preparing order
INSERT INTO orders (order_id, merchant_id, customer_id, order_type, delivery_address_id, payment_method, payment_status, fulfillment_status, subtotal, total, currency, placed_at, paid_at, created_at, updated_at)
VALUES (
    '66666666-6666-6666-6666-666666666602',
    '11111111-1111-1111-1111-111111111111',
    '44444444-4444-4444-4444-444444444402',
    'delivery',
    '55555555-5555-5555-5555-555555555502',
    'cod',
    'pending',
    'preparing',
    460.00,
    460.00,
    'INR',
    NOW() - INTERVAL '35 minutes',
    NULL,
    NOW() - INTERVAL '35 minutes',
    NOW() - INTERVAL '10 minutes'
);

INSERT INTO order_items (order_item_id, order_id, menu_item_id, name_snapshot, price_snapshot, quantity, line_total)
VALUES
    ('77777777-7777-7777-7777-777777777704', '66666666-6666-6666-6666-666666666602', '33333333-3333-3333-3333-333333333315', 'Schezwan Fried Rice', 140.00, 1, 140.00),
    ('77777777-7777-7777-7777-777777777705', '66666666-6666-6666-6666-666666666602', '33333333-3333-3333-3333-333333333317', 'Chilli Paneer', 180.00, 1, 180.00),
    ('77777777-7777-7777-7777-777777777706', '66666666-6666-6666-6666-666666666602', '33333333-3333-3333-3333-333333333318', 'Gobi Manchurian', 150.00, 1, 150.00);

-- Order 3: New order just placed
INSERT INTO orders (order_id, merchant_id, customer_id, order_type, delivery_address_id, payment_method, payment_status, fulfillment_status, subtotal, total, currency, placed_at, paid_at, created_at, updated_at)
VALUES (
    '66666666-6666-6666-6666-666666666603',
    '11111111-1111-1111-1111-111111111111',
    '44444444-4444-4444-4444-444444444403',
    'delivery',
    '55555555-5555-5555-5555-555555555503',
    'online',
    'captured',
    'new',
    255.00,
    255.00,
    'INR',
    NOW() - INTERVAL '12 minutes',
    NOW() - INTERVAL '12 minutes',
    NOW() - INTERVAL '12 minutes',
    NOW() - INTERVAL '12 minutes'
);

INSERT INTO order_items (order_item_id, order_id, menu_item_id, name_snapshot, price_snapshot, quantity, line_total)
VALUES
    ('77777777-7777-7777-7777-777777777707', '66666666-6666-6666-6666-666666666603', '33333333-3333-3333-3333-333333333303', 'Rava Masala Dosa', 90.00, 1, 90.00),
    ('77777777-7777-7777-7777-777777777708', '66666666-6666-6666-6666-666666666603', '33333333-3333-3333-3333-333333333304', 'Paneer Dosa', 110.00, 1, 110.00),
    ('77777777-7777-7777-7777-777777777709', '66666666-6666-6666-6666-666666666603', '33333333-3333-3333-3333-333333333322', 'Fresh Lime Soda', 45.00, 1, 45.00);

-- Order 4: Ready for pickup/delivery
INSERT INTO orders (order_id, merchant_id, customer_id, order_type, delivery_address_id, payment_method, payment_status, fulfillment_status, subtotal, total, currency, placed_at, paid_at, ready_at, created_at, updated_at)
VALUES (
    '66666666-6666-6666-6666-666666666604',
    '11111111-1111-1111-1111-111111111111',
    '44444444-4444-4444-4444-444444444404',
    'delivery',
    '55555555-5555-5555-5555-555555555504',
    'cod',
    'pending',
    'ready',
    200.00,
    200.00,
    'INR',
    NOW() - INTERVAL '1 hour 15 minutes',
    NULL,
    NOW() - INTERVAL '15 minutes',
    NOW() - INTERVAL '1 hour 15 minutes',
    NOW() - INTERVAL '15 minutes'
);

INSERT INTO order_items (order_item_id, order_id, menu_item_id, name_snapshot, price_snapshot, quantity, line_total)
VALUES
    ('77777777-7777-7777-7777-777777777710', '66666666-6666-6666-6666-666666666604', '33333333-3333-3333-3333-333333333306', 'Idli (2 pcs)', 40.00, 2, 80.00),
    ('77777777-7777-7777-7777-777777777711', '66666666-6666-6666-6666-666666666604', '33333333-3333-3333-3333-333333333310', 'Curd Rice', 60.00, 1, 60.00),
    ('77777777-7777-7777-7777-777777777712', '66666666-6666-6666-6666-666666666604', '33333333-3333-3333-3333-333333333320', 'Masala Tea', 30.00, 2, 60.00);

-- Order 5: Completed order from a few days ago
INSERT INTO orders (order_id, merchant_id, customer_id, order_type, delivery_address_id, payment_method, payment_status, fulfillment_status, subtotal, total, currency, placed_at, paid_at, ready_at, completed_at, created_at, updated_at)
VALUES (
    '66666666-6666-6666-6666-666666666605',
    '11111111-1111-1111-1111-111111111111',
    '44444444-4444-4444-4444-444444444405',
    'delivery',
    '55555555-5555-5555-5555-555555555505',
    'online',
    'captured',
    'completed',
    510.00,
    510.00,
    'INR',
    NOW() - INTERVAL '3 days 5 hours',
    NOW() - INTERVAL '3 days 5 hours',
    NOW() - INTERVAL '3 days 4 hours 30 minutes',
    NOW() - INTERVAL '3 days 4 hours',
    NOW() - INTERVAL '3 days 5 hours',
    NOW() - INTERVAL '3 days 4 hours'
);

INSERT INTO order_items (order_item_id, order_id, menu_item_id, name_snapshot, price_snapshot, quantity, line_total)
VALUES
    ('77777777-7777-7777-7777-777777777713', '66666666-6666-6666-6666-666666666605', '33333333-3333-3333-3333-333333333314', 'Veg Fried Rice', 120.00, 1, 120.00),
    ('77777777-7777-7777-7777-777777777714', '66666666-6666-6666-6666-666666666605', '33333333-3333-3333-3333-333333333316', 'Veg Hakka Noodles', 130.00, 1, 130.00),
    ('77777777-7777-7777-7777-777777777715', '66666666-6666-6666-6666-666666666605', '33333333-3333-3333-3333-333333333318', 'Gobi Manchurian', 150.00, 1, 150.00),
    ('77777777-7777-7777-7777-777777777716', '66666666-6666-6666-6666-666666666605', '33333333-3333-3333-3333-333333333323', 'Payasam', 60.00, 2, 120.00);

-- Order 6: Another recent completed order
INSERT INTO orders (order_id, merchant_id, customer_id, order_type, delivery_address_id, payment_method, payment_status, fulfillment_status, subtotal, total, currency, placed_at, paid_at, ready_at, completed_at, created_at, updated_at)
VALUES (
    '66666666-6666-6666-6666-666666666606',
    '11111111-1111-1111-1111-111111111111',
    '44444444-4444-4444-4444-444444444401',
    'delivery',
    '55555555-5555-5555-5555-555555555501',
    'cod',
    'captured',
    'completed',
    180.00,
    180.00,
    'INR',
    NOW() - INTERVAL '5 days 3 hours',
    NOW() - INTERVAL '5 days 2 hours 30 minutes',
    NOW() - INTERVAL '5 days 2 hours 45 minutes',
    NOW() - INTERVAL '5 days 2 hours 30 minutes',
    NOW() - INTERVAL '5 days 3 hours',
    NOW() - INTERVAL '5 days 2 hours 30 minutes'
);

INSERT INTO order_items (order_item_id, order_id, menu_item_id, name_snapshot, price_snapshot, quantity, line_total)
VALUES
    ('77777777-7777-7777-7777-777777777717', '66666666-6666-6666-6666-666666666606', '33333333-3333-3333-3333-333333333302', 'Plain Dosa', 60.00, 2, 120.00),
    ('77777777-7777-7777-7777-777777777718', '66666666-6666-6666-6666-666666666606', '33333333-3333-3333-3333-333333333320', 'Masala Tea', 30.00, 2, 60.00);

-- Add notification templates
INSERT INTO notification_templates (template_id, merchant_id, notification_kind, template_name, language_code, body, is_active, updated_at)
VALUES
    ('88888888-8888-8888-8888-888888888801', '11111111-1111-1111-1111-111111111111', 'order_confirmed', 'order_confirmed_template', 'en', 'Hi {{customer_name}}! Your order #{{order_id}} has been confirmed. Total: ₹{{total}}. Estimated delivery: {{estimated_time}} mins.', true, NOW()),
    ('88888888-8888-8888-8888-888888888802', '11111111-1111-1111-1111-111111111111', 'order_ready', 'order_ready_template', 'en', 'Your order #{{order_id}} is ready! 🎉', true, NOW()),
    ('88888888-8888-8888-8888-888888888803', '11111111-1111-1111-1111-111111111111', 'order_completed', 'order_completed_template', 'en', 'Thank you for ordering from Varkeys! Hope you enjoyed your meal. 😊', true, NOW());

-- Summary
SELECT 
    'Demo data for Varkeys created successfully!' as status,
    (SELECT COUNT(*) FROM menu_items WHERE merchant_id = '11111111-1111-1111-1111-111111111111') as menu_items,
    (SELECT COUNT(*) FROM customers WHERE merchant_id = '11111111-1111-1111-1111-111111111111') as customers,
    (SELECT COUNT(*) FROM orders WHERE merchant_id = '11111111-1111-1111-1111-111111111111') as orders,
    (SELECT COUNT(*) FROM addresses WHERE merchant_id = '11111111-1111-1111-1111-111111111111') as addresses;
