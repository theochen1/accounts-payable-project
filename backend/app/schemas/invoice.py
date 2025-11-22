from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
from app.schemas.po import POResponse
from app.schemas.matching import MatchingResult


class InvoiceLineResponse(BaseModel):
    id: int
    line_no: int
    sku: Optional[str]
    description: str
    quantity: Decimal
    unit_price: Decimal

    class Config:
        from_attributes = True


class InvoiceResponse(BaseModel):
    id: int
    invoice_number: str
    vendor_id: Optional[int]
    po_number: Optional[str]
    invoice_date: Optional[date]
    total_amount: Optional[Decimal]
    currency: str
    pdf_storage_path: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InvoiceListResponse(BaseModel):
    id: int
    invoice_number: str
    vendor_id: Optional[int]
    vendor_name: Optional[str] = None
    po_number: Optional[str]
    total_amount: Optional[Decimal]
    currency: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class InvoiceDetailResponse(BaseModel):
    id: int
    invoice_number: str
    vendor_id: Optional[int]
    vendor_name: Optional[str] = None
    po_number: Optional[str]
    invoice_date: Optional[date]
    total_amount: Optional[Decimal]
    currency: str
    pdf_storage_path: Optional[str]
    ocr_json: Optional[dict]
    status: str
    created_at: datetime
    updated_at: datetime
    invoice_lines: List[InvoiceLineResponse] = []
    purchase_order: Optional[POResponse] = None
    matching_result: Optional[MatchingResult] = None

    class Config:
        from_attributes = True


class InvoiceCreate(BaseModel):
    invoice_number: str
    vendor_id: Optional[int] = None
    po_number: Optional[str] = None
    invoice_date: Optional[date] = None
    total_amount: Optional[Decimal] = None
    currency: str = "USD"
    pdf_storage_path: Optional[str] = None
    ocr_json: Optional[dict] = None


class DecisionCreate(BaseModel):
    decision: str = Field(..., pattern="^(approved|rejected|routed)$")
    reason: Optional[str] = None
    user_identifier: str = "manager@example.com"

