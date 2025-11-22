from sqlalchemy.orm import Session
from typing import Optional
from app.models.invoice import Invoice
from app.models.purchase_order import PurchaseOrder
from app.schemas.matching import MatchingResult, MatchingIssue, LineItemMatch
from app.utils.matching_rules import (
    check_po_exists,
    check_vendor_match,
    check_currency_match,
    check_total_match,
    match_line_items
)
from app.config import settings


def match_invoice_to_po(db: Session, invoice_id: int) -> MatchingResult:
    """
    Main matching function: matches an invoice to its PO and returns a structured result
    
    Args:
        db: Database session
        invoice_id: ID of the invoice to match
        
    Returns:
        MatchingResult object with status, issues, and line item matches
    """
    # Fetch invoice with lines
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise ValueError(f"Invoice {invoice_id} not found")
    
    if not invoice.po_number:
        return MatchingResult(
            status="exception",
            overall_match=False,
            issues=[MatchingIssue(
                type="missing_po",
                severity="exception",
                message="Invoice does not have a PO number",
                details={}
            )]
        )
    
    # Fetch PO with lines
    po = db.query(PurchaseOrder).filter(PurchaseOrder.po_number == invoice.po_number).first()
    
    # Run matching rules
    issues = []
    line_item_matches = []
    
    # Check PO exists
    po_exists, issue = check_po_exists(po, invoice.po_number)
    if not po_exists:
        return MatchingResult(
            status="exception",
            overall_match=False,
            issues=[issue] if issue else []
        )
    
    # Check vendor match
    vendor_match, issue = check_vendor_match(invoice.vendor_id, po.vendor_id)
    if not vendor_match and issue:
        issues.append(issue)
    
    # Check currency match
    currency_match, issue = check_currency_match(invoice.currency or "USD", po.currency or "USD")
    if not currency_match and issue:
        issues.append(issue)
    
    # Check total match
    total_match, issue, total_diff, total_diff_percent = check_total_match(
        invoice.total_amount,
        po.total_amount,
        settings.matching_tolerance
    )
    if not total_match and issue:
        issues.append(issue)
    
    # Match line items
    if invoice.invoice_lines and po.po_lines:
        line_item_matches = match_line_items(invoice.invoice_lines, po.po_lines)
        # Add line item issues to main issues list
        for line_match in line_item_matches:
            if not line_match.matched and line_match.issues:
                issues.append(MatchingIssue(
                    type="line_item_mismatch",
                    severity="needs_review",
                    message=f"Line {line_match.invoice_line_no}: {', '.join(line_match.issues)}",
                    details={
                        "invoice_line_no": line_match.invoice_line_no,
                        "po_line_no": line_match.po_line_no,
                        "issues": line_match.issues
                    }
                ))
    
    # Determine overall status
    has_exception = any(issue.severity == "exception" for issue in issues)
    has_needs_review = any(issue.severity == "needs_review" for issue in issues)
    
    if has_exception:
        status = "exception"
    elif has_needs_review or len(line_item_matches) > 0 and not all(m.matched for m in line_item_matches):
        status = "needs_review"
    else:
        status = "matched"
    
    overall_match = status == "matched" and len(issues) == 0
    
    # Update invoice status
    invoice.status = status
    db.commit()
    
    return MatchingResult(
        status=status,
        overall_match=overall_match,
        issues=issues,
        line_item_matches=line_item_matches,
        vendor_match=vendor_match,
        currency_match=currency_match,
        total_match=total_match,
        total_difference=total_diff,
        total_difference_percent=total_diff_percent
    )

