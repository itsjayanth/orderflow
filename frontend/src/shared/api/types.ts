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

export interface MenuItem {
  menu_item_id: string
  category: string
  name: string
  price: string
  is_available: boolean
  created_at: string
  updated_at: string
}
