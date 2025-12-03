from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, DateTime, Date, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String, nullable=False, index=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=True)  # May be null initially
    po_number = Column(String, nullable=True, index=True)
    invoice_date = Column(Date, nullable=True)
    total_amount = Column(Numeric(10, 2), nullable=True)
    currency = Column(String, default="USD")
    contact_email = Column(String, nullable=True)  # Email for escalation and exception handling
    pdf_storage_path = Column(String, nullable=True)
    ocr_json = Column(JSON, nullable=True)  # Store raw OCR output
    status = Column(String, default="new", index=True)  # new, matched, needs_review, exception, approved, rejected, routed
    source_document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)  # Link to source document
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    vendor = relationship("Vendor", back_populates="invoices")
    invoice_lines = relationship("InvoiceLine", back_populates="invoice", cascade="all, delete-orphan")
    decisions = relationship("Decision", back_populates="invoice", cascade="all, delete-orphan")
    source_document = relationship("Document", backref="invoices")

