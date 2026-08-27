// Same "#0001" convention as shared/lib/orderNumber.ts's formatOrderNumber,
// applied to items instead of orders.
export function formatItemNumber(itemNumber: number): string {
  return `#${String(itemNumber).padStart(4, '0')}`
}
