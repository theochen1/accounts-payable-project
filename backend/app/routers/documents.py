"""
Documents Router - Unified document upload and processing queue
"""
import os
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Tuple

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Query, BackgroundTasks
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
from app.config import settings

logger = logging.getLogger(__name__)


def get_ocr_service():
    """Get the appropriate OCR service based on configuration"""
    if settings.ocr_provider == "agent":
        # Ensemble OCR agent with reasoning - best accuracy
        from app.services.ocr_agent_service import ocr_agent_service
        return ocr_agent_service
    elif settings.ocr_provider in ("hybrid", "gemini", "gpt4o"):
        from app.services.ocr_service_hybrid import hybrid_ocr_service
        return hybrid_ocr_service
    # Default to Azure-based OCR service
    return ocr_service

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


@router.get("/{document_id}/file")
def get_document_file(document_id: int, db: Session = Depends(get_db)):
    """Serve the document file"""
    from fastapi.responses import Response
    
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        file_content = storage_service.download_file(document.storage_path)
        
        # Determine content type from filename
        ext = os.path.splitext(document.filename.lower())[1] if document.filename else ''
        content_types = {
            '.pdf': 'application/pdf',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
            '.tiff': 'image/tiff',
            '.tif': 'image/tiff',
        }
        content_type = content_types.get(ext, 'application/octet-stream')
        
        return Response(
            content=file_content,
            media_type=content_type,
            headers={
                "Content-Disposition": f'inline; filename="{document.filename}"'
            }
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found in storage")
    except Exception as e:
        logger.error(f"Failed to serve file for document {document_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to serve file: {str(e)}")


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
        
        # Process with OCR (uses configured provider: azure, hybrid, gemini, or gpt4o)
        active_ocr_service = get_ocr_service()
        logger.info(f"Starting OCR for document {document_id} ({document.filename}) using provider: {settings.ocr_provider}")
        ocr_data = await active_ocr_service.process_file(file_content, document.filename)
        
        # Match vendor against existing vendors using intelligent matching
        from app.services.vendor_matching_service import vendor_matching_service
        if ocr_data.get('vendor_name'):
            logger.info(f"Matching vendor '{ocr_data.get('vendor_name')}' against existing vendors...")
            
            # Use intelligent vendor matching (fuzzy + LLM reasoning)
            match_result = await vendor_matching_service.match_vendor(
                ocr_data=ocr_data,
                db=db,
                file_content=file_content,
                filename=document.filename
            )
            
            # Add vendor match suggestions to OCR data for the frontend
            ocr_data['vendor_match'] = {
                'matched_vendor_id': match_result.get('vendor_id'),
                'matched_vendor_name': match_result.get('vendor_name'),
                'confidence': match_result.get('confidence'),
                'match_type': match_result.get('match_type'),
                'suggested_vendor': match_result.get('suggested_vendor'),
                'reasoning': match_result.get('reasoning')
            }
            logger.info(f"Vendor match result: {match_result.get('match_type')} - {match_result.get('vendor_name')} (confidence: {match_result.get('confidence', 0):.0%})")
        
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
    background_tasks: BackgroundTasks,
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
        
    except HTTPException:
        # Re-raise HTTPExceptions (they already have proper status codes)
        raise
    except Exception as e:
        logger.error(f"Failed to save document {document_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _find_or_create_vendor(
    vendor_id: Optional[int], 
    vendor_name: str, 
    currency: str, 
    db: Session,
    ocr_data: Optional[Dict] = None,
    file_content: Optional[bytes] = None,
    filename: Optional[str] = None
) -> Tuple[int, Dict]:
    """
    Intelligently find or create a vendor using LLM matching
    
    Args:
        vendor_id: Explicit vendor ID if provided
        vendor_name: Extracted vendor name from OCR
        currency: Default currency for new vendors
        db: Database session
        ocr_data: Full OCR data for context-aware matching
        file_content: Original file for vision-based verification
        filename: Original filename
        
    Returns:
        Tuple of (Vendor ID, match_result dict with details)
    """
    from app.services.vendor_matching_service import vendor_matching_service
    
    if vendor_id:
        vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
        return vendor_id, {
            'vendor_id': vendor_id,
            'vendor_name': vendor.name if vendor else None,
            'confidence': 1.0,
            'match_type': 'explicit_id',
            'reasoning': 'Vendor ID was explicitly provided'
        }
    
    if not vendor_name:
        raise HTTPException(status_code=400, detail="Vendor name is required")
    
    # Build OCR context for intelligent matching
    ocr_context = ocr_data or {'vendor_name': vendor_name}
    
    # Use intelligent vendor matching
    match_result = await vendor_matching_service.match_vendor(
        ocr_data=ocr_context,
        db=db,
        file_content=file_content,
        filename=filename
    )
    
    logger.info(f"Vendor matching result: {match_result.get('match_type')} - {match_result.get('reasoning', '')[:100]}")
    
    if match_result.get('vendor_id'):
        # Found existing vendor
        logger.info(f"Matched vendor '{vendor_name}' to existing vendor: {match_result['vendor_name']} "
                   f"(confidence: {match_result['confidence']:.0%}, type: {match_result['match_type']})")
        return match_result['vendor_id'], match_result
    
    # No match - create new vendor with cleaned name
    suggested_name = match_result.get('suggested_vendor') or match_result.get('vendor_name') or vendor_name
    vendor = Vendor(name=suggested_name, default_currency=currency)
    db.add(vendor)
    db.flush()
    logger.info(f"Created new vendor: {suggested_name}")
    
    match_result['vendor_id'] = vendor.id
    match_result['vendor_name'] = suggested_name
    match_result['match_type'] = 'created_new'
    
    return vendor.id, match_result


async def _save_invoice(document: Document, data, db: Session):
    """Save document as an Invoice"""
    from app.schemas.document import InvoiceSaveData
    from app.services.storage_service import storage_service
    
    # Get original file content for vision-based vendor verification if needed
    file_content = None
    try:
        file_content = await storage_service.get_file(document.storage_path)
    except Exception as e:
        logger.warning(f"Could not retrieve file for vendor matching: {e}")
    
    # Find or create vendor using intelligent matching with full OCR context
    vendor_id, vendor_match = await _find_or_create_vendor(
        vendor_id=data.vendor_id,
        vendor_name=data.vendor_name,
        currency=data.currency,
        db=db,
        ocr_data=document.ocr_data,
        file_content=file_content,
        filename=document.filename
    )
    
    # Log vendor matching details for debugging
    if vendor_match.get('match_type') not in ['exact', 'explicit_id']:
        logger.info(f"Vendor matching for invoice: {vendor_match}")
    
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
    matching_result = None
    try:
        matching_result = match_invoice_to_po(db, invoice.id)
        logger.info(f"Invoice {invoice.id} matching completed")
        
        # If there are exceptions, trigger agent resolution
        if matching_result and matching_result.status in ["exception", "needs_review"]:
            # Import here to avoid circular dependency
            from app.routers.agents import run_agent_workflow
            import uuid
            task_id = str(uuid.uuid4())
            # Note: We need to create a new db session for background task
            # For MVP, we'll trigger via API call instead
            logger.info(f"Invoice {invoice.id} has exceptions. Agent resolution should be triggered via /api/agents/resolve")
    except Exception as e:
        logger.warning(f"Matching failed for invoice {invoice.id}: {str(e)}")
    
    logger.info(f"Invoice saved: ID={invoice.id}, Number={invoice.invoice_number}")
    
    return {
        "success": True,
        "document_type": "invoice",
        "id": invoice.id,
        "reference_number": invoice.invoice_number,
        "matching_status": matching_result.status if matching_result else None
    }


async def _save_po(document: Document, data, db: Session):
    """Save document as a Purchase Order"""
    
    # Find or create vendor using intelligent matching
    try:
        vendor_id, vendor_match = await _find_or_create_vendor(
            vendor_id=data.vendor_id,
            vendor_name=data.vendor_name,
            currency=data.currency,
            db=db,
            ocr_data=document.ocr_data,
            file_content=None,  # PO save doesn't need vision verification
            filename=document.filename
        )
        logger.info(f"PO vendor match: {vendor_match.get('match_type')} - {vendor_match.get('vendor_name')}")
    except HTTPException:
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
        # If PO exists and was created from the same document, update it
        if existing_po.source_document_id is not None and existing_po.source_document_id == document.id:
            logger.info(f"PO {data.po_number} already exists from this document. Updating existing PO.")
            po = existing_po
            # Update PO fields
            po.vendor_id = vendor_id
            po.total_amount = data.total_amount
            po.currency = data.currency
            po.order_date = order_date
            po.requester_email = data.requester_email
            # Delete existing line items
            db.query(POLine).filter(POLine.po_id == po.id).delete()
            db.flush()
        else:
            # PO exists from a different document (or was created before document system)
            source_info = f"document {existing_po.source_document_id}" if existing_po.source_document_id else "legacy system"
            raise HTTPException(
                status_code=400, 
                detail=f"PO number {data.po_number} already exists (created from {source_info})"
            )
    else:
        # Create new PO
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

