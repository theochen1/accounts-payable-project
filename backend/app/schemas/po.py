from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from decimal import Decimal


class POLineResponse(BaseModel):
    id: int
    line_no: int
    sku: Optional[str]
    description: str
    quantity: Decimal
    unit_price: Decimal

    class Config:
        from_attributes = True


class POResponse(BaseModel):
    id: int
    po_number: str
    vendor_id: int
    vendor_name: Optional[str] = None
    total_amount: Decimal
    currency: str
    status: str
    requester_email: Optional[str]
    created_at: datetime
    updated_at: datetime
    po_lines: List[POLineResponse] = []

    class Config:
        from_attributes = True

