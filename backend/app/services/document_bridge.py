"""
Service to bridge Document records (from OCR) to Invoice/PurchaseOrder records (for matching).
Converts finalized Document records into structured Invoice or PurchaseOrder records.
"""
import logging
import difflib
from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.document import Document
from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceLine
from app.models.purchase_order import PurchaseOrder
from app.models.po_line import POLine
from app.models.vendor import Vendor

logger = logging.getLogger(__name__)


class DocumentBridge:
    """Bridge service to convert Document records to Invoice/PO records"""
    
    def _ensure_vendor_id(self, document: Document, db: Session) -> int:
        """
        Ensure vendor_id is set. If missing, try to get from vendor_match or create new vendor.
        
        Args:
            document: Document record
            db: Database session
            
        Returns:
            vendor_id (int)
            
        Raises:
            ValueError if vendor_name is also missing
        """
        vendor_id = document.vendor_id
        
        # Try to get from vendor_match first
        if vendor_id is None and document.vendor_match and isinstance(document.vendor_match, dict):
            vendor_id = document.vendor_match.get('matched_vendor_id')
        
        # If still None and we have a vendor_name, create or find vendor
        if vendor_id is None and document.vendor_name:
            vendor_name = document.vendor_name.strip()
            
            # Try exact match first (case-insensitive)
            existing_vendor = db.query(Vendor).filter(
                Vendor.name.ilike(vendor_name)
            ).first()
            
            if existing_vendor:
                vendor_id = existing_vendor.id
                logger.info(f"Found existing vendor (exact match): '{vendor_name}' -> ID {vendor_id}")
            else:
                # Try fuzzy match - normalize vendor names for comparison
                all_vendors = db.query(Vendor).all()
                normalized_input = self._normalize_vendor_name(vendor_name)
                
                best_match = None
                best_ratio = 0.0
                
                for vendor in all_vendors:
                    normalized_vendor = self._normalize_vendor_name(vendor.name)
                    # Use simple similarity check
                    similarity = self._string_similarity(normalized_input, normalized_vendor)
                    if similarity > best_ratio and similarity >= 0.8:  # 80% similarity threshold
                        best_ratio = similarity
                        best_match = vendor
                
                if best_match:
                    vendor_id = best_match.id
                    logger.info(f"Found existing vendor (fuzzy match, {best_ratio:.0%}): '{vendor_name}' -> '{best_match.name}' (ID {vendor_id})")
                else:
                    # Create new vendor
                    new_vendor = Vendor(name=vendor_name)
                    db.add(new_vendor)
                    db.flush()
                    vendor_id = new_vendor.id
                    logger.info(f"Created new vendor: '{vendor_name}' with ID {vendor_id}")
        
        # If still None, raise error
        if vendor_id is None:
            raise ValueError(
                f"Cannot determine vendor: vendor_id is not set and vendor_name is missing. "
                f"Please verify the document and ensure vendor information is provided."
            )
        
        return vendor_id
    
    def _normalize_vendor_name(self, name: str) -> str:
        """Normalize vendor name for comparison (remove common suffixes, lowercase)"""
        if not name:
            return ""
        
        # Remove common company suffixes
        suffixes = [
            ', Inc.', ', Inc', ' Inc.', ' Inc',
            ', LLC', ', L.L.C.', ' LLC', ' L.L.C.',
            ', Corp.', ', Corp', ' Corp.', ' Corp',
            ', Ltd.', ', Ltd', ' Ltd.', ' Ltd',
            ', Co.', ', Co', ' Co.', ' Co',
            ' Corporation', ' Incorporated', ' Limited',
            ' Company', ' & Co', ' and Company',
            ', PLC', ' PLC', ' plc',
            ' GmbH', ' AG', ' S.A.', ' SA',
        ]
        
        normalized = name.strip()
        for suffix in suffixes:
            if normalized.lower().endswith(suffix.lower()):
                normalized = normalized[:-len(suffix)].strip()
        
        # Remove extra whitespace and convert to lowercase
        normalized = ' '.join(normalized.split()).lower()
        return normalized
    
    def _string_similarity(self, s1: str, s2: str) -> float:
        """Calculate similarity ratio between two strings (0.0 to 1.0)"""
        return difflib.SequenceMatcher(None, s1, s2).ratio()
    
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
        vendor_id = self._ensure_vendor_id(document, db)
        
        # Extract PO number from type_specific_data
        po_number = None
        if document.type_specific_data:
            po_number_raw = document.type_specific_data.get('po_number')
            logger.info(f"Extracting PO number from document {document.id}: type_specific_data={document.type_specific_data}, po_number_raw={po_number_raw}")
            # Strip whitespace and convert empty strings to None
            if po_number_raw and isinstance(po_number_raw, str):
                po_number = po_number_raw.strip() if po_number_raw.strip() else None
            elif po_number_raw:
                po_number = po_number_raw
        logger.info(f"Extracted PO number for invoice creation: {po_number}")
        
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
        
        logger.info(f"Created Invoice {invoice.id} from Document {document.id} (invoice_number: {invoice.invoice_number}, po_number: {repr(invoice.po_number)})")
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
        vendor_id = self._ensure_vendor_id(document, db)
        
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

