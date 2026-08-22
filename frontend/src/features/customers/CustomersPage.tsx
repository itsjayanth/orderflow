import { zodResolver } from '@hookform/resolvers/zod'
import { ChevronDown, Search, UserPlus, Users } from 'lucide-react'
import { Fragment, useEffect, useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useSearchParams } from 'react-router-dom'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Pagination,
  PaginationContent,
  PaginationInfo,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination'
import { Sheet } from '@/components/ui/sheet'
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
import { ApiError } from '@/shared/api/client'
import type { CustomerOut } from '@/shared/api/types'
import { EmptyState } from '@/shared/components/EmptyState'
import { PageHeader } from '@/shared/components/PageHeader'
import { formatCustomerNumber } from '@/shared/lib/customerNumber'
import { formatPhoneNumber } from '@/shared/lib/phoneNumber'

import { CustomerDetailCard } from './CustomerDetailCard'
import { RemoveCustomerDialog } from './RemoveCustomerDialog'
import { useCreateCustomer } from './useCreateCustomer'
import { useCustomers } from './useCustomers'
import { useUpdateCustomer } from './useUpdateCustomer'

type TimelineFilter = 'all' | '7d' | '30d'

const TIMELINE_OPTIONS: { value: TimelineFilter; label: string }[] = [
  { value: 'all', label: 'All time' },
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
]

// Purely client-side pagination -- useCustomers is a one-shot fetch (no
// polling, unlike Orders' 5s refetch), so page/selection only need to reset
// on an actual filter change, not guard against a poll tick resetting them
// out from under the user.
const PAGE_SIZE = 15
const SKELETON_ROW_COUNT = 5

// Leading checkbox + expand-chevron columns, plus Customer ID and Name --
// the list is deliberately just enough to recognize a customer at a
// glance. Everything else (phone, addresses, email, status, order
// history, edit/remove actions) lives one click away in the expanded
// CustomerDetailCard, mirroring OrdersPage's "monitoring row expands into
// a rich detail card" pattern.
const COLUMN_COUNT = 4

// Applied per-<th> rather than on <thead> -- see OrdersPage.tsx for why
// (Blink doesn't honor `position: sticky` on <thead> itself).
const STICKY_HEAD_CLASS = 'bg-card border-border sticky top-0 z-10 border-b'

function isTimelineFilter(value: string | null): value is TimelineFilter {
  return value === 'all' || value === '7d' || value === '30d'
}

function customerLabel(customer: CustomerOut): string {
  return customer.display_name ?? formatPhoneNumber(customer.whatsapp_number)
}

function matchesSearch(customer: CustomerOut, query: string): boolean {
  const q = query.trim().toLowerCase().replace(/^#/, '')
  if (!q) return true

  const nameMatch = customer.display_name?.toLowerCase().includes(q) ?? false
  const idMatch =
    String(customer.customer_number).includes(q) ||
    formatCustomerNumber(customer.customer_number).toLowerCase().includes(q)

  // Strip non-digits so "98765", "+91 98765", and "9876543210" all match
  // against the raw stored number the same way CatalogPage strips a
  // leading "#" before matching item numbers.
  const digitsQuery = q.replace(/\D/g, '')
  const phoneMatch =
    digitsQuery.length > 0 && customer.whatsapp_number.replace(/\D/g, '').includes(digitsQuery)

  return nameMatch || idMatch || phoneMatch
}

function matchesTimeline(customer: CustomerOut, filter: TimelineFilter, now: Date): boolean {
  if (filter === 'all') return true
  if (!customer.last_order_at) return false

  const days = filter === '7d' ? 7 : 30
  const cutoffMs = now.getTime() - days * 24 * 60 * 60 * 1000
  return new Date(customer.last_order_at).getTime() >= cutoffMs
}

function countByTimeline(customers: CustomerOut[] | undefined): Record<TimelineFilter, number> {
  const now = new Date()
  const counts: Record<TimelineFilter, number> = { all: customers?.length ?? 0, '7d': 0, '30d': 0 }
  for (const customer of customers ?? []) {
    if (matchesTimeline(customer, '7d', now)) counts['7d'] += 1
    if (matchesTimeline(customer, '30d', now)) counts['30d'] += 1
  }
  return counts
}

const customerFormSchema = z.object({
  whatsapp_number: z
    .string()
    .min(6, 'Enter a valid WhatsApp number')
    .max(32, 'Enter a valid WhatsApp number'),
  display_name: z.string().max(255).optional(),
  default_contact_phone: z.string().max(32).optional(),
})

type CustomerFormValues = z.infer<typeof customerFormSchema>

interface CustomerFormSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  editingCustomer: CustomerOut | null
}

