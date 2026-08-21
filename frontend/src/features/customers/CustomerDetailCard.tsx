import { Pencil, RotateCcw, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { CustomerOut } from '@/shared/api/types'
import { StatusBadge } from '@/shared/components/StatusBadge'
import { formatCustomerNumber } from '@/shared/lib/customerNumber'
import { formatOrderNumber } from '@/shared/lib/orderNumber'
import { formatPhoneNumber } from '@/shared/lib/phoneNumber'
import { useOrders } from '../orders/useOrders'
import { useCustomer } from './useCustomer'
import { useUpdateCustomer } from './useUpdateCustomer'

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-muted-foreground mb-1 text-xs font-medium tracking-wide uppercase">
      {children}
    </p>
  )
}

// Shared by the Customers list's inline row expansion -- the one place
// that renders "everything about this customer": contact info, every
// saved address, and their recent order history, plus the edit/remove
// actions. Mirrors OrderDetailCard's role/shape for the Orders tab, so the
// two "expand a monitoring row into a rich detail card" interactions feel
// like the same app.
export function CustomerDetailCard({
  customer,
  onEdit,
}: {
  customer: CustomerOut
  onEdit: (customer: CustomerOut) => void
}) {
  const detail = useCustomer(customer.customer_id)
  const orders = useOrders({ customerId: customer.customer_id })
  const updateCustomer = useUpdateCustomer()

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="space-y-1">
          <p className="font-medium">
            {customer.display_name ?? formatPhoneNumber(customer.whatsapp_number)}{' '}
            <span className="text-muted-foreground font-normal">
              ({formatCustomerNumber(customer.customer_number)})
            </span>
          </p>
        </div>
        {customer.is_active ? (
          <Badge tone="green">Active</Badge>
        ) : (
          <Badge tone="gray">Removed</Badge>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div>
          <SectionLabel>WhatsApp number</SectionLabel>
          <p className="text-sm tabular-nums">{formatPhoneNumber(customer.whatsapp_number)}</p>
        </div>
        <div>
          <SectionLabel>Delivery contact</SectionLabel>
          <p className="text-sm tabular-nums">
            {customer.default_contact_phone
              ? formatPhoneNumber(customer.default_contact_phone)
              : 'Same as WhatsApp number'}
          </p>
        </div>
        <div>
          <SectionLabel>Email</SectionLabel>
          <p className={customer.email ? 'text-sm' : 'text-muted-foreground text-sm italic'}>
            {customer.email ?? 'Not provided'}
          </p>
        </div>
      </div>

      <div>
        <SectionLabel>Saved addresses</SectionLabel>
        {detail.isLoading && <p className="text-muted-foreground text-sm">Loading…</p>}
        {detail.data && detail.data.addresses.length === 0 && (
          <p className="text-muted-foreground text-sm">No saved addresses.</p>
        )}
        {detail.data && detail.data.addresses.length > 0 && (
          <ul className="space-y-2">
            {detail.data.addresses.map((address) => (
              <li key={address.address_id} className="flex items-start gap-2 text-sm">
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
      </div>

      <div>
        <SectionLabel>Recent orders</SectionLabel>
        {orders.isLoading && <p className="text-muted-foreground text-sm">Loading…</p>}
        {orders.data && orders.data.length === 0 && (
          <p className="text-muted-foreground text-sm">No orders yet.</p>
        )}
        {orders.data && orders.data.length > 0 && (
          <ul className="divide-border border-border divide-y rounded-lg border">
            {orders.data.map((order) => (
              <li key={order.order_id}>
                <Link
                  to={`/orders/${order.order_id}`}
                  className="hover:bg-muted/40 flex items-center justify-between gap-3 px-3 py-2 text-sm transition-colors duration-150"
                >
                  <span className="text-primary font-medium">
                    {formatOrderNumber(order.order_number)}
                  </span>
                  <span className="text-muted-foreground">
                    {new Date(order.placed_at).toLocaleDateString()}
                  </span>
                  <span className="tabular-nums">
                    {order.currency} {order.total}
                  </span>
                  {order.fulfillment_status ? (
                    <StatusBadge status={order.fulfillment_status} />
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        <Button type="button" size="sm" variant="outline" onClick={() => onEdit(customer)}>
          <Pencil className="size-4" />
          Edit
        </Button>
        {customer.is_active ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="hover:text-destructive"
            disabled={updateCustomer.isPending}
            onClick={() =>
              updateCustomer.mutate({ customer_id: customer.customer_id, is_active: false })
            }
          >
            <Trash2 className="size-4" />
            Remove
          </Button>
        ) : (
          <Button
            type="button"
            size="sm"
            variant="outline"
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
  )
}
