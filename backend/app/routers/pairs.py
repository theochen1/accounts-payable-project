"""
Document Pairs API router - handles document pair operations and workflow.
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID

from app.database import get_db
from app.models.document_pair import DocumentPair
from app.models.invoice import Invoice
from app.schemas.document_pair import (
    DocumentPairSummary,
    DocumentPairDetail,
    LineItemComparison,
    TimelineEntry,
    ValidationIssueResponse,
    IssueResolutionRequest,
    PairApprovalRequest,
    StageTimestamps
)
from app.services.document_pair_service import document_pair_service
from app.schemas.invoice import InvoiceDetailResponse
from app.schemas.po import POResponse
from app.schemas.matching_v2 import MatchingResultResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/matching/pairs", tags=["document-pairs"])


@router.get("", response_model=List[DocumentPairSummary])
def list_pairs(
    status: Optional[List[str]] = Query(None),
    stage: Optional[List[str]] = Query(None),
    has_issues: Optional[bool] = Query(None),
    vendor: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    List all document pairs with filtering.
    
    Query params:
    - status: Filter by overall_status (in_progress, needs_review, approved, rejected)
    - stage: Filter by current_stage (uploaded, extracted, matched, validated, approved)
    - has_issues: Filter by requires_review flag
    - vendor: Filter by vendor name (partial match)
    - limit: Max results (1-100)
    - offset: Pagination offset
    """
    pairs = document_pair_service.get_pairs(
        db=db,
        status=status,
        stage=stage,
        has_issues=has_issues,
        vendor=vendor,
        limit=limit,
        offset=offset
    )
    
    # Convert to summary format
    summaries = []
    for pair in pairs:
        # Get invoice details
        invoice = pair.invoice
        po = pair.purchase_order
        
        # Count unresolved issues
        issue_count = len([issue for issue in pair.validation_issues if not issue.resolved])
        
        summaries.append(DocumentPairSummary(
            id=pair.id,
            invoice_id=pair.invoice_id,
            po_id=pair.po_id,
            invoice_number=invoice.invoice_number if invoice else "N/A",
            po_number=po.po_number if po else None,
            vendor_name=invoice.vendor.name if invoice and invoice.vendor else None,
            total_amount=float(invoice.total_amount) if invoice and invoice.total_amount else None,
            current_stage=pair.current_stage,
            overall_status=pair.overall_status,
            requires_review=pair.requires_review,
            issue_count=issue_count,
            created_at=pair.created_at,
            updated_at=pair.updated_at
        ))
    
    return summaries


@router.get("/{pair_id}", response_model=DocumentPairDetail)
def get_pair(pair_id: UUID, db: Session = Depends(get_db)):
    """
    Get full pair detail with invoice, PO, issues, and matching result.
    """
    pair = document_pair_service.get_pair_detail(pair_id, db)
    if not pair:
        raise HTTPException(status_code=404, detail="Document pair not found")
    
    # Build invoice detail response
    invoice = pair.invoice
    invoice_detail = InvoiceDetailResponse(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        vendor_id=invoice.vendor_id,
        vendor_name=invoice.vendor.name if invoice.vendor else None,
        po_number=invoice.po_number,
        invoice_date=invoice.invoice_date,
        total_amount=invoice.total_amount,
        currency=invoice.currency,
        contact_email=invoice.contact_email,
        pdf_storage_path=invoice.pdf_storage_path,
        ocr_json=invoice.ocr_json,
        status=invoice.status,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
        invoice_lines=[],  # Will be populated from relationship
        purchase_order=None,
        matching_result=None
    )
    
    # Add invoice lines
    from app.schemas.invoice import InvoiceLineResponse
    invoice_detail.invoice_lines = [
        InvoiceLineResponse(
            id=line.id,
            line_no=line.line_no,
            description=line.description,
            quantity=line.quantity,
            unit_price=line.unit_price
        )
        for line in invoice.invoice_lines
    ]
    
    # Build PO response if exists
    po_response = None
    if pair.purchase_order:
        po = pair.purchase_order
        from app.schemas.po import POLineResponse
        po_response = POResponse(
            id=po.id,
            po_number=po.po_number,
            vendor_id=po.vendor_id,
            vendor_name=po.vendor.name if po.vendor else None,
            total_amount=po.total_amount,
            currency=po.currency,
            status=po.status,
            requester_email=po.requester_email,
            created_at=po.created_at,
            updated_at=po.updated_at,
            po_lines=[
                POLineResponse(
                    id=line.id,
                    line_no=line.line_no,
                    description=line.description,
                    quantity=line.quantity,
                    unit_price=line.unit_price
                )
                for line in po.po_lines
            ]
        )
    
    # Build matching result response if exists
    matching_result_response = None
    if pair.matching_result:
        mr = pair.matching_result
        matching_result_response = MatchingResultResponse(
            id=mr.id,
            invoice_id=mr.invoice_id,
            po_id=mr.po_id,
            match_status=mr.match_status,
            confidence_score=float(mr.confidence_score) if mr.confidence_score else None,
            issues=mr.issues,
            reasoning=mr.reasoning,
            matched_by=mr.matched_by,
            matched_at=mr.matched_at,
            reviewed_by=mr.reviewed_by,
            reviewed_at=mr.reviewed_at,
            created_at=mr.created_at,
            invoice_number=invoice.invoice_number,
            vendor_name=invoice.vendor.name if invoice.vendor else None,
            total_amount=float(invoice.total_amount) if invoice.total_amount else None,
            currency=invoice.currency
        )
    
    # Build validation issues
    validation_issues = [
        ValidationIssueResponse(
            id=issue.id,
            category=issue.category,
            severity=issue.severity,
            field=issue.field,
            description=issue.description,
            invoice_value=issue.invoice_value,
            po_value=issue.po_value,
            suggestion=issue.suggestion,
            resolved=issue.resolved,
            resolved_by=issue.resolved_by,
            resolved_at=issue.resolved_at,
            resolution_action=issue.resolution_action,
            resolution_notes=issue.resolution_notes,
            created_at=issue.created_at
        )
        for issue in pair.validation_issues
    ]
    
    # Build stage timestamps
    stage_timestamps = StageTimestamps(
        uploaded=pair.uploaded_at,
        extracted=pair.extracted_at,
        matched=pair.matched_at,
        validated=pair.validated_at,
        approved=pair.approved_at
    )
    
    # Count issues
    issue_count = len([issue for issue in pair.validation_issues if not issue.resolved])
    
    # Get confidence and reasoning from matching result
    confidence_score = float(pair.matching_result.confidence_score) if pair.matching_result and pair.matching_result.confidence_score else None
    reasoning = pair.matching_result.reasoning if pair.matching_result else None
    
    return DocumentPairDetail(
        id=pair.id,
        invoice_id=pair.invoice_id,
        po_id=pair.po_id,
        invoice_number=invoice.invoice_number,
        po_number=po_response.po_number if po_response else None,
        vendor_name=invoice.vendor.name if invoice.vendor else None,
        total_amount=float(invoice.total_amount) if invoice.total_amount else None,
        current_stage=pair.current_stage,
        overall_status=pair.overall_status,
        requires_review=pair.requires_review,
        issue_count=issue_count,
        created_at=pair.created_at,
        updated_at=pair.updated_at,
        invoice=invoice_detail,
        purchase_order=po_response,
        matching_result=matching_result_response,
        validation_issues=validation_issues,
        stage_timestamps=stage_timestamps,
        confidence_score=confidence_score,
        reasoning=reasoning
    )


