// Same "#0001" convention as shared/lib/orderNumber.ts's formatOrderNumber
// and shared/lib/customerNumber.ts's formatCustomerNumber, applied to
// appointments.
export function formatAppointmentNumber(appointmentNumber: number): string {
  return `#${String(appointmentNumber).padStart(4, '0')}`
}
