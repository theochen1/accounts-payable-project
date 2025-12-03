"""
OCR Agent Service - Multi-Model Ensemble with Reasoning

This service implements an intelligent OCR agent that:
1. Uses multiple models in parallel (Gemini, GPT-4o, Azure DI)
2. Applies reasoning to validate extracted data
3. Uses consensus mechanism to reconcile disagreements
4. Performs targeted re-extraction when issues are detected
5. Verifies line item math (qty × price = total)

Key insight: Many OCR errors come from column confusion in tables.
The agent explicitly reasons about column structure.
"""

import asyncio
import base64
import json
import logging
import re
from io import BytesIO
from typing import Dict, List, Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass, field

from openai import AsyncOpenAI
from pdf2image import convert_from_bytes
from PIL import Image

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result from a single model extraction - document-type-aware"""
    model_name: str
    document_type: str  # 'invoice', 'purchase_order', 'receipt'
    
    # Common fields (all document types)
    vendor_name: Optional[str] = None
    document_number: Optional[str] = None  # Unified: invoice_number, po_number, or receipt_number
    document_date: Optional[str] = None    # Unified: invoice_date, order_date, or transaction_date
    total_amount: Optional[float] = None
    currency: str = "USD"
    line_items: List[Dict] = field(default_factory=list)
    
    # Type-specific data (stored as dict)
    type_specific_data: Dict = field(default_factory=dict)
    
    confidence: float = 0.0
    raw_response: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ValidationIssue:
    """Validation issue detected"""
    issue_type: str
    severity: str  # "error", "warning", "info"
    message: str
    field: Optional[str] = None
    line_number: Optional[int] = None
    expected_value: Optional[float] = None
    actual_value: Optional[float] = None


class OCRAgentService:
    """
    Intelligent OCR Agent using multi-model ensemble and reasoning
    """
    
    def __init__(self):
        # Initialize OpenAI client only
        self._init_openai()
        
        # Timeout and retry settings
        self.timeout = settings.ocr_timeout_seconds
        self.max_retries = settings.ocr_max_retries
        
        logger.info("OCR Agent Service initialized with OpenAI-only approach")
    
    def _init_openai(self):
        """Initialize OpenAI client"""
        self.openai_api_key = settings.openai_api_key
        self.openai_client = None
        
        if self.openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=self.openai_api_key)
            logger.info("OpenAI GPT-4o initialized")
        else:
            logger.warning("OpenAI API key not configured")
    
    async def process_file(self, file_content: bytes, filename: str, document_type: str = "invoice") -> Dict:
        """
        Main entry point - Process document with OpenAI OCR (two-call approach)
        
        Args:
            file_content: Binary file content
            filename: Original filename
            document_type: 'invoice', 'purchase_order', or 'receipt'
        
        Flow:
        1. Extract all data with GPT-4o (single call)
        2. Validate and format with GPT-4o (single call)
        3. Return validated result
        """
        logger.info(f"OCR Agent processing {filename} (type: {document_type}) with OpenAI-only approach")
        
        if not self.openai_client:
            logger.error("OpenAI client not initialized")
            return self._create_fallback_response("OpenAI client not available")
        
        # Step 1: Extract with OpenAI
        extraction_result = await self._extract_with_openai(file_content, filename, document_type)
        
        if not extraction_result:
            logger.error("OpenAI extraction failed")
            return self._create_fallback_response("OpenAI extraction failed")
        
        # Step 2: Validate and format with OpenAI
        validated_result = await self._validate_and_format(
            file_content, filename, extraction_result, document_type
        )
        
        # Set extraction source
        validated_result['extraction_source'] = 'ocr_agent_openai'
        
        # Log final extraction result
        logger.info("=" * 80)
        logger.info("OCR AGENT FINAL EXTRACTION RESULT")
        logger.info("=" * 80)
        logger.info(f"Vendor Name: {validated_result.get('vendor_name', 'NOT FOUND')}")
        logger.info(f"Document Number: {validated_result.get('document_number', 'NOT FOUND')}")
        logger.info(f"Document Date: {validated_result.get('document_date', 'NOT FOUND')}")
        logger.info(f"Total Amount: {validated_result.get('total_amount', 'NOT FOUND')}")
        logger.info(f"Currency: {validated_result.get('currency', 'NOT FOUND')}")
        logger.info(f"Line Items: {len(validated_result.get('line_items', []))}")
        type_specific = validated_result.get('type_specific_data', {})
        if type_specific:
            logger.info(f"Type-Specific Data: {list(type_specific.keys())}")
        logger.info("=" * 80)
        
        return validated_result
    
    async def _extract_with_openai(
        self,
        file_content: bytes,
        filename: str,
        document_type: str = "invoice"
    ) -> Optional[Dict]:
        """
        Single OpenAI extraction call - extracts all data from document
        
        Returns:
            Dict with extracted fields or None if extraction fails
        """
        if not self.openai_client:
            return None
        
        try:
            # Convert PDF to image if needed
            if self._is_pdf(filename):
                try:
                    image_content, mime_type = self._convert_pdf_to_image(file_content)
                    base64_image = base64.b64encode(image_content).decode('utf-8')
                    logger.info("Converted PDF to image for OpenAI extraction")
                except Exception as e:
                    logger.error(f"PDF conversion failed: {e}")
                    return None
            else:
                base64_image = base64.b64encode(file_content).decode('utf-8')
                mime_type = self._get_mime_type(filename)
            
            # Get type-specific prompt
            prompt = self._get_extraction_prompt(document_type)
            
            logger.info(f"Calling OpenAI GPT-4o for extraction (document_type: {document_type})")
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{base64_image}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=4096,
                temperature=0.0,
                timeout=self.timeout
            )
            
            if response.choices and response.choices[0].message.content:
                data = self._parse_json_response(response.choices[0].message.content)
                # Convert to unified format
                extraction_result = self._dict_to_extraction_result(data, "gpt-4o", document_type, response.choices[0].message.content)
                # Convert ExtractionResult to dict
                result = self._extraction_to_dict(extraction_result)
                logger.info("OpenAI extraction completed successfully")
                return result
            
        except Exception as e:
            logger.error(f"OpenAI extraction failed: {e}")
        
        return None
    
    async def _validate_and_format(
        self,
        file_content: bytes,
        filename: str,
        extraction_result: Dict,
        document_type: str = "invoice"
    ) -> Dict:
        """
        Single OpenAI validation call - verifies math, fixes format issues, validates fields
        
        Returns:
            Validated and corrected extraction result
        """
        if not self.openai_client:
            logger.warning("OpenAI client not available for validation, returning original result")
            return extraction_result
        
        try:
            # Convert PDF to image if needed
            if self._is_pdf(filename):
                try:
                    image_content, mime_type = self._convert_pdf_to_image(file_content)
                    base64_image = base64.b64encode(image_content).decode('utf-8')
                except Exception as e:
                    logger.error(f"PDF conversion failed for validation: {e}")
                    return extraction_result
            else:
                base64_image = base64.b64encode(file_content).decode('utf-8')
                mime_type = self._get_mime_type(filename)
            
            # Calculate current line item sum
            line_items = extraction_result.get('line_items', [])
            total_amount = extraction_result.get('total_amount', 0)
            calculated_sum = sum(
                (item.get('quantity') or 0) * (item.get('unit_price') or 0)
                for item in line_items
            )
            
            # Build validation prompt
            doc_type_label = {
                "invoice": "invoice",
                "purchase_order": "purchase order",
                "receipt": "receipt"
            }.get(document_type, "document")
            
            total_constraint_note = ""
            if total_amount > 0 and calculated_sum > 0:
                variance = abs(total_amount - calculated_sum) / total_amount
                if variance > 0.01:  # More than 1% difference
                    total_constraint_note = f"""

