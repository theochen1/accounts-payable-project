from typing import List, Tuple, Optional
from decimal import Decimal
import difflib
from app.models.purchase_order import PurchaseOrder
from app.models.po_line import POLine
from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceLine
from app.schemas.matching import MatchingIssue, LineItemMatch
from app.config import settings


def check_po_exists(po: Optional[PurchaseOrder], po_number: str) -> Tuple[bool, Optional[MatchingIssue]]:
    """
    Check if PO exists
    
    Returns:
        (exists, issue) tuple
    """
    if po is None:
        return False, MatchingIssue(
            type="missing_po",
            severity="exception",
            message=f"Purchase order {po_number} not found",
            details={"po_number": po_number}
        )
    return True, None


def check_vendor_match(invoice_vendor_id: Optional[int], po_vendor_id: int) -> Tuple[bool, Optional[MatchingIssue]]:
    """
    Check if invoice vendor matches PO vendor
    
    Returns:
        (matches, issue) tuple
    """
    if invoice_vendor_id is None:
        return False, MatchingIssue(
            type="vendor_mismatch",
            severity="exception",
            message="Invoice vendor not identified",
            details={"invoice_vendor_id": None, "po_vendor_id": po_vendor_id}
        )
    
    if invoice_vendor_id != po_vendor_id:
        return False, MatchingIssue(
            type="vendor_mismatch",
            severity="exception",
            message="Invoice vendor does not match PO vendor",
            details={"invoice_vendor_id": invoice_vendor_id, "po_vendor_id": po_vendor_id}
        )
    
    return True, None


def check_currency_match(invoice_currency: str, po_currency: str) -> Tuple[bool, Optional[MatchingIssue]]:
    """
    Check if invoice currency matches PO currency
    
    Returns:
        (matches, issue) tuple
    """
    if invoice_currency.upper() != po_currency.upper():
        return False, MatchingIssue(
            type="currency_mismatch",
            severity="exception",
            message=f"Invoice currency ({invoice_currency}) does not match PO currency ({po_currency})",
            details={"invoice_currency": invoice_currency, "po_currency": po_currency}
        )
    return True, None


def check_total_match(
    invoice_total: Optional[Decimal],
    po_total: Decimal,
    tolerance: Optional[float] = None
) -> Tuple[bool, Optional[MatchingIssue], Optional[Decimal], Optional[float]]:
    """
    Check if invoice total matches PO total within tolerance
    
    Returns:
        (matches, issue, difference, difference_percent) tuple
    """
    if tolerance is None:
        tolerance = settings.matching_tolerance
    
    if invoice_total is None:
        return False, MatchingIssue(
            type="total_mismatch",
            severity="exception",
            message="Invoice total amount is missing",
            details={"po_total": float(po_total)}
        ), None, None
    
    difference = abs(float(invoice_total) - float(po_total))
    difference_percent = (difference / float(po_total)) * 100 if float(po_total) > 0 else 0
    
    if difference_percent > (tolerance * 100):  # Convert tolerance to percentage
        severity = "exception" if difference_percent > 5 else "needs_review"
        return False, MatchingIssue(
            type="total_mismatch",
            severity=severity,
            message=f"Invoice total ({invoice_total}) differs from PO total ({po_total}) by {difference_percent:.2f}%",
            details={
                "invoice_total": float(invoice_total),
                "po_total": float(po_total),
                "difference": difference,
                "difference_percent": difference_percent
            }
        ), Decimal(str(difference)), difference_percent
    
    return True, None, Decimal(str(difference)), difference_percent


