"""
Email schemas for API requests and responses
"""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr
from uuid import UUID


class EmailDraftRequest(BaseModel):
    """Request to draft an email for a document pair"""
    document_pair_id: UUID
    issue_ids: Optional[List[UUID]] = None  # If None, includes all unresolved issues


class EmailDraftResponse(BaseModel):
    """Response containing email draft"""
    email_log_id: UUID
    to_addresses: List[str]
    cc_addresses: Optional[List[str]]
    subject: str
    body_text: str
    body_html: str
    summary: str
    status: str  # 'draft'


class EmailSendRequest(BaseModel):
    """Request to send an email (with optional edits)"""
    email_log_id: UUID
    subject: Optional[str] = None  # If provided, overrides draft subject
    body_text: Optional[str] = None  # If provided, overrides draft body
    body_html: Optional[str] = None  # If provided, overrides draft HTML
    to_addresses: Optional[List[str]] = None  # If provided, overrides draft recipients
    cc_addresses: Optional[List[str]] = None  # If provided, overrides draft CC


class EmailSendResponse(BaseModel):
    """Response after sending email"""
    email_log_id: UUID
    message_id: str
    thread_id: Optional[str]
    success: bool
    status: str  # 'sent' or 'failed'
    error_message: Optional[str] = None


class EmailLogResponse(BaseModel):
    """Email log entry response"""
    id: UUID
    document_pair_id: UUID
    to_addresses: List[str]
    cc_addresses: Optional[List[str]]
    subject: str
    body_text: str
    body_html: Optional[str]
    issue_ids: Optional[List[UUID]]
    status: str  # draft/sent/failed
    gmail_message_id: Optional[str]
    gmail_thread_id: Optional[str]
    drafted_at: datetime
    drafted_by: Optional[str]
    sent_at: Optional[datetime]
    sent_by: Optional[str]
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

