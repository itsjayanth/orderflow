from pydantic import BaseModel


class NotificationTemplateOut(BaseModel):
    notification_kind: str
    template_name: str
    language_code: str
    body: str
    is_active: bool
    is_configured: bool


class NotificationTemplateUpdate(BaseModel):
    template_name: str
    language_code: str = "en"
    body: str
    is_active: bool = True
