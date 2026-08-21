// Shared with DashboardHomePage.tsx (hero revenue figure) and
// DashboardTrendChart.tsx (chart axis/tooltip) so both read the exact same
// formatting -- pulled out once two call-sites needed it instead of
// keeping two copies in sync by hand.
export function formatCurrency(value: string | number | undefined, currency = 'INR'): string {
  const amount = Number(value ?? 0)
  return `${currency} ${new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(amount)}`
}

// A shorter form for tight spaces (chart Y-axis ticks) -- e.g. "INR 1.2k"
// instead of "INR 1,234.00".
export function formatCompactCurrency(value: number, currency = 'INR'): string {
  return `${currency} ${new Intl.NumberFormat('en-IN', { notation: 'compact', maximumFractionDigits: 1 }).format(value)}`
}
