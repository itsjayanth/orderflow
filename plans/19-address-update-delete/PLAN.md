# 19 — Add saved-address update/delete API

Trello card: https://trello.com/c/nHuMYu1r/19-medium-add-saved-address-update-delete-api-not-customer-thats-now-built
Branch: `feature/19-address-update-delete`

## Problem / goal

`Address` rows (`backend/src/customers/domain/models.py`) are lookup/create-only —
`AddressRepository` has `create`, `list_for_customer`, `get_primary_for_customer` but no
`update` or `delete`. Neither a customer nor staff can fix a typo'd address or remove a
stale one; every correction just adds another row. `Customer` already got full dashboard
CRUD (create/update/deactivate) in an earlier change — this card is specifically the
`Address` gap that was left behind.

## Scope

In scope:
- `AddressRepository.update()` — tenant+customer-scoped partial update of an address's
  fields (label, line1, line2, landmark, city, pincode, geo_lat, geo_long, is_default).
  Setting `is_default=True` unsets `is_default` on the customer's other addresses (single
  default per customer, matching `get_primary_for_customer`'s semantics).
- `AddressRepository.delete()` — tenant+customer-scoped delete, blocked with a typed
  exception if any `Order.delivery_address_id` references the address (past orders must
  keep their delivery address intact; `Order` has no cascade/nullify path today and adding
  one is out of scope).
- `PATCH /api/v1/customers/{customer_id}/addresses/{address_id}` and
  `DELETE /api/v1/customers/{customer_id}/addresses/{address_id}` on the dashboard-facing
  customers router.
- Tests covering: successful update, `is_default` exclusivity, 404 for wrong
  customer/tenant/address, successful delete, 409 when an order references the address.

Out of scope: WhatsApp-side (Flow) address editing, a generalized soft-delete flag on
`Address`, cascading/nullifying `Order.delivery_address_id` on delete.

## Affected modules

- `backend/src/customers/adapters/repository.py` (`AddressRepository`)
- `backend/src/customers/api/schemas.py` (new `AddressUpdate` schema)
- `backend/src/customers/api/router.py` (two new endpoints)
- `backend/tests/test_customers.py` (or a new `test_addresses.py`)

## Acceptance criteria

- [x] Staff can PATCH an existing address's fields via the API and see the update reflected
      on the next GET.
- [x] Setting `is_default=True` on one address clears it on the customer's other addresses.
- [x] DELETE removes an address with no order history.
- [x] DELETE on an address referenced by any order returns 409, not a raw DB error, and the
      address is left intact.
- [x] Both endpoints 404 for an address that doesn't belong to the given customer_id/tenant.
- [x] `ruff check`, `mypy`, and `pytest` (customers + full suite) all pass.

## Implementation steps

1. `AddressRepository.update(tenant, customer_id, address_id, **fields)` — fetch scoped by
   `merchant_id` + `customer_id` + `address_id`, return `None` if not found; apply only the
   fields actually passed (`exclude_unset` pattern, matching `CustomerRepository.update`);
   if `is_default` is being set `True`, first clear `is_default` on the customer's other
   addresses in the same flush.
2. `AddressRepository.delete(tenant, customer_id, address_id)` — fetch scoped the same way,
   return `False` if not found; check for a referencing `Order` (deferred import of
   `orders.domain.models.Order` inside the method, to avoid a circular import since
   `orders/domain/models.py` already imports from `customers.domain.models`); raise
   `AddressInUseError` if referenced; otherwise delete and return `True`.
3. Add `AddressUpdate` Pydantic schema to `customers/api/schemas.py` — all fields optional.
4. Add the two router endpoints; map `AddressInUseError` → 409, not-found → 404.
5. Tests for all acceptance-criteria bullets above.
6. Run `ruff check .`, `mypy src`, `pytest` from `backend/`; fix anything red.

## Risks

- Circular import between `customers` and `orders` domain models if the order-reference
  check isn't deferred correctly — mitigated by the function-scoped import in step 2.
- `is_default` exclusivity touching other rows needs the same-transaction guarantee (single
  `flush`, not a separate commit) so a crash mid-update can't leave two defaults set.

## Testing strategy

`pytest backend/tests/test_customers.py` (or new `test_addresses.py`) exercising the repo
methods directly plus the two endpoints through the existing FastAPI test-client fixtures
used elsewhere in that file. No new fixtures/migrations needed — `Address`/`Order` schema
is unchanged.

## Progress Log

2026-09-04 — Implemented `AddressRepository.update()`/`delete()` in
`backend/src/customers/adapters/repository.py`: `update()` applies an
exclude_unset-style partial update scoped by merchant_id + customer_id +
address_id, and clears `is_default` on the customer's other addresses (same
flush) when `is_default=True` is set; `delete()` is scoped the same way and
raises a new `AddressInUseError` (via a function-scoped import of
`orders.domain.models.Order` to avoid a circular import) when any
`Order.delivery_address_id` references the address.

2026-09-04 — Added the `AddressUpdate` Pydantic schema
(`backend/src/customers/api/schemas.py`) and the
`PATCH /api/v1/customers/{customer_id}/addresses/{address_id}` and
`DELETE /api/v1/customers/{customer_id}/addresses/{address_id}` endpoints
(`backend/src/customers/api/router.py`), mapping not-found to 404 and
`AddressInUseError` to 409.

2026-09-04 — Added tests in `backend/tests/test_customers.py` covering every
acceptance-criteria bullet: repository-level update (partial fields,
is_default exclusivity, not-found) and delete (success, order-referenced
raises `AddressInUseError`), plus API-level PATCH/DELETE tests (success,
404 for wrong customer, 404 for wrong tenant, 404 not-found, 409 when an
order references the address). Added an `_seed_order_referencing_address`
test helper mirroring `test_orders.py`'s `_seed_order` pattern. Started a
local Postgres 16 instance and set up `orderflow`/`orderflow_test`
databases + `.env` to run the suite (none of this is part of the app
config). `ruff check .`, `mypy src` (one pre-existing, unrelated error in
`payments/api/router.py` confirmed present on `main` too), and `pytest`
(customers: 33 passed; full suite: 719 passed) all green.
