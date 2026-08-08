// Same "#0001" convention as shared/lib/orderNumber.ts's formatOrderNumber
// and shared/lib/itemNumber.ts's formatItemNumber, applied to customers.
export function formatCustomerNumber(customerNumber: number): string {
  return `#${String(customerNumber).padStart(4, '0')}`
}