⚠️ CRITICAL MATH CONSTRAINT:
- Current sum of line items: ${calculated_sum:,.2f}
- Document total: ${total_amount:,.2f}
- Difference: {abs(total_amount - calculated_sum):,.2f} ({variance * 100:.1f}%)

The sum of ALL line items MUST equal the document total. If it doesn't, there's likely a number format error."""
            
            prompt = f"""VALIDATION REQUEST: Please verify and correct the extracted data from this {doc_type_label}.

CURRENT EXTRACTED DATA:
{json.dumps(extraction_result, indent=2)}
{total_constraint_note}

YOUR TASK:
1. Look at the ORIGINAL document image carefully
2. Verify ALL extracted fields are correct:
   - Vendor name, document number, document date, total amount, currency
   - Type-specific fields (check type_specific section)
3. CRITICALLY verify line items:
   - Identify EACH column header: Date? Description? Price? Qty? Total?
   - For each line item, verify:
     * Is the quantity correct?
     * Is the unit price correct (price for ONE unit)?
     * Does qty × unit_price ≈ line total shown on document?
4. COMMON OCR ERRORS to check:
   - Decimal point vs comma confusion (e.g., $33.48 read as $33,48)
   - Column confusion (Total column mistaken for Unit Price)
   - If qty=45000 and unit_price=45000, that's likely WRONG (unit price is probably $1.00)
