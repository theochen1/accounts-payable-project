from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from decimal import Decimal


class POLineResponse(BaseModel):
    id: int
    line_no: int
    description: str
    quantity: Decimal
    unit_price: Decimal

    class Config:
        from_attributes = True


class POLineCreate(BaseModel):
    line_no: int
    description: str
    quantity: Decimal
    unit_price: Decimal


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


class POListResponse(BaseModel):
    id: int
    po_number: str
    vendor_id: int
    vendor_name: Optional[str] = None
    total_amount: Decimal
    currency: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class POCreate(BaseModel):
    po_number: str
    vendor_id: int
    currency: str = "USD"
    status: str = "open"
    requester_email: Optional[str] = None
    po_lines: List[POLineCreate]

