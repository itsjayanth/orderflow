import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { cn } from '@/lib/utils'
import type { CustomerOut } from '@/shared/api/types'
import { formatPhoneNumber } from '@/shared/lib/phoneNumber'

import { useCustomers } from './useCustomers'

type TimelineFilter = 'all' | '7d' | '30d'

const TIMELINE_OPTIONS: { value: TimelineFilter; label: string }[] = [
  { value: 'all', label: 'All time' },
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
]

function isTimelineFilter(value: string | null): value is TimelineFilter {
  return value === 'all' || value === '7d' || value === '30d'
}

function matchesSearch(customer: CustomerOut, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true

  const nameMatch = customer.display_name?.toLowerCase().includes(q) ?? false

  // Strip non-digits so "98765", "+91 98765", and "9876543210" all match
  // against the raw stored number the same way CatalogPage strips a
  // leading "#" before matching item numbers.
  const digitsQuery = q.replace(/\D/g, '')
  const phoneMatch =
    digitsQuery.length > 0 && customer.whatsapp_number.replace(/\D/g, '').includes(digitsQuery)

  return nameMatch || phoneMatch
}

function matchesTimeline(customer: CustomerOut, filter: TimelineFilter, now: Date): boolean {
  if (filter === 'all') return true
  if (!customer.last_order_at) return false

  const days = filter === '7d' ? 7 : 30
  const cutoffMs = now.getTime() - days * 24 * 60 * 60 * 1000
  return new Date(customer.last_order_at).getTime() >= cutoffMs
}

function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleDateString()
}

export function CustomersPage() {
  const { data: customers, isLoading, isError } = useCustomers()
  const [search, setSearch] = useState('')
  const [searchParams, setSearchParams] = useSearchParams()
  const timelineParam = searchParams.get('timeline')
  const [timeline, setTimeline] = useState<TimelineFilter>(
    isTimelineFilter(timelineParam) ? timelineParam : 'all',
  )

  function selectTimeline(next: TimelineFilter) {
    setTimeline(next)
    setSearchParams(next === 'all' ? {} : { timeline: next })
  }

  const visibleCustomers = useMemo(() => {
    const now = new Date()
    return customers?.filter(
      (customer) => matchesSearch(customer, search) && matchesTimeline(customer, timeline, now),
    )
  }, [customers, search, timeline])

  const isFiltering = search.trim() !== '' || timeline !== 'all'

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Customers</h1>
        <p className="text-muted-foreground text-sm">
          Customers who have messaged your WhatsApp number.
        </p>
      </div>

      {isLoading && <p className="text-muted-foreground text-sm">Loading customers…</p>}
      {isError && (
        <p className="text-destructive text-sm">Failed to load customers. Please try again.</p>
      )}

      {customers && (
        <>
          {customers.length > 0 && (
            <div className="flex flex-wrap items-center gap-3">
              <Input
                type="search"
                placeholder="Search by name or phone…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="max-w-sm"
                aria-label="Search customers"
              />
              <div className="flex flex-wrap gap-1">
                {TIMELINE_OPTIONS.map((option) => (
                  <Button
                    key={option.value}
                    type="button"
                    size="sm"
                    variant={timeline === option.value ? 'default' : 'outline'}
                    onClick={() => selectTimeline(option.value)}
                    className={cn(timeline !== option.value && 'text-muted-foreground')}
                  >
                    {option.label}
                  </Button>
                ))}
              </div>
            </div>
          )}

          <Card className="overflow-hidden py-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Phone</TableHead>
                  <TableHead>Last order</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {customers.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={3} className="text-muted-foreground text-center">
                      No customers yet.
                    </TableCell>
                  </TableRow>
                ) : visibleCustomers?.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={3} className="text-muted-foreground text-center">
                      {isFiltering
                        ? 'No customers match your search or filter.'
                        : 'No customers yet.'}
                    </TableCell>
                  </TableRow>
                ) : (
                  visibleCustomers?.map((customer) => (
                    <TableRow key={customer.customer_id}>
                      <TableCell>
                        {customer.display_name ?? formatPhoneNumber(customer.whatsapp_number)}
                      </TableCell>
                      <TableCell>{formatPhoneNumber(customer.whatsapp_number)}</TableCell>
                      <TableCell>{formatDate(customer.last_order_at)}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </Card>
        </>
      )}
    </div>
  )
}
