import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class ItemOut(BaseModel):
    item_id: uuid.UUID
    item_number: int
    category: str
    name: str
    price: Decimal
    is_available: bool
    image_url: str | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class ItemCreate(BaseModel):
    category: str = Field(min_length=1)
    name: str = Field(min_length=1)
    price: Decimal = Field(gt=0)
    image_url: str | None = Field(default=None, max_length=2048)


class ItemUpdate(BaseModel):
    category: str | None = Field(default=None, min_length=1)
    name: str | None = Field(default=None, min_length=1)
    price: Decimal | None = Field(default=None, gt=0)
    is_available: bool | None = None
    image_url: str | None = Field(default=None, max_length=2048)
