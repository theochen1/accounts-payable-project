from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid


class ValidationIssue(Base):
    """Represents a validation issue found during invoice-PO matching"""
    __tablename__ = "validation_issues"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    document_pair_id = Column(UUID(as_uuid=True), ForeignKey("document_pairs.id", ondelete="CASCADE"), nullable=False, index=True)

    category = Column(String(50), nullable=False)  # vendor_mismatch, calculation_error, etc.
    severity = Column(String(20), nullable=False, index=True)  # critical/warning/info
    field = Column(String(100), nullable=True)  # Which field has the issue
    description = Column(Text, nullable=False)
    line_number = Column(Integer, nullable=True)  # Line number for line-item issues

    invoice_value = Column(JSONB, nullable=True)  # The value from invoice
    po_value = Column(JSONB, nullable=True)       # The value from PO
    suggestion = Column(Text, nullable=True)      # AI-suggested resolution

    # Resolution tracking
    resolved = Column(Boolean, default=False, index=True)
    resolved_by = Column(String(100), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_action = Column(String(50), nullable=True)  # accepted/overridden/corrected
    resolution_notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document_pair = relationship("DocumentPair", back_populates="validation_issues")

