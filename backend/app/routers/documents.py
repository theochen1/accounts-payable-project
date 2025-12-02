"""
Documents Router - Unified document processing pipeline
"""
import os
import json
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.document import Document
from app.models.vendor import Vendor
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentClassify,
    DocumentVerify,
    DocumentOCRResult,
    ProcessedDocumentResponse
)
from app.services.field_mapper import field_mapper
from app.services.storage_service import storage_service
from app.services.matching_service import match_invoice_to_po
from app.config import settings

logger = logging.getLogger(__name__)


def get_ocr_service():
    """Get the appropriate OCR service based on configuration"""
    if settings.ocr_provider == "agent":
        from app.services.ocr_agent_service import ocr_agent_service
        return ocr_agent_service
    elif settings.ocr_provider in ("hybrid", "gemini", "gpt4o"):
        from app.services.ocr_service_hybrid import hybrid_ocr_service
        return hybrid_ocr_service
    from app.services.ocr_service import ocr_service
    return ocr_service

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("", response_model=List[DocumentListResponse])
def list_documents(
    status: Optional[str] = Query(None, description="Filter by status"),
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    db: Session = Depends(get_db)
):
    """List all documents with optional filters"""
    query = db.query(Document)
    
    if status:
        query = query.filter(Document.status == status)
    if document_type:
        query = query.filter(Document.document_type == document_type)
    
    documents = query.order_by(Document.created_at.desc()).all()
    return documents