5. MATH CONSTRAINT (CRITICAL):
   - Sum of (quantity × unit_price) for ALL lines MUST equal document total
   - If it doesn't match, correct number formatting (swap periods/commas)
   - Use the document total as a constraint to find correct values

Return the CORRECTED and VALIDATED data as JSON using the same structure:
{{
    "vendor_name": "correct vendor name",
    "document_number": "correct document number",
    "document_date": "YYYY-MM-DD",
    "total_amount": correct_number,
    "currency": "USD",
    "line_items": [
        {{
            "line_no": 1,
            "description": "correct description",
            "quantity": correct_quantity,
            "unit_price": correct_unit_price,
            "line_total": correct_line_total
        }}
    ],
    "type_specific_data": {{
        // Include all type-specific fields here
    }},
    "validation_notes": "What was verified/corrected and why. Include math check: sum of line items = total"
}}

IMPORTANT: 
- Use "document_number" (not invoice_number/po_number) and "document_date" (not invoice_date/order_date) for common fields
- Put type-specific fields in "type_specific_data" section
- After correction, verify that sum of all (quantity × unit_price) equals the document total
- Return ONLY JSON, no markdown."""

            logger.info("Calling OpenAI GPT-4o for validation and formatting")
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{base64_image}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=4096,
                temperature=0.0,
                timeout=self.timeout
            )
            
            if response.choices and response.choices[0].message.content:
                validated_data = self._parse_json_response(response.choices[0].message.content)
                
                # Merge validation notes into raw_ocr
                if 'raw_ocr' not in validated_data:
                    validated_data['raw_ocr'] = {}
                validated_data['raw_ocr']['validation_pass'] = True
                validated_data['raw_ocr']['validation_notes'] = validated_data.get('validation_notes')
                validated_data['raw_ocr']['source'] = 'ocr_agent_openai'
                
                # Remove validation_notes from top level (it's in raw_ocr now)
                validated_data.pop('validation_notes', None)
                
                logger.info(f"Validation complete: {validated_data.get('raw_ocr', {}).get('validation_notes', 'No notes')}")
                return validated_data
            
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            # Return original result if validation fails
            return extraction_result
        
        return extraction_result
    
    def _get_extraction_prompt(self, document_type: str) -> str:
        """Get type-specific extraction prompt"""
        
        if document_type == "purchase_order":
            return """Analyze this PURCHASE ORDER document VERY CAREFULLY.

VENDOR IDENTIFICATION FOR PURCHASE ORDERS (CRITICAL):
- On a Purchase Order, the company at the TOP/LETTERHEAD is the BUYER (the company placing the order)
- The VENDOR/SUPPLIER is the company in the "TO:", "Vendor:", "Supplier:", or "Ship To:" field
- This is the OPPOSITE of an invoice where the letterhead IS the vendor

