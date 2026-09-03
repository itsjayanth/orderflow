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


class EmbeddedSignupRequest(BaseModel):
    """What Meta's Embedded Signup popup hands back client-side (see
    frontend/src/features/onboarding/useEmbeddedSignup.ts). Every field but
    `event` is optional -- a CANCEL carries no code or IDs at all, and the
    endpoint has to be able to respond to that rather than reject it as a
    malformed request. code has a ~30s TTL at Meta and is never logged,
    stored, or echoed back."""

    code: str | None = Field(None, description="Embedded Signup authorization code (~30s TTL)")
    waba_id: str | None = Field(None, description="WhatsApp Business Account ID")
    phone_number_id: str | None = Field(None, description="WhatsApp phone number ID")
    business_id: str | None = Field(None, description="Meta business portfolio ID")
    event: str = Field(
        "FINISH",
        description="Terminal session event from the popup: FINISH, FINISH_ONLY_WABA, or CANCEL",
    )
    backend_base_url: str | None = Field(
        None,
        description=(
            "This deployment's own public base URL (e.g. https://api.example.com), used to build "
            "the WABA webhook subscription's override_callback_uri -- required because the Meta "
            "App backing Embedded Signup is shared with fastflow/ORDZO, so without an override, "
            "webhook events would route to fastflow's backend instead of orderflow's."
        ),
    )


class EmbeddedSignupResult(BaseModel):
    status: str  # "connected" | "not_completed"
    message: str
    phone_number_id: str | None = None
    display_phone_number: str | None = None
    connection_status: str | None = None
    pending_steps: list[str] = Field(default_factory=list)


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


class BusinessProfileOut(BaseModel):
    address_line1: str | None
    address_line2: str | None
    city: str | None
    pincode: str | None
    business_category: str | None
    license_no: str | None


class BusinessProfileUpdate(BaseModel):
    address_line1: str
    address_line2: str | None = None
    city: str
    pincode: str
    business_category: str
    license_no: str | None = None


class OnboardingStatusOut(BaseModel):
    onboarding_status: str
    restaurant_enabled: bool
    appointment_enabled: bool
    whatsapp_connected: bool
    profile_completed: bool
    has_available_item: bool
    has_available_service: bool


class VerticalsSelectionRequest(BaseModel):
    """Multi-select -- both can be true at once. Not a one-time choice: this
    same request shape is submitted both by the onboarding wizard's first
    step and, later, by Settings' "Business types" section to add a
    vertical (VERTICAL_TOGGLE_PLAN.md)."""

    restaurant_enabled: bool = False
    appointment_enabled: bool = False


class VerticalsSelectionOut(BaseModel):
    restaurant_enabled: bool
    appointment_enabled: bool
