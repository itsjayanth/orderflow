import type * as React from 'react'

import { cn } from '@/lib/utils'

// Extracts the header markup duplicated at the top of OrdersPage,
// CustomersPage, CatalogPage, DashboardHomePage, OnboardingPage, and
// SettingsPage (`<h1 className="text-2xl font-semibold">` + a
// `text-muted-foreground text-sm` description + a right-aligned actions
// slot). Not yet wired into any of those pages -- that call-site
// migration is a later phase; this is just the reusable primitive.
interface PageHeaderProps {
  title: string
  description?: string
  actions?: React.ReactNode
  className?: string
}

export function PageHeader({ title, description, actions, className }: PageHeaderProps) {
  return (
    <div className={cn('flex flex-wrap items-end justify-between gap-4', className)}>
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">{title}</h1>
        {description && <p className="text-muted-foreground text-sm">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}
