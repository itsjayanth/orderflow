import { Pencil, RotateCcw, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableRow } from '@/components/ui/table'
import type { CustomerOut } from '@/shared/api/types'
import { StatusBadge } from '@/shared/components/StatusBadge'
import { formatCustomerNumber } from '@/shared/lib/customerNumber'
import { formatOrderNumber } from '@/shared/lib/orderNumber'
import { formatPhoneNumber } from '@/shared/lib/phoneNumber'
import { useOrders } from '../orders/useOrders'
import { useCustomer } from './useCustomer'
import { useUpdateCustomer } from './useUpdateCustomer'

// Left-column label cell shared by every profile row -- fixed width so the
// value column lines up from "Customer ID" all the way down to the order
// history rows below it.
function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <TableCell className="text-muted-foreground w-44 align-top text-xs font-medium tracking-wide uppercase">
      {children}
    </TableCell>
  )
}

// Shared by the Customers list's inline row expansion -- the one place
// that renders "everything about this customer" as a single profile
// table: identity/contact fields, saved addresses, and order history all
// as rows of one <table>, rather than scattered across separate cards.
// Mirrors OrderDetailCard's role/shape for the Orders tab, so the two
// "expand a monitoring row into a rich detail card" interactions feel
// like the same app.
export function CustomerDetailCard({
  customer,
  onEdit,
  onRemove,
}: {
  customer: CustomerOut
  onEdit: (customer: CustomerOut) => void
  onRemove: (customer: CustomerOut) => void
}) {
  const detail = useCustomer(customer.customer_id)
  const orders = useOrders({ customerId: customer.customer_id })
  const updateCustomer = useUpdateCustomer()
  const label = customer.display_name ?? formatPhoneNumber(customer.whatsapp_number)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <div className="flex items-center gap-2">
          <p className="text-base font-semibold">{label}</p>
          {customer.is_active ? (
            <Badge tone="green">Active</Badge>
          ) : (
            <Badge tone="gray">Removed</Badge>
          )}
          {/* Read-only -- only the customer's own STOP/START WhatsApp
              message flips this (Phase 12), so there's no toggle here. */}
          {customer.marketing_opt_out && <Badge tone="amber">Opted out</Badge>}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            aria-label={`Edit ${label}`}
            onClick={() => onEdit(customer)}
          >
            <Pencil className="size-4" />
            Edit
          </Button>
          {customer.is_active ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="hover:text-destructive"
              aria-label={`Remove ${label}`}
              disabled={updateCustomer.isPending}
              onClick={() => onRemove(customer)}
            >
              <Trash2 className="size-4" />
              Remove
            </Button>
          ) : (
            <Button
              type="button"
              size="sm"
              variant="outline"
              aria-label={`Restore ${label}`}
              disabled={updateCustomer.isPending}
              onClick={() =>
                updateCustomer.mutate({ customer_id: customer.customer_id, is_active: true })
              }
            >
              <RotateCcw className="size-4" />
              Restore
            </Button>
          )}
        </div>
      </div>

      {/* Everything about this customer lives in this one table: identity
          and contact fields as label/value rows, then an "Order history"
          section rule, then one row per past order. */}
      <div className="border-border overflow-hidden rounded-lg border">
        <Table>
          <TableBody>
            <TableRow>
              <FieldLabel>Customer ID</FieldLabel>
              <TableCell className="font-mono text-sm">
                {formatCustomerNumber(customer.customer_number)}
              </TableCell>
            </TableRow>
            <TableRow>
              <FieldLabel>WhatsApp number</FieldLabel>
              <TableCell className="text-sm tabular-nums">
                {formatPhoneNumber(customer.whatsapp_number)}
              </TableCell>
            </TableRow>
            <TableRow>
              <FieldLabel>Delivery contact</FieldLabel>
              <TableCell className="text-sm tabular-nums">
                {customer.default_contact_phone
                  ? formatPhoneNumber(customer.default_contact_phone)
                  : 'Same as WhatsApp number'}
              </TableCell>
            </TableRow>
            <TableRow>
              <FieldLabel>Email</FieldLabel>
              <TableCell
                className={customer.email ? 'text-sm' : 'text-muted-foreground text-sm italic'}
              >
                {customer.email ?? 'Not provided'}
              </TableCell>
            </TableRow>
            <TableRow>
              <FieldLabel>Saved addresses</FieldLabel>
              <TableCell className="whitespace-normal text-sm">
                {detail.isLoading && <span className="text-muted-foreground">Loading…</span>}
                {detail.data && detail.data.addresses.length === 0 && (
                  <span className="text-muted-foreground italic">No saved addresses.</span>
                )}
                {detail.data && detail.data.addresses.length > 0 && (
                  <ul className="space-y-1.5">
                    {detail.data.addresses.map((address) => (
                      <li key={address.address_id} className="flex flex-wrap items-start gap-x-2">
                        <span className="text-muted-foreground shrink-0">{address.label}:</span>
                        <span>
                          {address.line1}
                          {address.line2 ? `, ${address.line2}` : ''}
                          {address.landmark ? ` (near ${address.landmark})` : ''}
                          {`, ${address.city} ${address.pincode}`}
                        </span>
                        {address.is_default && (
                          <Badge tone="gray" className="shrink-0">
                            Default
                          </Badge>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </TableCell>
            </TableRow>

            <TableRow className="hover:bg-transparent">
              <TableCell
                colSpan={2}
                className="bg-muted/40 text-muted-foreground py-2 text-xs font-semibold tracking-wide uppercase"
              >
                Order history
              </TableCell>
            </TableRow>

            {orders.isLoading && (
              <TableRow>
                <TableCell colSpan={2} className="text-muted-foreground text-sm">
                  Loading…
                </TableCell>
              </TableRow>
            )}
            {orders.data && orders.data.length === 0 && (
              <TableRow>
                <TableCell colSpan={2} className="text-muted-foreground text-sm italic">
                  No orders yet.
                </TableCell>
              </TableRow>
            )}
            {orders.data?.map((order) => (
              <TableRow key={order.order_id}>
                <TableCell className="text-sm">
                  <Link
                    to={`/orders/${order.order_id}`}
                    className="text-primary font-medium hover:underline"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {formatOrderNumber(order.order_number)}
                  </Link>
                </TableCell>
                <TableCell className="whitespace-normal">
                  <div className="flex flex-wrap items-center gap-3 text-sm">
                    <span className="text-muted-foreground">
                      {new Date(order.placed_at).toLocaleDateString()}
                    </span>
                    <span className="tabular-nums">
                      {order.currency} {order.total}
                    </span>
                    {order.fulfillment_status ? (
                      <StatusBadge status={order.fulfillment_status} />
                    ) : (
                      <span className="text-muted-foreground">Awaiting payment</span>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
