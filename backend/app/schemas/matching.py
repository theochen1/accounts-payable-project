from pydantic import BaseModel
from typing import List, Optional
from decimal import Decimal


class LineItemMatch(BaseModel):
    """Represents the matching result for a single line item"""
    invoice_line_no: int
    po_line_no: Optional[int] = None
    matched: bool
    issues: List[str] = []
    invoice_quantity: Optional[Decimal] = None
    po_quantity: Optional[Decimal] = None
    invoice_unit_price: Optional[Decimal] = None
    po_unit_price: Optional[Decimal] = None


class MatchingIssue(BaseModel):
    """Represents a single matching issue"""
    type: str  # e.g., "missing_po", "vendor_mismatch", "currency_mismatch", "total_mismatch", "line_item_mismatch"
    severity: str  # "exception" or "needs_review"
    message: str
    details: Optional[dict] = None


class MatchingResult(BaseModel):
    """Complete matching result between invoice and PO"""
    status: str  # "matched", "needs_review", "exception"
    overall_match: bool
    issues: List[MatchingIssue] = []
    line_item_matches: List[LineItemMatch] = []
    vendor_match: bool = True
    currency_match: bool = True
    total_match: bool = True
    total_difference: Optional[Decimal] = None
    total_difference_percent: Optional[float] = None

