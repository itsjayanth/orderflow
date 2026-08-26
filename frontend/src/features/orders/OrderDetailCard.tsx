import { Banknote, Pencil } from 'lucide-react'
import { useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableRow } from '@/components/ui/table'
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

// Left-column label cell shared by every row -- fixed width so the value
// column lines up from "Placed" all the way down to the item rows below
// it, the same convention CustomerDetailCard's profile table uses.
function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <TableCell className="text-muted-foreground w-40 align-top text-xs font-medium tracking-wide uppercase">
      {children}
    </TableCell>
  )
}

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
        className="group text-foreground hover:text-primary flex items-center gap-1.5 text-sm transition-colors duration-150"
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

function formatAddress(address: OrderDetailOut['delivery_address']): string {
  if (!address) return ''
  return (
    address.line1 +
    (address.line2 ? `, ${address.line2}` : '') +
    (address.landmark ? ` (near ${address.landmark})` : '') +
    `, ${address.city} ${address.pincode}`
  )
}

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

// Shared by OrderDetailPage (full page) and OrdersPage's inline row
// expansion -- the one place that renders "everything about this order"
// as a single profile table: who it's for, its current status, where
// it's going, staff notes, every action a kitchen/dashboard user can
// take, and the line items themselves, all as rows of one <table> rather
// than scattered across separate blocks. Mirrors CustomerDetailCard's
// role/shape for the Customers tab. Kept action-heavy on purpose (per
// product ask: the Orders *list* is monitoring-only, this card is where
// an admin actually does something with an order) -- except the
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
  const isDelivery = order.order_type === 'delivery'

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <p className="text-base font-semibold">
          {order.customer_name ?? formatPhoneNumber(order.customer_whatsapp_number)}{' '}
          <span className="text-muted-foreground font-normal">
            ({formatCustomerNumber(order.customer_number)})
          </span>
        </p>
      </div>

      {/* Everything about this order lives in this one table: identity,
          status, and fulfillment fields as label/value rows, then an
          "Items" section rule, then one row per line item and the
          total. */}
      <div className="border-border overflow-hidden rounded-lg border">
        <Table>
          <TableBody>
            <TableRow>
              <FieldLabel>Placed</FieldLabel>
              <TableCell className="text-sm">
                {new Date(order.placed_at).toLocaleString()}
              </TableCell>
            </TableRow>
            <TableRow>
              <FieldLabel>Contact number</FieldLabel>
              <TableCell className="whitespace-normal">
                <ContactPhoneEditor
                  orderId={order.order_id}
                  contactPhone={order.contact_phone}
                  fallbackPhone={order.customer_whatsapp_number}
                />
              </TableCell>
            </TableRow>
            <TableRow>
              <FieldLabel>Fulfillment</FieldLabel>
              <TableCell className="text-sm">{capitalize(order.order_type)}</TableCell>
            </TableRow>
            <TableRow>
              <FieldLabel>Order status</FieldLabel>
              <TableCell>
                {order.fulfillment_status ? (
                  <StatusBadge status={order.fulfillment_status} />
                ) : (
                  <Badge tone="gray">Awaiting payment</Badge>
                )}
              </TableCell>
            </TableRow>
            <TableRow>
              <FieldLabel>Payment</FieldLabel>
              <TableCell>
                <Badge tone={paymentStatusTone(order.payment_status)}>
                  {PAYMENT_STATUS_LABELS[order.payment_status] ?? order.payment_status}
                </Badge>
              </TableCell>
            </TableRow>
            {isDelivery && (
              <TableRow>
                <FieldLabel>Delivery address</FieldLabel>
                <TableCell className="whitespace-normal text-sm">
                  {order.delivery_address ? (
                    formatAddress(order.delivery_address)
                  ) : (
                    <span className="text-muted-foreground italic">No address on file.</span>
                  )}
                </TableCell>
              </TableRow>
            )}
            <TableRow>
              <FieldLabel>Notes</FieldLabel>
              <TableCell className="whitespace-normal">
                <NotesEditor orderId={order.order_id} notes={order.notes} />
              </TableCell>
            </TableRow>
            {(showActionsRow || showNoActionsFallback) && (
              <TableRow>
                <FieldLabel>Actions</FieldLabel>
                <TableCell className="whitespace-normal">
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
                    <p className="text-destructive mt-2 text-sm">
                      Failed to update status. Please try again.
                    </p>
                  )}
                  {collectPayment.isError && (
                    <p className="text-destructive mt-2 text-sm">
                      Failed to mark payment collected. Please try again.
                    </p>
                  )}
                </TableCell>
              </TableRow>
            )}

            <TableRow className="hover:bg-transparent">
              <TableCell
                colSpan={2}
                className="bg-muted/40 text-muted-foreground py-2 text-xs font-semibold tracking-wide uppercase"
              >
                Items
              </TableCell>
            </TableRow>

            {order.items.map((item) => (
              <TableRow key={item.order_item_id}>
                <TableCell className="text-sm font-medium">{item.name_snapshot}</TableCell>
                <TableCell className="whitespace-normal">
                  <div className="flex items-center justify-between gap-3 text-sm">
                    <span className="text-muted-foreground tabular-nums">
                      {item.quantity} × {order.currency} {item.price_snapshot}
                    </span>
                    <span className="font-medium tabular-nums">
                      {order.currency} {item.line_total}
                    </span>
                  </div>
                </TableCell>
              </TableRow>
            ))}

            <TableRow className="hover:bg-transparent">
              <TableCell className="text-sm font-semibold">Total</TableCell>
              <TableCell className="text-right text-base font-semibold tabular-nums">
                {order.currency} {order.total}
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
