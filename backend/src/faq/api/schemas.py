import datetime
import uuid

from pydantic import BaseModel, Field


class FAQItemOut(BaseModel):
    faq_item_id: uuid.UUID
    question_text: str
    answer_text: str
    keywords: list[str]
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class FAQItemCreate(BaseModel):
    question_text: str = Field(min_length=1, max_length=500)
    answer_text: str = Field(min_length=1)
    keywords: list[str] = Field(default_factory=list)


class FAQItemUpdate(BaseModel):
    question_text: str | None = Field(default=None, min_length=1, max_length=500)
    answer_text: str | None = Field(default=None, min_length=1)
    keywords: list[str] | None = None
    is_active: bool | None = None
