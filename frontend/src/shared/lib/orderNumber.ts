// Matches the "#0001" formatting used in WhatsApp notification messages
// (backend/src/notifications/adapters/whatsapp_channel.py's `order_number`
// context variable) so the same order reads the same everywhere.
export function formatOrderNumber(orderNumber: number): string {
  return `#${String(orderNumber).padStart(4, '0')}`
}