@router.get("/{pair_id}/comparison", response_model=List[LineItemComparison])
def get_line_comparison(pair_id: UUID, db: Session = Depends(get_db)):
    """
    Get line-by-line field comparison with diff highlighting.
    """
    try:
        comparisons = document_pair_service.get_line_items_comparison(pair_id, db)
        return comparisons
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{pair_id}/timeline", response_model=List[TimelineEntry])
def get_timeline(pair_id: UUID, db: Session = Depends(get_db)):
    """
    Get chronological audit log for the pair.
    """
    try:
        timeline = document_pair_service.get_timeline(pair_id, db)
        return timeline
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{pair_id}/issues/{issue_id}/resolve", response_model=ValidationIssueResponse)
def resolve_issue(
    pair_id: UUID,
    issue_id: UUID,
    resolution: IssueResolutionRequest,
    db: Session = Depends(get_db)
):
    """
    Resolve a validation issue.
    """
    try:
        issue = document_pair_service.resolve_issue(pair_id, issue_id, resolution, db)
        return ValidationIssueResponse(
            id=issue.id,
            category=issue.category,
            severity=issue.severity,
            field=issue.field,
            description=issue.description,
            invoice_value=issue.invoice_value,
            po_value=issue.po_value,
            suggestion=issue.suggestion,
            resolved=issue.resolved,
            resolved_by=issue.resolved_by,
            resolved_at=issue.resolved_at,
            resolution_action=issue.resolution_action,
            resolution_notes=issue.resolution_notes,
            created_at=issue.created_at
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{pair_id}/advance", response_model=DocumentPairDetail)
def advance_stage(pair_id: UUID, db: Session = Depends(get_db)):
    """
    Advance to next workflow stage.
    """
    try:
        pair = document_pair_service.advance_stage(pair_id, db)
        # Return updated detail
        return get_pair(pair_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{pair_id}/approve", response_model=DocumentPairDetail)
def approve_pair(
    pair_id: UUID,
    request: PairApprovalRequest,
    db: Session = Depends(get_db)
):
    """
    Approve the pair.
    """
    try:
        pair = document_pair_service.approve_pair(pair_id, request.notes or "", db)
        # Return updated detail
        return get_pair(pair_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{pair_id}/reject", response_model=DocumentPairDetail)
def reject_pair(
    pair_id: UUID,
    request: PairApprovalRequest,
    db: Session = Depends(get_db)
):
    """
    Reject the pair.
    """
    try:
        pair = document_pair_service.reject_pair(pair_id, request.notes or "", db)
        # Return updated detail
        return get_pair(pair_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

