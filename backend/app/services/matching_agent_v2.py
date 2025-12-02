"""
Matching Agent V2 - Complete rebuild with LLM reasoning and comprehensive validation.
Implements the full decision tree from the spec with exact match requirements.
"""
import json
import logging
from decimal import Decimal
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from langchain_openai import ChatOpenAI

from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceLine
from app.models.purchase_order import PurchaseOrder
from app.models.po_line import POLine
from app.models.matching_result import MatchingResult
from app.schemas.matching_v2 import (
    MatchingIssueV2,
    IssueCategory,
    MatchingResultCreate
)
from app.config import settings

logger = logging.getLogger(__name__)


class MatchingAgentV2:
    """Enhanced matching agent with LLM reasoning and comprehensive validation"""
    
    def __init__(self, db: Session, llm_client: Optional[ChatOpenAI] = None):
        self.db = db
        self.llm = llm_client or ChatOpenAI(
            model=settings.agent_model,
            temperature=settings.agent_temperature,
            api_key=settings.openai_api_key
        )
    
    async def process_invoice(self, invoice_id: int) -> MatchingResult:
        """
        Main entry point - runs full matching pipeline.
        
        Args:
            invoice_id: ID of invoice to process
            
        Returns:
            MatchingResult record
        """
        logger.info(f"Processing invoice {invoice_id} with MatchingAgentV2")
        
        # Load invoice and find PO
        invoice = self._load_invoice(invoice_id)
        po = self._find_po(invoice)
        
        # Run validation decision tree
        issues = []
        issues.extend(self._validate_header(invoice, po))
        
        # Only continue with line item validation if header checks passed
        if not any(issue.severity == "critical" for issue in issues):
            issues.extend(self._validate_line_items(invoice, po))
            issues.extend(self._validate_calculations(invoice, po))
        
        # LLM reasoning pass
        reasoning = await self._generate_reasoning(invoice, po, issues)
        
        # Determine status and confidence
        status, confidence = self._calculate_result(issues)
        
        # Persist result
        return self._save_result(invoice, po, status, confidence, issues, reasoning)
    
    def _load_invoice(self, invoice_id: int) -> Invoice:
        """Load invoice with lines"""
        invoice = self.db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        return invoice
    
    def _find_po(self, invoice: Invoice) -> Optional[PurchaseOrder]:
        """Find PO by PO number"""
        if not invoice.po_number:
            return None
        
        return self.db.query(PurchaseOrder).filter(
            PurchaseOrder.po_number == invoice.po_number
        ).first()
    
    def _validate_header(self, invoice: Invoice, po: Optional[PurchaseOrder]) -> List[MatchingIssueV2]:
        """
        Validate header-level fields (decision tree steps 1-7).
        
        Returns:
            List of MatchingIssueV2 objects
        """
        issues = []
        
        # 1. PO number exists
        if not invoice.po_number:
            issues.append(MatchingIssueV2(
                category=IssueCategory.MISSING_REFERENCE,
                severity="critical",
                message="Invoice has no PO number",
                details={"invoice_id": invoice.id, "invoice_number": invoice.invoice_number}
            ))
            return issues  # Can't continue without PO
        
        # 2. PO found in database
        if not po:
            issues.append(MatchingIssueV2(
                category=IssueCategory.MISSING_REFERENCE,
                severity="critical",
                message=f"PO {invoice.po_number} not found in database",
                details={"po_number": invoice.po_number, "invoice_id": invoice.id}
            ))
            return issues
        
        # 3. Duplicate check - check if invoice_number already processed for this vendor
        existing_invoice = self.db.query(Invoice).filter(
            Invoice.invoice_number == invoice.invoice_number,
            Invoice.vendor_id == invoice.vendor_id,
            Invoice.id != invoice.id,
            Invoice.status.in_(["matched", "approved", "processed"])
        ).first()
        
        if existing_invoice:
            issues.append(MatchingIssueV2(
                category=IssueCategory.DUPLICATE_INVOICE,
                severity="critical",
                message=f"Invoice {invoice.invoice_number} already processed for vendor",
                details={
                    "invoice_number": invoice.invoice_number,
                    "existing_invoice_id": existing_invoice.id,
                    "vendor_id": invoice.vendor_id
                }
            ))
        
        # 4. Vendor match (exact)
        if invoice.vendor_id != po.vendor_id:
            issues.append(MatchingIssueV2(
                category=IssueCategory.VENDOR_MISMATCH,
                severity="critical",
                message="Invoice vendor does not match PO vendor",
                details={
                    "invoice_vendor_id": invoice.vendor_id,
                    "po_vendor_id": po.vendor_id
                }
            ))
        
        # 5. Total match (exact - no tolerance for exact match requirement)
        invoice_total = float(invoice.total_amount) if invoice.total_amount else 0
        po_total = float(po.total_amount) if po.total_amount else 0
        
        if abs(invoice_total - po_total) > 0.01:  # Allow 1 cent rounding difference
            difference = invoice_total - po_total
            difference_percent = (difference / po_total * 100) if po_total > 0 else 0
            
            issues.append(MatchingIssueV2(
                category=IssueCategory.TOTAL_MISMATCH,
                severity="high" if abs(difference_percent) > 5 else "medium",
                message=f"Invoice total ({invoice_total}) does not match PO total ({po_total})",
                details={
                    "invoice_total": invoice_total,
                    "po_total": po_total,
                    "difference": difference,
                    "difference_percent": difference_percent
                }
            ))
        
        # 6. Currency match
        invoice_currency = (invoice.currency or "USD").upper()
        po_currency = (po.currency or "USD").upper()
        
        if invoice_currency != po_currency:
            issues.append(MatchingIssueV2(
                category=IssueCategory.TOTAL_MISMATCH,  # Currency mismatch affects total
                severity="high",
                message=f"Invoice currency ({invoice_currency}) does not match PO currency ({po_currency})",
                details={
                    "invoice_currency": invoice_currency,
                    "po_currency": po_currency
                }
            ))
        
        # 7. Date validation (invoice_date > po_date)
        if invoice.invoice_date and po.order_date:
            if invoice.invoice_date < po.order_date:
                issues.append(MatchingIssueV2(
                    category=IssueCategory.DATE_ANOMALY,
                    severity="medium",
                    message=f"Invoice date ({invoice.invoice_date}) is before PO date ({po.order_date})",
                    details={
                        "invoice_date": invoice.invoice_date.isoformat(),
                        "po_date": po.order_date.isoformat()
                    }
                ))
        
        return issues
    
    def _validate_line_items(self, invoice: Invoice, po: PurchaseOrder) -> List[MatchingIssueV2]:
        """
        Validate line item-level fields (decision tree step 7).
        
        Returns:
            List of MatchingIssueV2 objects
        """
        issues = []
        
        invoice_lines = invoice.invoice_lines or []
        po_lines = po.po_lines or []
        
        # Line count match
        if len(invoice_lines) != len(po_lines):
            issues.append(MatchingIssueV2(
                category=IssueCategory.LINE_COUNT_MISMATCH,
                severity="high",
                message=f"Invoice has {len(invoice_lines)} line items, PO has {len(po_lines)}",
                details={
                    "invoice_line_count": len(invoice_lines),
                    "po_line_count": len(po_lines)
                }
            ))
        
        # Per-line validation: SKU, quantity, unit_price, line_total
        # Match invoice lines to PO lines by line number or SKU
        po_lines_by_line_no = {line.line_no: line for line in po_lines}
        po_lines_by_sku = {line.sku: line for line in po_lines if line.sku}
        
        matched_po_lines = set()
        
        for inv_line in invoice_lines:
            # Find matching PO line
            po_line = None
            
            # Try by line number first
            if inv_line.line_no in po_lines_by_line_no:
                po_line = po_lines_by_line_no[inv_line.line_no]
            # Try by SKU
            elif inv_line.sku and inv_line.sku in po_lines_by_sku:
                po_line = po_lines_by_sku[inv_line.sku]
            
            if not po_line:
                issues.append(MatchingIssueV2(
                    category=IssueCategory.LINE_ITEM_DISCREPANCY,
                    severity="high",
                    message=f"Invoice line {inv_line.line_no} not found in PO",
                    details={
                        "invoice_line_no": inv_line.line_no,
                        "invoice_sku": inv_line.sku,
                        "invoice_description": inv_line.description
                    },
                    line_number=inv_line.line_no
                ))
                continue
            
            # Check if PO line already matched
            if po_line.id in matched_po_lines:
                issues.append(MatchingIssueV2(
                    category=IssueCategory.LINE_ITEM_DISCREPANCY,
                    severity="high",
                    message=f"PO line {po_line.line_no} matched to multiple invoice lines",
                    details={
                        "po_line_no": po_line.line_no
                    },
                    line_number=inv_line.line_no
                ))
                continue
            
            matched_po_lines.add(po_line.id)
            
            # Exact quantity match
            inv_qty = float(inv_line.quantity) if inv_line.quantity else 0
            po_qty = float(po_line.quantity) if po_line.quantity else 0
            
            if abs(inv_qty - po_qty) > 0.01:  # Allow 1 cent rounding
                if inv_qty > po_qty:
                    issues.append(MatchingIssueV2(
                        category=IssueCategory.QUANTITY_OVERAGE,
                        severity="high",
                        message=f"Line {inv_line.line_no}: Invoice quantity ({inv_qty}) exceeds PO quantity ({po_qty})",
                        details={
                            "invoice_qty": inv_qty,
                            "po_qty": po_qty,
                            "overage": inv_qty - po_qty
                        },
                        line_number=inv_line.line_no
                    ))
                else:
                    issues.append(MatchingIssueV2(
                        category=IssueCategory.LINE_ITEM_DISCREPANCY,
                        severity="medium",
                        message=f"Line {inv_line.line_no}: Quantity mismatch (invoice: {inv_qty}, PO: {po_qty})",
                        details={
                            "invoice_qty": inv_qty,
                            "po_qty": po_qty
                        },
                        line_number=inv_line.line_no
                    ))
            
            # Exact unit price match
            inv_price = float(inv_line.unit_price) if inv_line.unit_price else 0
            po_price = float(po_line.unit_price) if po_line.unit_price else 0
            
            if abs(inv_price - po_price) > 0.01:  # Allow 1 cent rounding
                issues.append(MatchingIssueV2(
                    category=IssueCategory.LINE_ITEM_DISCREPANCY,
                    severity="high",
                    message=f"Line {inv_line.line_no}: Unit price mismatch (invoice: {inv_price}, PO: {po_price})",
                    details={
                        "invoice_unit_price": inv_price,
                        "po_unit_price": po_price,
                        "difference": inv_price - po_price
                    },
                    line_number=inv_line.line_no
                ))
            
            # SKU/description match (if SKU exists)
            if inv_line.sku and po_line.sku:
                if inv_line.sku != po_line.sku:
                    issues.append(MatchingIssueV2(
                        category=IssueCategory.LINE_ITEM_DISCREPANCY,
                        severity="medium",
                        message=f"Line {inv_line.line_no}: SKU mismatch (invoice: {inv_line.sku}, PO: {po_line.sku})",
                        details={
                            "invoice_sku": inv_line.sku,
                            "po_sku": po_line.sku
                        },
                        line_number=inv_line.line_no
                    ))
        
        # Check for unmatched PO lines
        for po_line in po_lines:
            if po_line.id not in matched_po_lines:
                issues.append(MatchingIssueV2(
                    category=IssueCategory.LINE_ITEM_DISCREPANCY,
                    severity="medium",
                    message=f"PO line {po_line.line_no} not found in invoice",
                    details={
                        "po_line_no": po_line.line_no,
                        "po_sku": po_line.sku,
                        "po_description": po_line.description
                    }
                ))
        
        return issues
    
    def _validate_calculations(self, invoice: Invoice, po: PurchaseOrder) -> List[MatchingIssueV2]:
        """
        Validate calculations: line totals and document totals.
        
        Returns:
            List of MatchingIssueV2 objects
        """
        issues = []
        
        invoice_lines = invoice.invoice_lines or []
        po_lines = po.po_lines or []
        
        # Validate invoice line totals
        invoice_line_total_sum = 0
        for inv_line in invoice_lines:
            qty = float(inv_line.quantity) if inv_line.quantity else 0
            price = float(inv_line.unit_price) if inv_line.unit_price else 0
            expected_line_total = qty * price
            
            # Note: InvoiceLine doesn't have line_total field, so we can't validate it
            # But we can validate the sum matches the document total
            invoice_line_total_sum += expected_line_total
        
        invoice_total = float(invoice.total_amount) if invoice.total_amount else 0
        
        if abs(invoice_line_total_sum - invoice_total) > 0.01:
            issues.append(MatchingIssueV2(
                category=IssueCategory.CALCULATION_ERROR,
                severity="high",
                message=f"Sum of invoice line totals ({invoice_line_total_sum}) does not match invoice total ({invoice_total})",
                details={
                    "calculated_total": invoice_line_total_sum,
                    "invoice_total": invoice_total,
                    "difference": invoice_line_total_sum - invoice_total
                }
            ))
        
        # Validate PO line totals
        po_line_total_sum = 0
        for po_line in po_lines:
            qty = float(po_line.quantity) if po_line.quantity else 0
            price = float(po_line.unit_price) if po_line.unit_price else 0
            po_line_total_sum += qty * price
        
        po_total = float(po.total_amount) if po.total_amount else 0
        
        if abs(po_line_total_sum - po_total) > 0.01:
            issues.append(MatchingIssueV2(
                category=IssueCategory.CALCULATION_ERROR,
                severity="high",
                message=f"Sum of PO line totals ({po_line_total_sum}) does not match PO total ({po_total})",
                details={
                    "calculated_total": po_line_total_sum,
                    "po_total": po_total,
                    "difference": po_line_total_sum - po_total
                }
            ))
        
        return issues
    
    async def _generate_reasoning(self, invoice: Invoice, po: Optional[PurchaseOrder], issues: List[MatchingIssueV2]) -> str:
        """
        Generate LLM reasoning for the matching decision.
        
        Returns:
            Reasoning text
        """
        try:
            # Serialize invoice and PO data
            invoice_data = self._serialize_invoice(invoice)
            po_data = self._serialize_po(po) if po else None
            
            prompt = f"""You are an expert accounts payable analyst reviewing invoice-PO matches.

Invoice Data:
{json.dumps(invoice_data, indent=2, default=str)}

Purchase Order Data:
{json.dumps(po_data, indent=2, default=str) if po_data else "PO not found"}

Validation Issues Found:
{json.dumps([issue.dict() for issue in issues], indent=2, default=str)}

Your task:
1. Analyze the discrepancies found during automated validation
2. Determine if this is a "matched" (no issues) or "needs_review" (has issues) case
3. Provide clear, concise reasoning explaining your decision (2-3 sentences)
4. Categorize the primary issue type if needs_review
5. Suggest a recommended action

Output format (JSON):
{{
    "status": "matched" or "needs_review",
    "primary_issue": "category_name" or null,
    "reasoning": "2-3 sentence explanation",
    "recommended_action": "brief next step suggestion"
}}
"""
            
            response = await self.llm.ainvoke(prompt)
            content = response.content
            
            # Parse JSON from response (might be wrapped in markdown)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            reasoning_data = json.loads(content)
            return reasoning_data.get("reasoning", "No reasoning provided")
            
        except Exception as e:
            logger.error(f"Error generating LLM reasoning: {e}", exc_info=True)
            return f"Automated validation found {len(issues)} issue(s). Manual review recommended."
    
    def _serialize_invoice(self, invoice: Invoice) -> Dict[str, Any]:
        """Serialize invoice for LLM prompt"""
        return {
            "id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "vendor_id": invoice.vendor_id,
            "po_number": invoice.po_number,
            "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
            "total_amount": float(invoice.total_amount) if invoice.total_amount else None,
            "currency": invoice.currency,
            "line_items": [
                {
                    "line_no": line.line_no,
                    "sku": line.sku,
                    "description": line.description,
                    "quantity": float(line.quantity) if line.quantity else None,
                    "unit_price": float(line.unit_price) if line.unit_price else None
                }
                for line in (invoice.invoice_lines or [])
            ]
        }
    
    def _serialize_po(self, po: PurchaseOrder) -> Dict[str, Any]:
        """Serialize PO for LLM prompt"""
        return {
            "id": po.id,
            "po_number": po.po_number,
            "vendor_id": po.vendor_id,
            "order_date": po.order_date.isoformat() if po.order_date else None,
            "total_amount": float(po.total_amount) if po.total_amount else None,
            "currency": po.currency,
            "line_items": [
                {
                    "line_no": line.line_no,
                    "sku": line.sku,
                    "description": line.description,
                    "quantity": float(line.quantity) if line.quantity else None,
                    "unit_price": float(line.unit_price) if line.unit_price else None
                }
                for line in (po.po_lines or [])
            ]
        }
    
    def _calculate_result(self, issues: List[MatchingIssueV2]) -> tuple[str, float]:
        """
        Calculate match status and confidence score based on issues.
        
        Returns:
            (status, confidence_score) tuple
        """
        if not issues:
            return ("matched", 1.0)
        
        # Check for critical issues
        critical_issues = [i for i in issues if i.severity == "critical"]
        if critical_issues:
            return ("needs_review", 0.0)
        
        # Calculate confidence based on issue severity and count
        severity_weights = {
            "high": 0.3,
            "medium": 0.5,
            "low": 0.7
        }
        
        min_confidence = 1.0
        for issue in issues:
            weight = severity_weights.get(issue.severity, 0.5)
            min_confidence = min(min_confidence, weight)
        
        # Reduce confidence further based on number of issues
        issue_penalty = min(len(issues) * 0.1, 0.5)
        confidence = max(0.0, min_confidence - issue_penalty)
        
        return ("needs_review", confidence)
    
    def _save_result(self, invoice: Invoice, po: Optional[PurchaseOrder], status: str, 
                     confidence: float, issues: List[MatchingIssueV2], reasoning: str) -> MatchingResult:
        """Save matching result to database"""
        
        # Convert issues to JSONB format
        issues_json = [issue.dict() for issue in issues]
        
        matching_result = MatchingResult(
            invoice_id=invoice.id,
            po_id=po.id if po else None,
            match_status=status,
            confidence_score=Decimal(str(confidence)),
            issues=issues_json,
            reasoning=reasoning,
            matched_by="agent"
        )
        
        self.db.add(matching_result)
        
        # Update invoice status
        if status == "matched":
            invoice.status = "matched"
        else:
            invoice.status = "needs_review"
        
        self.db.commit()
        self.db.refresh(matching_result)
        
        logger.info(f"Saved matching result {matching_result.id} for invoice {invoice.id}: {status} (confidence: {confidence:.2f})")
        
        return matching_result