function CustomerFormSheet({ open, onOpenChange, editingCustomer }: CustomerFormSheetProps) {
  const createCustomer = useCreateCustomer()
  const updateCustomer = useUpdateCustomer()
  const isEditing = editingCustomer !== null
  const isPending = createCustomer.isPending || updateCustomer.isPending

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CustomerFormValues>({ resolver: zodResolver(customerFormSchema) })

  // biome-ignore lint/correctness/useExhaustiveDependencies: reset/createCustomer.reset/updateCustomer.reset are re-created every render by useForm/useMutation -- including them would re-clear in-progress edits on every keystroke.
  useEffect(() => {
    if (!open) return
    reset({
      whatsapp_number: editingCustomer?.whatsapp_number ?? '',
      display_name: editingCustomer?.display_name ?? '',
      default_contact_phone: editingCustomer?.default_contact_phone ?? '',
    })
    createCustomer.reset()
    updateCustomer.reset()
  }, [open, editingCustomer])

  const onSubmit = (data: CustomerFormValues) => {
    const displayName = data.display_name?.trim() || undefined
    const defaultContactPhone = data.default_contact_phone?.trim() || undefined

    if (isEditing) {
      updateCustomer.mutate(
        {
          customer_id: editingCustomer.customer_id,
          display_name: displayName,
          default_contact_phone: defaultContactPhone,
        },
        { onSuccess: () => onOpenChange(false) },
      )
    } else {
      createCustomer.mutate(
        {
          whatsapp_number: data.whatsapp_number.trim(),
          display_name: displayName,
          default_contact_phone: defaultContactPhone,
        },
        { onSuccess: () => onOpenChange(false) },
      )
    }
  }

  const mutationError = isEditing ? updateCustomer.error : createCustomer.error

  return (
    <Sheet
      open={open}
      onOpenChange={onOpenChange}
      title={isEditing ? 'Edit customer' : 'Add customer'}
      footer={
        <Button type="submit" form="customer-form" className="w-full" disabled={isPending}>
          {isPending ? 'Saving…' : isEditing ? 'Save changes' : 'Save customer'}
        </Button>
      }
    >
      <form id="customer-form" onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="whatsapp_number">WhatsApp number</Label>
          <Input
            id="whatsapp_number"
            placeholder="+91 98765 43210"
            disabled={isEditing}
            {...register('whatsapp_number')}
          />
          {isEditing ? (
            <p className="text-muted-foreground text-xs">
              The WhatsApp number can't be changed — it's how incoming messages are matched to this
              customer.
            </p>
          ) : (
            errors.whatsapp_number && (
              <p className="text-destructive text-sm">{errors.whatsapp_number.message}</p>
            )
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="display_name">Name</Label>
          <Input id="display_name" placeholder="Asha Rao" {...register('display_name')} />
        </div>

        <div className="space-y-2">
          <Label htmlFor="default_contact_phone">Delivery contact number (optional)</Label>
          <Input
            id="default_contact_phone"
            placeholder="Use WhatsApp number by default"
            {...register('default_contact_phone')}
          />
        </div>

        {mutationError && (
          <p className="text-destructive text-sm">
            {mutationError instanceof ApiError && mutationError.status === 409
              ? 'A customer with this WhatsApp number already exists.'
              : 'Something went wrong. Please try again.'}
          </p>
        )}
      </form>
    </Sheet>
  )
}

// What's being confirmed in RemoveCustomerDialog -- a single row's Remove
// action (row-level or from inside the expanded detail card), or the
// bulk-bar's "Remove selected" (which only ever targets the *active*
// customers within the current selection; removing an already-removed
// customer is meaningless).
type RemoveTarget = { kind: 'single'; customer: CustomerOut } | { kind: 'bulk' }

export function CustomersPage() {
  const [showRemoved, setShowRemoved] = useState(false)
  const { data: customers, isLoading, isError } = useCustomers(showRemoved)
  const updateCustomer = useUpdateCustomer()
  const [search, setSearch] = useState('')
  const [searchParams, setSearchParams] = useSearchParams()
  const timelineParam = searchParams.get('timeline')
  const [timeline, setTimeline] = useState<TimelineFilter>(
    isTimelineFilter(timelineParam) ? timelineParam : 'all',
  )
  const [sheetOpen, setSheetOpen] = useState(false)
  const [editingCustomer, setEditingCustomer] = useState<CustomerOut | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [expandedCustomerId, setExpandedCustomerId] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [removeTarget, setRemoveTarget] = useState<RemoveTarget | null>(null)

  // The meaning of "selected" (and of "page 1") resets whenever the visible
  // set fundamentally changes.
  // biome-ignore lint/correctness/useExhaustiveDependencies: intentional reset trigger -- these values aren't read in the body, only watched
  useEffect(() => {
    setPage(1)
    setSelectedIds(new Set())
  }, [search, timeline, showRemoved])

  function selectTimeline(next: TimelineFilter) {
    setTimeline(next)
    setSearchParams(next === 'all' ? {} : { timeline: next })
  }

  function openCreateSheet() {
    setEditingCustomer(null)
    setSheetOpen(true)
  }

  function openEditSheet(customer: CustomerOut) {
    setEditingCustomer(customer)
    setSheetOpen(true)
  }

  function toggleExpanded(customerId: string) {
    setExpandedCustomerId((current) => (current === customerId ? null : customerId))
  }

  function toggleSelectOne(customerId: string, checked: boolean) {
    setSelectedIds((current) => {
      const next = new Set(current)
      if (checked) next.add(customerId)
      else next.delete(customerId)
      return next
    })
  }

  function toggleSelectPage(customerIds: string[], checked: boolean) {
    setSelectedIds((current) => {
      const next = new Set(current)
      for (const id of customerIds) {
        if (checked) next.add(id)
        else next.delete(id)
      }
      return next
    })
  }

  function clearSelection() {
    setSelectedIds(new Set())
  }

  const counts = useMemo(() => countByTimeline(customers), [customers])

  const visibleCustomers = useMemo(() => {
    const now = new Date()
    return customers?.filter(
      (customer) => matchesSearch(customer, search) && matchesTimeline(customer, timeline, now),
    )
  }, [customers, search, timeline])

  const isFiltering = search.trim() !== '' || timeline !== 'all'

  const totalPages = visibleCustomers
    ? Math.max(1, Math.ceil(visibleCustomers.length / PAGE_SIZE))
    : 1

  // Bounds-safety clamp for when the underlying set shrinks (e.g. a
  // customer is removed while "Show removed" is off) and the current page
  // no longer exists.
  useEffect(() => {
    setPage((current) => Math.min(current, totalPages))
  }, [totalPages])

  const pagedCustomers = visibleCustomers?.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const pageCustomerIds = useMemo(
    () => pagedCustomers?.map((customer) => customer.customer_id) ?? [],
    [pagedCustomers],
  )
  const allPageSelected =
    pageCustomerIds.length > 0 && pageCustomerIds.every((id) => selectedIds.has(id))
  const somePageSelected = !allPageSelected && pageCustomerIds.some((id) => selectedIds.has(id))

  const selectedCustomers = useMemo(
    () => customers?.filter((customer) => selectedIds.has(customer.customer_id)) ?? [],
    [customers, selectedIds],
  )
  const activeSelected = useMemo(
    () => selectedCustomers.filter((customer) => customer.is_active),
    [selectedCustomers],
  )
  const inactiveSelected = useMemo(
    () => selectedCustomers.filter((customer) => !customer.is_active),
    [selectedCustomers],
  )

  function runBulkRestore() {
    for (const customer of inactiveSelected) {
      updateCustomer.mutate({ customer_id: customer.customer_id, is_active: true })
    }
    clearSelection()
  }

  const removeDialogCount = removeTarget?.kind === 'bulk' ? activeSelected.length : 1
  const removeDialogLabel =
    removeTarget?.kind === 'single' ? customerLabel(removeTarget.customer) : undefined

  function confirmRemove() {
    if (!removeTarget) return
    if (removeTarget.kind === 'single') {
      updateCustomer.mutate({ customer_id: removeTarget.customer.customer_id, is_active: false })
    } else {
      for (const customer of activeSelected) {
        updateCustomer.mutate({ customer_id: customer.customer_id, is_active: false })
      }
      clearSelection()
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Customers"
        description="Everyone who has messaged your WhatsApp number, plus anyone you add manually. Expand a row for full details."
        actions={
          <Button type="button" onClick={openCreateSheet}>
            <UserPlus />
            Add customer
          </Button>
        }
      />

      {isError && (
        <p className="text-destructive text-sm">Failed to load customers. Please try again.</p>
      )}

      {!isError && (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <Input
              type="search"
              placeholder="Search by customer ID, name, or phone…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="max-w-sm"
              aria-label="Search customers"
            />
            <Button
              type="button"
              size="sm"
              variant={showRemoved ? 'default' : 'outline'}
              className={cn('ml-auto', !showRemoved && 'text-muted-foreground')}
              onClick={() => setShowRemoved((v) => !v)}
            >
              {showRemoved ? 'Showing removed' : 'Show removed'}
            </Button>
          </div>

          <Tabs value={timeline} onValueChange={(value) => selectTimeline(value as TimelineFilter)}>
            <TabsList>
              {TIMELINE_OPTIONS.map((option) => (
                <TabsTrigger key={option.value} value={option.value}>
                  {option.label}
                  <span
                    className={cn(
                      'rounded-full px-1.5 py-0.5 text-xs font-semibold',
                      timeline === option.value
                        ? 'bg-primary/10 text-primary'
                        : 'bg-muted text-muted-foreground',
                    )}
                  >
                    {counts[option.value]}
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
                  {inactiveSelected.length > 0 && (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={updateCustomer.isPending}
                      onClick={runBulkRestore}
                    >
                      Restore selected
                    </Button>
                  )}
                  {activeSelected.length > 0 && (
                    <Button
                      type="button"
                      size="sm"
                      variant="destructive"
                      disabled={updateCustomer.isPending}
                      onClick={() => setRemoveTarget({ kind: 'bulk' })}
                    >
                      Remove selected
                    </Button>
                  )}
                </div>
              </div>
            )}
            {/* See OrdersPage.tsx's identical wrapper for why
                `[&>div]:overflow-visible` is needed here -- Table's own
                wrapper div sets `overflow-x-auto`, which forces its
                `overflow-y` to `auto` too and makes IT the nearest
                scrolling ancestor instead of this div, breaking sticky. */}
            <div className="max-h-[32rem] overflow-auto [&>div]:overflow-visible">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className={cn(STICKY_HEAD_CLASS, 'w-10')}>
                      <Checkbox
                        aria-label="Select all customers on this page"
                        checked={
                          allPageSelected ? true : somePageSelected ? 'indeterminate' : false
                        }
                        onCheckedChange={(checked) =>
                          toggleSelectPage(pageCustomerIds, checked === true)
                        }
                        disabled={pageCustomerIds.length === 0}
                      />
                    </TableHead>
                    <TableHead className={cn(STICKY_HEAD_CLASS, 'w-8')} />
                    <TableHead className={STICKY_HEAD_CLASS}>Customer ID</TableHead>
                    <TableHead className={STICKY_HEAD_CLASS}>Name</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {isLoading &&
                    Array.from({ length: SKELETON_ROW_COUNT }).map((_, i) => (
                      // Transient placeholder rows with no identity of their own -- index keys are fine here.
                      // biome-ignore lint/suspicious/noArrayIndexKey: skeleton placeholders have no stable identity
                      <TableRow key={`customers-skeleton-${i}`} className="hover:bg-transparent">
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
                      </TableRow>
                    ))}

                  {!isLoading && customers && customers.length === 0 && (
                    <TableRow className="hover:bg-transparent">
                      <TableCell colSpan={COLUMN_COUNT}>
                        <EmptyState
                          icon={Users}
                          title="No customers yet. Add one to get started."
                        />
                      </TableCell>
                    </TableRow>
                  )}

                  {!isLoading &&
                    customers &&
                    customers.length > 0 &&
                    visibleCustomers?.length === 0 && (
                      <TableRow className="hover:bg-transparent">
                        <TableCell colSpan={COLUMN_COUNT}>
                          <EmptyState
                            icon={isFiltering ? Search : Users}
                            title={
                              isFiltering
                                ? 'No customers match your search or filter.'
                                : 'No customers yet.'
                            }
                          />
                        </TableCell>
                      </TableRow>
                    )}

                  {!isLoading &&
                    pagedCustomers?.map((customer) => {
                      const isSelected = selectedIds.has(customer.customer_id)
                      const isExpanded = expandedCustomerId === customer.customer_id
                      const label = customerLabel(customer)
                      const detailRowId = `customer-detail-${customer.customer_id}`
                      return (
                        <Fragment key={customer.customer_id}>
                          <TableRow
                            onClick={() => toggleExpanded(customer.customer_id)}
                            aria-expanded={isExpanded}
                            aria-controls={detailRowId}
                            className={cn(
                              'cursor-pointer',
                              !customer.is_active && 'opacity-60',
                              isExpanded && 'bg-muted/40',
                              isSelected && !isExpanded && 'bg-primary/5',
                            )}
                          >
                            <TableCell className="py-2.5" onClick={(e) => e.stopPropagation()}>
                              <Checkbox
                                aria-label={`Select ${label}`}
                                checked={isSelected}
                                onCheckedChange={(checked) =>
                                  toggleSelectOne(customer.customer_id, checked === true)
                                }
                              />
                            </TableCell>
                            <TableCell className="py-2.5">
                              <Button
                                type="button"
                                size="icon"
                                variant="ghost"
                                aria-label={isExpanded ? `Collapse ${label}` : `Expand ${label}`}
                                aria-expanded={isExpanded}
                                onClick={(e) => {
                                  e.stopPropagation()
                                  toggleExpanded(customer.customer_id)
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
                            <TableCell className="text-muted-foreground py-2.5 font-mono text-sm">
                              {formatCustomerNumber(customer.customer_number)}
                            </TableCell>
                            <TableCell className="py-2.5 font-medium">{label}</TableCell>
                          </TableRow>
                          {isExpanded && (
                            <TableRow id={detailRowId} className="hover:bg-transparent">
                              <TableCell
                                colSpan={COLUMN_COUNT}
                                className="bg-muted/30 whitespace-normal p-5"
                              >
                                <CustomerDetailCard
                                  customer={customer}
                                  onEdit={openEditSheet}
                                  onRemove={(target) =>
                                    setRemoveTarget({ kind: 'single', customer: target })
                                  }
                                />
                              </TableCell>
                            </TableRow>
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
        </>
      )}

      <CustomerFormSheet
        open={sheetOpen}
        onOpenChange={setSheetOpen}
        editingCustomer={editingCustomer}
      />

      <RemoveCustomerDialog
        open={removeTarget !== null}
        onOpenChange={(open) => {
          if (!open) setRemoveTarget(null)
        }}
        count={removeDialogCount}
        customerLabel={removeDialogLabel}
        onConfirm={confirmRemove}
      />
    </div>
  )
}
