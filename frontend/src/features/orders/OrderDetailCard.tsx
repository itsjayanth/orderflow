import { Banknote, Pencil } from 'lucide-react'
import { useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import type { OrderDetailOut } from '@/shared/api/types'
import { StatusBadge } from '@/shared/components/StatusBadge'
import { formatCustomerNumber } from '@/shared/lib/customerNumber'
import { PAYMENT_STATUS_LABELS, paymentStatusTone } from '@/shared/lib/paymentStatus'
import { formatPhoneNumber } from '@/shared/lib/phoneNumber'

import { legalNextStatuses, STATUS_LABELS } from './statusTransitions'
import { useCollectCodPayment } from './useCollectCodPayment'
import { useUpdateOrderDetails } from './useUpdateOrderDetails'
import { useUpdateOrderStatus } from './useUpdateOrderStatus'

function ContactPhoneEditor({
  orderId,
  contactPhone,
  fallbackPhone,
}: {
  orderId: string
  contactPhone: string | null
  fallbackPhone: string
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(contactPhone ?? fallbackPhone)
  const updateDetails = useUpdateOrderDetails()

  const save = () => {
    updateDetails.mutate(
      { orderId, contactPhone: draft.trim() },
      { onSuccess: () => setEditing(false) },
    )
  }

  const displayValue = formatPhoneNumber(contactPhone ?? fallbackPhone)

  if (!editing) {
    return (
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          setDraft(contactPhone ?? fallbackPhone)
          setEditing(true)
        }}
        className="group text-muted-foreground hover:text-foreground flex items-center gap-1.5 text-sm transition-colors duration-150"
      >
        <span className="tabular-nums">Contact: {displayValue}</span>
        <Pencil className="size-3 opacity-0 transition-opacity duration-150 group-hover:opacity-100" />
      </button>
    )
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        autoFocus
        placeholder="+91 98765 43210"
        aria-label="Contact number"
        className="h-8 w-44 text-sm"
      />
      <Button type="button" size="sm" onClick={save} disabled={updateDetails.isPending}>
        Save
      </Button>
      <Button type="button" size="sm" variant="outline" onClick={() => setEditing(false)}>
        Cancel
      </Button>
    </div>
  )
}

function NotesEditor({ orderId, notes }: { orderId: string; notes: string | null }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(notes ?? '')
  const updateDetails = useUpdateOrderDetails()

  const save = () => {
    updateDetails.mutate({ orderId, notes: draft.trim() }, { onSuccess: () => setEditing(false) })
  }

  if (!editing) {
    return (
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          setDraft(notes ?? '')
          setEditing(true)
        }}
        className="group text-left"
      >
        <p className="text-muted-foreground mb-1 text-xs font-medium tracking-wide uppercase">
          Notes
        </p>
        <p
          className={
            notes
              ? 'text-sm'
              : 'text-muted-foreground group-hover:text-foreground text-sm italic transition-colors duration-150'
          }
        >
          {notes || 'Add a note (e.g. "no onion", "call before delivering")…'}
        </p>
      </button>
    )
  }

  return (
    <div className="space-y-2">
      <p className="text-muted-foreground text-xs font-medium tracking-wide uppercase">Notes</p>
      <Textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        autoFocus
        placeholder="No onion, call before delivering…"
        aria-label="Order notes"
        className="min-h-16 text-sm"
      />
      <div className="flex gap-2">
        <Button type="button" size="sm" onClick={save} disabled={updateDetails.isPending}>
          Save
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={() => setEditing(false)}>
          Cancel
        </Button>
      </div>
    </div>
  )
}

function DeliveryAddress({ order }: { order: OrderDetailOut }) {
  if (order.order_type !== 'delivery') return null

  return (
    <div>
      <p className="text-muted-foreground mb-1 text-xs font-medium tracking-wide uppercase">
        Delivery address
      </p>
      {order.delivery_address ? (
        <p className="text-sm">
          {order.delivery_address.line1}
          {order.delivery_address.line2 ? `, ${order.delivery_address.line2}` : ''}
          {order.delivery_address.landmark ? ` (near ${order.delivery_address.landmark})` : ''}
          {`, ${order.delivery_address.city} ${order.delivery_address.pincode}`}
        </p>
      ) : (
        <p className="text-muted-foreground text-sm italic">No address on file.</p>
      )}
    </div>
  )
}

