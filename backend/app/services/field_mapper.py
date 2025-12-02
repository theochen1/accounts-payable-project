"""
Field Mapper Service - Normalizes OCR output to unified document schema

Handles variations in OCR field naming and maps to standardized document structure.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger(__name__)


class FieldMapper:
    """Maps OCR output variations to unified document schema"""
    
    # Field mapping dictionaries for common OCR variations
    INVOICE_FIELD_MAP = {
        "invoice_number": "document_number",
        "invoice_id": "document_number",
        "invoice_no": "document_number",
        "invoice_num": "document_number",
        "invoice_date": "document_date",
        "date": "document_date",
        "invoice_due_date": "due_date",
        "due_date": "due_date",
        "vendor": "vendor_name",
        "vendor_name": "vendor_name",
        "supplier": "vendor_name",
        "supplier_name": "vendor_name",
        "total": "total_amount",
        "total_amount": "total_amount",
        "amount": "total_amount",
        "grand_total": "total_amount",
        "subtotal": "subtotal",
        "tax": "tax_amount",
        "tax_amount": "tax_amount",
        "line_items": "line_items",
        "items": "line_items",
        "products": "line_items",
    }
    
    PO_FIELD_MAP = {
        "po_number": "document_number",
        "po_no": "document_number",
        "purchase_order_number": "document_number",
        "order_number": "document_number",
        "order_date": "document_date",
        "po_date": "document_date",
        "date": "document_date",
        "vendor": "vendor_name",
        "vendor_name": "vendor_name",
        "supplier": "vendor_name",
        "supplier_name": "vendor_name",
        "total": "total_amount",
        "total_amount": "total_amount",
        "amount": "total_amount",
        "requester": "requester_name",
        "requester_name": "requester_name",
        "requested_by": "requester_name",
        "requester_email": "requester_email",
        "email": "requester_email",
        "ship_to": "ship_to_address",
        "ship_to_address": "ship_to_address",
        "shipping_address": "ship_to_address",
        "line_items": "line_items",
        "items": "line_items",
        "products": "line_items",
    }
    
    RECEIPT_FIELD_MAP = {
        "receipt_number": "document_number",
        "receipt_no": "document_number",
        "transaction_id": "transaction_id",
        "transaction_number": "transaction_id",
        "receipt_date": "document_date",
        "transaction_date": "document_date",
        "date": "document_date",
        "merchant": "vendor_name",
        "merchant_name": "vendor_name",
        "store": "vendor_name",
        "store_name": "vendor_name",
        "total": "total_amount",
        "total_amount": "total_amount",
        "amount": "total_amount",
        "payment_method": "payment_method",
        "payment_type": "payment_method",
        "paid_with": "payment_method",
    }
    
    @staticmethod
    def normalize(raw_data: Dict[str, Any], document_type: str) -> Dict[str, Any]:
        """
        Normalize OCR output to unified document schema.
        
        With type-aware extraction, this mainly handles edge cases and ensures
        consistent output format. The OCR agent already produces unified field names.
        
        Args:
            raw_data: OCR extraction output (should already use unified schema)
            document_type: 'invoice', 'purchase_order', or 'receipt'
            
        Returns:
            Normalized dict with unified field names
        """
        # Handle 'po' -> 'purchase_order' mapping
        if document_type == "po":
            document_type = "purchase_order"
        
        # Start with the data as-is (OCR agent already produces unified schema)
        normalized = raw_data.copy()
        
        # Ensure common fields use unified names (handle edge cases)
        # Map old field names to unified names if present
        if "invoice_number" in normalized and "document_number" not in normalized:
            normalized["document_number"] = normalized.pop("invoice_number")
        if "po_number" in normalized and "document_number" not in normalized:
            normalized["document_number"] = normalized.pop("po_number")
        if "receipt_number" in normalized and "document_number" not in normalized:
            normalized["document_number"] = normalized.pop("receipt_number")
        
        if "invoice_date" in normalized and "document_date" not in normalized:
            normalized["document_date"] = normalized.pop("invoice_date")
        if "order_date" in normalized and "document_date" not in normalized:
            normalized["document_date"] = normalized.pop("order_date")
        if "transaction_date" in normalized and "document_date" not in normalized:
            normalized["document_date"] = normalized.pop("transaction_date")
        
        if "merchant_name" in normalized and "vendor_name" not in normalized:
            normalized["vendor_name"] = normalized.pop("merchant_name")
        
        # Ensure type_specific_data exists and is properly structured
        if "type_specific" in normalized:
            normalized["type_specific_data"] = normalized.pop("type_specific")
        elif "type_specific_data" not in normalized:
            normalized["type_specific_data"] = {}
        
        # Extract type-specific fields into type_specific_data if they're at top level
        type_specific = normalized.get("type_specific_data", {})
        
        if document_type == "invoice":
            for field in ["po_number", "tax_amount", "payment_terms", "due_date"]:
                if field in normalized and field not in type_specific:
                    type_specific[field] = normalized.pop(field)
        elif document_type == "purchase_order":
            for field in ["requester_name", "requester_email", "ship_to_address", "order_date"]:
                if field in normalized and field not in type_specific:
                    type_specific[field] = normalized.pop(field)
        elif document_type == "receipt":
            for field in ["payment_method", "transaction_id"]:
                if field in normalized and field not in type_specific:
                    type_specific[field] = normalized.pop(field)
        
        normalized["type_specific_data"] = type_specific
        
        # Normalize line items (ensure consistent format)
        if "line_items" in normalized:
            normalized["line_items"] = FieldMapper._normalize_line_items(normalized["line_items"])
        
        # Preserve raw OCR data
        if "raw_ocr" not in normalized:
            normalized["raw_ocr"] = raw_data
        
        return normalized
    
    @staticmethod
    def _normalize_line_items(line_items: list) -> list:
        """Normalize line items to standard format"""
        normalized = []
        for item in line_items:
            if isinstance(item, dict):
                normalized_item = {
                    "line_no": item.get("line_no", item.get("line_number", item.get("line", 1))),
                    "sku": item.get("sku") or item.get("product_code") or item.get("item_code"),
                    "description": item.get("description") or item.get("item_description") or item.get("product") or "",
                    "quantity": FieldMapper._to_decimal(item.get("quantity") or item.get("qty") or item.get("amount") or 0),
                    "unit_price": FieldMapper._to_decimal(item.get("unit_price") or item.get("price") or item.get("unit_cost") or 0),
                }
                # Include line_total if present
                if "line_total" in item or "total" in item:
                    normalized_item["line_total"] = FieldMapper._to_decimal(item.get("line_total") or item.get("total") or 0)
                normalized.append(normalized_item)
        return normalized
    
    @staticmethod
    def _extract_type_specific_data(raw_data: Dict[str, Any], document_type: str) -> Dict[str, Any]:
        """
        Extract type-specific fields into type_specific_data dict.
        
        This is mainly for backward compatibility. With type-aware extraction,
        type_specific_data should already be present in the OCR output.
        """
        type_data = {}
        
        if document_type == "invoice":
            if "po_number" in raw_data:
                type_data["po_number"] = raw_data["po_number"]
            if "payment_terms" in raw_data:
                type_data["payment_terms"] = raw_data["payment_terms"]
            if "due_date" in raw_data:
                type_data["due_date"] = raw_data["due_date"]
            if "tax_amount" in raw_data or "tax" in raw_data:
                type_data["tax_amount"] = FieldMapper._to_decimal(raw_data.get("tax_amount") or raw_data.get("tax") or 0)
        
        elif document_type == "purchase_order":
            if "requester_name" in raw_data or "requester" in raw_data:
                type_data["requester_name"] = raw_data.get("requester_name") or raw_data.get("requester")
            if "requester_email" in raw_data or "email" in raw_data:
                type_data["requester_email"] = raw_data.get("requester_email") or raw_data.get("email")
            if "ship_to_address" in raw_data or "ship_to" in raw_data:
                type_data["ship_to_address"] = raw_data.get("ship_to_address") or raw_data.get("ship_to")
            if "order_date" in raw_data:
                type_data["order_date"] = raw_data["order_date"]
        
        elif document_type == "receipt":
            if "payment_method" in raw_data or "payment_type" in raw_data:
                type_data["payment_method"] = raw_data.get("payment_method") or raw_data.get("payment_type")
            if "transaction_id" in raw_data:
                type_data["transaction_id"] = raw_data["transaction_id"]
        
        return type_data if type_data else {}
    
    @staticmethod
    def _to_decimal(value: Any) -> Decimal:
        """Convert value to Decimal safely"""
        if value is None:
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        try:
            # Remove currency symbols and commas
            if isinstance(value, str):
                cleaned = value.replace("$", "").replace(",", "").strip()
                return Decimal(cleaned)
            return Decimal(str(value))
        except (ValueError, TypeError):
            logger.warning(f"Could not convert {value} to Decimal, using 0")
            return Decimal("0")
    
    @staticmethod
    def to_unified_document_format(normalized_data: Dict[str, Any], document_type: str) -> Dict[str, Any]:
        """
        Convert normalized OCR data to unified document format for database storage.
        
        Separates common fields from type-specific fields.
        """
        # Extract common fields
        document = {
            "vendor_name": normalized_data.get("vendor_name"),
            "document_number": normalized_data.get("document_number"),
            "document_date": normalized_data.get("document_date"),
            "total_amount": normalized_data.get("total_amount"),
            "currency": normalized_data.get("currency", "USD"),
            "line_items": normalized_data.get("line_items", []),
        }
        
        # Extract type-specific data
        type_specific = normalized_data.get("type_specific_data", {})
        if not type_specific:
            # Try to extract from normalized_data directly
            type_specific = FieldMapper._extract_type_specific_data(normalized_data, document_type)
        
        document["type_specific_data"] = type_specific or {}
        document["raw_ocr"] = normalized_data.get("raw_ocr", normalized_data)
        
        return document


# Singleton instance
field_mapper = FieldMapper()