Example:
  Letterhead: "Everchem Specialty Chemicals" = BUYER (issuing the PO)
  TO: "Wanhua Chemical" = VENDOR (supplier fulfilling the order)
  
  vendor_name should be "Wanhua Chemical" (NOT Everchem)

CRITICAL: Pay close attention to the TABLE COLUMNS. Common column headers include:
- "Date" - when the line item was ordered
- "Item Description" / "Description" - product name or SKU
- "Price" / "Unit Price" - cost PER UNIT (usually a small number like $1.00, $2.50)
- "Qty" / "Quantity" - how many units (can be large like 45,000)
- "Total" / "Amount" - line total = Quantity × Unit Price

⚠️ COMMON ERROR TO AVOID:
- If you see "45,000.00" in both Qty and Total columns, the UNIT PRICE is likely $1.00
- Do NOT confuse the "Total" column with "Unit Price"
- The line total should ALWAYS equal quantity × unit_price (approximately)

VERIFY YOUR MATH: For each line item, check that:
  quantity × unit_price ≈ line_total (from the document)

Extract and return JSON using this EXACT structure:
{
    "vendor_name": "Company name from TO/Vendor/Supplier field (NOT the letterhead/buyer)",
    "document_number": "Purchase order number",
    "document_date": "YYYY-MM-DD format (order date)",
    "total_amount": number (grand total),
    "currency": "USD/EUR/etc",
    "line_items": [
        {
            "line_no": 1,
            "description": "Item description",
            "quantity": number (how many units),
            "unit_price": number (price PER SINGLE UNIT),
            "line_total": number (from document, should ≈ qty × unit_price)
        }
    ],
    "type_specific": {
        "buyer_name": "Company name from letterhead/header (company issuing the PO)",
        "requester_name": "Name of person requesting the PO",
        "requester_email": "Email address of person requesting the PO (look for any email addresses on the document - requester, contact, or vendor email)",
        "ship_to_address": "Shipping address if present"
    },
    "table_columns_found": ["Date", "Description", "Price", "Qty", "Total"],
    "extraction_notes": "Any uncertainty about column interpretation or vendor identification"
}

IMPORTANT: Use "document_number" (not "po_number") and "document_date" (not "order_date") for common fields.
Put PO-specific fields like buyer_name, requester_email in the "type_specific" section.

CRITICAL: Look carefully for ANY email addresses on the document - check headers, footers, contact sections, and signature areas. Extract the requester_email if found.

Return ONLY the JSON, no markdown."""
        
        elif document_type == "receipt":
            return """Analyze this RECEIPT document VERY CAREFULLY.

Extract and return JSON using this EXACT structure:
{
    "vendor_name": "Store/merchant name",
    "document_number": "Receipt number or transaction ID",
    "document_date": "YYYY-MM-DD format (transaction date)",
    "total_amount": number (total paid),
    "currency": "USD/EUR/etc",
    "line_items": [
        {
            "line_no": 1,
            "description": "Item description",
            "quantity": number,
            "unit_price": number,
            "line_total": number
        }
    ],
    "type_specific": {
        "payment_method": "Cash/Credit Card/Debit/etc",
        "transaction_id": "Transaction ID if present"
    }
}

IMPORTANT: Use "vendor_name" (not "merchant_name"), "document_number" (not "receipt_number"), and "document_date" (not "transaction_date") for common fields.
Put receipt-specific fields like payment_method in the "type_specific" section.

CRITICAL: Look carefully for ANY email addresses on the document - check headers, footers, and contact sections. Extract as contact_email in type_specific if found.

Return ONLY the JSON, no markdown."""
        
        else:  # invoice (default)
            return """Analyze this INVOICE document VERY CAREFULLY.

CRITICAL: Pay close attention to the TABLE COLUMNS. Common column headers include:
- "Date" - when the line item was ordered/shipped
- "Item Description" / "Description" - product name or SKU
- "Price" / "Unit Price" - cost PER UNIT (usually a small number like $1.00, $2.50)
- "Qty" / "Quantity" - how many units (can be large like 45,000)
- "Total" / "Amount" - line total = Quantity × Unit Price

