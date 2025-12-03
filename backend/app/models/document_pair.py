from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid


class DocumentPair(Base):
    """Represents a paired invoice and purchase order moving through workflow stages"""
    __tablename__ = "document_pairs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False, index=True)
    po_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=True, index=True)
    matching_result_id = Column(UUID(as_uuid=True), ForeignKey("matching_results.id"), nullable=True)

    # Workflow stage: uploaded/extracted/matched/validated/approved
    current_stage = Column(String(20), default="matched", index=True)
    # Status: in_progress/needs_review/approved/rejected
    overall_status = Column(String(20), default="in_progress", index=True)

    # Stage timestamps
    uploaded_at = Column(DateTime(timezone=True), nullable=True)
    extracted_at = Column(DateTime(timezone=True), nullable=True)
    matched_at = Column(DateTime(timezone=True), server_default=func.now())
    validated_at = Column(DateTime(timezone=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    # Flags
    requires_review = Column(Boolean, default=False, index=True)
    has_critical_issues = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    invoice = relationship("Invoice", backref="document_pairs")
    purchase_order = relationship("PurchaseOrder", backref="document_pairs")
    matching_result = relationship("MatchingResult", backref="document_pair")
    validation_issues = relationship("ValidationIssue", back_populates="document_pair", cascade="all, delete-orphan")

