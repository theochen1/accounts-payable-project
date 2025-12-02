"""
Matching API router - handles invoice-PO matching and review queue operations.
"""
import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from uuid import UUID

from app.database import get_db
from app.models.matching_result import MatchingResult
from app.models.review_queue import ReviewQueue
from app.models.invoice import Invoice
from app.schemas.matching_v2 import (
    MatchingResultResponse,
    ReviewQueueItemResponse,
    ReviewQueueResolveRequest,
    BatchProcessRequest,
    BatchProcessResponse
)
from app.services.matching_agent_v2 import MatchingAgentV2
from app.services.review_queue_service import review_queue_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/matching", tags=["matching"])


@router.post("/{invoice_id}/process", response_model=MatchingResultResponse)
async def process_invoice_matching(
    invoice_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Trigger matching for an invoice.
    Runs matching agent and adds to review queue if needed.
    """
    from sqlalchemy.orm import joinedload
    
    invoice = db.query(Invoice).options(joinedload(Invoice.vendor)).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Run matching agent
    agent = MatchingAgentV2(db)
    matching_result = await agent.process_invoice(invoice_id)
    
    # Add to review queue if needs_review
    if matching_result.match_status == "needs_review":
        review_queue_service.add_to_queue(matching_result, db)
    
    # Build response with invoice details
    result_dict = {
        "id": matching_result.id,
        "invoice_id": matching_result.invoice_id,
        "po_id": matching_result.po_id,
        "match_status": matching_result.match_status,
        "confidence_score": float(matching_result.confidence_score) if matching_result.confidence_score else None,
        "issues": matching_result.issues,
        "reasoning": matching_result.reasoning,
        "matched_by": matching_result.matched_by,
        "matched_at": matching_result.matched_at,
        "reviewed_by": matching_result.reviewed_by,
        "reviewed_at": matching_result.reviewed_at,
        "created_at": matching_result.created_at,
        "invoice_number": invoice.invoice_number,
        "vendor_name": invoice.vendor.name if invoice.vendor else None,
        "total_amount": float(invoice.total_amount) if invoice.total_amount else None,
        "currency": invoice.currency,
    }
    
    return MatchingResultResponse(**result_dict)


@router.get("/results/{result_id}", response_model=MatchingResultResponse)
def get_matching_result(result_id: UUID, db: Session = Depends(get_db)):
    """Get matching result by ID"""
    result = db.query(MatchingResult).filter(MatchingResult.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Matching result not found")
    
    # Include invoice details
    result_dict = {
        "id": result.id,
        "invoice_id": result.invoice_id,
        "po_id": result.po_id,
        "match_status": result.match_status,
        "confidence_score": float(result.confidence_score) if result.confidence_score else None,
        "issues": result.issues,
        "reasoning": result.reasoning,
        "matched_by": result.matched_by,
        "matched_at": result.matched_at,
        "reviewed_by": result.reviewed_by,
        "reviewed_at": result.reviewed_at,
        "created_at": result.created_at,
    }
    
    # Load invoice details
    invoice = result.invoice
    if invoice:
        result_dict["invoice_number"] = invoice.invoice_number
        result_dict["vendor_name"] = invoice.vendor.name if invoice.vendor else None
        result_dict["total_amount"] = float(invoice.total_amount) if invoice.total_amount else None
        result_dict["currency"] = invoice.currency
    
    return MatchingResultResponse(**result_dict)


@router.get("/review-queue", response_model=List[ReviewQueueItemResponse])
def list_review_queue(
    priority: Optional[str] = Query(None, description="Filter by priority"),
    issue_category: Optional[str] = Query(None, description="Filter by issue category"),
    status: Optional[str] = Query(None, description="Filter by status: pending or resolved"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    List review queue items with optional filters.
    """
    from sqlalchemy.orm import joinedload
    
    query = db.query(ReviewQueue).options(
        joinedload(ReviewQueue.matching_result).joinedload(MatchingResult.invoice).joinedload("vendor")
    )
    
    # Filter by priority
    if priority:
        query = query.filter(ReviewQueue.priority == priority)
    
    # Filter by issue category
    if issue_category:
        query = query.filter(ReviewQueue.issue_category == issue_category)
    
    # Filter by status (pending = resolved_at is None)
    if status == "pending":
        query = query.filter(ReviewQueue.resolved_at.is_(None))
    elif status == "resolved":
        query = query.filter(ReviewQueue.resolved_at.isnot(None))
    
    # Order by priority and created_at
    query = query.order_by(
        ReviewQueue.priority.desc(),  # critical first
        ReviewQueue.created_at.asc()  # oldest first within priority
    )
    
    items = query.limit(limit).all()
    
    # Build response with matching_result loaded
    results = []
    for item in items:
        matching_result_dict = None
        if item.matching_result:
            invoice = item.matching_result.invoice
            matching_result_dict = {
                "id": str(item.matching_result.id),
                "invoice_id": item.matching_result.invoice_id,
                "po_id": item.matching_result.po_id,
                "match_status": item.matching_result.match_status,
                "confidence_score": float(item.matching_result.confidence_score) if item.matching_result.confidence_score else None,
                "issues": item.matching_result.issues,
                "reasoning": item.matching_result.reasoning,
                "matched_by": item.matching_result.matched_by,
                "matched_at": item.matching_result.matched_at,
                "reviewed_by": item.matching_result.reviewed_by,
                "reviewed_at": item.matching_result.reviewed_at,
                "created_at": item.matching_result.created_at,
                "invoice_number": invoice.invoice_number if invoice else None,
                "vendor_name": invoice.vendor.name if invoice and invoice.vendor else None,
                "total_amount": float(invoice.total_amount) if invoice and invoice.total_amount else None,
                "currency": invoice.currency if invoice else None,
            }
        
        item_dict = {
            "id": str(item.id),
            "matching_result_id": str(item.matching_result_id),
            "priority": item.priority,
            "issue_category": item.issue_category,
            "assigned_to": item.assigned_to,
            "sla_deadline": item.sla_deadline,
            "created_at": item.created_at,
            "resolved_at": item.resolved_at,
            "resolution_notes": item.resolution_notes,
            "matching_result": matching_result_dict
        }
        results.append(ReviewQueueItemResponse(**item_dict))
    
    return results


@router.post("/review-queue/{queue_id}/resolve", response_model=ReviewQueueItemResponse)
def resolve_review_queue_item(
    queue_id: UUID,
    resolve_request: ReviewQueueResolveRequest,
    db: Session = Depends(get_db)
):
    """
    Resolve a review queue item (approve or reject).
    """
    queue_item = db.query(ReviewQueue).filter(ReviewQueue.id == queue_id).first()
    if not queue_item:
        raise HTTPException(status_code=404, detail="Review queue item not found")
    
    if queue_item.resolved_at:
        raise HTTPException(status_code=400, detail="Item already resolved")
    
    # Update queue item
    queue_item.resolved_at = datetime.now()
    queue_item.resolution_notes = resolve_request.notes
    
    # Update matching result
    matching_result = queue_item.matching_result
    matching_result.reviewed_by = "user"  # TODO: Get from auth context
    matching_result.reviewed_at = datetime.now()
    
    # Update invoice status based on resolution
    invoice = db.query(Invoice).filter(Invoice.id == matching_result.invoice_id).first()
    if invoice:
        if resolve_request.resolution == "approved":
            invoice.status = "approved"
        else:
            invoice.status = "rejected"
    
    db.commit()
    db.refresh(queue_item)
    
    logger.info(f"Resolved review queue item {queue_id}: {resolve_request.resolution}")
    
    # Build response with matching_result loaded
    item_dict = {
        "id": queue_item.id,
        "matching_result_id": queue_item.matching_result_id,
        "priority": queue_item.priority,
        "issue_category": queue_item.issue_category,
        "assigned_to": queue_item.assigned_to,
        "sla_deadline": queue_item.sla_deadline,
        "created_at": queue_item.created_at,
        "resolved_at": queue_item.resolved_at,
        "resolution_notes": queue_item.resolution_notes,
        "matching_result": MatchingResultResponse.model_validate(queue_item.matching_result) if queue_item.matching_result else None
    }
    return ReviewQueueItemResponse(**item_dict)


@router.post("/batch", response_model=BatchProcessResponse)
async def batch_process_invoices(
    batch_request: BatchProcessRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Process multiple invoices in batch.
    """
    results = []
    errors = []
    
    agent = MatchingAgentV2(db)
    
    for invoice_id in batch_request.invoice_ids:
        try:
            matching_result = await agent.process_invoice(invoice_id)
            
            # Add to review queue if needed
            if matching_result.match_status == "needs_review":
                review_queue_service.add_to_queue(matching_result, db)
            
            results.append(MatchingResultResponse.model_validate(matching_result))
        except Exception as e:
            logger.error(f"Error processing invoice {invoice_id}: {e}", exc_info=True)
            errors.append({
                "invoice_id": invoice_id,
                "error": str(e)
            })
    
    return BatchProcessResponse(
        processed_count=len(results),
        results=results,
        errors=errors
    )

