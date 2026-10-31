from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class OrderLookupRequest(BaseModel):
    order_number: str
    email: str


class OrderItemOut(BaseModel):
    product_name: str
    size: str
    quantity: int
    unit_price: Decimal
    return_status: str | None


class OrderStatusOut(BaseModel):
    order_number: str
    status: str
    ordered_at: datetime
    delivered_at: datetime | None
    items: list[OrderItemOut]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    ui_language: Literal["fr", "en"] | None = None


class SourceOut(BaseModel):
    document_name: str
    section_title: str


class ChatResponse(BaseModel):
    answer: str
    covered: bool  # False : question non couverte, ou langue non prise en charge
    language: str | None  # langue de la réponse, None si langue non prise en charge
    sources: list[SourceOut]