def match_line_items(
    invoice_lines: List[InvoiceLine],
    po_lines: List[POLine]
) -> List[LineItemMatch]:
    """
`    Match invoice line items to PO line items using fuzzy matching
    
    Matching strategy (in order of priority):
    1. Exact SKU match
    2. Exact description match (case-insensitive)
    3. Fuzzy description match (similarity >= 0.7)
    4. Substring match
    5. Fuzzy match with quantity/price similarity bonus
    
    Returns:
        List of LineItemMatch objects
    """
    matches = []
    
    # Create lookup dictionaries
    po_lines_by_sku = {line.sku: line for line in po_lines if line.sku}
    po_lines_by_exact_desc = {line.description.lower().strip(): line for line in po_lines}
    
    # Track which PO lines have been matched
    matched_po_lines = set()
    
    # Fuzzy matching threshold
    FUZZY_THRESHOLD = 0.7  # 70% similarity required
    
    def calculate_similarity(desc1: str, desc2: str) -> float:
        """Calculate string similarity using SequenceMatcher"""
        return difflib.SequenceMatcher(None, desc1.lower().strip(), desc2.lower().strip()).ratio()
    
    def find_best_po_match(invoice_line: InvoiceLine, available_po_lines: List[POLine]) -> Tuple[Optional[POLine], float]:
        """
        Find the best matching PO line using multiple criteria
        
        Returns:
            (best_po_line, confidence_score) tuple
        """
        invoice_desc = invoice_line.description.lower().strip() if invoice_line.description else ""
        best_match = None
        best_score = 0.0
        
        for po_line in available_po_lines:
            if po_line.id in matched_po_lines:
                continue
            
            score = 0.0
            
            # 1. SKU match (highest priority)
            if invoice_line.sku and po_line.sku:
                if invoice_line.sku == po_line.sku:
                    score = 1.0
                    best_match = po_line
                    best_score = score
                    break  # SKU match is definitive
            
            # 2. Exact description match
            po_desc = po_line.description.lower().strip() if po_line.description else ""
            if invoice_desc == po_desc:
                score = 0.95
                if score > best_score:
                    best_match = po_line
                    best_score = score
                continue
            
            # 3. Fuzzy description match
            if invoice_desc and po_desc:
                desc_similarity = calculate_similarity(invoice_desc, po_desc)
                if desc_similarity >= FUZZY_THRESHOLD:
                    score = desc_similarity
                    
                    # 4. Bonus for quantity similarity (if within 10%)
                    if invoice_line.quantity and po_line.quantity:
                        qty_diff = abs(float(invoice_line.quantity) - float(po_line.quantity))
                        qty_ratio = min(float(invoice_line.quantity), float(po_line.quantity)) / max(float(invoice_line.quantity), float(po_line.quantity))
                        if qty_ratio > 0.9:  # Within 10%
                            score += 0.1
                    
                    # 5. Bonus for price similarity (if within 5%)
                    if invoice_line.unit_price and po_line.unit_price:
                        price_diff = abs(float(invoice_line.unit_price) - float(po_line.unit_price))
                        price_ratio = min(float(invoice_line.unit_price), float(po_line.unit_price)) / max(float(invoice_line.unit_price), float(po_line.unit_price))
                        if price_ratio > 0.95:  # Within 5%
                            score += 0.1
                    
                    if score > best_score:
                        best_match = po_line
                        best_score = score
        
        # 6. Fallback: substring match (lower threshold)
        if best_score < FUZZY_THRESHOLD:
            for po_line in available_po_lines:
                if po_line.id in matched_po_lines:
                    continue
                
                po_desc = po_line.description.lower().strip() if po_line.description else ""
                if invoice_desc and po_desc:
                    # Check if one contains the other (substring match)
                    if invoice_desc in po_desc or po_desc in invoice_desc:
                        # Calculate a basic similarity score for substring matches
                        shorter = min(len(invoice_desc), len(po_desc))
                        longer = max(len(invoice_desc), len(po_desc))
                        substring_score = shorter / longer if longer > 0 else 0.0
                        
                        if substring_score > best_score:
                            best_match = po_line
                            best_score = substring_score
        
        return best_match, best_score
    
    # Match each invoice line
    for invoice_line in invoice_lines:
        match = LineItemMatch(
            invoice_line_no=invoice_line.line_no,
            matched=False,
            issues=[],
            invoice_sku=invoice_line.sku,
            invoice_quantity=invoice_line.quantity,
            invoice_unit_price=invoice_line.unit_price
        )
        
        # Try to match by SKU first (exact match)
        po_line = None
        if invoice_line.sku:
            po_line = po_lines_by_sku.get(invoice_line.sku)
        
        # If no SKU match, use fuzzy matching
        if po_line is None:
            # Try exact description match first
            invoice_desc = invoice_line.description.lower().strip() if invoice_line.description else ""
            po_line = po_lines_by_exact_desc.get(invoice_desc)
            
            # If no exact match, use fuzzy matching
            if po_line is None:
                available_po_lines = [line for line in po_lines if line.id not in matched_po_lines]
                po_line, confidence = find_best_po_match(invoice_line, available_po_lines)
                
                if po_line and confidence < FUZZY_THRESHOLD:
                    # Match found but confidence is low
                    match.issues.append(
                        f"Low confidence match (similarity: {confidence:.0%})"
                    )
        
        if po_line is None:
            match.issues.append(f"Line {invoice_line.line_no}: No matching PO line found")
            matches.append(match)
            continue
        
        # Check if this PO line was already matched (shouldn't happen with new logic, but safety check)
        if po_line.id in matched_po_lines:
            match.issues.append(f"Line {invoice_line.line_no}: PO line {po_line.line_no} already matched to another invoice line")
            matches.append(match)
            continue
        
        matched_po_lines.add(po_line.id)
        match.po_line_no = po_line.line_no
        match.po_sku = po_line.sku
        match.po_quantity = po_line.quantity
        match.po_unit_price = po_line.unit_price
        
        # Compare quantities (with tolerance)
        if invoice_line.quantity and po_line.quantity:
            qty_diff = abs(float(invoice_line.quantity) - float(po_line.quantity))
            if qty_diff > 0.01:
                match.issues.append(
                    f"Quantity mismatch: invoice={invoice_line.quantity}, PO={po_line.quantity}"
                )
        
        # Compare unit prices (with tolerance)
        if invoice_line.unit_price and po_line.unit_price:
            price_diff = abs(float(invoice_line.unit_price) - float(po_line.unit_price))
            if price_diff > 0.01:
                match.issues.append(
                    f"Unit price mismatch: invoice={invoice_line.unit_price}, PO={po_line.unit_price}"
                )
        
        match.matched = len(match.issues) == 0
        matches.append(match)
    
    # Check for unmatched PO lines
    for po_line in po_lines:
        if po_line.id not in matched_po_lines:
            match = LineItemMatch(
                invoice_line_no=-1,  # No invoice line
                po_line_no=po_line.line_no,
                matched=False,
                issues=[f"PO line {po_line.line_no} not found in invoice"],
                po_sku=po_line.sku,
                po_quantity=po_line.quantity,
                po_unit_price=po_line.unit_price
            )
            matches.append(match)
    
    return matches

