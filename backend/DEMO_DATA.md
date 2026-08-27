# Demo Data for Varkeys Restaurant

## Merchant Details
- **Business Name**: Varkeys Restaurant
- **Owner Contact**: +919876543210
- **Cuisine**: South Indian, Chinese
- **Location**: 123 MG Road, Koramangala, Bangalore 560034
- **Status**: Active (completed onboarding)

## Staff Login
- **Email**: admin@varkeys.com
- **Password**: password123
- **Role**: Owner

## Menu Items (24 items across 6 categories)

### Dosa & Crepes (5 items)
- Masala Dosa - ₹80
- Plain Dosa - ₹60
- Rava Masala Dosa - ₹90
- Paneer Dosa - ₹110
- Cheese Dosa - ₹100

### Idli & Vada (4 items)
- Idli (2 pcs) - ₹40
- Medu Vada (2 pcs) - ₹50
- Sambar Vada (2 pcs) - ₹55
- Idli Vada Combo - ₹70

### Rice Items (4 items)
- Curd Rice - ₹60
- Lemon Rice - ₹70
- Sambar Rice - ₹80
- Tamarind Rice - ₹75

### Chinese (5 items)
- Veg Fried Rice - ₹120
- Schezwan Fried Rice - ₹140
- Veg Hakka Noodles - ₹130
- Chilli Paneer - ₹180
- Gobi Manchurian - ₹150

### Beverages (4 items)
- Filter Coffee - ₹40
- Masala Tea - ₹30
- Buttermilk - ₹35
- Fresh Lime Soda - ₹45

### Desserts (2 items)
- Payasam - ₹60
- Kesari - ₹50

## Customers (5 customers)
1. **Rajesh Kumar** (+919876501234) - HSR Layout
2. **Priya Sharma** (+919876502345) - BTM Layout
3. **Amit Patel** (+919876503456) - Koramangala
4. **Sneha Reddy** (+919876504567) - Jayanagar
5. **Vikram Singh** (+919876505678) - Sarjapur Road

## Orders (6 orders in various states)

### New Orders (1)
- **Amit Patel** - ₹255 - Rava Masala Dosa, Paneer Dosa, Fresh Lime Soda (placed 12 mins ago)

### Processing (1)
- **Priya Sharma** - ₹460 - Schezwan Fried Rice, Chilli Paneer, Gobi Manchurian (placed 35 mins ago, COD)

### Ready (1)
- **Sneha Reddy** - ₹200 - 2x Idli, Curd Rice, 2x Masala Tea (ready 15 mins ago, COD)

### Completed (3)
- **Rajesh Kumar** - ₹290 - 2x Masala Dosa, Medu Vada, 2x Filter Coffee (completed 2 days ago)
- **Vikram Singh** - ₹520 - Veg Fried Rice, Veg Hakka Noodles, Gobi Manchurian, 2x Payasam (completed 3 days ago)
- **Rajesh Kumar** - ₹180 - 2x Plain Dosa, 2x Masala Tea (completed 5 days ago, COD)

## How to Use

### Load Demo Data
```bash
cd backend
psql -U orderflow -h localhost -d orderflow -f demo_data_varkeys.sql
```

### Login to Dashboard
1. Navigate to http://localhost:5173
2. Login with: admin@varkeys.com / password123
3. You'll see:
   - 1 new order ready to accept
   - 1 order in preparation
   - 1 order ready for delivery
   - 3 completed orders

### Reset Demo Data
Simply re-run the SQL script - it cleans up and recreates everything:
```bash
psql -U orderflow -h localhost -d orderflow -f demo_data_varkeys.sql
```

## Database IDs Reference

- Merchant ID: `11111111-1111-1111-1111-111111111111`
- Staff User ID: `22222222-2222-2222-2222-222222222222`
- Menu Item IDs: `333333...01` through `333333...24`
- Customer IDs: `444444...01` through `444444...05`
- Address IDs: `555555...01` through `555555...05`
- Order IDs: `666666...01` through `666666...06`
- Order Item IDs: `777777...01` through `777777...18`
- Template IDs: `888888...01` through `888888...03`

