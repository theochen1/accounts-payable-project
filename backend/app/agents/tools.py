"""
Agent tools for resolving invoice matching exceptions.
These tools provide capabilities like fuzzy vendor matching, historical price lookup, etc.
"""
import difflib
import logging
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.vendor import Vendor
from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceLine

logger = logging.getLogger(__name__)


def fuzzy_match_vendor(invoice_vendor_name: str, db: Session) -> Optional[dict]:
    """
    Find vendor in database using fuzzy string matching.
    
    Args:
        invoice_vendor_name: Vendor name from invoice
        db: Database session
        
    Returns:
        Best matching vendor with confidence score, or None
    """
    if not invoice_vendor_name:
        return None
    
    # Get all vendors
    vendors = db.query(Vendor).all()
    if not vendors:
        return None
    
    vendor_names = [v.name for v in vendors]
    
    # Use difflib for fuzzy matching
    matches = difflib.get_close_matches(
        invoice_vendor_name, 
        vendor_names, 
        n=1, 
        cutoff=0.8
    )
    
    if matches:
        matched_name = matches[0]
        vendor = db.query(Vendor).filter(Vendor.name == matched_name).first()
        
        if not vendor:
            return None
        
        # Calculate similarity score
        similarity = difflib.SequenceMatcher(
            None, 
            invoice_vendor_name.lower(), 
            matched_name.lower()
        ).ratio()
        
        logger.info(f"Fuzzy matched '{invoice_vendor_name}' to '{matched_name}' with {similarity:.2%} confidence")
        
        return {
            "vendor_id": vendor.id,
            "vendor_name": vendor.name,
            "confidence": similarity,
            "original_name": invoice_vendor_name
        }
    
    return None


def get_historical_prices(sku: str, vendor_id: int, db: Session, days: int = 90) -> List[dict]:
    """
    Get historical prices for a SKU from a specific vendor.
    
    Args:
        sku: Product SKU
        vendor_id: Vendor ID
        db: Database session
        days: Lookback period in days
        
    Returns:
        List of historical prices with dates
    """
    if not sku or not vendor_id:
        return []
    
    cutoff_date = datetime.now().date() - timedelta(days=days)
    
    try:
        historical_prices = db.query(InvoiceLine).join(Invoice).filter(
            InvoiceLine.sku == sku,
            Invoice.vendor_id == vendor_id,
            Invoice.invoice_date >= cutoff_date,
            Invoice.status == 'approved'  # Only approved invoices
        ).all()
        
        return [
            {
                "price": float(line.unit_price),
                "quantity": float(line.quantity),
                "invoice_date": line.invoice.invoice_date.isoformat() if line.invoice.invoice_date else None,
                "invoice_id": str(line.invoice_id)
            }
            for line in historical_prices
        ]
    except Exception as e:
        logger.error(f"Error fetching historical prices: {e}")
        return []


def validate_price_variance_policy(
    variance_percent: float, 
    po_value: float, 
    vendor_id: int,
    db: Session
) -> dict:
    """
    Check if price variance is within acceptable policy limits.
    
    Args:
        variance_percent: Percentage difference
        po_value: Total PO value
        vendor_id: Vendor ID
        db: Database session
        
    Returns:
        Policy validation result with reasoning
    """
    # Get vendor-specific policy (if exists)
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    
    # Default policy: 5% for high-value POs, 10% for low-value
    # Note: Add price_variance_threshold_high/low to Vendor model if needed
    if po_value > 10000:
        threshold = 5.0  # 5% for high-value
    else:
        threshold = 10.0  # 10% for low-value
    
    within_policy = variance_percent <= threshold
    
    reasoning = f"Variance {variance_percent:.2f}% {'within' if within_policy else 'exceeds'} policy limit of {threshold}%"
    
    logger.info(f"Price variance policy check: {reasoning}")
    
    return {
        "within_policy": within_policy,
        "threshold": threshold,
        "variance": variance_percent,
        "po_value": po_value,
        "reasoning": reasoning
    }


def update_invoice_vendor(invoice_id: int, new_vendor_id: int, db: Session) -> bool:
    """
    Update invoice vendor ID.
    
    Args:
        invoice_id: Invoice ID
        new_vendor_id: New vendor ID
        db: Database session
        
    Returns:
        Success boolean
    """
    try:
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            logger.error(f"Invoice {invoice_id} not found")
            return False
        
        old_vendor_id = invoice.vendor_id
        invoice.vendor_id = new_vendor_id
        db.commit()
        
        # Log the change
        logger.info(f"Invoice {invoice_id}: Updated vendor from {old_vendor_id} to {new_vendor_id}")
        
        return True
    except Exception as e:
        logger.error(f"Failed to update vendor: {e}")
        db.rollback()
        return False

