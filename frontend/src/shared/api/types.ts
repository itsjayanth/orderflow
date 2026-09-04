export interface AccessTokenResponse {
  access_token: string
  token_type: string
}

export type MerchantVertical = 'restaurant' | 'appointment'

export interface Merchant {
  merchant_id: string
  business_name: string
  onboarding_status: string
  restaurant_enabled: boolean
  appointment_enabled: boolean
  website_url: string | null
}

export interface StaffUser {
  staff_user_id: string
  name: string
  email_or_phone: string
  role: string
  last_login_at: string | null
}

export interface MeResponse {
  staff_user: StaffUser
  merchant: Merchant
}

export interface CustomerOut {
  customer_id: string
  customer_number: number
  whatsapp_number: string
  display_name: string | null
  default_contact_phone: string | null
  email: string | null
  first_seen_at: string
  last_order_at: string | null
  is_active: boolean
  // Read-only -- only the customer's own STOP/START WhatsApp message
  // changes this (see backend/src/conversation/domain/handler.py); no
  // dashboard write path exists.
  marketing_opt_out: boolean
  marketing_opt_out_at: string | null
}

export interface AddressOut {
  address_id: string
  label: string
  line1: string
  line2: string | null
  landmark: string | null
  city: string
  pincode: string
  geo_lat: number | null
  geo_long: number | null
  is_default: boolean
  created_at: string
}

export interface CustomerWithAddressesOut extends CustomerOut {
  addresses: AddressOut[]
}

export interface Item {
  item_id: string
  item_number: number
  category: string
  name: string
  price: string
  is_available: boolean
  image_url: string | null
  created_at: string
  updated_at: string
}

export type FulfillmentStatus = 'new' | 'processing' | 'ready' | 'completed' | 'cancelled'

export interface OrderItemOut {
  order_item_id: string
  item_id: string
  name_snapshot: string
  price_snapshot: string
  quantity: number
  line_total: string
}

export interface OrderOut {
  order_id: string
  order_number: number
  customer_id: string
  customer_number: number
  customer_name: string | null
  customer_whatsapp_number: string
  order_type: string
  payment_method: string
  payment_status: string
  fulfillment_status: FulfillmentStatus | null
  contact_phone: string | null
  notes: string | null
  subtotal: string
  total: string
  currency: string
  placed_at: string
  paid_at: string | null
  ready_at: string | null
  completed_at: string | null
  items: OrderItemOut[]
}

// GET /api/v1/orders/{id} only -- adds the delivery address, which needs an
// extra join the list endpoint deliberately skips (see backend
// orders/api/schemas.py's OrderDetailOut docstring).
export interface OrderDetailOut extends OrderOut {
  delivery_address: AddressOut | null
}

export interface OrderSummaryOut {
  total_orders: number
  revenue_generated: string
  amount_collected: string
  cod_orders: number
  new_orders: number
  processing_orders: number
  ready_orders: number
  completed_orders: number
  cancelled_orders: number
}

export interface PaymentSettingsOut {
  razorpay_key_id: string | null
  razorpay_key_secret_set: boolean
  using_real_gateway: boolean
}

export interface WhatsAppSettingsOut {
  phone_number_id: string | null
  display_phone_number: string | null
  access_token_set: boolean
  connection_status: string
}

export interface WebsiteLinkClickStatsOut {
  count: number
  days: number
}

export interface EmbeddedSignupRequest {
  code: string
  waba_id: string | null
  phone_number_id: string | null
  business_id: string | null
  event: string
  backend_base_url: string | null
}

export interface EmbeddedSignupResult {
  status: 'connected' | 'not_completed'
  message: string
  phone_number_id: string | null
  display_phone_number: string | null
  connection_status: string | null
  pending_steps: string[]
}

export interface WhatsAppTestMessageResult {
  status: 'success' | 'failed'
  message: string
}

export interface WhatsAppFlowSetupResult {
  flow_id: string
}

export type OnboardingStatus =
  | 'registered'
  | 'vertical_selected'
  | 'meta_connected'
  | 'whatsapp_verified'
  | 'profile_completed'
  | 'catalog_ready'
  | 'live'

export interface OnboardingStatusOut {
  onboarding_status: OnboardingStatus
  restaurant_enabled: boolean
  appointment_enabled: boolean
  whatsapp_connected: boolean
  profile_completed: boolean
  has_available_item: boolean
  has_available_service: boolean
}

export interface VerticalsSelectionOut {
  restaurant_enabled: boolean
  appointment_enabled: boolean
}

export interface BusinessProfileOut {
  address_line1: string | null
  address_line2: string | null
  city: string | null
  pincode: string | null
  business_category: string | null
  license_no: string | null
}

export interface FAQItemOut {
  faq_item_id: string
  question_text: string
  answer_text: string
  keywords: string[]
  is_active: boolean
  created_at: string
  updated_at: string
}

export type NotificationKind =
  | 'order_confirmed'
  | 'order_processing'
  | 'order_ready'
  | 'order_completed'
  | 'appointment_requested'
  | 'appointment_confirmed'
  | 'appointment_cancelled'
  | 'appointment_reminder_60m'
  | 'appointment_reminder_30m'

export interface NotificationTemplateOut {
  notification_kind: NotificationKind
  template_name: string
  language_code: string
  body: string
  is_active: boolean
  is_configured: boolean
}