# Demo Data for Urban Threads Clothing (non-food vertical)

A second, separate demo dataset for a `Retail / Clothing` merchant --
exercises the same schema as the Varkeys dataset above with no
restaurant-specific data, as a concrete check that the platform doesn't
assume food semantics anywhere.

## Merchant Details
- **Business Name**: Urban Threads Clothing
- **Owner Contact**: +919876509999
- **Business Category**: Retail / Clothing
- **Location**: 45 Commercial Street, Shivaji Nagar, Bangalore 560001
- **Status**: Active (`onboarding_status` = `live`)

## Staff Login
- **Email**: admin@urbanthreads.example
- **Password**: password123
- **Role**: Owner

## Items (16 items across 4 categories)

### Shirts (4 items)
- Classic White Shirt - Rs 1299
- Blue Denim Shirt - Rs 1499
- Checked Flannel Shirt - Rs 1199
- Black Polo Shirt - Rs 899

### Trousers (4 items)
- Slim Fit Chinos - Rs 1799
- Formal Black Trousers - Rs 1999
- Cargo Trousers - Rs 1699
- Grey Track Pants - Rs 999

### Shoes (4 items)
- Running Sneakers - Rs 2999
- Leather Formal Shoes - Rs 3499
- Canvas Casuals - Rs 1499
- Sports Sandals - Rs 899

### Accessories (4 items)
- Leather Belt - Rs 699
- Analog Wrist Watch - Rs 2499
- Canvas Backpack - Rs 1899
- Aviator Sunglasses - Rs 1299

## Customers (5 customers)
1. **Ananya Iyer** (+919812345601) - Indiranagar
2. **Rohit Malhotra** (+919812345602) - Whitefield
3. **Fatima Sheikh** (+919812345603) - Jayanagar
4. **Karan Mehta** (+919812345604) - Malleswaram
5. **Divya Nair** (+919812345605) - Electronic City

## Orders (6 orders across fulfillment states)

### New (1)
- **Fatima Sheikh** - Rs 1199 - Checked Flannel Shirt (placed 10 mins ago, pickup, online)

### Processing (1)
- **Rohit Malhotra** - Rs 2999 - Running Sneakers (placed 40 mins ago, COD)

### Ready (1)
- **Karan Mehta** - Rs 1998 - Leather Belt, Aviator Sunglasses (ready 10 mins ago, COD)

### Completed (2)
- **Ananya Iyer** - Rs 3098 - Classic White Shirt, Slim Fit Chinos (completed 4 days ago)
- **Divya Nair** - Rs 5398 - Leather Formal Shoes, Canvas Backpack (completed 6 days ago)

### Cancelled (1)
- **Ananya Iyer** - Rs 999 - Grey Track Pants (placed 2 days ago, payment abandoned)

## How to Use

### Load Demo Data
```bash
cd backend
PGPASSWORD=orderflow psql -U orderflow -h localhost -d orderflow -f demo_data_clothing_store.sql
```

### Login to Dashboard
1. Navigate to http://localhost:5173
2. Login with: admin@urbanthreads.example / password123
3. You'll see:
   - 1 new order
   - 1 order processing
   - 1 order ready for pickup/delivery
   - 2 completed orders
   - 1 cancelled order

### Reset Demo Data
Simply re-run the SQL script - it cleans up and recreates everything:
```bash
PGPASSWORD=orderflow psql -U orderflow -h localhost -d orderflow -f demo_data_clothing_store.sql
```

## Database IDs Reference

- Merchant ID: `99999999-9999-9999-9999-999999999999`
- Staff User ID: `aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa`
- Item IDs: `bbbbbbbb...01` through `bbbbbbbb...16`
- Customer IDs: `cccccccc...01` through `cccccccc...05`
- Address IDs: `dddddddd...01` through `dddddddd...05`
- Order IDs: `eeeeeeee...01` through `eeeeeeee...06`
- Order Item IDs: `ffffffff...01` through `ffffffff...09`
- Template IDs: `00000000...01` through `00000000...03`
