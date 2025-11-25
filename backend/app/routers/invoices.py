from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime
import os
import logging

logger = logging.getLogger(__name__)
from app.database import get_db
from app.models.invoice import Invoice
from app.models.vendor import Vendor
from app.models.decision import Decision
from app.schemas.invoice import (
    InvoiceResponse,
    InvoiceListResponse,
    InvoiceDetailResponse,
    DecisionCreate
)
from app.schemas.po import POResponse
from app.services.storage_service import storage_service
from app.services.ocr_service import ocr_service
from app.services.matching_service import match_invoice_to_po
from app.schemas.matching import MatchingResult

router = APIRouter(prefix="/api/invoices", tags=["invoices"])


@router.get("", response_model=List[InvoiceListResponse])
def list_invoices(
    status: Optional[str] = Query(None, description="Filter by status"),
    vendor_id: Optional[int] = Query(None, description="Filter by vendor ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """List invoices with optional filters"""
    query = db.query(Invoice)
    
    if status:
        query = query.filter(Invoice.status == status)
    if vendor_id:
        query = query.filter(Invoice.vendor_id == vendor_id)
    
    invoices = query.order_by(Invoice.created_at.desc()).offset(skip).limit(limit).all()
    
    # Enrich with vendor names
    result = []
    for invoice in invoices:
        vendor_name = None
        if invoice.vendor_id:
            vendor = db.query(Vendor).filter(Vendor.id == invoice.vendor_id).first()
            vendor_name = vendor.name if vendor else None
        
        result.append(InvoiceListResponse(
            id=invoice.id,
            invoice_number=invoice.invoice_number,
            vendor_id=invoice.vendor_id,
            vendor_name=vendor_name,
            po_number=invoice.po_number,
            total_amount=invoice.total_amount,
            currency=invoice.currency,
            status=invoice.status,
            created_at=invoice.created_at
        ))
    
    return result


@router.get("/{invoice_id}", response_model=InvoiceDetailResponse)
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Get invoice detail with PO and matching results"""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Get vendor name
    vendor_name = None
    if invoice.vendor_id:
        vendor = db.query(Vendor).filter(Vendor.id == invoice.vendor_id).first()
        vendor_name = vendor.name if vendor else None
    
    # Get PO if exists
    po_response = None
    matching_result = None
    if invoice.po_number:
        from app.models.purchase_order import PurchaseOrder
        po = db.query(PurchaseOrder).filter(PurchaseOrder.po_number == invoice.po_number).first()
        if po:
            # Get vendor name for PO
            po_vendor = db.query(Vendor).filter(Vendor.id == po.vendor_id).first()
            po_response = POResponse(
                id=po.id,
                po_number=po.po_number,
                vendor_id=po.vendor_id,
                vendor_name=po_vendor.name if po_vendor else None,
                total_amount=po.total_amount,
                currency=po.currency,
                status=po.status,
                requester_email=po.requester_email,
                created_at=po.created_at,
                updated_at=po.updated_at,
                po_lines=[{
                    "id": line.id,
                    "line_no": line.line_no,
                    "sku": line.sku,
                    "description": line.description,
                    "quantity": line.quantity,
                    "unit_price": line.unit_price
                } for line in po.po_lines]
            )
            
            # Get matching result
            matching_result = match_invoice_to_po(db, invoice_id)
    
    # Get invoice lines
    from app.schemas.invoice import InvoiceLineResponse
    invoice_lines = [
        InvoiceLineResponse(
            id=line.id,
            line_no=line.line_no,
            sku=line.sku,
            description=line.description,
            quantity=line.quantity,
            unit_price=line.unit_price
        )
        for line in invoice.invoice_lines
    ]
    
    return InvoiceDetailResponse(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        vendor_id=invoice.vendor_id,
        vendor_name=vendor_name,
        po_number=invoice.po_number,
        invoice_date=invoice.invoice_date,
        total_amount=invoice.total_amount,
        currency=invoice.currency,
        pdf_storage_path=invoice.pdf_storage_path,
        ocr_json=invoice.ocr_json,
        status=invoice.status,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
        invoice_lines=invoice_lines,
        purchase_order=po_response,
        matching_result=matching_result
    )


@router.post("/upload")
async def upload_invoice(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload invoice (PDF or image), process with OCR, and run matching"""
    # Allowed file extensions
    allowed_extensions = {'.pdf', '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.tif'}
    file_ext = os.path.splitext(file.filename.lower())[1] if file.filename else ''
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"File type not supported. Allowed types: PDF, PNG, JPG, JPEG, GIF, BMP, WEBP, TIFF"
        )
    
    # Read file content
    file_content = await file.read()
    
    # Upload to storage
    storage_path = storage_service.upload_file(file_content, file.filename)
    
    # Process with OCR
    logger.info(f"Starting OCR processing for file: {file.filename} ({len(file_content)} bytes)")
    try:
        ocr_data = await ocr_service.process_file(file_content, file.filename)
        logger.info(f"OCR processing completed successfully. Extracted invoice_number: {ocr_data.get('invoice_number')}, vendor: {ocr_data.get('vendor_name')}")
    except Exception as e:
        # For MVP: If OCR fails, create a basic invoice record with minimal data
        # This allows testing the rest of the system even if OCR is not working
        logger.error(f"OCR processing failed: {str(e)}. Creating invoice with minimal data.", exc_info=True)
        ocr_data = {
            "vendor_name": None,
            "invoice_number": f"INV-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
            "po_number": None,
            "invoice_date": None,
            "total_amount": None,
            "currency": "USD",
            "line_items": [],
            "raw_ocr": {"error": str(e), "fallback": True}
        }
    
    # Extract vendor (try to find or create)
    vendor_id = None
    if ocr_data.get("vendor_name"):
        vendor_name = ocr_data['vendor_name'].strip()
        logger.info(f"Looking up vendor: '{vendor_name}'")
        
        # Try multiple matching strategies
        # 1. Exact match (case-insensitive)
        vendor = db.query(Vendor).filter(Vendor.name.ilike(vendor_name)).first()
        
        # 2. Partial match (contains)
        if not vendor:
            vendor = db.query(Vendor).filter(Vendor.name.ilike(f"%{vendor_name}%")).first()
        
        # 3. Reverse partial match (vendor name contains database name)
        if not vendor:
            # Try to find vendors where the database name is contained in the extracted name
            all_vendors = db.query(Vendor).all()
            for v in all_vendors:
                if v.name.lower() in vendor_name.lower() or vendor_name.lower() in v.name.lower():
                    vendor = v
                    logger.info(f"Found vendor using reverse match: '{v.name}' matches '{vendor_name}'")
                    break
        
        if vendor:
            vendor_id = vendor.id
            logger.info(f"Found vendor: {vendor.name} (ID: {vendor_id})")
        else:
            # Auto-create vendor if not found (like Ramp - creates vendors automatically)
            logger.info(f"Vendor '{vendor_name}' not found. Creating new vendor...")
            from app.models.vendor import Vendor
            new_vendor = Vendor(
                name=vendor_name,
                default_currency=ocr_data.get("currency", "USD")
            )
            db.add(new_vendor)
            db.flush()  # Get the ID without committing
            vendor_id = new_vendor.id
            logger.info(f"Created new vendor: {new_vendor.name} (ID: {vendor_id})")
    
    # Create invoice record
    from decimal import Decimal
    
    # Parse invoice_date string to date object if present
    invoice_date_obj = None
    invoice_date_str = ocr_data.get("invoice_date")
    if invoice_date_str:
        try:
            # Parse YYYY-MM-DD format
            invoice_date_obj = datetime.strptime(invoice_date_str, "%Y-%m-%d").date()
            logger.info(f"Parsed invoice_date: '{invoice_date_str}' -> {invoice_date_obj}")
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse invoice_date '{invoice_date_str}': {str(e)}")
            invoice_date_obj = None
    
    # Ensure invoice_number is never None (database constraint)
    invoice_number = ocr_data.get("invoice_number") or f"INV-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    
    invoice = Invoice(
        invoice_number=invoice_number,
        vendor_id=vendor_id,
        po_number=ocr_data.get("po_number"),
        invoice_date=invoice_date_obj,  # Use parsed date object
        total_amount=Decimal(str(ocr_data["total_amount"])) if ocr_data.get("total_amount") else None,
        currency=ocr_data.get("currency", "USD"),
        pdf_storage_path=storage_path,
        ocr_json=ocr_data.get("raw_ocr", ocr_data),
        status="new"
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    
    # Create invoice lines
    if ocr_data.get("line_items"):
        from app.models.invoice_line import InvoiceLine
        for item in ocr_data["line_items"]:
            invoice_line = InvoiceLine(
                invoice_id=invoice.id,
                line_no=item.get("line_no", 0),
                sku=item.get("sku"),
                description=item.get("description", ""),
                quantity=Decimal(str(item["quantity"])) if item.get("quantity") else Decimal("0"),
                unit_price=Decimal(str(item["unit_price"])) if item.get("unit_price") else Decimal("0")
            )
            db.add(invoice_line)
        db.commit()
    
    # Run matching
    try:
        matching_result = match_invoice_to_po(db, invoice.id)
    except Exception as e:
        # Matching failed, but invoice is saved
        matching_result = None
    
    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "status": invoice.status,
        "matching_result": matching_result
    }


@router.post("/{invoice_id}/approve")
def approve_invoice(
    invoice_id: int,
    decision: DecisionCreate,
    db: Session = Depends(get_db)
):
    """Approve an invoice"""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    decision_record = Decision(
        invoice_id=invoice_id,
        user_identifier=decision.user_identifier,
        decision="approved",
        reason=decision.reason
    )
    db.add(decision_record)
    invoice.status = "approved"
    db.commit()
    
    return {"message": "Invoice approved", "invoice_id": invoice_id}


@router.post("/{invoice_id}/reject")
def reject_invoice(
    invoice_id: int,
    decision: DecisionCreate,
    db: Session = Depends(get_db)
):
    """Reject an invoice"""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    if not decision.reason:
        raise HTTPException(status_code=400, detail="Reason is required for rejection")
    
    decision_record = Decision(
        invoice_id=invoice_id,
        user_identifier=decision.user_identifier,
        decision="rejected",
        reason=decision.reason
    )
    db.add(decision_record)
    invoice.status = "rejected"
    db.commit()
    
    return {"message": "Invoice rejected", "invoice_id": invoice_id}


@router.post("/{invoice_id}/route")
def route_invoice(
    invoice_id: int,
    decision: DecisionCreate,
    db: Session = Depends(get_db)
):
    """Route an invoice to another person/process"""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    if not decision.reason:
        raise HTTPException(status_code=400, detail="Routing target/reason is required")
    
    decision_record = Decision(
        invoice_id=invoice_id,
        user_identifier=decision.user_identifier,
        decision="routed",
        reason=decision.reason
    )
    db.add(decision_record)
    invoice.status = "routed"
    db.commit()
    
    return {"message": "Invoice routed", "invoice_id": invoice_id}