export interface TestCheckoutResponse {
  order_id: string
  order_number: number
  payment_status: string
  fulfillment_status: FulfillmentStatus | null
  total: string
  payment_link_url: string | null
}

export interface PublicItemOut {
  item_id: string
  category: string
  name: string
  price: string
  image_url: string | null
}

export interface PublicCatalogOut {
  business_name: string
  items: PublicItemOut[]
  merchant_whatsapp_number: string | null
}

export interface OrderingFlowCheckoutResponse {
  order_id: string
  order_number: number
  payment_status: string
  fulfillment_status: FulfillmentStatus | null
  total: string
  payment_link_url: string | null
}

export interface OrderingFlowAddressOut {
  line1: string
  line2: string | null
  landmark: string | null
  city: string
  pincode: string
}

export interface OrderingFlowCustomerLookupOut {
  display_name: string | null
  address: OrderingFlowAddressOut | null
  default_contact_phone: string | null
  last_payment_method: 'cod' | 'online' | null
}

export interface AppointmentAvailabilityWindow {
  day_of_week: number // 0=Monday .. 6=Sunday
  start_time: string // "HH:MM:SS"
  end_time: string // "HH:MM:SS"
  slot_duration_minutes: number
  buffer_minutes: number
}

export interface AppointmentAvailabilitySettingsOut {
  timezone: string
  windows: AppointmentAvailabilityWindow[]
  // Minutes-before-appointment offsets the reminder scan sends a
  // WhatsApp reminder at -- only 60 and 30 currently map to an actual
  // notification kind (see backend/src/shared/scheduler.py's
  // _REMINDER_KIND_BY_OFFSET_MINUTES). No settings UI edits this list
  // yet; it's round-tripped unmodified by the availability save so that
  // save doesn't silently reset it back to the default.
  reminder_offsets_minutes: number[]
}

export interface AppointmentServiceSettingsOut {
  service_id: string
  name: string
  duration_minutes: number
  price: string | null
  is_active: boolean
}

export type AppointmentStatus = 'requested' | 'confirmed' | 'completed' | 'cancelled'

export type AppointmentPaymentStatus = 'not_required' | 'pending' | 'paid' | 'failed'
export type AppointmentCreatedVia = 'flow' | 'browser' | 'dashboard'

export type AppointmentEventType =
  | 'requested'
  | 'confirmed'
  | 'completed'
  | 'cancelled'
  | 'rescheduled'
  | 'reminder_sent'

// One row of the Task 5 history timeline -- fields irrelevant to a given
// event_type are simply null (e.g. offset_minutes only on
// "reminder_sent", from_appointment_date/from_start_time only on
// "rescheduled"). Mirrors backend/src/appointments/api/schemas.py's
// AppointmentStatusEventOut.
export interface AppointmentStatusEventOut {
  event_type: AppointmentEventType
  from_status: AppointmentStatus | null
  to_status: AppointmentStatus | null
  from_appointment_date: string | null // "YYYY-MM-DD"
  from_start_time: string | null // "HH:MM:SS"
  to_appointment_date: string | null // "YYYY-MM-DD"
  to_start_time: string | null // "HH:MM:SS"
  offset_minutes: number | null
  // Raw actor value -- a staff_user_id, "system", or a creation surface
  // ("flow"/"browser"). Prefer changed_by_name for display.
  changed_by: string
  // Resolved staff display name when changed_by is a staff_user_id that
  // still exists; null for "system"/"flow"/"browser" or a deleted staff
  // account.
  changed_by_name: string | null
  changed_at: string
}

export interface AppointmentOut {
  appointment_id: string
  appointment_number: number
  customer_id: string
  customer_number: number
  customer_whatsapp_number: string
  customer_name: string | null
  name: string
  email: string
  appointment_date: string // "YYYY-MM-DD"
  start_time: string // "HH:MM:SS"
  end_time: string // "HH:MM:SS"
  service_id: string | null
  staff_id: string | null
  created_via: AppointmentCreatedVia
  payment_status: AppointmentPaymentStatus
  notes: string | null
  status: AppointmentStatus
  requested_at: string
  confirmed_at: string | null
  completed_at: string | null
  cancelled_at: string | null
  // Only populated on GET /api/v1/appointments/{id} -- the list endpoint
  // returns an empty array here (see appointments/api/router.py's
  // _to_appointment_out).
  status_events: AppointmentStatusEventOut[]
}

export interface AppointmentFlowInfoOut {
  business_name: string
  // Null until the merchant connects WhatsApp during onboarding. Mirrors
  // PublicCatalogOut.merchant_whatsapp_number -- the dialable display
  // number, used to link the booking confirmation back to the chat.
  merchant_whatsapp_number: string | null
}

export interface AppointmentFlowServiceOut {
  service_id: string
  name: string
  duration_minutes: number
  price: string | null
}

export interface AppointmentFlowSlotOut {
  start_time: string
  end_time: string
}

export interface AppointmentFlowCustomerLookupOut {
  display_name: string | null
  // Null both for a brand-new customer and for a returning one who's
  // never given an email (e.g. only ever ordered food before) -- either
  // way the booking form just shows an empty, fillable field.
  email: string | null
}

export interface AppointmentFlowBookingResponse {
  appointment_id: string
  appointment_number: number
  status: string
  appointment_date: string
  start_time: string
  end_time: string
}