// Shared by OrderDetailPage (full page) and OrdersPage's inline row
// expansion -- the one place that renders "everything about this order":
// who it's for, where it's going, what's in it, staff notes, and every
// action a kitchen/dashboard user can take. Kept action-heavy on purpose
// (per product ask: the Orders *list* is monitoring-only, this card is
// where an admin actually does something with an order) -- except the
// fulfillment-status "Mark {status}" row, which `showStatusActions=false`
// hides in the OrdersPage row-expansion context, where the row-level
// StatusActionsMenu dropdown already covers that same action.
export function OrderDetailCard({
  order,
  showStatusActions = true,
}: {
  order: OrderDetailOut
  showStatusActions?: boolean
}) {
  const updateStatus = useUpdateOrderStatus()
  const collectPayment = useCollectCodPayment()

  const nextStatuses = order.fulfillment_status ? legalNextStatuses(order.fulfillment_status) : []
  const canCollectCodPayment =
    order.payment_method === 'cod' && order.payment_status === 'cod_pending'
  const showFulfillmentActions = showStatusActions && nextStatuses.length > 0
  const showActionsRow = showFulfillmentActions || canCollectCodPayment
  const showNoActionsFallback =
    showStatusActions && nextStatuses.length === 0 && !canCollectCodPayment

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="space-y-1">
          <p className="font-medium">
            {order.customer_name ?? formatPhoneNumber(order.customer_whatsapp_number)}{' '}
            <span className="text-muted-foreground font-normal">
              ({formatCustomerNumber(order.customer_number)})
            </span>
          </p>
          <ContactPhoneEditor
            orderId={order.order_id}
            contactPhone={order.contact_phone}
            fallbackPhone={order.customer_whatsapp_number}
          />
        </div>
        <p className="text-muted-foreground text-sm">
          {new Date(order.placed_at).toLocaleString()}
        </p>
      </div>

      <div className="grid gap-x-8 gap-y-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        {/* Left column: status, actions, delivery/notes -- everything about
            the order's current state and what to do about it. */}
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
                Kitchen status
              </span>
              {order.fulfillment_status ? (
                <StatusBadge status={order.fulfillment_status} />
              ) : (
                <Badge tone="gray">Awaiting payment</Badge>
              )}
            </div>
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
                Payment
              </span>
              <Badge tone={paymentStatusTone(order.payment_status)}>
                {PAYMENT_STATUS_LABELS[order.payment_status] ?? order.payment_status}
              </Badge>
            </div>
          </div>

          {showActionsRow && (
            <div className="flex flex-wrap items-center gap-2">
              {showFulfillmentActions &&
                nextStatuses.map((status) => (
                  <Button
                    key={status}
                    type="button"
                    size="sm"
                    variant={status === 'cancelled' ? 'outline' : 'default'}
                    disabled={updateStatus.isPending}
                    onClick={() =>
                      updateStatus.mutate({
                        orderId: order.order_id,
                        toStatus: status,
                      })
                    }
                  >
                    Mark {STATUS_LABELS[status]}
                  </Button>
                ))}
              {canCollectCodPayment && (
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  disabled={collectPayment.isPending}
                  onClick={() => collectPayment.mutate(order.order_id)}
                >
                  <Banknote />
                  Mark payment collected
                </Button>
              )}
            </div>
          )}
          {showNoActionsFallback && (
            <p className="text-muted-foreground text-sm">
              No further actions -- this order is in a final state.
            </p>
          )}

          {updateStatus.isError && (
            <p className="text-destructive text-sm">Failed to update status. Please try again.</p>
          )}
          {collectPayment.isError && (
            <p className="text-destructive text-sm">
              Failed to mark payment collected. Please try again.
            </p>
          )}

          <DeliveryAddress order={order} />
          <NotesEditor orderId={order.order_id} notes={order.notes} />
        </div>

        {/* Right column: what was ordered and what it came to. */}
        <div className="space-y-3">
          <p className="text-muted-foreground text-xs font-medium tracking-wide uppercase">Items</p>
          <div className="border-border overflow-hidden rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Item</TableHead>
                  <TableHead>Quantity</TableHead>
                  <TableHead>Price</TableHead>
                  <TableHead>Line total</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {order.items.map((item) => (
                  <TableRow key={item.order_item_id}>
                    <TableCell className="font-medium">{item.name_snapshot}</TableCell>
                    <TableCell className="tabular-nums">{item.quantity}</TableCell>
                    <TableCell className="tabular-nums">{item.price_snapshot}</TableCell>
                    <TableCell className="tabular-nums">{item.line_total}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <p className="text-right text-lg font-semibold tabular-nums">
            Total: {order.currency} {order.total}
          </p>
        </div>
      </div>
    </div>
  )
}
