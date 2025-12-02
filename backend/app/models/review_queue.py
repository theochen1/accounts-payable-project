from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid


class ReviewQueue(Base):
    """Represents an item in the review queue for human oversight"""
    __tablename__ = "review_queue"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    matching_result_id = Column(UUID(as_uuid=True), ForeignKey("matching_results.id"), nullable=False, index=True)
    priority = Column(String(10), nullable=False, index=True)  # 'low', 'medium', 'high', 'critical'
    issue_category = Column(String(50), nullable=False)  # Primary problem category
    assigned_to = Column(String(100), nullable=True)  # AP manager user ID
    sla_deadline = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True, index=True)
    resolution_notes = Column(Text, nullable=True)

    # Relationships
    matching_result = relationship("MatchingResult", back_populates="review_queue_items")

