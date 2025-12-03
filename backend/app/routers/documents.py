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


def convert_decimals_to_float(obj):
    """Recursively convert Decimal objects to float for JSON serialization"""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {key: convert_decimals_to_float(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimals_to_float(item) for item in obj]
    elif isinstance(obj, date):
        return obj.isoformat()
    elif isinstance(obj, datetime):
        return obj.isoformat()
    return obj


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
    
    # Build ocr_data for frontend compatibility
    ocr_data = _build_ocr_data_from_document(document)
    
    # Create response dict
    response_dict = {
        'id': document.id,
        'document_type': document.document_type,
        'status': document.status,
        'vendor_name': document.vendor_name,
        'vendor_id': document.vendor_id,
        'document_number': document.document_number,
        'document_date': document.document_date,
        'total_amount': document.total_amount,
        'currency': document.currency,
        'type_specific_data': document.type_specific_data,
        'line_items': document.line_items,
        'filename': document.filename,
        'file_path': document.file_path,
        'raw_ocr': document.raw_ocr,
        'extraction_source': document.extraction_source,
        'vendor_match': document.vendor_match,
        'error_message': document.error_message,
        'uploaded_at': document.uploaded_at,
        'processed_at': document.processed_at,
        'created_at': document.created_at,
        'updated_at': document.updated_at,
        'ocr_data': ocr_data,
    }
    
    return DocumentResponse(**response_dict)


def _build_ocr_data_from_document(document: Document) -> Dict:
    """Build ocr_data dict from document fields for frontend compatibility"""
    ocr_data = {}
    
    if document.document_type == 'invoice':
        ocr_data = {
            'invoice_number': document.document_number,
            'invoice_date': document.document_date.isoformat() if document.document_date else None,
            'po_number': document.type_specific_data.get('po_number') if document.type_specific_data else None,
            'vendor_name': document.vendor_name,
            'total_amount': float(document.total_amount) if document.total_amount else None,
            'currency': document.currency,
            'line_items': document.line_items or [],
            'vendor_match': document.vendor_match,
        }
        if document.type_specific_data:
            if 'tax_amount' in document.type_specific_data:
                ocr_data['tax_amount'] = float(document.type_specific_data['tax_amount']) if isinstance(document.type_specific_data['tax_amount'], (Decimal, int, float)) else document.type_specific_data['tax_amount']
            if 'payment_terms' in document.type_specific_data:
                ocr_data['payment_terms'] = document.type_specific_data['payment_terms']
            if 'due_date' in document.type_specific_data:
                due_date = document.type_specific_data['due_date']
                ocr_data['due_date'] = due_date.isoformat() if hasattr(due_date, 'isoformat') else due_date
    elif document.document_type == 'purchase_order':
        ocr_data = {
            'po_number': document.document_number,
            'order_date': None,
            'requester_email': None,
            'requester_name': None,
            'ship_to_address': None,
            'vendor_name': document.vendor_name,
            'total_amount': float(document.total_amount) if document.total_amount else None,
            'currency': document.currency,
            'line_items': document.line_items or [],
            'vendor_match': document.vendor_match,
        }
        if document.type_specific_data:
            if 'order_date' in document.type_specific_data:
                order_date = document.type_specific_data['order_date']
                ocr_data['order_date'] = order_date.isoformat() if hasattr(order_date, 'isoformat') else order_date
            ocr_data['requester_email'] = document.type_specific_data.get('requester_email')
            ocr_data['requester_name'] = document.type_specific_data.get('requester_name')
            ocr_data['ship_to_address'] = document.type_specific_data.get('ship_to_address')
        # Fallback to document_date if order_date not in type_specific_data
        if not ocr_data['order_date'] and document.document_date:
            ocr_data['order_date'] = document.document_date.isoformat()
    elif document.document_type == 'receipt':
        ocr_data = {
            'receipt_number': document.document_number,
            'transaction_date': document.document_date.isoformat() if document.document_date else None,
            'merchant_name': document.vendor_name,
            'total_amount': float(document.total_amount) if document.total_amount else None,
            'currency': document.currency,
            'payment_method': document.type_specific_data.get('payment_method') if document.type_specific_data else None,
            'transaction_id': document.type_specific_data.get('transaction_id') if document.type_specific_data else None,
            'line_items': document.line_items or [],
        }
    else:
        # Generic fallback
        ocr_data = {
            'document_number': document.document_number,
            'document_date': document.document_date.isoformat() if document.document_date else None,
            'vendor_name': document.vendor_name,
            'total_amount': float(document.total_amount) if document.total_amount else None,
            'currency': document.currency,
            'line_items': document.line_items or [],
            'vendor_match': document.vendor_match,
            'type_specific_data': document.type_specific_data,
        }
    
    return ocr_data


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
        # First, ensure document_type is passed correctly (handle 'po' -> 'purchase_order' mapping)
        doc_type = document.document_type
        if doc_type == 'po':
            doc_type = 'purchase_order'
        
        normalized_data = field_mapper.normalize(ocr_data, doc_type)
        unified_data = field_mapper.to_unified_document_format(normalized_data, doc_type)
        
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
        
        # Convert Decimals to float for JSON serialization
        document.type_specific_data = convert_decimals_to_float(unified_data.get('type_specific_data', {}))
        document.line_items = convert_decimals_to_float(unified_data.get('line_items', []))
        document.raw_ocr = convert_decimals_to_float(unified_data.get('raw_ocr', unified_data))
        document.vendor_match = convert_decimals_to_float(unified_data.get('vendor_match'))
        
        document.extraction_source = unified_data.get('extraction_source', settings.ocr_provider)
        document.vendor_id = unified_data.get('vendor_match', {}).get('matched_vendor_id')
        
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
    
    # Allow verification from pending_verification or verified status (idempotent)
    if document.status not in ["pending_verification", "verified"]:
        raise HTTPException(status_code=400, detail=f"Document must be in pending_verification or verified status. Current status: {document.status}")
    
    # Update document with verified data
    document.vendor_name = verify_data.vendor_name
    document.vendor_id = verify_data.vendor_id
    document.document_number = verify_data.document_number
    document.document_date = verify_data.document_date
    document.total_amount = verify_data.total_amount
    document.currency = verify_data.currency
    
    # Convert line items to dict and convert Decimals to float
    document.line_items = convert_decimals_to_float([item.dict() for item in verify_data.line_items])
    
    # Store type-specific data (convert Decimals to float)
    type_specific = {}
    if document.document_type == "invoice" and verify_data.invoice_data:
        type_specific = convert_decimals_to_float(verify_data.invoice_data.dict(exclude_none=True))
    elif document.document_type == "purchase_order" and verify_data.po_data:
        type_specific = convert_decimals_to_float(verify_data.po_data.dict(exclude_none=True))
    elif document.document_type == "receipt" and verify_data.receipt_data:
        type_specific = convert_decimals_to_float(verify_data.receipt_data.dict(exclude_none=True))
    
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
    """Finalize document - create Invoice/PO record and trigger matching - status: verified -> processed"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.status != "verified":
        raise HTTPException(status_code=400, detail=f"Document must be verified before finalizing. Current status: {document.status}")
    
    # Use document bridge to create Invoice or PO record
    from app.services.document_bridge import document_bridge
    
    created_record = None
        if document.document_type == "invoice":
        try:
            invoice = document_bridge.create_invoice_from_document(document, db)
            created_record = {"type": "invoice", "id": invoice.id, "invoice_number": invoice.invoice_number}
            logger.info(f"Created Invoice {invoice.id} from Document {document_id}")
            
            # Trigger matching if PO exists
            if invoice.po_number:
                from app.services.matching_agent_v2 import MatchingAgentV2
                from app.services.review_queue_service import review_queue_service
                
                try:
                    agent = MatchingAgentV2(db)
                    matching_result = await agent.process_invoice(invoice.id)
                    
                    # Add to review queue if needed
                    if matching_result.match_status == "needs_review":
                        review_queue_service.add_to_queue(matching_result, db)
                        logger.info(f"Added invoice {invoice.id} to review queue")
        else:
                        logger.info(f"Invoice {invoice.id} matched successfully")
    except Exception as e:
                    logger.error(f"Error running matching for invoice {invoice.id}: {e}", exc_info=True)
                    # Continue anyway - matching can be retried later
        
    except Exception as e:
            logger.error(f"Error creating Invoice from Document {document_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to create Invoice: {str(e)}")
    
    elif document.document_type == "purchase_order":
        try:
            po = document_bridge.create_po_from_document(document, db)
            created_record = {"type": "purchase_order", "id": po.id, "po_number": po.po_number}
            logger.info(f"Created PurchaseOrder {po.id} from Document {document_id}")
    except Exception as e:
            logger.error(f"Error creating PurchaseOrder from Document {document_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to create PurchaseOrder: {str(e)}")
    
    # Update status to processed
    document.status = "processed"
    document.processed_at = datetime.now()
    db.commit()
    
    logger.info(f"Document {document_id} finalized, status: processed")
    return {
        "success": True,
        "document_id": document_id,
        "status": "processed",
        "created_record": created_record,
        "message": "Document finalized successfully"
    }


@router.delete("/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db)):
    """Delete a document and its associated file from storage"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete the file from storage if it exists
    if document.file_path:
        try:
            storage_service.delete_file(document.file_path)
            logger.info(f"File deleted from storage: {document.file_path}")
        except Exception as e:
            logger.warning(f"Failed to delete file from storage: {e}")
            # Continue with database deletion even if file deletion fails
    
    # Delete the document record
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
