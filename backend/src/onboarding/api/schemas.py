from pydantic import BaseModel, Field


class WhatsAppSettingsOut(BaseModel):
    phone_number_id: str | None
    display_phone_number: str | None
    access_token_set: bool
    connection_status: str
    # "manual" | "embedded_signup" | None (no account connected yet)
    connection_method: str | None = None


class WhatsAppSettingsUpdate(BaseModel):
    phone_number_id: str
    access_token: str
    display_phone_number: str | None = None


class EmbeddedSignupConfigOut(BaseModel):
    """App-level (non-secret) values the frontend needs to init Meta's
    Facebook Login for Business JS SDK. `configured=False` means
    META_APP_ID/META_APP_SECRET/META_CONFIGURATION_ID aren't set on this
    deployment -- the frontend hides the "Connect WhatsApp" button rather
    than launching a popup that can only fail."""

    app_id: str
    config_id: str
    graph_api_version: str
    configured: bool


class EmbeddedSignupCompleteRequest(BaseModel):
    code: str = Field(..., description="Auth code returned by FB.login's callback")
    waba_id: str = Field(
        ..., description="WABA ID captured from the SDK's WA_EMBEDDED_SIGNUP event"
    )
    phone_number_id: str = Field(
        ..., description="Phone number ID captured from the SDK's WA_EMBEDDED_SIGNUP event"
    )


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
