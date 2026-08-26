-- Demo data for existing Varkeys merchant (ede3aa6d-c111-47e2-bb75-65fbb915c5f1)
-- Run with: psql -U orderflow -h localhost -d orderflow -f demo_data_existing.sql

-- Clean up existing demo data for this merchant (keep merchant and staff)
DELETE FROM order_items WHERE order_id IN (SELECT order_id FROM orders WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1');
DELETE FROM order_status_events WHERE order_id IN (SELECT order_id FROM orders WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1');
DELETE FROM payment_events WHERE order_id IN (SELECT order_id FROM orders WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1');
DELETE FROM orders WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1';
DELETE FROM addresses WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1';
DELETE FROM customers WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1';
DELETE FROM menu_items WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1';
DELETE FROM notification_templates WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1';
DELETE FROM whatsapp_business_accounts WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1';
DELETE FROM merchant_payment_credentials WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1';

-- Update merchant details
UPDATE merchants SET
    business_name = 'Varkeys Restaurant',
    kitchen_address_line1 = '123 MG Road',
    kitchen_address_line2 = 'Koramangala',
    kitchen_city = 'Bangalore',
    kitchen_pincode = '560034',
    cuisine_type = 'South Indian, Chinese',
    fssai_license_no = 'FSSAI12345678901234'
WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1';

-- Create menu items (South Indian section)
INSERT INTO menu_items (menu_item_id, merchant_id, category, name, price, is_available, created_at, updated_at)
VALUES
    (gen_random_uuid(), 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', 'Dosa & Crepes', 'Masala Dosa', 80.00, true, NOW() - INTERVAL '80 days', NOW()),
    (gen_random_uuid(), 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', 'Dosa & Crepes', 'Plain Dosa', 60.00, true, NOW() - INTERVAL '80 days', NOW()),
    (gen_random_uuid(), 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', 'Dosa & Crepes', 'Rava Masala Dosa', 90.00, true, NOW() - INTERVAL '80 days', NOW()),
    (gen_random_uuid(), 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', 'Dosa & Crepes', 'Paneer Dosa', 110.00, true, NOW() - INTERVAL '80 days', NOW()),
    (gen_random_uuid(), 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', 'Dosa & Crepes', 'Cheese Dosa', 100.00, true, NOW() - INTERVAL '80 days', NOW()),
    
    (gen_random_uuid(), 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', 'Idli & Vada', 'Idli (2 pcs)', 40.00, true, NOW() - INTERVAL '80 days', NOW()),
    (gen_random_uuid(), 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', 'Idli & Vada', 'Medu Vada (2 pcs)', 50.00, true, NOW() - INTERVAL '80 days', NOW()),
    (gen_random_uuid(), 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', 'Idli & Vada', 'Sambar Vada (2 pcs)', 55.00, true, NOW() - INTERVAL '80 days', NOW()),
    (gen_random_uuid(), 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', 'Idli & Vada', 'Idli Vada Combo', 70.00, true, NOW() - INTERVAL '80 days', NOW()),
    
    (gen_random_uuid(), 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', 'Rice Items', 'Curd Rice', 60.00, true, NOW() - INTERVAL '80 days', NOW()),
    (gen_random_uuid(), 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', 'Rice Items', 'Lemon Rice', 70.00, true, NOW() - INTERVAL '80 days', NOW()),
    (gen_random_uuid(), 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', 'Rice Items', 'Sambar Rice', 80.00, true, NOW() - INTERVAL '80 days', NOW()),
    (gen_random_uuid(), 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', 'Rice Items', 'Tamarind Rice', 75.00, true, NOW() - INTERVAL '80 days', NOW()),
    
    (gen_random_uuid(), 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', 'Chinese', 'Veg Fried Rice', 120.00, true, NOW() - INTERVAL '80 days', NOW()),
    (gen_random_uuid(), 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', 'Chinese', 'Schezwan Fried Rice', 140.00, true, NOW() - INTERVAL '80 days', NOW()),
    (gen_random_uuid(), 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', 'Chinese', 'Veg Hakka Noodles', 130.00, true, NOW() - INTERVAL '80 days', NOW()),
    (gen_random_uuid(), 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', 'Chinese', 'Chilli Paneer', 180.00, true, NOW() - INTERVAL '80 days', NOW()),
    (gen_random_uuid(), 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', 'Chinese', 'Gobi Manchurian', 150.00, true, NOW() - INTERVAL '80 days', NOW()),
    
    (gen_random_uuid(), 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', 'Beverages', 'Filter Coffee', 40.00, true, NOW() - INTERVAL '80 days', NOW()),
    (gen_random_uuid(), 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', 'Beverages', 'Masala Tea', 30.00, true, NOW() - INTERVAL '80 days', NOW()),
    (gen_random_uuid(), 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', 'Beverages', 'Buttermilk', 35.00, true, NOW() - INTERVAL '80 days', NOW()),
    (gen_random_uuid(), 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', 'Beverages', 'Fresh Lime Soda', 45.00, true, NOW() - INTERVAL '80 days', NOW()),
    
    (gen_random_uuid(), 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', 'Desserts', 'Payasam', 60.00, true, NOW() - INTERVAL '80 days', NOW()),
    (gen_random_uuid(), 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', 'Desserts', 'Kesari', 50.00, true, NOW() - INTERVAL '80 days', NOW());

-- Create customers with realistic data
DO $$
DECLARE
    cust1_id UUID := gen_random_uuid();
    cust2_id UUID := gen_random_uuid();
    cust3_id UUID := gen_random_uuid();
    cust4_id UUID := gen_random_uuid();
    cust5_id UUID := gen_random_uuid();
    addr1_id UUID := gen_random_uuid();
    addr2_id UUID := gen_random_uuid();
    addr3_id UUID := gen_random_uuid();
    addr4_id UUID := gen_random_uuid();
    addr5_id UUID := gen_random_uuid();
    order1_id UUID := gen_random_uuid();
    order2_id UUID := gen_random_uuid();
    order3_id UUID := gen_random_uuid();
    order4_id UUID := gen_random_uuid();
    order5_id UUID := gen_random_uuid();
    order6_id UUID := gen_random_uuid();
    item_masala_dosa UUID;
    item_plain_dosa UUID;
    item_rava_dosa UUID;
    item_paneer_dosa UUID;
    item_idli UUID;
    item_vada UUID;
    item_curd_rice UUID;
    item_fried_rice UUID;
    item_schezwan_rice UUID;
    item_noodles UUID;
    item_chilli_paneer UUID;
    item_gobi_manchurian UUID;
    item_filter_coffee UUID;
    item_masala_tea UUID;
    item_lime_soda UUID;
    item_payasam UUID;
BEGIN
    -- Get menu item IDs
    SELECT menu_item_id INTO item_masala_dosa FROM menu_items WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1' AND name = 'Masala Dosa';
    SELECT menu_item_id INTO item_plain_dosa FROM menu_items WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1' AND name = 'Plain Dosa';
    SELECT menu_item_id INTO item_rava_dosa FROM menu_items WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1' AND name = 'Rava Masala Dosa';
    SELECT menu_item_id INTO item_paneer_dosa FROM menu_items WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1' AND name = 'Paneer Dosa';
    SELECT menu_item_id INTO item_idli FROM menu_items WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1' AND name = 'Idli (2 pcs)';
    SELECT menu_item_id INTO item_vada FROM menu_items WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1' AND name = 'Medu Vada (2 pcs)';
    SELECT menu_item_id INTO item_curd_rice FROM menu_items WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1' AND name = 'Curd Rice';
    SELECT menu_item_id INTO item_fried_rice FROM menu_items WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1' AND name = 'Veg Fried Rice';
    SELECT menu_item_id INTO item_schezwan_rice FROM menu_items WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1' AND name = 'Schezwan Fried Rice';
    SELECT menu_item_id INTO item_noodles FROM menu_items WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1' AND name = 'Veg Hakka Noodles';
    SELECT menu_item_id INTO item_chilli_paneer FROM menu_items WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1' AND name = 'Chilli Paneer';
    SELECT menu_item_id INTO item_gobi_manchurian FROM menu_items WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1' AND name = 'Gobi Manchurian';
    SELECT menu_item_id INTO item_filter_coffee FROM menu_items WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1' AND name = 'Filter Coffee';
    SELECT menu_item_id INTO item_masala_tea FROM menu_items WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1' AND name = 'Masala Tea';
    SELECT menu_item_id INTO item_lime_soda FROM menu_items WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1' AND name = 'Fresh Lime Soda';
    SELECT menu_item_id INTO item_payasam FROM menu_items WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1' AND name = 'Payasam';

    -- Create customers
    INSERT INTO customers (customer_id, merchant_id, whatsapp_number, display_name, first_seen_at, last_order_at)
    VALUES
        (cust1_id, 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', '+919876501234', 'Rajesh Kumar', NOW() - INTERVAL '45 days', NOW() - INTERVAL '2 days'),
        (cust2_id, 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', '+919876502345', 'Priya Sharma', NOW() - INTERVAL '60 days', NOW() - INTERVAL '35 minutes'),
        (cust3_id, 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', '+919876503456', 'Amit Patel', NOW() - INTERVAL '30 days', NOW() - INTERVAL '12 minutes'),
        (cust4_id, 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', '+919876504567', 'Sneha Reddy', NOW() - INTERVAL '20 days', NOW() - INTERVAL '1 hour 15 minutes'),
        (cust5_id, 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', '+919876505678', 'Vikram Singh', NOW() - INTERVAL '15 days', NOW() - INTERVAL '3 days');

    -- Create addresses
    INSERT INTO addresses (address_id, merchant_id, customer_id, label, line1, line2, city, pincode, is_default, created_at)
    VALUES
        (addr1_id, 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', cust1_id, 'Home', 'Flat 301, Prestige Towers', 'HSR Layout Sector 2', 'Bangalore', '560102', true, NOW() - INTERVAL '45 days'),
        (addr2_id, 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', cust2_id, 'Home', '24/7 BTM Layout 1st Stage', 'Near Water Tank', 'Bangalore', '560068', true, NOW() - INTERVAL '60 days'),
        (addr3_id, 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', cust3_id, 'Home', 'Sobha Apartments B-402', 'Koramangala 6th Block', 'Bangalore', '560095', true, NOW() - INTERVAL '30 days'),
        (addr4_id, 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', cust4_id, 'Home', 'House No 45, 17th Cross', 'Jayanagar 4th Block', 'Bangalore', '560011', true, NOW() - INTERVAL '20 days'),
        (addr5_id, 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', cust5_id, 'Home', 'Green Meadows Villa 12', 'Sarjapur Road', 'Bangalore', '560035', true, NOW() - INTERVAL '15 days');

    -- Order 1: Completed order from 2 days ago
    INSERT INTO orders (order_id, merchant_id, customer_id, order_type, delivery_address_id, payment_method, payment_status, fulfillment_status, subtotal, total, currency, placed_at, paid_at, ready_at, completed_at, created_at, updated_at)
    VALUES (
        order1_id,
        'ede3aa6d-c111-47e2-bb75-65fbb915c5f1',
        cust1_id,
        'delivery',
        addr1_id,
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
        (gen_random_uuid(), order1_id, item_masala_dosa, 'Masala Dosa', 80.00, 2, 160.00),
        (gen_random_uuid(), order1_id, item_vada, 'Medu Vada (2 pcs)', 50.00, 1, 50.00),
        (gen_random_uuid(), order1_id, item_filter_coffee, 'Filter Coffee', 40.00, 2, 80.00);

    -- Order 2: Processing order
    INSERT INTO orders (order_id, merchant_id, customer_id, order_type, delivery_address_id, payment_method, payment_status, fulfillment_status, subtotal, total, currency, placed_at, created_at, updated_at)
    VALUES (
        order2_id,
        'ede3aa6d-c111-47e2-bb75-65fbb915c5f1',
        cust2_id,
        'delivery',
        addr2_id,
        'cod',
        'pending',
        'processing',
        470.00,
        470.00,
        'INR',
        NOW() - INTERVAL '35 minutes',
        NOW() - INTERVAL '35 minutes',
        NOW() - INTERVAL '10 minutes'
    );

    INSERT INTO order_items (order_item_id, order_id, menu_item_id, name_snapshot, price_snapshot, quantity, line_total)
    VALUES
        (gen_random_uuid(), order2_id, item_schezwan_rice, 'Schezwan Fried Rice', 140.00, 1, 140.00),
        (gen_random_uuid(), order2_id, item_chilli_paneer, 'Chilli Paneer', 180.00, 1, 180.00),
        (gen_random_uuid(), order2_id, item_gobi_manchurian, 'Gobi Manchurian', 150.00, 1, 150.00);

    -- Order 3: New order just placed
    INSERT INTO orders (order_id, merchant_id, customer_id, order_type, delivery_address_id, payment_method, payment_status, fulfillment_status, subtotal, total, currency, placed_at, paid_at, created_at, updated_at)
    VALUES (
        order3_id,
        'ede3aa6d-c111-47e2-bb75-65fbb915c5f1',
        cust3_id,
        'delivery',
        addr3_id,
        'online',
        'captured',
        'new',
        245.00,
        245.00,
        'INR',
        NOW() - INTERVAL '12 minutes',
        NOW() - INTERVAL '12 minutes',
        NOW() - INTERVAL '12 minutes',
        NOW() - INTERVAL '12 minutes'
    );

    INSERT INTO order_items (order_item_id, order_id, menu_item_id, name_snapshot, price_snapshot, quantity, line_total)
    VALUES
        (gen_random_uuid(), order3_id, item_rava_dosa, 'Rava Masala Dosa', 90.00, 1, 90.00),
        (gen_random_uuid(), order3_id, item_paneer_dosa, 'Paneer Dosa', 110.00, 1, 110.00),
        (gen_random_uuid(), order3_id, item_lime_soda, 'Fresh Lime Soda', 45.00, 1, 45.00);

    -- Order 4: Ready for delivery
    INSERT INTO orders (order_id, merchant_id, customer_id, order_type, delivery_address_id, payment_method, payment_status, fulfillment_status, subtotal, total, currency, placed_at, ready_at, created_at, updated_at)
    VALUES (
        order4_id,
        'ede3aa6d-c111-47e2-bb75-65fbb915c5f1',
        cust4_id,
        'delivery',
        addr4_id,
        'cod',
        'pending',
        'ready',
        200.00,
        200.00,
        'INR',
        NOW() - INTERVAL '1 hour 15 minutes',
        NOW() - INTERVAL '15 minutes',
        NOW() - INTERVAL '1 hour 15 minutes',
        NOW() - INTERVAL '15 minutes'
    );

    INSERT INTO order_items (order_item_id, order_id, menu_item_id, name_snapshot, price_snapshot, quantity, line_total)
    VALUES
        (gen_random_uuid(), order4_id, item_idli, 'Idli (2 pcs)', 40.00, 2, 80.00),
        (gen_random_uuid(), order4_id, item_curd_rice, 'Curd Rice', 60.00, 1, 60.00),
        (gen_random_uuid(), order4_id, item_masala_tea, 'Masala Tea', 30.00, 2, 60.00);

    -- Order 5: Completed order from 3 days ago
    INSERT INTO orders (order_id, merchant_id, customer_id, order_type, delivery_address_id, payment_method, payment_status, fulfillment_status, subtotal, total, currency, placed_at, paid_at, ready_at, completed_at, created_at, updated_at)
    VALUES (
        order5_id,
        'ede3aa6d-c111-47e2-bb75-65fbb915c5f1',
        cust5_id,
        'delivery',
        addr5_id,
        'online',
        'captured',
        'completed',
        520.00,
        520.00,
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
        (gen_random_uuid(), order5_id, item_fried_rice, 'Veg Fried Rice', 120.00, 1, 120.00),
        (gen_random_uuid(), order5_id, item_noodles, 'Veg Hakka Noodles', 130.00, 1, 130.00),
        (gen_random_uuid(), order5_id, item_gobi_manchurian, 'Gobi Manchurian', 150.00, 1, 150.00),
        (gen_random_uuid(), order5_id, item_payasam, 'Payasam', 60.00, 2, 120.00);

    -- Order 6: Completed order from 5 days ago
    INSERT INTO orders (order_id, merchant_id, customer_id, order_type, delivery_address_id, payment_method, payment_status, fulfillment_status, subtotal, total, currency, placed_at, paid_at, ready_at, completed_at, created_at, updated_at)
    VALUES (
        order6_id,
        'ede3aa6d-c111-47e2-bb75-65fbb915c5f1',
        cust1_id,
        'delivery',
        addr1_id,
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
        (gen_random_uuid(), order6_id, item_plain_dosa, 'Plain Dosa', 60.00, 2, 120.00),
        (gen_random_uuid(), order6_id, item_masala_tea, 'Masala Tea', 30.00, 2, 60.00);
END $$;

-- Add notification templates
INSERT INTO notification_templates (template_id, merchant_id, notification_kind, template_name, language_code, body, is_active, updated_at)
VALUES
    (gen_random_uuid(), 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', 'order_confirmed', 'order_confirmed_template', 'en', 'Hi {{customer_name}}! Your order #{{order_id}} has been confirmed. Total: ₹{{total}}. Estimated delivery: {{estimated_time}} mins.', true, NOW()),
    (gen_random_uuid(), 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', 'order_ready', 'order_ready_template', 'en', 'Your order #{{order_id}} is ready! 🎉', true, NOW()),
    (gen_random_uuid(), 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1', 'order_completed', 'order_completed_template', 'en', 'Thank you for ordering from Varkeys! Hope you enjoyed your meal. 😊', true, NOW());

-- Summary
SELECT 
    'Demo data added successfully!' as status,
    (SELECT COUNT(*) FROM menu_items WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1') as menu_items,
    (SELECT COUNT(*) FROM customers WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1') as customers,
    (SELECT COUNT(*) FROM orders WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1') as orders,
    (SELECT COUNT(*) FROM addresses WHERE merchant_id = 'ede3aa6d-c111-47e2-bb75-65fbb915c5f1') as addresses;