⚠️ COMMON ERROR TO AVOID:
- If you see "45,000.00" in both Qty and Total columns, the UNIT PRICE is likely $1.00
- Do NOT confuse the "Total" column with "Unit Price"
- The line total should ALWAYS equal quantity × unit_price (approximately)

VERIFY YOUR MATH: For each line item, check that:
  quantity × unit_price ≈ line_total (from the document)

Extract and return JSON using this EXACT structure:
{
    "vendor_name": "Company that SENT/ISSUED the invoice (from letterhead, NOT Bill To)",
    "document_number": "Invoice number/ID",
    "document_date": "YYYY-MM-DD format",
    "total_amount": number (grand total),
    "currency": "USD/EUR/etc",
    "line_items": [
        {
            "line_no": 1,
            "description": "Item description",
            "quantity": number (how many units),
            "unit_price": number (price PER SINGLE UNIT),
            "line_total": number (from document, should ≈ qty × unit_price)
        }
    ],
    "type_specific": {
        "po_number": "PO number if present",
        "tax_amount": number (tax if present),
        "payment_terms": "Payment terms if present",
        "due_date": "Due date if present (YYYY-MM-DD)",
        "contact_email": "Any email address found on the invoice (vendor contact, billing contact, etc.)"
    },
    "table_columns_found": ["Date", "Description", "Price", "Qty", "Total"],
    "extraction_notes": "Any uncertainty about column interpretation"
}

IMPORTANT: Use "document_number" (not "invoice_number") and "document_date" (not "invoice_date") for common fields.
Put invoice-specific fields like po_number, tax_amount, payment_terms, due_date in the "type_specific" section.

CRITICAL: Look carefully for ANY email addresses on the document - check headers, footers, contact sections, and signature areas. Extract as contact_email in type_specific if found.

