from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid


class MatchingResult(Base):
    """Represents the result of matching an invoice to a purchase order"""
    __tablename__ = "matching_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False, index=True)
    po_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=True)
    match_status = Column(String(20), nullable=False, index=True)  # 'matched', 'needs_review'
    confidence_score = Column(Numeric(3, 2), nullable=True)  # 0.00 to 1.00
    issues = Column(JSONB, nullable=True)  # Array of MatchingIssueV2 objects
    reasoning = Column(Text, nullable=True)  # LLM-generated explanation
    matched_by = Column(String(20), nullable=True)  # 'agent' or 'human'
    matched_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_by = Column(String(100), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    invoice = relationship("Invoice", backref="matching_results")
    purchase_order = relationship("PurchaseOrder", backref="matching_results")
    review_queue_items = relationship("ReviewQueue", back_populates="matching_result", cascade="all, delete-orphan")

