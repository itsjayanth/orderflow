import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class MenuItemOut(BaseModel):
    menu_item_id: uuid.UUID
    category: str
    name: str
    price: Decimal
    is_available: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class MenuItemCreate(BaseModel):
    category: str = Field(min_length=1)
    name: str = Field(min_length=1)
    price: Decimal = Field(gt=0)


class MenuItemUpdate(BaseModel):
    category: str | None = Field(default=None, min_length=1)
    name: str | None = Field(default=None, min_length=1)
    price: Decimal | None = Field(default=None, gt=0)
    is_available: bool | None = None
