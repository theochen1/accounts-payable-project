from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime, date
from decimal import Decimal


# Base line item schema
class LineItemBase(BaseModel):
    """Base line item schema"""
    line_no: int
    sku: Optional[str] = None
    description: str
    quantity: Decimal
    unit_price: Decimal


# Type-specific data schemas
class InvoiceTypeData(BaseModel):
    """Type-specific data for invoices"""
    po_number: Optional[str] = None
    payment_terms: Optional[str] = None
    due_date: Optional[date] = None
    tax_amount: Optional[Decimal] = None


class PurchaseOrderTypeData(BaseModel):
    """Type-specific data for purchase orders"""
    requester_name: Optional[str] = None
    requester_email: Optional[str] = None
    ship_to_address: Optional[str] = None
    order_date: Optional[date] = None


class ReceiptTypeData(BaseModel):
    """Type-specific data for receipts"""
    merchant_name: Optional[str] = None
    payment_method: Optional[str] = None
    transaction_id: Optional[str] = None


# Document request/response schemas
class DocumentBase(BaseModel):
    """Base document schema"""
    document_type: Literal["invoice", "purchase_order", "receipt"]
    vendor_name: Optional[str] = None
    document_number: Optional[str] = None
    document_date: Optional[date] = None
    total_amount: Optional[Decimal] = None
    currency: str = "USD"
    line_items: List[LineItemBase] = []


class DocumentCreate(BaseModel):
    """Schema for creating a document (upload)"""
    filename: str
    file_path: str


class DocumentClassify(BaseModel):
    """Schema for classifying a document"""
    document_type: Literal["invoice", "purchase_order", "receipt"]


class DocumentVerify(BaseModel):
    """Schema for verifying/submitting document data"""
    vendor_name: Optional[str] = None
    vendor_id: Optional[int] = None
    document_number: str
    document_date: Optional[date] = None
    total_amount: Optional[Decimal] = None
    currency: str = "USD"
    line_items: List[LineItemBase] = []
    
    # Type-specific fields (only one should be populated based on document_type)
    invoice_data: Optional[InvoiceTypeData] = None
    po_data: Optional[PurchaseOrderTypeData] = None
    receipt_data: Optional[ReceiptTypeData] = None


class DocumentResponse(BaseModel):
    """Full document response schema"""
    id: int
    document_type: Optional[str] = None  # Can be null until classified
    status: str
    vendor_name: Optional[str] = None
    vendor_id: Optional[int] = None
    document_number: Optional[str] = None
    document_date: Optional[date] = None
    total_amount: Optional[Decimal] = None
    currency: str = "USD"
    type_specific_data: Optional[Dict[str, Any]] = None
    line_items: Optional[List[Dict[str, Any]]] = None
    filename: str
    file_path: str
    raw_ocr: Optional[Dict[str, Any]] = None
    extraction_source: Optional[str] = None
    vendor_match: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    uploaded_at: datetime
    processed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Simplified response for listing documents"""
    id: int
    filename: str
    document_type: Optional[str] = None  # Can be null until classified
    status: str
    vendor_name: Optional[str] = None
    document_number: Optional[str] = None
    total_amount: Optional[Decimal] = None
    currency: str = "USD"
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentOCRResult(BaseModel):
    """Response schema for OCR processing result"""
    id: int
    status: str
    ocr_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class ProcessedDocumentResponse(BaseModel):
    """Response for processed documents"""
    id: int
    document_type: str
    document_number: str
    vendor_name: Optional[str] = None
    total_amount: Optional[Decimal] = None
    currency: str
    status: str
    document_date: Optional[date] = None
    created_at: datetime

    class Config:
        from_attributes = True
