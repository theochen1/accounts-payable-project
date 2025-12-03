"""
Document Pair Service - Manages document pairs and workflow progression.
"""
import logging
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from uuid import UUID
from decimal import Decimal

from app.models.document_pair import DocumentPair
from app.models.validation_issue import ValidationIssue
from app.models.matching_result import MatchingResult
from app.models.invoice import Invoice
from app.models.purchase_order import PurchaseOrder
from app.models.invoice_line import InvoiceLine
from app.models.po_line import POLine
from app.models.document import Document
from app.schemas.document_pair import (
    ValidationIssueResponse,
    TimelineEntry,
    LineItemComparison,
    FieldComparison,
    IssueResolutionRequest,
    StageTimestamps
)
from app.schemas.matching_v2 import MatchingIssueV2, IssueCategory

logger = logging.getLogger(__name__)


class DocumentPairService:
    """Service for managing document pairs and workflow"""
    
    def create_pair(
        self,
        invoice_id: int,
        po_id: Optional[int],
        matching_result_id: UUID,
        db: Session
    ) -> DocumentPair:
        """
        Create document pair after matching, extract issues from matching result.
        
        Args:
            invoice_id: Invoice ID
            po_id: Purchase Order ID (can be None)
            matching_result_id: Matching result UUID
            db: Database session
            
        Returns:
            Created DocumentPair
        """
        # Check if pair already exists
        existing = db.query(DocumentPair).filter(
            DocumentPair.invoice_id == invoice_id,
            DocumentPair.po_id == po_id
        ).first()
        
        if existing:
            logger.info(f"Document pair already exists for invoice {invoice_id}, PO {po_id}")
            return existing
        
        # Load matching result
        matching_result = db.query(MatchingResult).filter(
            MatchingResult.id == matching_result_id
        ).first()
        
        if not matching_result:
            raise ValueError(f"Matching result {matching_result_id} not found")
        
        # Get invoice and document to extract timestamps
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        
        # Extract timestamps from invoice's source document
        uploaded_at = None
        extracted_at = None
        if invoice.source_document_id:
            document = db.query(Document).filter(Document.id == invoice.source_document_id).first()
            if document:
                uploaded_at = document.uploaded_at
                extracted_at = document.processed_at if document.status == "processed" else None
        
        # Create pair
        pair = DocumentPair(
            invoice_id=invoice_id,
            po_id=po_id,
            matching_result_id=matching_result_id,
            current_stage="matched",
            overall_status="needs_review" if matching_result.match_status == "needs_review" else "in_progress",
            uploaded_at=uploaded_at,
            extracted_at=extracted_at,
            matched_at=datetime.now(),
            requires_review=matching_result.match_status == "needs_review",
            has_critical_issues=any(
                issue.get("severity") == "critical" 
                for issue in (matching_result.issues or [])
            )
        )
        
        db.add(pair)
        db.flush()  # Get pair.id
        
        # Extract issues from matching result
        issues = self._extract_issues_from_matching(matching_result, pair.id)
        
        # Create validation issues
        for issue_data in issues:
            validation_issue = ValidationIssue(
                document_pair_id=pair.id,
                **issue_data
            )
            db.add(validation_issue)
        
        db.commit()
        db.refresh(pair)
        
        logger.info(f"Created document pair {pair.id} for invoice {invoice_id}, PO {po_id}")
        return pair
    
    def get_pairs(
        self,
        db: Session,
        status: Optional[List[str]] = None,
        stage: Optional[List[str]] = None,
        has_issues: Optional[bool] = None,
        vendor: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[DocumentPair]:
        """
        List pairs with filtering.
        
        Args:
            db: Database session
            status: Filter by overall_status
            stage: Filter by current_stage
            has_issues: Filter by requires_review
            vendor: Filter by vendor name
            limit: Max results
            offset: Pagination offset
            
        Returns:
            List of DocumentPair objects
        """
        query = db.query(DocumentPair).options(
            joinedload(DocumentPair.invoice).joinedload(Invoice.vendor),
            joinedload(DocumentPair.purchase_order)
        )
        
        if status:
            query = query.filter(DocumentPair.overall_status.in_(status))
        
        if stage:
            query = query.filter(DocumentPair.current_stage.in_(stage))
        
        if has_issues is not None:
            query = query.filter(DocumentPair.requires_review == has_issues)
        
        if vendor:
            query = query.join(Invoice).join(Invoice.vendor).filter(
                Invoice.vendor.has(name__ilike=f"%{vendor}%")
            )
        
        return query.order_by(DocumentPair.created_at.desc()).limit(limit).offset(offset).all()
    
    def get_pair_detail(self, pair_id: UUID, db: Session) -> Optional[DocumentPair]:
        """
        Get pair with all relationships loaded.
        
        Args:
            pair_id: Pair UUID
            db: Database session
            
        Returns:
            DocumentPair with all relationships
        """
        return db.query(DocumentPair).options(
            joinedload(DocumentPair.invoice).joinedload(Invoice.invoice_lines),
            joinedload(DocumentPair.invoice).joinedload(Invoice.vendor),
            joinedload(DocumentPair.purchase_order).joinedload(PurchaseOrder.po_lines),
            joinedload(DocumentPair.purchase_order).joinedload(PurchaseOrder.vendor),
            joinedload(DocumentPair.matching_result),
            joinedload(DocumentPair.validation_issues)
        ).filter(DocumentPair.id == pair_id).first()
    
    def get_line_items_comparison(self, pair_id: UUID, db: Session) -> List[LineItemComparison]:
        """
        Compare invoice and PO line items field-by-field.
        
        Args:
            pair_id: Pair UUID
            db: Database session
            
        Returns:
            List of LineItemComparison objects
        """
        pair = self.get_pair_detail(pair_id, db)
        if not pair:
            raise ValueError(f"Pair {pair_id} not found")
        
        invoice_lines = pair.invoice.invoice_lines if pair.invoice else []
        po_lines = pair.purchase_order.po_lines if pair.purchase_order else []
        
        comparisons = []
        
        # Create a map of PO lines by line_no
        po_line_map = {line.line_no: line for line in po_lines}
        
        # Process each invoice line
        for inv_line in invoice_lines:
            po_line = po_line_map.get(inv_line.line_no)
            
            # Field comparisons
            field_comparisons = []
            
            # Description comparison
            desc_match = False
            desc_similarity = None
            if po_line:
                desc_match = inv_line.description.strip().lower() == po_line.description.strip().lower()
                if not desc_match:
                    # Simple similarity check (could use fuzzy matching)
                    desc_similarity = self._calculate_similarity(
                        inv_line.description,
                        po_line.description
                    )
            
            field_comparisons.append(FieldComparison(
                field_name="description",
                invoice_value=inv_line.description,
                po_value=po_line.description if po_line else None,
                match=desc_match,
                similarity=desc_similarity,
                diff_explanation=None if desc_match else "Description mismatch",
                severity="warning" if not desc_match and po_line else None
            ))
            
            # SKU comparison (only if both invoice and PO have SKUs)
            # Skip SKU comparison if either side doesn't have SKU data
            if inv_line.sku and po_line and po_line.sku:
                sku_match = inv_line.sku.strip().lower() == po_line.sku.strip().lower()
                
                field_comparisons.append(FieldComparison(
                    field_name="sku",
                    invoice_value=inv_line.sku,
                    po_value=po_line.sku,
                    match=sku_match,
                    similarity=None,
                    diff_explanation=None if sku_match else "SKU mismatch",
                    severity="warning" if not sku_match else None
                ))
            
            # Quantity comparison
            qty_match = False
            if po_line:
                qty_match = float(inv_line.quantity) == float(po_line.quantity)
            
            field_comparisons.append(FieldComparison(
                field_name="quantity",
                invoice_value=float(inv_line.quantity),
                po_value=float(po_line.quantity) if po_line else None,
                match=qty_match,
                similarity=None,
                diff_explanation=None if qty_match else f"Quantity mismatch: {inv_line.quantity} vs {po_line.quantity if po_line else 'N/A'}",
                severity="high" if not qty_match and po_line else None
            ))
            
            # Unit price comparison
            price_match = False
            if po_line:
                price_match = abs(float(inv_line.unit_price) - float(po_line.unit_price)) < 0.01
            
            field_comparisons.append(FieldComparison(
                field_name="unit_price",
                invoice_value=float(inv_line.unit_price),
                po_value=float(po_line.unit_price) if po_line else None,
                match=price_match,
                similarity=None,
                diff_explanation=None if price_match else f"Price mismatch: ${inv_line.unit_price} vs ${po_line.unit_price if po_line else 'N/A'}",
                severity="high" if not price_match and po_line else None
            ))
            
            # Determine overall match status
            all_match = all(fc.match for fc in field_comparisons)
            if not po_line:
                overall_match = "missing"
            elif all_match:
                overall_match = "perfect"
            elif any(fc.severity == "high" for fc in field_comparisons):
                overall_match = "mismatch"
            else:
                overall_match = "partial"
            
            # Get issues for this line
            line_issues = [
                ValidationIssueResponse.model_validate(issue)
                for issue in pair.validation_issues
                if issue.line_number == inv_line.line_no
            ]
            
            comparisons.append(LineItemComparison(
                line_number=inv_line.line_no,
                invoice_line={
                    "id": inv_line.id,
                    "line_no": inv_line.line_no,
                    "sku": inv_line.sku,
                    "description": inv_line.description,
                    "quantity": float(inv_line.quantity),
                    "unit_price": float(inv_line.unit_price),
                    "line_total": float(inv_line.quantity) * float(inv_line.unit_price)
                },
                po_line={
                    "id": po_line.id,
                    "line_no": po_line.line_no,
                    "sku": po_line.sku,
                    "description": po_line.description,
                    "quantity": float(po_line.quantity),
                    "unit_price": float(po_line.unit_price),
                    "line_total": float(po_line.quantity) * float(po_line.unit_price)
                } if po_line else None,
                field_comparisons=field_comparisons,
                overall_match=overall_match,
                issues=line_issues
            ))
        
        return comparisons
    
    def get_timeline(self, pair_id: UUID, db: Session) -> List[TimelineEntry]:
        """
        Build timeline from pair, invoice, document, and matching_result timestamps.
        
        Args:
            pair_id: Pair UUID
            db: Database session
            
        Returns:
            List of TimelineEntry objects sorted by timestamp
        """
        pair = self.get_pair_detail(pair_id, db)
        if not pair:
            raise ValueError(f"Pair {pair_id} not found")
        
        timeline = []
        
        # Upload event
        if pair.uploaded_at:
            timeline.append(TimelineEntry(
                timestamp=pair.uploaded_at,
                event_type="uploaded",
                description=f"Document uploaded",
                actor=None,
                details={"document_id": pair.invoice.source_document_id}
            ))
        
        # Extraction event
        if pair.extracted_at:
            timeline.append(TimelineEntry(
                timestamp=pair.extracted_at,
                event_type="extracted",
                description="OCR extraction completed",
                actor="ocr_agent",
                details={}
            ))
        
        # Matching event
        if pair.matched_at:
            timeline.append(TimelineEntry(
                timestamp=pair.matched_at,
                event_type="matched",
                description=f"Invoice {pair.invoice.invoice_number} matched to PO {pair.purchase_order.po_number if pair.purchase_order else 'N/A'}",
                actor="matching_agent",
                details={
                    "matching_result_id": str(pair.matching_result_id),
                    "confidence": float(pair.matching_result.confidence_score) if pair.matching_result else None
                }
            ))
        
        # Validation event (if validated)
        if pair.validated_at:
            timeline.append(TimelineEntry(
                timestamp=pair.validated_at,
                event_type="validated",
                description="Line items validated",
                actor="matching_agent",
                details={}
            ))
        
        # Approval event
        if pair.approved_at:
            timeline.append(TimelineEntry(
                timestamp=pair.approved_at,
                event_type="approved",
                description=f"Pair approved",
                actor=None,
                details={"status": pair.overall_status}
            ))
        
        # Issue resolution events
        for issue in pair.validation_issues:
            if issue.resolved_at:
                timeline.append(TimelineEntry(
                    timestamp=issue.resolved_at,
                    event_type="issue_resolved",
                    description=f"Issue resolved: {issue.description}",
                    actor=issue.resolved_by,
                    details={
                        "issue_id": str(issue.id),
                        "resolution_action": issue.resolution_action
                    }
                ))
        
        # Sort by timestamp descending
        timeline.sort(key=lambda x: x.timestamp, reverse=True)
        
        return timeline
    
    def resolve_issue(
        self,
        pair_id: UUID,
        issue_id: UUID,
        resolution: IssueResolutionRequest,
        db: Session
    ) -> ValidationIssue:
        """
        Mark issue as resolved, check if all issues resolved to advance stage.
        
        Args:
            pair_id: Pair UUID
            issue_id: Issue UUID
            resolution: Resolution request
            db: Database session
            
        Returns:
            Updated ValidationIssue
        """
        pair = db.query(DocumentPair).filter(DocumentPair.id == pair_id).first()
        if not pair:
            raise ValueError(f"Pair {pair_id} not found")
        
        issue = db.query(ValidationIssue).filter(
            ValidationIssue.id == issue_id,
            ValidationIssue.document_pair_id == pair_id
        ).first()
        
        if not issue:
            raise ValueError(f"Issue {issue_id} not found")
        
        issue.resolved = True
        issue.resolved_at = datetime.now()
        issue.resolved_by = "user"  # TODO: Get from auth context
        issue.resolution_action = resolution.resolution_action
        issue.resolution_notes = resolution.notes
        
        db.commit()
        db.refresh(issue)
        
        # Check if all issues are resolved
        unresolved_count = db.query(ValidationIssue).filter(
            ValidationIssue.document_pair_id == pair_id,
            ValidationIssue.resolved == False
        ).count()
        
        if unresolved_count == 0:
            pair.requires_review = False
            if pair.overall_status == "needs_review":
                pair.overall_status = "in_progress"
            db.commit()
        
        logger.info(f"Resolved issue {issue_id} for pair {pair_id}")
        return issue
    
    def advance_stage(self, pair_id: UUID, db: Session) -> DocumentPair:
        """
        Move to next workflow stage if conditions met.
        
        Args:
            pair_id: Pair UUID
            db: Database session
            
        Returns:
            Updated DocumentPair
        """
        pair = db.query(DocumentPair).filter(DocumentPair.id == pair_id).first()
        if not pair:
            raise ValueError(f"Pair {pair_id} not found")
        
        stage_order = {
            "matched": "validated",
            "validated": "approved",
        }
        
        next_stage = stage_order.get(pair.current_stage)
        if next_stage:
            pair.current_stage = next_stage
            setattr(pair, f"{next_stage}_at", datetime.now())
            db.commit()
            db.refresh(pair)
            logger.info(f"Advanced pair {pair_id} to stage {next_stage}")
        
        return pair
    
    def approve_pair(self, pair_id: UUID, notes: str, db: Session) -> DocumentPair:
        """
        Approve pair, update invoice status.
        
        Args:
            pair_id: Pair UUID
            notes: Approval notes
            db: Database session
            
        Returns:
            Updated DocumentPair
        """
        pair = self.get_pair_detail(pair_id, db)
        if not pair:
            raise ValueError(f"Pair {pair_id} not found")
        
        pair.overall_status = "approved"
        pair.current_stage = "approved"
        pair.approved_at = datetime.now()
        
        # Update invoice status
        if pair.invoice:
            pair.invoice.status = "approved"
        
        db.commit()
        db.refresh(pair)
        
        logger.info(f"Approved pair {pair_id}")
        return pair
    
    def reject_pair(self, pair_id: UUID, reason: str, db: Session) -> DocumentPair:
        """
        Reject pair, update invoice status.
        
        Args:
            pair_id: Pair UUID
            reason: Rejection reason
            db: Database session
            
        Returns:
            Updated DocumentPair
        """
        pair = self.get_pair_detail(pair_id, db)
        if not pair:
            raise ValueError(f"Pair {pair_id} not found")
        
        pair.overall_status = "rejected"
        
        # Update invoice status
        if pair.invoice:
            pair.invoice.status = "rejected"
        
        db.commit()
        db.refresh(pair)
        
        logger.info(f"Rejected pair {pair_id}: {reason}")
        return pair
    
    def _extract_issues_from_matching(
        self,
        matching_result: MatchingResult,
        pair_id: UUID
    ) -> List[dict]:
        """
        Convert MatchingIssueV2 objects to ValidationIssue records.
        
        Args:
            matching_result: MatchingResult with issues
            pair_id: Document pair UUID
            
        Returns:
            List of issue dictionaries
        """
        issues = []
        
        if not matching_result.issues:
            return issues
        
        for issue_data in matching_result.issues:
            # Handle both dict and MatchingIssueV2 objects
            if isinstance(issue_data, dict):
                issue_dict = issue_data
            else:
                issue_dict = issue_data.dict() if hasattr(issue_data, 'dict') else issue_data
            
            # Extract field from details if available
            field = issue_dict.get("details", {}).get("field") or issue_dict.get("field")
            
            # Extract invoice_value and po_value from details
            # Handle various field types: invoice_value/po_value, invoice_description/po_description, etc.
            details = issue_dict.get("details", {})
            invoice_value = (
                details.get("invoice_value") or 
                details.get("invoice_description") or
                details.get("invoice_sku") or
                details.get("invoice_qty") or
                details.get("invoice_unit_price")
            )
            po_value = (
                details.get("po_value") or 
                details.get("po_description") or
                details.get("po_sku") or
                details.get("po_qty") or
                details.get("po_unit_price")
            )
            
            issues.append({
                "category": issue_dict.get("category", "unknown"),
                "severity": issue_dict.get("severity", "low"),
                "field": field,
                "description": issue_dict.get("message", issue_dict.get("description", "")),
                "invoice_value": invoice_value,
                "po_value": po_value,
                "suggestion": None,  # Could be extracted from LLM reasoning
                "line_number": issue_dict.get("line_number")
            })
        
        return issues
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """
        Simple similarity calculation (Levenshtein-based).
        Returns value between 0 and 1.
        """
        if not str1 or not str2:
            return 0.0
        
        if str1.lower() == str2.lower():
            return 1.0
        
        # Simple character overlap similarity
        set1 = set(str1.lower())
        set2 = set(str2.lower())
        
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0


# Singleton instance
document_pair_service = DocumentPairService()

