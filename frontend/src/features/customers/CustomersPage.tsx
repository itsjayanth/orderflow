import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

import { useCustomers } from './useCustomers'

function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleDateString()
}

export function CustomersPage() {
  const { data: customers, isLoading, isError } = useCustomers()

  return (
    <div className="space-y-4">
      <div className="space-y-2">
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
            ) : (
              customers.map((customer) => (
                <TableRow key={customer.customer_id}>
                  <TableCell>{customer.display_name ?? customer.whatsapp_number}</TableCell>
                  <TableCell>{customer.whatsapp_number}</TableCell>
                  <TableCell>{formatDate(customer.last_order_at)}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      )}
    </div>
  )
}
