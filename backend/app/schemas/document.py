from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from decimal import Decimal


class DocumentResponse(BaseModel):
    """Response schema for document in the queue"""
    id: int
    filename: str
    storage_path: str
    document_type: Optional[str] = None  # 'invoice' | 'po' | null
    status: str  # pending, processing, processed, error
    error_message: Optional[str] = None
    ocr_data: Optional[Dict[str, Any]] = None
    processed_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Simplified response for listing documents"""
    id: int
    filename: str
    document_type: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    processed_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentUpdateType(BaseModel):
    """Request schema for setting document type"""
    document_type: str  # 'invoice' | 'po'


class DocumentOCRResult(BaseModel):
    """Response schema for OCR processing result"""
    id: int
    status: str
    ocr_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


# Schemas for saving processed documents

class InvoiceLineCreate(BaseModel):
    """Line item for invoice"""
    line_no: int = 0
    sku: Optional[str] = None
    description: str
    quantity: Decimal
    unit_price: Decimal


class InvoiceSaveData(BaseModel):
    """Data for saving a processed invoice"""
    invoice_number: str
    vendor_name: Optional[str] = None
    vendor_id: Optional[int] = None
    po_number: Optional[str] = None
    invoice_date: Optional[str] = None  # YYYY-MM-DD format
    total_amount: Optional[Decimal] = None
    currency: str = "USD"
    line_items: List[InvoiceLineCreate] = []


class POLineCreate(BaseModel):
    """Line item for purchase order"""
    line_no: int = 0
    sku: Optional[str] = None
    description: str
    quantity: Decimal
    unit_price: Decimal


class POSaveData(BaseModel):
    """Data for saving a processed purchase order"""
    po_number: str
    vendor_name: Optional[str] = None
    vendor_id: Optional[int] = None
    order_date: Optional[str] = None  # YYYY-MM-DD format
    total_amount: Decimal
    currency: str = "USD"
    requester_email: Optional[str] = None
    po_lines: List[POLineCreate] = []


class DocumentSaveRequest(BaseModel):
    """Request schema for saving a document as Invoice or PO"""
    invoice_data: Optional[InvoiceSaveData] = None
    po_data: Optional[POSaveData] = None


# Processed documents combined view

class ProcessedDocumentResponse(BaseModel):
    """Combined response for processed invoices and POs"""
    id: int
    document_type: str  # 'invoice' | 'po'
    reference_number: str  # invoice_number or po_number
    vendor_name: Optional[str] = None
    total_amount: Optional[Decimal] = None
    currency: str
    status: str
    date: Optional[str] = None  # invoice_date or order_date
    source_document_id: Optional[int] = None
    created_at: datetime