@router.post("", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a document file - status: uploaded (alias for /upload)"""
    return await _upload_document_impl(file, db)


@router.post("/upload", response_model=DocumentResponse)
async def upload_document_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a document file - status: uploaded"""
    return await _upload_document_impl(file, db)


async def _upload_document_impl(
    file: UploadFile,
    db: Session
) -> DocumentResponse:
    """Internal implementation for document upload"""
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
    
    # Create document record with status=uploaded
    document = Document(
        filename=file.filename,
        file_path=storage_path,
        document_type=None,  # Will be set in classify step
        status="uploaded"
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    
    logger.info(f"Document created with ID {document.id}, status: uploaded")
    return document


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: int, db: Session = Depends(get_db)):
    """Get a single document with full details"""
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
        file_content = storage_service.download_file(document.file_path)
        
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


@router.post("/{document_id}/classify", response_model=DocumentResponse)
def classify_document(
    document_id: int,
    classify: DocumentClassify,
    db: Session = Depends(get_db)
):
    """Set document type - status: uploaded -> classified"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.status != "uploaded":
        raise HTTPException(status_code=400, detail=f"Can only classify documents with status 'uploaded'. Current status: {document.status}")
    
    if classify.document_type not in ['invoice', 'purchase_order', 'receipt']:
        raise HTTPException(status_code=400, detail="document_type must be 'invoice', 'purchase_order', or 'receipt'")
    
    document.document_type = classify.document_type
    document.status = "classified"
    db.commit()
    db.refresh(document)
    
    logger.info(f"Document {document_id} classified as: {classify.document_type}")
    return document


@router.post("/{document_id}/process-ocr", response_model=DocumentOCRResult)
async def process_ocr(document_id: int, db: Session = Depends(get_db)):
    """Process document with OCR - status: classified -> ocr_processing -> pending_verification"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.status != "classified":
        raise HTTPException(status_code=400, detail=f"Document must be classified before OCR. Current status: {document.status}")
    
    if not document.document_type:
        raise HTTPException(status_code=400, detail="Document type must be set before OCR processing")
    
    # Set to processing
    document.status = "ocr_processing"
    document.error_message = None
    db.commit()
    
    try:
        # Download file from storage
        file_content = storage_service.download_file(document.file_path)
        
        # Process with OCR
        active_ocr_service = get_ocr_service()
        logger.info(f"Starting OCR for document {document_id} ({document.filename}) using provider: {settings.ocr_provider}")
        logger.info(f"Document type: {document.document_type}")
        
        # Pass document type to OCR service
        if hasattr(active_ocr_service, 'process_file'):
            import inspect
            sig = inspect.signature(active_ocr_service.process_file)
            if 'document_type' in sig.parameters:
                ocr_data = await active_ocr_service.process_file(file_content, document.filename, document_type=document.document_type)
            else:
                ocr_data = await active_ocr_service.process_file(file_content, document.filename)
        else:
            ocr_data = await active_ocr_service.process_file(file_content, document.filename)
        
        # Normalize OCR output using FieldMapper
        normalized_data = field_mapper.normalize(ocr_data, document.document_type)
        unified_data = field_mapper.to_unified_document_format(normalized_data, document.document_type)
        
        # Log OCR results
        try:
            logger.info("=" * 80)
            logger.info(f"OCR EXTRACTION RESULTS for document {document_id} ({document.filename})")
            logger.info("=" * 80)
            logger.info(f"OCR data keys: {list(unified_data.keys())}")
            
            try:
                ocr_json = json.dumps(unified_data, indent=2, default=str)
                if len(ocr_json) > 5000:
                    logger.info("Full OCR data (first 5000 chars):")
                    logger.info(ocr_json[:5000])
                    logger.info("... (truncated)")
                else:
                    logger.info(f"Full OCR data (JSON):\n{ocr_json}")
            except Exception as e:
                logger.warning(f"Could not serialize OCR data to JSON: {e}")
                logger.info(f"OCR data (repr): {repr(unified_data)}")
            
            logger.info("-" * 80)
            
            # Log type-specific fields
            if document.document_type == 'purchase_order':
                logger.info("PO-SPECIFIC FIELDS:")
                logger.info(f"  PO Number: {unified_data.get('document_number', 'NOT FOUND')}")
                type_data = unified_data.get('type_specific_data', {})
                logger.info(f"  Order Date: {type_data.get('order_date', 'NOT FOUND')}")
                logger.info(f"  Requester Email: {type_data.get('requester_email', 'NOT FOUND')}")
                logger.info(f"  Vendor Name: {unified_data.get('vendor_name', 'NOT FOUND')}")
                logger.info(f"  Total Amount: {unified_data.get('total_amount', 'NOT FOUND')}")
            elif document.document_type == 'invoice':
                logger.info("INVOICE-SPECIFIC FIELDS:")
                logger.info(f"  Invoice Number: {unified_data.get('document_number', 'NOT FOUND')}")
                type_data = unified_data.get('type_specific_data', {})
                logger.info(f"  PO Number: {type_data.get('po_number', 'NOT FOUND')}")
                logger.info(f"  Invoice Date: {unified_data.get('document_date', 'NOT FOUND')}")
                logger.info(f"  Vendor Name: {unified_data.get('vendor_name', 'NOT FOUND')}")
                logger.info(f"  Total Amount: {unified_data.get('total_amount', 'NOT FOUND')}")
            
            logger.info(f"Line Items Count: {len(unified_data.get('line_items', []))}")
            if unified_data.get('line_items'):
                try:
                    first_item = json.dumps(unified_data['line_items'][0], indent=2, default=str)
                    logger.info(f"First line item:\n{first_item}")
                except Exception as e:
                    logger.info(f"First line item (repr): {repr(unified_data['line_items'][0])}")
            
            logger.info("=" * 80)
        except Exception as e:
            logger.error(f"Error logging OCR results: {e}", exc_info=True)
        
        # Match vendor against existing vendors
        from app.services.vendor_matching_service import vendor_matching_service
        if unified_data.get('vendor_name'):
            logger.info(f"Matching vendor '{unified_data.get('vendor_name')}' against existing vendors...")
            
            match_result = await vendor_matching_service.match_vendor(
                ocr_data=unified_data,
                db=db,
                file_content=file_content,
                filename=document.filename
            )
            
            unified_data['vendor_match'] = {
                'matched_vendor_id': match_result.get('vendor_id'),
                'matched_vendor_name': match_result.get('vendor_name'),
                'confidence': match_result.get('confidence'),
                'match_type': match_result.get('match_type'),
                'suggested_vendor': match_result.get('suggested_vendor'),
                'reasoning': match_result.get('reasoning')
            }
            logger.info(f"Vendor match result: {match_result.get('match_type')} - {match_result.get('vendor_name')} (confidence: {match_result.get('confidence', 0):.0%})")
        
        # Store OCR results in document
        document.vendor_name = unified_data.get('vendor_name')
        document.document_number = unified_data.get('document_number')
        document.document_date = unified_data.get('document_date')
        document.total_amount = unified_data.get('total_amount')
        document.currency = unified_data.get('currency', 'USD')
        document.type_specific_data = unified_data.get('type_specific_data', {})
        document.line_items = unified_data.get('line_items', [])
        document.raw_ocr = unified_data.get('raw_ocr', unified_data)
        document.extraction_source = unified_data.get('extraction_source', settings.ocr_provider)
        document.vendor_id = unified_data.get('vendor_match', {}).get('matched_vendor_id')
        document.vendor_match = unified_data.get('vendor_match')
        
        # Update status to pending_verification
        document.status = "pending_verification"
        document.error_message = None
        db.commit()
        db.refresh(document)
        
        logger.info(f"Document {document_id} OCR processing completed, status: pending_verification")
        return DocumentOCRResult(
            id=document.id,
            status=document.status,
            ocr_data={
                'vendor_name': document.vendor_name,
                'document_number': document.document_number,
                'document_date': document.document_date.isoformat() if document.document_date else None,
                'total_amount': float(document.total_amount) if document.total_amount else None,
                'currency': document.currency,
                'line_items': document.line_items,
                'type_specific_data': document.type_specific_data,
                'vendor_match': document.vendor_match
            }
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


@router.post("/{document_id}/verify", response_model=DocumentResponse)
async def verify_document(
    document_id: int,
    verify_data: DocumentVerify,
    db: Session = Depends(get_db)
):
    """Save verified/corrected data - status: pending_verification -> verified"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.status != "pending_verification":
        raise HTTPException(status_code=400, detail=f"Document must be in pending_verification status. Current status: {document.status}")
    
    # Update document with verified data
    document.vendor_name = verify_data.vendor_name
    document.vendor_id = verify_data.vendor_id
    document.document_number = verify_data.document_number
    document.document_date = verify_data.document_date
    document.total_amount = verify_data.total_amount
    document.currency = verify_data.currency
    document.line_items = [item.dict() for item in verify_data.line_items]
    
    # Store type-specific data
    type_specific = {}
    if document.document_type == "invoice" and verify_data.invoice_data:
        type_specific = verify_data.invoice_data.dict(exclude_none=True)
    elif document.document_type == "purchase_order" and verify_data.po_data:
        type_specific = verify_data.po_data.dict(exclude_none=True)
    elif document.document_type == "receipt" and verify_data.receipt_data:
        type_specific = verify_data.receipt_data.dict(exclude_none=True)
    
    document.type_specific_data = type_specific
    
    # Update status to verified
    document.status = "verified"
    db.commit()
    db.refresh(document)
    
    logger.info(f"Document {document_id} verified and saved")
    return document


@router.post("/{document_id}/finalize", response_model=Dict)
async def finalize_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    """Finalize document - trigger agentic workflow if needed - status: verified -> processed"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.status != "verified":
        raise HTTPException(status_code=400, detail=f"Document must be verified before finalizing. Current status: {document.status}")
    
    # For invoices with PO references, trigger matching and potentially agentic workflow
    if document.document_type == "invoice":
        po_number = document.type_specific_data.get('po_number') if document.type_specific_data else None
        
        if po_number:
            # Import here to avoid circular dependency
            from app.models.purchase_order import PurchaseOrder
            po = db.query(PurchaseOrder).filter(PurchaseOrder.po_number == po_number).first()
            
            if po:
                # Run matching (this would create an Invoice record and match it)
                # For now, we'll just mark as processed
                # In a full implementation, this would create the Invoice and trigger matching
                logger.info(f"Invoice document {document_id} references PO {po_number}, matching will be handled separately")
    
    # Update status to processed
    document.status = "processed"
    document.processed_at = datetime.now()
    db.commit()
    
    logger.info(f"Document {document_id} finalized, status: processed")
    return {
        "success": True,
        "document_id": document_id,
        "status": "processed",
        "message": "Document finalized successfully"
    }


@router.delete("/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db)):
    """Delete a document"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.status == "processed":
        raise HTTPException(
            status_code=400, 
            detail="Cannot delete processed document"
        )
    
    db.delete(document)
    db.commit()
    
    logger.info(f"Document {document_id} deleted")
    return {"success": True, "message": "Document deleted"}


@router.get("/processed/all", response_model=List[ProcessedDocumentResponse])
def list_processed_documents(
    document_type: Optional[str] = Query(None, description="Filter by type"),
    db: Session = Depends(get_db)
):
    """List all processed documents"""
    query = db.query(Document).filter(Document.status == "processed")
    
    if document_type:
        query = query.filter(Document.document_type == document_type)
    
    documents = query.order_by(Document.processed_at.desc()).all()
    
    results = []
    for doc in documents:
        results.append(ProcessedDocumentResponse(
            id=doc.id,
            document_type=doc.document_type,
            document_number=doc.document_number or "",
            vendor_name=doc.vendor_name,
            total_amount=doc.total_amount,
            currency=doc.currency,
            status=doc.status,
            document_date=doc.document_date,
            created_at=doc.created_at
        ))
    
    return results
