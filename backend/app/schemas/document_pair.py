from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Literal
from enum import Enum
from datetime import datetime
from uuid import UUID
from decimal import Decimal

from app.schemas.invoice import InvoiceResponse, InvoiceDetailResponse
from app.schemas.po import POResponse
from app.schemas.matching_v2 import MatchingResultResponse


class WorkflowStage(str, Enum):
    """Workflow stages for document pairs"""
    UPLOADED = "uploaded"
    EXTRACTED = "extracted"
    MATCHED = "matched"
    VALIDATED = "validated"
    APPROVED = "approved"


class PairStatus(str, Enum):
    """Overall status of document pair"""
    IN_PROGRESS = "in_progress"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class ValidationIssueResponse(BaseModel):
    """Response schema for validation issue"""
    id: UUID
    category: str
    severity: str
    field: Optional[str] = None
    description: str
    invoice_value: Optional[Any] = None
    po_value: Optional[Any] = None
    suggestion: Optional[str] = None
    resolved: bool
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_action: Optional[str] = None
    resolution_notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class StageTimestamps(BaseModel):
    """Timestamps for each workflow stage"""
    uploaded: Optional[datetime] = None
    extracted: Optional[datetime] = None
    matched: Optional[datetime] = None
    validated: Optional[datetime] = None
    approved: Optional[datetime] = None


class DocumentPairSummary(BaseModel):
    """Summary schema for document pair list view"""
    id: UUID
    invoice_id: int
    po_id: Optional[int] = None
    invoice_number: str
    po_number: Optional[str] = None
    vendor_name: Optional[str] = None
    total_amount: Optional[float] = None
    current_stage: WorkflowStage
    overall_status: PairStatus
    requires_review: bool
    issue_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentPairDetail(BaseModel):
    """Full detail schema for document pair"""
    id: UUID
    invoice_id: int
    po_id: Optional[int] = None
    invoice_number: str
    po_number: Optional[str] = None
    vendor_name: Optional[str] = None
    total_amount: Optional[float] = None
    current_stage: WorkflowStage
    overall_status: PairStatus
    requires_review: bool
    issue_count: int
    created_at: datetime
    updated_at: datetime
    
    # Nested relationships
    invoice: InvoiceDetailResponse
    purchase_order: Optional[POResponse] = None
    matching_result: Optional[MatchingResultResponse] = None
    validation_issues: List[ValidationIssueResponse] = []
    stage_timestamps: StageTimestamps
    confidence_score: Optional[float] = None
    reasoning: Optional[str] = None

    class Config:
        from_attributes = True


class FieldComparison(BaseModel):
    """Comparison of a single field between invoice and PO"""
    field_name: str
    invoice_value: Any
    po_value: Any
    match: bool
    similarity: Optional[float] = None
    diff_explanation: Optional[str] = None
    severity: Optional[str] = None


class LineItemComparison(BaseModel):
    """Comparison of a single line item between invoice and PO"""
    line_number: int
    invoice_line: Optional[Dict[str, Any]] = None
    po_line: Optional[Dict[str, Any]] = None
    field_comparisons: List[FieldComparison] = []
    overall_match: Literal["perfect", "partial", "mismatch", "missing"]
    issues: List[ValidationIssueResponse] = []


class TimelineEntry(BaseModel):
    """Single entry in the audit timeline"""
    timestamp: datetime
    event_type: str  # uploaded/extracted/matched/validated/approved/issue_resolved
    description: str
    actor: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class IssueResolutionRequest(BaseModel):
    """Request schema for resolving a validation issue"""
    resolution_action: Literal["accepted", "overridden", "corrected"]
    notes: Optional[str] = None


class PairApprovalRequest(BaseModel):
    """Request schema for approving/rejecting a pair"""
    notes: Optional[str] = None

