"""
Documents Router - Unified document upload and processing queue
"""
import os
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.document import Document
from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceLine
from app.models.purchase_order import PurchaseOrder
from app.models.po_line import POLine
from app.models.vendor import Vendor
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentUpdateType,
    DocumentOCRResult,
    DocumentSaveRequest,
    ProcessedDocumentResponse
)
from app.services.ocr_service import ocr_service
from app.services.storage_service import storage_service
from app.services.matching_service import match_invoice_to_po

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("", response_model=List[DocumentListResponse])
def list_documents(
    status: Optional[str] = Query(None, description="Filter by status: pending, processing, processed, error"),
    db: Session = Depends(get_db)
):
    """List all documents in the queue"""
    query = db.query(Document)
    if status:
        query = query.filter(Document.status == status)
    # Show newest first
    documents = query.order_by(Document.created_at.desc()).all()
    return documents


@router.post("", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a document to the processing queue"""
    # Validate file type
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
    logger.info(f"Document uploaded to storage: {storage_path}")
    
    # Create document record in pending state
    document = Document(
        filename=file.filename,
        storage_path=storage_path,
        document_type=None,  # User will select type
        status="pending"
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    
    logger.info(f"Document created with ID {document.id}, status: pending")
    return document


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: int, db: Session = Depends(get_db)):
    """Get a single document with full details including OCR data"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.patch("/{document_id}/type", response_model=DocumentResponse)
def set_document_type(
    document_id: int,
    update: DocumentUpdateType,
    db: Session = Depends(get_db)
):
    """Set the document type (invoice or po)"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if update.document_type not in ['invoice', 'po']:
        raise HTTPException(status_code=400, detail="document_type must be 'invoice' or 'po'")
    
    if document.status not in ['pending', 'error']:
        raise HTTPException(status_code=400, detail="Can only change type for pending or error documents")
    
    document.document_type = update.document_type
    db.commit()
    db.refresh(document)
    
    logger.info(f"Document {document_id} type set to: {update.document_type}")
    return document


@router.post("/{document_id}/process", response_model=DocumentOCRResult)
async def process_document(document_id: int, db: Session = Depends(get_db)):
    """Process document with OCR and extract data"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not document.document_type:
        raise HTTPException(status_code=400, detail="Document type must be set before processing")
    
    if document.status == "processing":
        raise HTTPException(status_code=400, detail="Document is already being processed")
    
    # Set to processing
    document.status = "processing"
    document.error_message = None
    db.commit()
    
    try:
        # Download file from storage
        file_content = storage_service.download_file(document.storage_path)
        
        # Process with OCR
        logger.info(f"Starting OCR for document {document_id} ({document.filename})")
        ocr_data = await ocr_service.process_file(file_content, document.filename)
        
        # Store OCR results
        document.ocr_data = ocr_data
        document.status = "processed"
        document.error_message = None
        db.commit()
        db.refresh(document)
        
        logger.info(f"Document {document_id} processed successfully")
        return DocumentOCRResult(
            id=document.id,
            status=document.status,
            ocr_data=document.ocr_data
        )
        
    except Exception as e:
        logger.error(f"OCR processing failed for document {document_id}: {str(e)}", exc_info=True)
        document.status = "error"
        document.error_message = str(e)
        db.commit()
        db.refresh(document)
        
        return DocumentOCRResult(
            id=document.id,
            status=document.status,
            error_message=document.error_message
        )


@router.post("/{document_id}/retry", response_model=DocumentOCRResult)
async def retry_document(document_id: int, db: Session = Depends(get_db)):
    """Retry OCR processing for a failed document"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.status != "error":
        raise HTTPException(status_code=400, detail="Can only retry documents with error status")
    
    # Reprocess
    return await process_document(document_id, db)


@router.post("/{document_id}/save")
async def save_document(
    document_id: int,
    save_data: DocumentSaveRequest,
    db: Session = Depends(get_db)
):
    """Save a processed document as an Invoice or PO"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.status != "processed":
        raise HTTPException(status_code=400, detail="Document must be processed before saving")
    
    if not document.document_type:
        raise HTTPException(status_code=400, detail="Document type not set")
    
    try:
        if document.document_type == "invoice":
            if not save_data.invoice_data:
                raise HTTPException(status_code=400, detail="invoice_data required for invoice documents")
            
            result = await _save_invoice(document, save_data.invoice_data, db)
            
        elif document.document_type == "po":
            if not save_data.po_data:
                raise HTTPException(status_code=400, detail="po_data required for PO documents")
            
            result = await _save_po(document, save_data.po_data, db)
        
        else:
            raise HTTPException(status_code=400, detail=f"Unknown document type: {document.document_type}")
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to save document {document_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _save_invoice(document: Document, data, db: Session):
    """Save document as an Invoice"""
    from app.schemas.document import InvoiceSaveData
    
    # Find or create vendor
    vendor_id = data.vendor_id
    if not vendor_id and data.vendor_name:
        vendor = db.query(Vendor).filter(Vendor.name.ilike(data.vendor_name)).first()
        if not vendor:
            # Try partial match
            vendor = db.query(Vendor).filter(Vendor.name.ilike(f"%{data.vendor_name}%")).first()
        if not vendor:
            # Create new vendor
            vendor = Vendor(name=data.vendor_name, default_currency=data.currency)
            db.add(vendor)
            db.flush()
            logger.info(f"Created new vendor: {data.vendor_name}")
        vendor_id = vendor.id
    
    # Parse date
    invoice_date = None
    if data.invoice_date:
        try:
            invoice_date = datetime.strptime(data.invoice_date, "%Y-%m-%d").date()
        except ValueError:
            logger.warning(f"Could not parse invoice date: {data.invoice_date}")
    
    # Create invoice
    invoice = Invoice(
        invoice_number=data.invoice_number,
        vendor_id=vendor_id,
        po_number=data.po_number,
        invoice_date=invoice_date,
        total_amount=data.total_amount,
        currency=data.currency,
        pdf_storage_path=document.storage_path,
        ocr_json=document.ocr_data,
        status="new",
        source_document_id=document.id
    )
    db.add(invoice)
    db.flush()
    
    # Create line items
    for item in data.line_items:
        line = InvoiceLine(
            invoice_id=invoice.id,
            line_no=item.line_no,
            sku=item.sku,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price
        )
        db.add(line)
    
    # Update document
    document.processed_id = invoice.id
    db.commit()
    
    # Run matching
    try:
        matching_result = match_invoice_to_po(db, invoice.id)
        logger.info(f"Invoice {invoice.id} matching completed")
    except Exception as e:
        logger.warning(f"Matching failed for invoice {invoice.id}: {str(e)}")
    
    logger.info(f"Invoice saved: ID={invoice.id}, Number={invoice.invoice_number}")
    
    return {
        "success": True,
        "document_type": "invoice",
        "id": invoice.id,
        "reference_number": invoice.invoice_number
    }


async def _save_po(document: Document, data, db: Session):
    """Save document as a Purchase Order"""
    
    # Find or create vendor
    vendor_id = data.vendor_id
    if not vendor_id and data.vendor_name:
        vendor = db.query(Vendor).filter(Vendor.name.ilike(data.vendor_name)).first()
        if not vendor:
            vendor = db.query(Vendor).filter(Vendor.name.ilike(f"%{data.vendor_name}%")).first()
        if not vendor:
            vendor = Vendor(name=data.vendor_name, default_currency=data.currency)
            db.add(vendor)
            db.flush()
            logger.info(f"Created new vendor: {data.vendor_name}")
        vendor_id = vendor.id
    
    if not vendor_id:
        raise HTTPException(status_code=400, detail="Vendor is required for purchase orders")
    
    # Parse date
    order_date = None
    if data.order_date:
        try:
            order_date = datetime.strptime(data.order_date, "%Y-%m-%d").date()
        except ValueError:
            logger.warning(f"Could not parse order date: {data.order_date}")
    
    # Check if PO number already exists
    existing_po = db.query(PurchaseOrder).filter(PurchaseOrder.po_number == data.po_number).first()
    if existing_po:
        raise HTTPException(status_code=400, detail=f"PO number {data.po_number} already exists")
    
    # Create PO
    po = PurchaseOrder(
        po_number=data.po_number,
        vendor_id=vendor_id,
        total_amount=data.total_amount,
        currency=data.currency,
        status="open",
        order_date=order_date,
        requester_email=data.requester_email,
        source_document_id=document.id
    )
    db.add(po)
    db.flush()
    
    # Create line items
    for item in data.po_lines:
        line = POLine(
            po_id=po.id,
            line_no=item.line_no,
            sku=item.sku,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price
        )
        db.add(line)
    
    # Update document
    document.processed_id = po.id
    db.commit()
    
    logger.info(f"PO saved: ID={po.id}, Number={po.po_number}")
    
    return {
        "success": True,
        "document_type": "po",
        "id": po.id,
        "reference_number": po.po_number
    }


@router.delete("/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db)):
    """Delete a document from the queue"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.processed_id:
        raise HTTPException(
            status_code=400, 
            detail="Cannot delete document that has been processed. Delete the invoice/PO first."
        )
    
    db.delete(document)
    db.commit()
    
    logger.info(f"Document {document_id} deleted")
    return {"success": True, "message": "Document deleted"}


@router.get("/processed/all", response_model=List[ProcessedDocumentResponse])
def list_processed_documents(
    document_type: Optional[str] = Query(None, description="Filter by type: invoice, po"),
    db: Session = Depends(get_db)
):
    """List all processed invoices and POs in a unified view"""
    results = []
    
    # Get invoices
    if not document_type or document_type == "invoice":
        invoices = db.query(Invoice).order_by(Invoice.created_at.desc()).all()
        for inv in invoices:
            vendor_name = inv.vendor.name if inv.vendor else None
            results.append(ProcessedDocumentResponse(
                id=inv.id,
                document_type="invoice",
                reference_number=inv.invoice_number,
                vendor_name=vendor_name,
                total_amount=inv.total_amount,
                currency=inv.currency,
                status=inv.status,
                date=inv.invoice_date.isoformat() if inv.invoice_date else None,
                source_document_id=inv.source_document_id,
                created_at=inv.created_at
            ))
    
    # Get POs
    if not document_type or document_type == "po":
        pos = db.query(PurchaseOrder).order_by(PurchaseOrder.created_at.desc()).all()
        for po in pos:
            vendor_name = po.vendor.name if po.vendor else None
            results.append(ProcessedDocumentResponse(
                id=po.id,
                document_type="po",
                reference_number=po.po_number,
                vendor_name=vendor_name,
                total_amount=po.total_amount,
                currency=po.currency,
                status=po.status,
                date=po.order_date.isoformat() if po.order_date else None,
                source_document_id=po.source_document_id,
                created_at=po.created_at
            ))
    
    # Sort by created_at descending
    results.sort(key=lambda x: x.created_at, reverse=True)
    
    return results

