from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid


class EmailLog(Base):
    """Tracks emails sent for document pair escalations"""
    __tablename__ = "email_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    document_pair_id = Column(UUID(as_uuid=True), ForeignKey("document_pairs.id", ondelete="CASCADE"), nullable=False, index=True)

    # Email details
    to_addresses = Column(ARRAY(String), nullable=False)
    cc_addresses = Column(ARRAY(String), nullable=True)
    subject = Column(String, nullable=False)
    body_text = Column(Text, nullable=False)
    body_html = Column(Text, nullable=True)

    # Metadata
    issue_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True)  # Array of validation_issue IDs this email addresses
    status = Column(String, default='draft', index=True)  # draft/sent/failed

    # Gmail API details
    gmail_message_id = Column(String, nullable=True)  # Gmail's message ID after sending
    gmail_thread_id = Column(String, nullable=True)

    # Tracking
    drafted_at = Column(DateTime(timezone=True), server_default=func.now())
    drafted_by = Column(String, nullable=True)  # User who drafted
    sent_at = Column(DateTime(timezone=True), nullable=True)
    sent_by = Column(String, nullable=True)  # User who sent
    error_message = Column(Text, nullable=True)  # If sending failed

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document_pair = relationship("DocumentPair", backref="emails")

