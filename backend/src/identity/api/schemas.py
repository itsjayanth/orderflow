import datetime
import uuid

from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    business_name: str
    owner_name: str
    owner_contact: EmailStr
    password: str


class LoginRequest(BaseModel):
    email_or_phone: str
    password: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MerchantOut(BaseModel):
    merchant_id: uuid.UUID
    business_name: str
    onboarding_status: str

    model_config = {"from_attributes": True}


class StaffUserOut(BaseModel):
    staff_user_id: uuid.UUID
    name: str
    email_or_phone: str
    role: str
    last_login_at: datetime.datetime | None

    model_config = {"from_attributes": True}


class MeResponse(BaseModel):
    staff_user: StaffUserOut
    merchant: MerchantOut
