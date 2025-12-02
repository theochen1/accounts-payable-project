from sqlalchemy import Column, Integer, String, DateTime, JSON, Date, Numeric
from sqlalchemy.sql import func
from app.database import Base


class Document(Base):
    """
    Unified document model supporting invoices, purchase orders, and receipts.
    Uses JSONB for type-specific fields to maintain flexibility.
    """
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    document_type = Column(String, nullable=False, index=True)  # 'invoice', 'purchase_order', 'receipt'
    status = Column(String, default="uploaded", index=True)  # uploaded, classified, ocr_processing, pending_verification, verified, processed
    
    # Common fields (denormalized for queries)
    vendor_name = Column(String, nullable=True)
    document_number = Column(String, nullable=True, index=True)  # Generic: invoice_number, po_number, receipt_number
    document_date = Column(Date, nullable=True)
    total_amount = Column(Numeric(12, 2), nullable=True)
    currency = Column(String, default="USD")
    
    # Type-specific data as JSON
    # Invoice: {po_number, payment_terms, due_date, tax_amount}
    # PO: {requester_name, requester_email, ship_to_address, order_date}
    # Receipt: {merchant_name, payment_method, transaction_id}
    type_specific_data = Column(JSON, nullable=True)
    
    # Line items as JSON array
    # Format: [{"line_no": 1, "sku": "...", "description": "...", "quantity": 10, "unit_price": 5.00}]
    line_items = Column(JSON, nullable=True)
    
    # File and OCR metadata
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    raw_ocr = Column(JSON, nullable=True)  # Raw OCR extraction output
    extraction_source = Column(String, nullable=True)  # 'ocr_agent_ensemble', 'azure', etc.
    error_message = Column(String, nullable=True)
    
    # Vendor matching metadata
    vendor_id = Column(Integer, nullable=True)  # Matched vendor ID
    vendor_match = Column(JSON, nullable=True)  # Vendor matching result with confidence
    
    # Timestamps
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
