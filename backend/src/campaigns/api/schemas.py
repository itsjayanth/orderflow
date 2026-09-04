import datetime
import uuid

from pydantic import BaseModel, Field

from campaigns.domain.models import TEMPLATE_CATEGORIES, TEMPLATE_HEADER_TYPES


class TemplateButtonIn(BaseModel):
    type: str = Field(pattern="^(QUICK_REPLY|URL)$")
    text: str = Field(min_length=1, max_length=25)
    url: str | None = Field(default=None, max_length=2048)


class MessageTemplateOut(BaseModel):
    template_id: uuid.UUID
    name: str
    category: str
    language_code: str
    header_type: str
    header_text: str | None
    header_media_handle: str | None
    body_text: str
    body_variable_count: int
    footer_text: str | None
    buttons: list[dict[str, str | None]]
    meta_template_id: str | None
    meta_approval_status: str
    meta_rejection_reason: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class MessageTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=512)
    category: str = Field(pattern="^(" + "|".join(TEMPLATE_CATEGORIES) + ")$")
    language_code: str = Field(default="en_US", max_length=16)
    header_type: str = Field(default="NONE", pattern="^(" + "|".join(TEMPLATE_HEADER_TYPES) + ")$")
    header_text: str | None = Field(default=None, max_length=60)
    # base64-encoded image bytes -- decoded and uploaded via
    # campaigns/adapters/media_upload.py before submission. Only read when
    # header_type == "IMAGE".
    header_image_base64: str | None = None
    header_image_content_type: str | None = None
    body_text: str = Field(min_length=1, max_length=1024)
    footer_text: str | None = Field(default=None, max_length=60)
    buttons: list[TemplateButtonIn] = Field(default_factory=list)
