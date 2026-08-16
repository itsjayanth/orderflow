from pydantic import BaseModel, Field


class WhatsAppSettingsOut(BaseModel):
    phone_number_id: str | None
    display_phone_number: str | None
    access_token_set: bool
    connection_status: str


class WhatsAppSettingsUpdate(BaseModel):
    phone_number_id: str
    access_token: str
    display_phone_number: str | None = None


class WhatsAppTestMessageRequest(BaseModel):
    to: str = Field(..., description="Recipient phone number in E.164 format, e.g. +919876543210")


class WhatsAppTestMessageResult(BaseModel):
    status: str  # "success" | "failed"
    message: str


class WhatsAppFlowSetupRequest(BaseModel):
    meta_waba_id: str = Field(
        ...,
        description=(
            "The WhatsApp Business Account ID shown on Meta's API Setup page -- "
            "not stored anywhere in orderflow today, since onboarding only captures "
            "phone_number_id + access_token."
        ),
    )
    backend_base_url: str = Field(
        ..., description="This deployment's own public base URL, e.g. https://api.example.com"
    )


class WhatsAppFlowSetupResult(BaseModel):
    flow_id: str


class KitchenProfileOut(BaseModel):
    address_line1: str | None
    address_line2: str | None
    city: str | None
    pincode: str | None
    cuisine_type: str | None
    fssai_license_no: str | None


class KitchenProfileUpdate(BaseModel):
    address_line1: str
    address_line2: str | None = None
    city: str
    pincode: str
    cuisine_type: str
    fssai_license_no: str | None = None


class OnboardingStatusOut(BaseModel):
    onboarding_status: str
    whatsapp_connected: bool
    profile_completed: bool
    has_available_menu_item: bool
