import { ArrowDown, ArrowUp, ArrowUpDown, ChevronDown, Inbox, Search } from 'lucide-react'
import { Fragment, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import {
  Pagination,
  PaginationContent,
  PaginationInfo,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'
import type { FulfillmentStatus, OrderOut } from '@/shared/api/types'
import { DateRangeFilter, type DateRangeValue } from '@/shared/components/DateRangeFilter'
import { EmptyState } from '@/shared/components/EmptyState'
import { PageHeader } from '@/shared/components/PageHeader'
import { formatCustomerNumber } from '@/shared/lib/customerNumber'
import { formatOrderNumber } from '@/shared/lib/orderNumber'
import { formatPhoneNumber } from '@/shared/lib/phoneNumber'

import { CancelOrderDialog } from './CancelOrderDialog'
import { CreateTestOrderForm } from './CreateTestOrderForm'
import { OrderDetailCard } from './OrderDetailCard'
import { StatusActionsMenu } from './StatusActionsMenu'
import { legalNextStatuses, STATUS_LABELS } from './statusTransitions'
import { useOrder } from './useOrder'
import { useOrders } from './useOrders'
import { useUpdateOrderStatus } from './useUpdateOrderStatus'

// The full lifecycle, including "cancelled" -- a restaurant owner monitoring
// failed/undelivered orders needs it as a first-class tab too, and it's
// what the dashboard's "Failed" card links to.
const TABS: (FulfillmentStatus | 'all')[] = [
  'all',
  'new',
  'preparing',
  'ready',
  'completed',
  'cancelled',
]

const ALL_STATUSES: FulfillmentStatus[] = ['new', 'preparing', 'ready', 'completed', 'cancelled']

// The columns kept here are deliberately the "monitoring at a glance" set.
// Status is directly actionable here too (the dropdown), so the common
// case -- move an order along -- never needs the expanded card; that's
// reserved for everything else an admin might need to look up or edit
// (items, address, notes, payment method, contact). Bumped from 6 to 7 to
// account for the leading bulk-select checkbox column.
const COLUMN_COUNT = 7

// Applied per-<th> rather than on <thead> -- see the comment at the call
// site for why. `border-b` is repeated here (table.tsx's TableHeader
// already sets it on `thead`, but a sticky th needs its own bottom edge
// since it's no longer visually grouped under a bordered parent while
// pinned above scrolled-past rows).
const STICKY_HEAD_CLASS = 'bg-card border-border sticky top-0 z-10 border-b'

// Purely client-side pagination -- no backend page/cursor params exist,
// this just slices the already-fetched, already-polled array.
const PAGE_SIZE = 15
const SKELETON_ROW_COUNT = 5

type SortState = { column: 'placed_at' | null; direction: 'asc' | 'desc' }

function isFulfillmentStatus(value: string | null): value is FulfillmentStatus {
  return (
    value === 'new' ||
    value === 'preparing' ||
    value === 'ready' ||
    value === 'completed' ||
    value === 'cancelled'
  )
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString()
}

function matchesSearch(order: OrderOut, query: string): boolean {
  const q = query.trim().toLowerCase().replace(/^#/, '')
  if (!q) return true
  return (
    String(order.order_number).includes(q) ||
    formatOrderNumber(order.order_number).toLowerCase().includes(q) ||
    String(order.customer_number).includes(q) ||
    formatCustomerNumber(order.customer_number).toLowerCase().includes(q)
  )
}

function countByStatus(orders: OrderOut[] | undefined): Record<FulfillmentStatus | 'all', number> {
  const counts: Record<FulfillmentStatus | 'all', number> = {
    all: orders?.length ?? 0,
    new: 0,
    preparing: 0,
    ready: 0,
    completed: 0,
    cancelled: 0,
  }
  for (const order of orders ?? []) {
    if (order.fulfillment_status) counts[order.fulfillment_status] += 1
  }
  return counts
}

// Every status that's a legal next step for *every* selected order --
// orders with a null fulfillment_status ("Awaiting payment") have no legal
// transitions at all, so including one in the selection collapses this to
// an empty set (there's nothing every selected order could legally move to).
function computeBulkActions(selectedOrders: OrderOut[]): FulfillmentStatus[] {
  if (selectedOrders.length === 0) return []
  const perOrderLegal = selectedOrders.map(
    (order) => new Set(order.fulfillment_status ? legalNextStatuses(order.fulfillment_status) : []),
  )
  return ALL_STATUSES.filter((status) => perOrderLegal.every((legal) => legal.has(status)))
}

function ExpandedOrderRow({ orderId, rowId }: { orderId: string; rowId: string }) {
  const { data: order, isLoading } = useOrder(orderId)

  return (
    <TableRow id={rowId} className="hover:bg-transparent">
      <TableCell colSpan={COLUMN_COUNT} className="bg-muted/30 whitespace-normal p-5">
        {isLoading && (
          <div className="space-y-2">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        )}
        {order && <OrderDetailCard order={order} showStatusActions={false} />}
      </TableCell>
    </TableRow>
  )
}

export function OrdersPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const statusParam = searchParams.get('status')
  const [tab, setTab] = useState<FulfillmentStatus | 'all'>(
    isFulfillmentStatus(statusParam) ? statusParam : 'all',
  )
  // Date range lives in URL search params the same way `?status=` already
  // does -- a normal, bookmarkable/shareable query-string convention, not
  // special-cased local state.
  const from_date = searchParams.get('from_date') ?? undefined
  const to_date = searchParams.get('to_date') ?? undefined
  const range: DateRangeValue = { from_date, to_date }
  const { data: orders, isLoading } = useOrders(range)
  const [search, setSearch] = useState('')
  const [expandedOrderId, setExpandedOrderId] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [sort, setSort] = useState<SortState>({ column: null, direction: 'asc' })
  const [page, setPage] = useState(1)
  const [bulkCancelOpen, setBulkCancelOpen] = useState(false)
  const updateStatus = useUpdateOrderStatus()

  // The meaning of "selected" (and of "page 1") resets whenever the visible
  // set fundamentally changes -- but NOT on every 5-second poll tick, which
  // is why this depends on tab/search/range rather than on `orders` itself.
  // biome-ignore lint/correctness/useExhaustiveDependencies: intentional reset trigger -- these values aren't read in the body, only watched
  useEffect(() => {
    setPage(1)
    setSelectedIds(new Set())
  }, [tab, search, from_date, to_date])

  function selectTab(next: FulfillmentStatus | 'all') {
    setTab(next)
    const params = new URLSearchParams(searchParams)
    if (next === 'all') params.delete('status')
    else params.set('status', next)
    setSearchParams(params)
  }

  function selectRange(next: DateRangeValue) {
    const params = new URLSearchParams(searchParams)
    if (next.from_date) params.set('from_date', next.from_date)
    else params.delete('from_date')
    if (next.to_date) params.set('to_date', next.to_date)
    else params.delete('to_date')
    setSearchParams(params)
  }

  function toggleExpanded(orderId: string) {
    setExpandedOrderId((current) => (current === orderId ? null : orderId))
  }

  function toggleSort() {
    setSort((current) => {
      if (current.column !== 'placed_at') return { column: 'placed_at', direction: 'asc' }
      return { column: 'placed_at', direction: current.direction === 'asc' ? 'desc' : 'asc' }
    })
  }

  function toggleSelectOne(orderId: string, checked: boolean) {
    setSelectedIds((current) => {
      const next = new Set(current)
      if (checked) next.add(orderId)
      else next.delete(orderId)
      return next
    })
  }

  function toggleSelectPage(orderIds: string[], checked: boolean) {
    setSelectedIds((current) => {
      const next = new Set(current)
      for (const id of orderIds) {
        if (checked) next.add(id)
        else next.delete(id)
      }
      return next
    })
  }

  function clearSelection() {
    setSelectedIds(new Set())
  }

  const counts = useMemo(() => countByStatus(orders), [orders])
  const visibleOrders = useMemo(
    () =>
      orders
        ?.filter((order) => tab === 'all' || order.fulfillment_status === tab)
        .filter((order) => matchesSearch(order, search)),
    [orders, tab, search],
  )
  const isSearching = search.trim() !== ''

  const sortedOrders = useMemo(() => {
    if (!visibleOrders || sort.column !== 'placed_at') return visibleOrders
    const copy = [...visibleOrders]
    copy.sort((a, b) => {
      const diff = new Date(a.placed_at).getTime() - new Date(b.placed_at).getTime()
      return sort.direction === 'asc' ? diff : -diff
    })
    return copy
  }, [visibleOrders, sort])

  const totalPages = sortedOrders ? Math.max(1, Math.ceil(sortedOrders.length / PAGE_SIZE)) : 1

  // Bounds-safety clamp for when the underlying set shrinks (e.g. an order
  // moves off the current tab on a poll refresh) and the current page no
  // longer exists -- distinct from the tab/search/range reset above, which
  // always jumps back to page 1. Only fires when totalPages itself changes,
  // not on every poll tick.
  useEffect(() => {
    setPage((current) => Math.min(current, totalPages))
  }, [totalPages])

  const pagedOrders = sortedOrders?.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const pageOrderIds = useMemo(
    () => pagedOrders?.map((order) => order.order_id) ?? [],
    [pagedOrders],
  )
  const allPageSelected = pageOrderIds.length > 0 && pageOrderIds.every((id) => selectedIds.has(id))
  const somePageSelected = !allPageSelected && pageOrderIds.some((id) => selectedIds.has(id))

  const selectedOrders = useMemo(
    () => orders?.filter((order) => selectedIds.has(order.order_id)) ?? [],
    [orders, selectedIds],
  )
  const bulkActions = useMemo(() => computeBulkActions(selectedOrders), [selectedOrders])

  function runBulkStatusChange(status: FulfillmentStatus) {
    for (const order of selectedOrders) {
      updateStatus.mutate({ orderId: order.order_id, toStatus: status })
    }
    clearSelection()
  }

  function handleBulkAction(status: FulfillmentStatus) {
    if (status === 'cancelled') {
      setBulkCancelOpen(true)
      return
    }
    runBulkStatusChange(status)
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Orders"
        description="Live order queue -- change status right here, or expand a row for full details."
        actions={<DateRangeFilter value={range} onChange={selectRange} />}
      />

      <CreateTestOrderForm />

      <Input
        type="search"
        placeholder="Search by order ID or customer ID…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="max-w-sm"
        aria-label="Search orders"
      />

      <Tabs value={tab} onValueChange={(value) => selectTab(value as FulfillmentStatus | 'all')}>
        <TabsList>
          {TABS.map((status) => (
            <TabsTrigger key={status} value={status}>
              {status === 'all' ? 'All' : STATUS_LABELS[status]}
              <span
                className={cn(
                  'rounded-full px-1.5 py-0.5 text-xs font-semibold',
                  tab === status ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground',
                )}
              >
                {counts[status]}
              </span>
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <Card className="overflow-hidden py-0">
        {selectedIds.size > 0 && (
          <div className="bg-muted/50 border-border flex flex-wrap items-center gap-2 border-b px-4 py-2.5">
            <span className="text-sm font-medium">{selectedIds.size} selected</span>
            <Button type="button" size="sm" variant="ghost" onClick={clearSelection}>
              Clear
            </Button>
            <div className="ml-auto flex flex-wrap items-center gap-2">
              {bulkActions.map((status) => (
                <Button
                  key={status}
                  type="button"
                  size="sm"
                  variant={status === 'cancelled' ? 'destructive' : 'outline'}
                  onClick={() => handleBulkAction(status)}
                >
                  Mark {STATUS_LABELS[status]}
                </Button>
              ))}
              {bulkActions.length === 0 && (
                <span className="text-muted-foreground text-sm">No shared next status.</span>
              )}
            </div>
          </div>
        )}
        {/* Table's own wrapper sets `overflow-x-auto`, which per the CSS
            overflow spec silently computes its `overflow-y` to `auto` too
            (a non-`visible` value on one axis forces the other off
            `visible`) -- that makes IT the nearest scrolling ancestor for
            sticky's purposes instead of this div, even though it never
            actually scrolls, which breaks the sticky header entirely.
            `[&>div]:overflow-visible` neutralizes that inner wrapper so
            this outer div (which handles both axes itself) is the only
            real scroll container. */}
        <div className="max-h-[32rem] overflow-auto [&>div]:overflow-visible">
          <Table>
            {/* `position: sticky` on <thead> itself (table-header-group) isn't
                honored by Blink's table layout -- it has to go on each <th>
                individually for the header row to actually pin while the
                body scrolls underneath it. */}
            <TableHeader>
              <TableRow>
                <TableHead className={cn(STICKY_HEAD_CLASS, 'w-10')}>
                  <Checkbox
                    aria-label="Select all orders on this page"
                    checked={allPageSelected ? true : somePageSelected ? 'indeterminate' : false}
                    onCheckedChange={(checked) => toggleSelectPage(pageOrderIds, checked === true)}
                    disabled={pageOrderIds.length === 0}
                  />
                </TableHead>
                <TableHead className={cn(STICKY_HEAD_CLASS, 'w-8')} />
                <TableHead className={STICKY_HEAD_CLASS}>Order</TableHead>
                <TableHead className={STICKY_HEAD_CLASS}>Customer</TableHead>
                <TableHead className={STICKY_HEAD_CLASS}>
                  <button
                    type="button"
                    onClick={toggleSort}
                    className="hover:text-foreground -ml-1 inline-flex items-center gap-1 rounded px-1 py-0.5 transition-colors duration-150"
                  >
                    Placed
                    {sort.column === 'placed_at' ? (
                      sort.direction === 'asc' ? (
                        <ArrowUp className="size-3.5" />
                      ) : (
                        <ArrowDown className="size-3.5" />
                      )
                    ) : (
                      <ArrowUpDown className="size-3.5 opacity-50" />
                    )}
                  </button>
                </TableHead>
                <TableHead className={STICKY_HEAD_CLASS}>Items</TableHead>
                <TableHead className={STICKY_HEAD_CLASS}>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading &&
                Array.from({ length: SKELETON_ROW_COUNT }).map((_, i) => (
                  // Transient placeholder rows with no identity of their own -- index keys are fine here.
                  // biome-ignore lint/suspicious/noArrayIndexKey: skeleton placeholders have no stable identity
                  <TableRow key={`orders-skeleton-${i}`} className="hover:bg-transparent">
                    <TableCell className="py-2.5">
                      <Skeleton className="size-4 rounded-[4px]" />
                    </TableCell>
                    <TableCell className="py-2.5">
                      <Skeleton className="size-4 rounded-full" />
                    </TableCell>
                    <TableCell className="py-2.5">
                      <Skeleton className="h-4 w-14" />
                    </TableCell>
                    <TableCell className="py-2.5">
                      <Skeleton className="h-4 w-32" />
                    </TableCell>
                    <TableCell className="py-2.5">
                      <Skeleton className="h-4 w-28" />
                    </TableCell>
                    <TableCell className="py-2.5">
                      <Skeleton className="h-4 w-6" />
                    </TableCell>
                    <TableCell className="py-2.5">
                      <Skeleton className="h-5 w-20 rounded-full" />
                    </TableCell>
                  </TableRow>
                ))}
              {!isLoading && visibleOrders?.length === 0 && (
                <TableRow className="hover:bg-transparent">
                  <TableCell colSpan={COLUMN_COUNT}>
                    <EmptyState
                      icon={isSearching ? Search : Inbox}
                      title={
                        isSearching
                          ? `No orders match "${search}".`
                          : tab === 'all'
                            ? 'No orders yet.'
                            : `No ${STATUS_LABELS[tab].toLowerCase()} orders.`
                      }
                    />
                  </TableCell>
                </TableRow>
              )}
              {pagedOrders?.map((order) => {
                const isExpanded = expandedOrderId === order.order_id
                const isSelected = selectedIds.has(order.order_id)
                const detailRowId = `order-detail-${order.order_id}`
                return (
                  <Fragment key={order.order_id}>
                    <TableRow
                      onClick={() => toggleExpanded(order.order_id)}
                      aria-expanded={isExpanded}
                      aria-controls={detailRowId}
                      className={cn(
                        'cursor-pointer',
                        isExpanded && 'bg-muted/40',
                        isSelected && !isExpanded && 'bg-primary/5',
                      )}
                    >
                      <TableCell className="py-2.5" onClick={(e) => e.stopPropagation()}>
                        <Checkbox
                          aria-label={`Select order ${formatOrderNumber(order.order_number)}`}
                          checked={isSelected}
                          onCheckedChange={(checked) =>
                            toggleSelectOne(order.order_id, checked === true)
                          }
                        />
                      </TableCell>
                      <TableCell className="py-2.5">
                        <Button
                          type="button"
                          size="icon"
                          variant="ghost"
                          aria-label={
                            isExpanded
                              ? `Collapse order ${formatOrderNumber(order.order_number)}`
                              : `Expand order ${formatOrderNumber(order.order_number)}`
                          }
                          aria-expanded={isExpanded}
                          onClick={(e) => {
                            e.stopPropagation()
                            toggleExpanded(order.order_id)
                          }}
                        >
                          <ChevronDown
                            className={cn(
                              'text-muted-foreground size-4 transition-transform duration-150',
                              isExpanded && 'rotate-180',
                            )}
                          />
                        </Button>
                      </TableCell>
                      <TableCell className="text-primary py-2.5 font-medium">
                        {formatOrderNumber(order.order_number)}
                      </TableCell>
                      <TableCell className="py-2.5 font-medium">
                        {order.customer_name ?? formatPhoneNumber(order.customer_whatsapp_number)}
                      </TableCell>
                      <TableCell className="text-muted-foreground py-2.5">
                        {formatDateTime(order.placed_at)}
                      </TableCell>
                      <TableCell className="py-2.5 tabular-nums">{order.items.length}</TableCell>
                      <TableCell className="py-2.5">
                        <StatusActionsMenu order={order} />
                      </TableCell>
                    </TableRow>
                    {isExpanded && (
                      <ExpandedOrderRow orderId={order.order_id} rowId={detailRowId} />
                    )}
                  </Fragment>
                )
              })}
            </TableBody>
          </Table>
        </div>
        {totalPages > 1 && (
          <Pagination className="border-border border-t px-4 py-3">
            <PaginationInfo>
              Page {page} of {totalPages}
            </PaginationInfo>
            <PaginationContent>
              <PaginationItem>
                <PaginationPrevious
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                />
              </PaginationItem>
              <PaginationItem>
                <PaginationNext
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                />
              </PaginationItem>
            </PaginationContent>
          </Pagination>
        )}
      </Card>

      <CancelOrderDialog
        open={bulkCancelOpen}
        onOpenChange={setBulkCancelOpen}
        count={selectedOrders.length}
        onConfirm={() => runBulkStatusChange('cancelled')}
      />
    </div>
  )
}
