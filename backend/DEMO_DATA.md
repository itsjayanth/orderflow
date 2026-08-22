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

### Preparing (1)
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
