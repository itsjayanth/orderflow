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
