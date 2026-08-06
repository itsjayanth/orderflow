from pydantic import BaseModel


class WhatsAppSettingsOut(BaseModel):
    phone_number_id: str | None
    display_phone_number: str | None
    access_token_set: bool
    connection_status: str


class WhatsAppSettingsUpdate(BaseModel):
    phone_number_id: str
    access_token: str
    display_phone_number: str | None = None
