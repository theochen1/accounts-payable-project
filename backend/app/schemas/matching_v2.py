from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Literal
from enum import Enum
from decimal import Decimal
from datetime import datetime
from uuid import UUID


class IssueCategory(str, Enum):
    """Categories of matching issues"""
    MISSING_REFERENCE = "missing_reference"
    DUPLICATE_INVOICE = "duplicate_invoice"
    VENDOR_MISMATCH = "vendor_mismatch"
    TOTAL_MISMATCH = "total_mismatch"
    LINE_COUNT_MISMATCH = "line_count_mismatch"
    LINE_ITEM_DISCREPANCY = "line_item_discrepancy"
    CALCULATION_ERROR = "calculation_error"
    QUANTITY_OVERAGE = "quantity_overage"
    TAX_ERROR = "tax_error"
    DATE_ANOMALY = "date_anomaly"


class MatchingIssueV2(BaseModel):
    """Represents a single matching issue"""
    category: IssueCategory
    severity: Literal["low", "medium", "high", "critical"]
    message: str
    details: Dict[str, Any]
    line_number: Optional[int] = None

    class Config:
        use_enum_values = True


class MatchingResultCreate(BaseModel):
    """Schema for creating a matching result"""
    invoice_id: int
    po_id: Optional[int] = None
    match_status: Literal["matched", "needs_review"]
    confidence_score: float
    issues: List[MatchingIssueV2]
    reasoning: str


class MatchingResultResponse(BaseModel):
    """Response schema for matching result"""
    id: UUID
    invoice_id: int
    po_id: Optional[int] = None
    match_status: str
    confidence_score: Optional[float] = None
    issues: Optional[List[Dict[str, Any]]] = None
    reasoning: Optional[str] = None
    matched_by: Optional[str] = None
    matched_at: datetime
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    # Invoice details for convenience
    invoice_number: Optional[str] = None
    vendor_name: Optional[str] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = None

    class Config:
        from_attributes = True


class ReviewQueueItemCreate(BaseModel):
    """Schema for creating a review queue item"""
    matching_result_id: UUID
    priority: Literal["low", "medium", "high", "critical"]
    issue_category: str
    assigned_to: Optional[str] = None
    sla_deadline: Optional[datetime] = None


class ReviewQueueItemResponse(BaseModel):
    """Response schema for review queue item"""
    id: UUID
    matching_result_id: UUID
    priority: str
    issue_category: str
    assigned_to: Optional[str] = None
    sla_deadline: Optional[datetime] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    matching_result: Optional[MatchingResultResponse] = None

    class Config:
        from_attributes = True


class ReviewQueueResolveRequest(BaseModel):
    """Request schema for resolving a review queue item"""
    resolution: Literal["approved", "rejected"]
    notes: Optional[str] = None


class BatchProcessRequest(BaseModel):
    """Request schema for batch processing invoices"""
    invoice_ids: List[int]


class BatchProcessResponse(BaseModel):
    """Response schema for batch processing"""
    processed_count: int
    results: List[MatchingResultResponse]
    errors: List[Dict[str, Any]]