Return ONLY the JSON, no markdown."""
    
    def _validate_extraction(self, extraction: ExtractionResult) -> List[ValidationIssue]:
        """Validate an extraction result and identify issues"""
        
        issues = []
        
        # Check for missing critical fields
        if not extraction.vendor_name:
            issues.append(ValidationIssue(
                issue_type="missing_field",
                severity="warning",
                message="Vendor name is missing",
                field="vendor_name"
            ))
        
        if not extraction.total_amount:
            issues.append(ValidationIssue(
                issue_type="missing_field",
                severity="warning",
                message="Total amount is missing",
                field="total_amount"
            ))
        
        # Validate line items
        for idx, item in enumerate(extraction.line_items):
            qty = item.get('quantity')
            price = item.get('unit_price')
            line_total = item.get('line_total')
            
            # Check for suspicious values
            if qty is not None and qty > 100000:
                issues.append(ValidationIssue(
                    issue_type="suspicious_quantity",
                    severity="warning",
                    message=f"Line {idx+1}: Quantity {qty:,.0f} is unusually high",
                    field="quantity",
                    line_number=idx + 1,
                    actual_value=qty
                ))
            
            if price is not None and price > 10000:
                issues.append(ValidationIssue(
                    issue_type="suspicious_price",
                    severity="warning",
                    message=f"Line {idx+1}: Unit price ${price:,.2f} is unusually high",
                    field="unit_price",
                    line_number=idx + 1,
                    actual_value=price
                ))
            
            # CRITICAL: Check if qty × price math is reasonable
            if qty is not None and price is not None and qty > 0 and price > 0:
                calculated_total = qty * price
                
                # Check against line_total if available
                if line_total is not None and line_total > 0:
                    variance = abs(calculated_total - line_total) / line_total
                    if variance > 0.05:  # More than 5% difference
                        issues.append(ValidationIssue(
                            issue_type="math_mismatch",
                            severity="error",
                            message=f"Line {idx+1}: qty({qty:,.2f}) × price(${price:,.2f}) = ${calculated_total:,.2f}, but line_total is ${line_total:,.2f}",
                            field="line_calculation",
                            line_number=idx + 1,
                            expected_value=line_total,
                            actual_value=calculated_total
                        ))
                
                # Check for absurdly high totals (likely column confusion)
                if calculated_total > 1000000:  # > $1M per line item
                    issues.append(ValidationIssue(
                        issue_type="unreasonable_total",
                        severity="error",
                        message=f"Line {idx+1}: Calculated total ${calculated_total:,.2f} is unreasonably high - likely column confusion",
                        field="line_calculation",
                        line_number=idx + 1,
                        actual_value=calculated_total
                    ))
        
        # Check if line items sum to total
        if extraction.total_amount and extraction.line_items:
            line_sum = sum(
                (item.get('quantity') or 0) * (item.get('unit_price') or 0)
                for item in extraction.line_items
            )
            
            if line_sum > 0:
                variance = abs(extraction.total_amount - line_sum) / extraction.total_amount
                if variance > 0.1:  # More than 10% difference
                    # Check if this might be a number format issue (period/comma confusion)
                    # If the difference is very large, it's likely a format issue
                    diff_ratio = max(extraction.total_amount, line_sum) / min(extraction.total_amount, line_sum)
                    format_issue_hint = ""
                    if diff_ratio > 10:  # One is 10x the other - likely format confusion
                        format_issue_hint = " This may indicate number format confusion (period/comma misinterpretation)."
                    
                    issues.append(ValidationIssue(
                        issue_type="total_mismatch",
                        severity="error",
                        message=f"Sum of line items (${line_sum:,.2f}) doesn't match total (${extraction.total_amount:,.2f}).{format_issue_hint}",
                        field="total_amount",
                        expected_value=extraction.total_amount,
                        actual_value=line_sum
                    ))
        
        return issues
    
    def _dict_to_extraction_result(
        self, 
        data: Dict, 
        model_name: str,
        document_type: str,
        raw_response: str = None
    ) -> ExtractionResult:
        """Convert parsed dict to ExtractionResult with unified field names"""
        
        # Normalize line items
        line_items = []
        for item in data.get('line_items', []):
            normalized_item = {
                'line_no': item.get('line_no', item.get('line_number', item.get('line', 1))),
                'description': item.get('description') or item.get('item_description') or '',
                'quantity': item.get('quantity') or item.get('qty') or 0,
                'unit_price': item.get('unit_price') or item.get('price') or item.get('unit_cost') or 0,
            }
            if 'line_total' in item or 'total' in item:
                normalized_item['line_total'] = item.get('line_total') or item.get('total') or 0
            line_items.append(normalized_item)
        
        # Extract type-specific data from 'type_specific' section or top-level fields
        type_specific = data.get('type_specific', {})
        
        # For backward compatibility, also check top-level fields
        if document_type == "invoice":
            if 'po_number' in data and 'po_number' not in type_specific:
                type_specific['po_number'] = data['po_number']
            if 'tax_amount' in data and 'tax_amount' not in type_specific:
                type_specific['tax_amount'] = data['tax_amount']
            if 'payment_terms' in data and 'payment_terms' not in type_specific:
                type_specific['payment_terms'] = data['payment_terms']
            if 'due_date' in data and 'due_date' not in type_specific:
                type_specific['due_date'] = data['due_date']
        elif document_type == "purchase_order":
            if 'requester_email' in data and 'requester_email' not in type_specific:
                type_specific['requester_email'] = data['requester_email']
            if 'requester_name' in data and 'requester_name' not in type_specific:
                type_specific['requester_name'] = data['requester_name']
            if 'ship_to_address' in data and 'ship_to_address' not in type_specific:
                type_specific['ship_to_address'] = data['ship_to_address']
            # Handle order_date - if in type_specific, use it; otherwise use document_date
            if 'order_date' in data and 'order_date' not in type_specific:
                type_specific['order_date'] = data['order_date']
        elif document_type == "receipt":
            if 'payment_method' in data and 'payment_method' not in type_specific:
                type_specific['payment_method'] = data['payment_method']
            if 'transaction_id' in data and 'transaction_id' not in type_specific:
                type_specific['transaction_id'] = data['transaction_id']
        
        # Extract unified common fields
        vendor_name = data.get('vendor_name') or data.get('merchant_name')
        document_number = (
            data.get('document_number') or 
            data.get('invoice_number') or 
            data.get('po_number') or 
            data.get('receipt_number')
        )
        document_date = (
            data.get('document_date') or 
            data.get('invoice_date') or 
            data.get('order_date') or 
            data.get('transaction_date')
        )
        
        return ExtractionResult(
            model_name=model_name,
            document_type=document_type,
            vendor_name=vendor_name,
            document_number=document_number,
            document_date=document_date,
            total_amount=data.get('total_amount'),
            currency=data.get('currency', 'USD'),
            line_items=line_items,
            type_specific_data=type_specific,
            confidence=data.get('confidence', {}).get('overall', 0.8) if isinstance(data.get('confidence'), dict) else 0.8,
            raw_response=raw_response
        )
    
    def _extraction_to_dict(self, extraction: ExtractionResult) -> Dict:
        """Convert ExtractionResult to dict with unified schema"""
        
        # Return unified structure
        result = {
            'vendor_name': extraction.vendor_name,
            'document_number': extraction.document_number,
            'document_date': extraction.document_date,
            'total_amount': extraction.total_amount,
            'currency': extraction.currency,
            'line_items': extraction.line_items,
            'type_specific_data': extraction.type_specific_data,
        }
        
        # Log extraction result for debugging
        logger.info(f"[{extraction.model_name}] Extracted: vendor={extraction.vendor_name}, "
                   f"document_number={extraction.document_number}, "
                   f"document_date={extraction.document_date}, "
                   f"total={extraction.total_amount}, line_items={len(extraction.line_items)}, "
                   f"type_specific_keys={list(extraction.type_specific_data.keys())}")
        
        return result
    
    def _parse_json_response(self, content: str) -> Dict:
        """Parse JSON from LLM response"""
        
        if not content:
            return {}
        
        # Remove markdown code blocks
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```\s*', '', content)
        content = content.strip()
        
        # Find JSON object
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            content = match.group(0)
        
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return {}
    
    def _get_mime_type(self, filename: str) -> str:
        """Get MIME type from filename"""
        
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        return {
            'pdf': 'application/pdf',
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'gif': 'image/gif',
            'bmp': 'image/bmp',
            'webp': 'image/webp',
            'tiff': 'image/tiff',
            'tif': 'image/tiff',
        }.get(ext, 'application/octet-stream')
    
    def _is_pdf(self, filename: str) -> bool:
        """Check if file is a PDF"""
        return filename.lower().endswith('.pdf')
    
    def _convert_pdf_to_image(self, file_content: bytes) -> Tuple[bytes, str]:
        """
        Convert PDF to PNG image for vision APIs
        
        Returns:
            Tuple of (image_bytes, mime_type)
        """
        try:
            # Convert PDF to images (just first page for now)
            images = convert_from_bytes(file_content, first_page=1, last_page=1, dpi=200)
            
            if not images:
                raise ValueError("No pages found in PDF")
            
            # Convert first page to PNG
            img = images[0]
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            
            logger.info(f"Converted PDF to PNG image ({img.width}x{img.height})")
            return buffer.getvalue(), 'image/png'
            
        except Exception as e:
            logger.error(f"PDF to image conversion failed: {e}")
            raise
    
    def _create_fallback_response(self, error_msg: str) -> Dict:
        """Create fallback response when extraction fails"""
        
        return {
            "vendor_name": None,
            "invoice_number": None,
            "po_number": None,
            "invoice_date": None,
            "total_amount": None,
            "currency": "USD",
            "line_items": [],
            "extraction_source": "fallback",
            "raw_ocr": {
                "error": error_msg,
                "fallback": True
            }
        }


# Singleton instance
ocr_agent_service = OCRAgentService()

