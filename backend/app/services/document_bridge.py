"""
Service to bridge Document records (from OCR) to Invoice/PurchaseOrder records (for matching).
Converts finalized Document records into structured Invoice or PurchaseOrder records.
"""
import logging
from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.document import Document
from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceLine
from app.models.purchase_order import PurchaseOrder
from app.models.po_line import POLine

logger = logging.getLogger(__name__)


class DocumentBridge:
    """Bridge service to convert Document records to Invoice/PO records"""
    
    def create_invoice_from_document(self, document: Document, db: Session) -> Invoice:
        """
        Create Invoice record from verified Document.
        
        Args:
            document: Verified Document record
            db: Database session
            
        Returns:
            Created Invoice record
        """
        if document.document_type != "invoice":
            raise ValueError(f"Cannot create Invoice from document type: {document.document_type}")
        
        # Check if invoice already exists for this document_number
        existing_invoice = db.query(Invoice).filter(
            Invoice.invoice_number == document.document_number
        ).first()
        
        if existing_invoice:
            logger.info(f"Invoice {document.document_number} already exists, skipping creation")
            return existing_invoice
        
        # Ensure vendor_id is set (required for Invoice)
        vendor_id = document.vendor_id
        if vendor_id is None:
            # Try to get vendor_id from vendor_match if available
            if document.vendor_match and isinstance(document.vendor_match, dict):
                vendor_id = document.vendor_match.get('matched_vendor_id')
            
            # If still None, raise an error
            if vendor_id is None:
                raise ValueError(
                    f"Cannot create Invoice: vendor_id is required but not set. "
                    f"Please verify the document and select a vendor. "
                    f"Document vendor_name: {document.vendor_name}"
                )
        
        # Extract PO number from type_specific_data
        po_number = None
        if document.type_specific_data:
            po_number = document.type_specific_data.get('po_number')
        
        # Create Invoice record
        invoice = Invoice(
            invoice_number=document.document_number,
            vendor_id=vendor_id,
            po_number=po_number,
            invoice_date=document.document_date,
            total_amount=document.total_amount,
            currency=document.currency or "USD",
            pdf_storage_path=document.file_path,
            ocr_json=document.raw_ocr,
            status="pending_match",  # New status for matching workflow
            source_document_id=document.id
        )
        
        db.add(invoice)
        db.flush()  # Get invoice.id
        
        # Create invoice lines from document.line_items JSONB
        if document.line_items:
            for idx, line_item in enumerate(document.line_items, start=1):
                # Handle both dict and object formats
                if isinstance(line_item, dict):
                    line_no = line_item.get('line_no', idx)
                    sku = line_item.get('sku')
                    description = line_item.get('description', '')
                    quantity = Decimal(str(line_item.get('quantity', 0)))
                    unit_price = Decimal(str(line_item.get('unit_price', 0)))
                else:
                    line_no = getattr(line_item, 'line_no', idx)
                    sku = getattr(line_item, 'sku', None)
                    description = getattr(line_item, 'description', '')
                    quantity = Decimal(str(getattr(line_item, 'quantity', 0)))
                    unit_price = Decimal(str(getattr(line_item, 'unit_price', 0)))
                
                invoice_line = InvoiceLine(
                    invoice_id=invoice.id,
                    line_no=line_no,
                    sku=sku,
                    description=description,
                    quantity=quantity,
                    unit_price=unit_price
                )
                db.add(invoice_line)
        
        db.commit()
        db.refresh(invoice)
        
        logger.info(f"Created Invoice {invoice.id} from Document {document.id} (invoice_number: {invoice.invoice_number})")
        return invoice
    
    def create_po_from_document(self, document: Document, db: Session) -> PurchaseOrder:
        """
        Create PurchaseOrder record from verified Document.
        
        Args:
            document: Verified Document record
            db: Database session
            
        Returns:
            Created PurchaseOrder record
        """
        if document.document_type != "purchase_order":
            raise ValueError(f"Cannot create PurchaseOrder from document type: {document.document_type}")
        
        # Check if PO already exists for this document_number
        existing_po = db.query(PurchaseOrder).filter(
            PurchaseOrder.po_number == document.document_number
        ).first()
        
        if existing_po:
            logger.info(f"PurchaseOrder {document.document_number} already exists, skipping creation")
            return existing_po
        
        # Ensure vendor_id is set (required for PurchaseOrder)
        vendor_id = document.vendor_id
        if vendor_id is None:
            # Try to get vendor_id from vendor_match if available
            if document.vendor_match and isinstance(document.vendor_match, dict):
                vendor_id = document.vendor_match.get('matched_vendor_id')
            
            # If still None, raise an error
            if vendor_id is None:
                raise ValueError(
                    f"Cannot create PurchaseOrder: vendor_id is required but not set. "
                    f"Please verify the document and select a vendor. "
                    f"Document vendor_name: {document.vendor_name}"
                )
        
        # Extract PO-specific fields from type_specific_data
        requester_email = None
        order_date = document.document_date  # Default to document_date
        
        if document.type_specific_data:
            requester_email = document.type_specific_data.get('requester_email')
            # order_date might be in type_specific_data for POs
            if document.type_specific_data.get('order_date'):
                try:
                    order_date = datetime.strptime(document.type_specific_data['order_date'], '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    pass
        
        # Create PurchaseOrder record
        po = PurchaseOrder(
            po_number=document.document_number,
            vendor_id=vendor_id,
            total_amount=document.total_amount,
            currency=document.currency or "USD",
            status="open",  # Will be updated to fully_matched/partially_matched after matching
            order_date=order_date,
            requester_email=requester_email,
            source_document_id=document.id
        )
        
        db.add(po)
        db.flush()  # Get po.id
        
        # Create PO lines from document.line_items JSONB
        if document.line_items:
            for idx, line_item in enumerate(document.line_items, start=1):
                # Handle both dict and object formats
                if isinstance(line_item, dict):
                    line_no = line_item.get('line_no', idx)
                    sku = line_item.get('sku')
                    description = line_item.get('description', '')
                    quantity = Decimal(str(line_item.get('quantity', 0)))
                    unit_price = Decimal(str(line_item.get('unit_price', 0)))
                else:
                    line_no = getattr(line_item, 'line_no', idx)
                    sku = getattr(line_item, 'sku', None)
                    description = getattr(line_item, 'description', '')
                    quantity = Decimal(str(getattr(line_item, 'quantity', 0)))
                    unit_price = Decimal(str(getattr(line_item, 'unit_price', 0)))
                
                po_line = POLine(
                    po_id=po.id,
                    line_no=line_no,
                    sku=sku,
                    description=description,
                    quantity=quantity,
                    unit_price=unit_price
                )
                db.add(po_line)
        
        db.commit()
        db.refresh(po)
        
        logger.info(f"Created PurchaseOrder {po.id} from Document {document.id} (po_number: {po.po_number})")
        return po


# Singleton instance
document_bridge = DocumentBridge()

