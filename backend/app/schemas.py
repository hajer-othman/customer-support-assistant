from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


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