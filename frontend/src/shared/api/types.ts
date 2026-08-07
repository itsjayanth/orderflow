export interface AccessTokenResponse {
  access_token: string
  token_type: string
}

export interface Merchant {
  merchant_id: string
  business_name: string
  onboarding_status: string
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
  whatsapp_number: string
  display_name: string | null
  first_seen_at: string
  last_order_at: string | null
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

export interface MenuItem {
  menu_item_id: string
  item_number: number
  category: string
  name: string
  price: string
  is_available: boolean
  created_at: string
  updated_at: string
}

export type FulfillmentStatus = 'new' | 'preparing' | 'ready' | 'completed' | 'cancelled'

export interface OrderItemOut {
  order_item_id: string
  menu_item_id: string
  name_snapshot: string
  price_snapshot: string
  quantity: number
  line_total: string
}

export interface OrderOut {
  order_id: string
  order_number: number
  customer_id: string
  customer_name: string | null
  customer_whatsapp_number: string
  order_type: string
  payment_method: string
  payment_status: string
  fulfillment_status: FulfillmentStatus | null
  subtotal: string
  total: string
  currency: string
  placed_at: string
  paid_at: string | null
  ready_at: string | null
  completed_at: string | null
  items: OrderItemOut[]
}

export interface OrderSummaryOut {
  total_orders: number
  revenue_generated: string
  amount_collected: string
  cod_orders: number
  new_orders: number
  preparing_orders: number
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

export type OnboardingStatus =
  | 'registered'
  | 'meta_connected'
  | 'whatsapp_verified'
  | 'profile_completed'
  | 'catalog_ready'
  | 'live'

export interface OnboardingStatusOut {
  onboarding_status: OnboardingStatus
  whatsapp_connected: boolean
  profile_completed: boolean
  has_available_menu_item: boolean
}

export interface KitchenProfileOut {
  address_line1: string | null
  address_line2: string | null
  city: string | null
  pincode: string | null
  cuisine_type: string | null
  fssai_license_no: string | null
}

export type NotificationKind =
  | 'order_confirmed'
  | 'order_preparing'
  | 'order_ready'
  | 'order_completed'

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

export interface PublicMenuItemOut {
  menu_item_id: string
  category: string
  name: string
  price: string
}

export interface PublicMenuOut {
  business_name: string
  items: PublicMenuItemOut[]
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
}
