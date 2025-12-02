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
        # Initialize model clients
        self._init_gemini()
        self._init_openai()
        self._init_azure()
        
        # Timeout and retry settings
        self.timeout = settings.ocr_timeout_seconds
        self.max_retries = settings.ocr_max_retries
        
        logger.info("OCR Agent Service initialized with ensemble support")
    
    def _init_gemini(self):
        """Initialize Gemini client"""
        self.gemini_api_key = settings.gemini_api_key
        self.gemini_model = None
        self.gemini_model_name = settings.gemini_model
        
        if self.gemini_api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_api_key)
                self.gemini_model = genai.GenerativeModel(self.gemini_model_name)
                logger.info(f"Gemini {self.gemini_model_name} initialized")
            except ImportError:
                logger.warning("google-generativeai not installed")
            except Exception as e:
                logger.error(f"Gemini init failed: {e}")
    
    def _init_openai(self):
        """Initialize OpenAI client"""
        self.openai_api_key = settings.openai_api_key
        self.openai_client = None
        
        if self.openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=self.openai_api_key)
            logger.info("OpenAI GPT-4o initialized")
    
    def _init_azure(self):
        """Initialize Azure Document Intelligence client"""
        self.azure_endpoint = settings.azure_doc_intelligence_endpoint
        self.azure_key = settings.azure_doc_intelligence_key
        self.azure_client = None
        
        if self.azure_endpoint and self.azure_key:
            try:
                from azure.core.credentials import AzureKeyCredential
                from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
                self.azure_client = DocumentIntelligenceClient(
                    endpoint=self.azure_endpoint,
                    credential=AzureKeyCredential(self.azure_key)
                )
                logger.info("Azure Document Intelligence initialized")
            except Exception as e:
                logger.error(f"Azure DI init failed: {e}")
    
    async def process_file(self, file_content: bytes, filename: str, document_type: str = "invoice") -> Dict:
        """
        Main entry point - Process document with ensemble OCR agent
        
        Args:
            file_content: Binary file content
            filename: Original filename
            document_type: 'invoice', 'purchase_order', or 'receipt'
        
        Flow:
        1. Extract with multiple models in parallel
        2. Validate each extraction
        3. Apply reasoning to reconcile differences
        4. Targeted re-extraction if needed
        5. Return best result with confidence
        """
        logger.info(f"OCR Agent processing {filename} (type: {document_type}) with ensemble approach")
        
        # Step 1: Multi-model extraction in parallel
        extractions = await self._parallel_extraction(file_content, filename, document_type)
        
        if not extractions:
            logger.error("All extraction models failed")
            return self._create_fallback_response("All OCR models failed")
        
        logger.info(f"Got {len(extractions)} extraction results")
        
        # Step 2: Validate each extraction
        validated_results = []
        for extraction in extractions:
            issues = self._validate_extraction(extraction)
            validated_results.append((extraction, issues))
            
            if issues:
                logger.info(f"{extraction.model_name}: {len(issues)} validation issues")
                for issue in issues:
                    logger.info(f"  - [{issue.severity}] {issue.message}")
        
        # Step 3: Apply reasoning to reconcile and verify
        best_result = await self._reasoning_reconciliation(
            file_content, filename, validated_results, document_type
        )
        
        # Step 4: Check for total mismatch and attempt correction
        total_amount = best_result.get('total_amount')
        line_items = best_result.get('line_items', [])
        if total_amount and line_items:
            line_sum = sum(
                (item.get('quantity') or 0) * (item.get('unit_price') or 0)
                for item in line_items
            )
            if line_sum > 0:
                variance = abs(total_amount - line_sum) / total_amount
                if variance > 0.01:  # More than 1% difference
                    logger.info(f"Total mismatch detected: sum=${line_sum:,.2f}, total=${total_amount:,.2f}, variance={variance*100:.1f}%")
                    best_result = self._correct_number_format_with_total_constraint(best_result)
                    best_result['needs_verification'] = True
        
        # Step 5: Final verification pass if needed
        if best_result.get('needs_verification', False):
            logger.info("Running final verification pass with total constraint...")
            best_result = await self._verification_pass(
                file_content, filename, best_result, document_type
            )
        
        # Clean up and return
        best_result.pop('needs_verification', None)
        best_result.pop('_needs_number_format_correction', None)
        best_result.pop('_current_sum', None)
        best_result.pop('_variance_percent', None)
        best_result['extraction_source'] = 'ocr_agent_ensemble'
        
        # Log final extraction result
        logger.info("=" * 80)
        logger.info("OCR AGENT FINAL EXTRACTION RESULT")
        logger.info("=" * 80)
        logger.info(f"Vendor Name: {best_result.get('vendor_name', 'NOT FOUND')}")
        logger.info(f"Document Number: {best_result.get('document_number', 'NOT FOUND')}")
        logger.info(f"Document Date: {best_result.get('document_date', 'NOT FOUND')}")
        logger.info(f"Total Amount: {best_result.get('total_amount', 'NOT FOUND')}")
        logger.info(f"Currency: {best_result.get('currency', 'NOT FOUND')}")
        logger.info(f"Line Items: {len(best_result.get('line_items', []))}")
        type_specific = best_result.get('type_specific_data', {})
        if type_specific:
            logger.info(f"Type-Specific Data: {list(type_specific.keys())}")
        logger.info(f"Full result keys: {list(best_result.keys())}")
        logger.info("=" * 80)
        
        return best_result
    
    async def _parallel_extraction(
        self, 
        file_content: bytes, 
        filename: str,
        document_type: str = "invoice"
    ) -> List[ExtractionResult]:
        """Run extraction with all available models in parallel"""
        
        tasks = []
        
        # Gemini extraction
        if self.gemini_model:
            tasks.append(self._extract_gemini(file_content, filename, document_type))
        
        # GPT-4o extraction
        if self.openai_client:
            tasks.append(self._extract_gpt4o(file_content, filename, document_type))
        
        # Azure DI extraction
        if self.azure_client:
            tasks.append(self._extract_azure(file_content, filename, document_type))
        
        if not tasks:
            logger.error("No OCR models available")
            return []
        
        # Run in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        extractions = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Extraction error: {result}")
            elif result is not None:
                extractions.append(result)
        
        return extractions
    
    def _get_extraction_prompt(self, document_type: str) -> str:
        """Get type-specific extraction prompt"""
        
        if document_type == "purchase_order":
            return """Analyze this PURCHASE ORDER document VERY CAREFULLY.

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
    "vendor_name": "Company/Vendor name (supplier)",
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
        "requester_name": "Name of person requesting the PO",
        "requester_email": "Email address of person requesting the PO (look for any email addresses on the document - requester, contact, or vendor email)",
        "ship_to_address": "Shipping address if present"
    },
    "table_columns_found": ["Date", "Description", "Price", "Qty", "Total"],
    "extraction_notes": "Any uncertainty about column interpretation"
}

IMPORTANT: Use "document_number" (not "po_number") and "document_date" (not "order_date") for common fields.
Put PO-specific fields like requester_email in the "type_specific" section.

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
    
    async def _extract_gemini(
        self, 
        file_content: bytes, 
        filename: str,
        document_type: str = "invoice"
    ) -> Optional[ExtractionResult]:
        """Extract using Gemini with detailed column-aware prompt"""
        
        if not self.gemini_model:
            return None
        
        try:
            import google.generativeai as genai
            
            # Convert PDF to image if needed (Gemini vision works better with images)
            if self._is_pdf(filename):
                try:
                    image_content, mime_type = self._convert_pdf_to_image(file_content)
                    base64_image = base64.b64encode(image_content).decode('utf-8')
                    logger.info("Converted PDF to image for Gemini extraction")
                except Exception as e:
                    logger.warning(f"PDF conversion failed for Gemini: {e}, trying raw PDF")
                    base64_image = base64.b64encode(file_content).decode('utf-8')
                    mime_type = 'application/pdf'
            else:
                base64_image = base64.b64encode(file_content).decode('utf-8')
                mime_type = self._get_mime_type(filename)
            
            # Get type-specific prompt
            prompt = self._get_extraction_prompt(document_type)

            image_part = {
                "mime_type": mime_type,
                "data": base64_image
            }
            
            response = self.gemini_model.generate_content(
                [prompt, image_part],
                generation_config={
                    "temperature": 0.0,  # Deterministic
                    "max_output_tokens": 4096,
                }
            )
            
            if response and response.text:
                data = self._parse_json_response(response.text)
                return self._dict_to_extraction_result(data, "gemini", document_type, response.text)
            
        except Exception as e:
            logger.error(f"Gemini extraction failed: {e}")
        
        return None
    
    async def _extract_gpt4o(
        self, 
        file_content: bytes, 
        filename: str,
        document_type: str = "invoice"
    ) -> Optional[ExtractionResult]:
        """Extract using GPT-4o with detailed column-aware prompt"""
        
        if not self.openai_client:
            return None
        
        try:
            # GPT-4o Vision ONLY supports images, NOT PDFs - must convert
            if self._is_pdf(filename):
                try:
                    image_content, mime_type = self._convert_pdf_to_image(file_content)
                    base64_image = base64.b64encode(image_content).decode('utf-8')
                    logger.info("Converted PDF to image for GPT-4o extraction")
                except Exception as e:
                    logger.error(f"PDF conversion failed for GPT-4o: {e}")
                    return None  # Can't process PDF without conversion
            else:
                base64_image = base64.b64encode(file_content).decode('utf-8')
                mime_type = self._get_mime_type(filename)
            
            # Get type-specific prompt
            prompt = self._get_extraction_prompt(document_type)

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
                return self._dict_to_extraction_result(data, "gpt-4o", document_type, response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"GPT-4o extraction failed: {e}")
        
        return None
    
    async def _extract_azure(
        self, 
        file_content: bytes, 
        filename: str,
        document_type: str = "invoice"
    ) -> Optional[ExtractionResult]:
        """Extract using Azure Document Intelligence with document-type-aware routing"""
        
        if not self.azure_client:
            return None
        
        try:
            from io import BytesIO
            
            # Route to appropriate Azure model based on document type
            model_id_map = {
                "invoice": "prebuilt-invoice",
                "purchase_order": "prebuilt-layout",  # Generic layout model for POs
                "receipt": "prebuilt-receipt"
            }
            model_id = model_id_map.get(document_type, "prebuilt-invoice")
            
            document_stream = BytesIO(file_content)
            
            poller = await self.azure_client.begin_analyze_document(
                model_id=model_id,
                body=document_stream
            )
            
            result = await poller.result()
            
            # Convert Azure DI result to our unified format
            extraction = ExtractionResult(model_name="azure-di", document_type=document_type)
            type_specific = {}
            
            if hasattr(result, 'documents') and result.documents:
                doc = result.documents[0]
                if hasattr(doc, 'fields') and doc.fields:
                    fields = doc.fields
                    
                    # Extract common fields
                    if 'VendorName' in fields and hasattr(fields['VendorName'], 'value'):
                        extraction.vendor_name = str(fields['VendorName'].value)
                    
                    # Extract document_number based on document type
                    if document_type == "invoice":
                        if 'InvoiceId' in fields and hasattr(fields['InvoiceId'], 'value'):
                            extraction.document_number = str(fields['InvoiceId'].value)
                        if 'PurchaseOrder' in fields and hasattr(fields['PurchaseOrder'], 'value'):
                            type_specific['po_number'] = str(fields['PurchaseOrder'].value)
                    elif document_type == "purchase_order":
                        # For POs, Azure generic model may not have PO-specific fields
                        # Try common field names
                        if 'PurchaseOrderNumber' in fields and hasattr(fields['PurchaseOrderNumber'], 'value'):
                            extraction.document_number = str(fields['PurchaseOrderNumber'].value)
                        elif 'DocumentNumber' in fields and hasattr(fields['DocumentNumber'], 'value'):
                            extraction.document_number = str(fields['DocumentNumber'].value)
                    elif document_type == "receipt":
                        if 'ReceiptNumber' in fields and hasattr(fields['ReceiptNumber'], 'value'):
                            extraction.document_number = str(fields['ReceiptNumber'].value)
                        elif 'TransactionId' in fields and hasattr(fields['TransactionId'], 'value'):
                            extraction.document_number = str(fields['TransactionId'].value)
                            type_specific['transaction_id'] = str(fields['TransactionId'].value)
                    
                    # Extract document_date (unified field name)
                    date_field_map = {
                        "invoice": "InvoiceDate",
                        "purchase_order": "OrderDate",
                        "receipt": "TransactionDate"
                    }
                    date_field = date_field_map.get(document_type, "InvoiceDate")
                    if date_field in fields and hasattr(fields[date_field], 'value'):
                        date_val = fields[date_field].value
                        if hasattr(date_val, 'strftime'):
                            extraction.document_date = date_val.strftime('%Y-%m-%d')
                        else:
                            extraction.document_date = str(date_val)
                    # Fallback to InvoiceDate for invoices
                    elif document_type == "invoice" and 'InvoiceDate' in fields:
                        date_val = fields['InvoiceDate'].value
                        if hasattr(date_val, 'strftime'):
                            extraction.document_date = date_val.strftime('%Y-%m-%d')
                        else:
                            extraction.document_date = str(date_val)
                    
                    # Extract total_amount
                    total_field_map = {
                        "invoice": "InvoiceTotal",
                        "purchase_order": "TotalAmount",
                        "receipt": "Total"
                    }
                    total_field = total_field_map.get(document_type, "InvoiceTotal")
                    if total_field in fields and hasattr(fields[total_field], 'value'):
                        total_val = fields[total_field].value
                        if hasattr(total_val, 'amount'):
                            extraction.total_amount = float(total_val.amount)
                            if hasattr(total_val, 'currency_code'):
                                extraction.currency = total_val.currency_code
                        else:
                            extraction.total_amount = float(total_val) if total_val else None
                    # Fallback to InvoiceTotal for invoices
                    elif document_type == "invoice" and 'InvoiceTotal' in fields:
                        total_val = fields['InvoiceTotal'].value
                        if hasattr(total_val, 'amount'):
                            extraction.total_amount = float(total_val.amount)
                            if hasattr(total_val, 'currency_code'):
                                extraction.currency = total_val.currency_code
                        else:
                            extraction.total_amount = float(total_val) if total_val else None
                    
                    # Extract type-specific fields
                    if document_type == "invoice":
                        if 'Tax' in fields and hasattr(fields['Tax'], 'value'):
                            tax_val = fields['Tax'].value
                            if hasattr(tax_val, 'amount'):
                                type_specific['tax_amount'] = float(tax_val.amount)
                            else:
                                type_specific['tax_amount'] = float(tax_val) if tax_val else None
                        if 'PaymentTerms' in fields and hasattr(fields['PaymentTerms'], 'value'):
                            type_specific['payment_terms'] = str(fields['PaymentTerms'].value)
                        if 'DueDate' in fields and hasattr(fields['DueDate'], 'value'):
                            due_date_val = fields['DueDate'].value
                            if hasattr(due_date_val, 'strftime'):
                                type_specific['due_date'] = due_date_val.strftime('%Y-%m-%d')
                            else:
                                type_specific['due_date'] = str(due_date_val)
                    elif document_type == "receipt":
                        if 'PaymentMethod' in fields and hasattr(fields['PaymentMethod'], 'value'):
                            type_specific['payment_method'] = str(fields['PaymentMethod'].value)
                    
                    extraction.type_specific_data = type_specific
                    
                    # Extract line items
                    if 'Items' in fields and hasattr(fields['Items'], 'value'):
                        items = fields['Items'].value
                        if items:
                            for idx, item in enumerate(items, start=1):
                                if hasattr(item, 'value') and isinstance(item.value, dict):
                                    item_fields = item.value
                                    line_item = {
                                        "line_no": idx,
                                        "description": None,
                                        "quantity": None,
                                        "unit_price": None,
                                        "line_total": None
                                    }
                                    
                                    if 'Description' in item_fields and hasattr(item_fields['Description'], 'value'):
                                        line_item['description'] = str(item_fields['Description'].value)
                                    
                                    if 'Quantity' in item_fields and hasattr(item_fields['Quantity'], 'value'):
                                        line_item['quantity'] = float(item_fields['Quantity'].value)
                                    
                                    if 'UnitPrice' in item_fields and hasattr(item_fields['UnitPrice'], 'value'):
                                        price_val = item_fields['UnitPrice'].value
                                        if hasattr(price_val, 'amount'):
                                            line_item['unit_price'] = float(price_val.amount)
                                        else:
                                            line_item['unit_price'] = float(price_val) if price_val else None
                                    
                                    if 'Amount' in item_fields and hasattr(item_fields['Amount'], 'value'):
                                        amount_val = item_fields['Amount'].value
                                        if hasattr(amount_val, 'amount'):
                                            line_item['line_total'] = float(amount_val.amount)
                                        else:
                                            line_item['line_total'] = float(amount_val) if amount_val else None
                                    
                                    extraction.line_items.append(line_item)
            
            extraction.confidence = 0.8  # Default confidence for Azure DI
            return extraction
            
        except Exception as e:
            logger.error(f"Azure DI extraction failed: {e}")
        
        return None
    
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
    
    async def _reasoning_reconciliation(
        self,
        file_content: bytes,
        filename: str,
        validated_results: List[Tuple[ExtractionResult, List[ValidationIssue]]],
        document_type: str = "invoice"
    ) -> Dict:
        """
        Use reasoning to reconcile multiple extraction results
        
        This is the "brain" of the agent - it analyzes all results,
        identifies disagreements, and determines the most likely correct values.
        """
        
        # If only one result, use it (with validation-based corrections)
        if len(validated_results) == 1:
            extraction, issues = validated_results[0]
            result = self._extraction_to_dict(extraction)
            
            # Check for total mismatch issues and attempt correction
            total_mismatch_issues = [i for i in issues if i.issue_type == "total_mismatch"]
            if total_mismatch_issues:
                result = self._correct_number_format_with_total_constraint(result)
            
            # If there are errors, flag for verification
            if any(i.severity == "error" for i in issues):
                result['needs_verification'] = True
                result['validation_issues'] = [i.message for i in issues]
            
            return result
        
        # Multiple results - find consensus and resolve conflicts
        logger.info("Reconciling multiple extraction results...")
        
        # Build comparison data
        comparison = self._build_comparison(validated_results)
        
        # If we have GPT-4o, use it for intelligent reconciliation
        if self.openai_client:
            return await self._llm_reconciliation(
                file_content, filename, comparison, validated_results, document_type
            )
        
        # Fallback: Simple voting with preference for low-error results
        return self._voting_reconciliation(validated_results)
    
    def _build_comparison(
        self,
        validated_results: List[Tuple[ExtractionResult, List[ValidationIssue]]]
    ) -> Dict:
        """Build a comparison structure for reconciliation"""
        
        comparison = {
            "models": [],
            "vendor_name": {},
            "document_number": {},
            "document_date": {},
            "total_amount": {},
            "line_items": {}
        }
        
        for extraction, issues in validated_results:
            model = extraction.model_name
            error_count = sum(1 for i in issues if i.severity == "error")
            comparison["models"].append({
                "name": model,
                "error_count": error_count,
                "issue_count": len(issues)
            })
            
            # Track values by model
            if extraction.vendor_name:
                comparison["vendor_name"][model] = extraction.vendor_name
            if extraction.document_number:
                comparison["document_number"][model] = extraction.document_number
            if extraction.document_date:
                comparison["document_date"][model] = extraction.document_date
            if extraction.total_amount:
                comparison["total_amount"][model] = extraction.total_amount
            
            # Track line items
            for idx, item in enumerate(extraction.line_items):
                key = f"line_{idx+1}"
                if key not in comparison["line_items"]:
                    comparison["line_items"][key] = {}
                comparison["line_items"][key][model] = {
                    "qty": item.get("quantity"),
                    "price": item.get("unit_price"),
                    "total": item.get("line_total")
                }
        
        return comparison
    
    async def _llm_reconciliation(
        self,
        file_content: bytes,
        filename: str,
        comparison: Dict,
        validated_results: List[Tuple[ExtractionResult, List[ValidationIssue]]],
        document_type: str = "invoice"
    ) -> Dict:
        """Use LLM reasoning to reconcile extraction results"""
        
        # Convert PDF to image for GPT-4o vision
        if self._is_pdf(filename):
            try:
                image_content, mime_type = self._convert_pdf_to_image(file_content)
                base64_image = base64.b64encode(image_content).decode('utf-8')
            except Exception as e:
                logger.error(f"PDF conversion failed for reconciliation: {e}")
                return self._voting_reconciliation(validated_results)
        else:
            base64_image = base64.b64encode(file_content).decode('utf-8')
            mime_type = self._get_mime_type(filename)
        
        # Build comparison summary for the prompt
        comparison_text = self._format_comparison_for_prompt(comparison, validated_results)
        
        # Calculate totals from comparison for constraint checking
        total_amounts = list(comparison.get("total_amount", {}).values())
        invoice_total = total_amounts[0] if total_amounts else None
        
        total_constraint_section = ""
        if invoice_total:
            total_constraint_section = f"""

⚠️ CRITICAL MATH CONSTRAINT:
- The invoice total is: ${invoice_total:,.2f}
- Sum of ALL line items (quantity × unit_price) MUST equal this total
- Use this as a constraint to verify and correct number formats"""
        
        prompt = f"""You are an expert at resolving OCR conflicts. Multiple OCR models have extracted data from the same invoice with DIFFERENT results.

EXTRACTION COMPARISON:
{comparison_text}
{total_constraint_section}

YOUR TASK:
1. Look at the ORIGINAL document image
2. Identify which model got each field CORRECT
3. Pay SPECIAL attention to line item columns (Price vs Qty vs Total)
4. Use MATH to verify: quantity × unit_price should ≈ line_total
5. CRITICAL: Verify that sum of all line items equals the invoice total

COMMON ERROR PATTERNS:
- OCR often confuses the "Total" column with "Unit Price"
- If you see qty=45000 and unit_price=45000, resulting in a BILLION dollar line...
- That's WRONG. Look at the actual columns carefully.

- Decimal point vs comma confusion:
  - OCR might read $33.48 as $33,48 (treating period as thousands separator)
  - Or read $122,779.36 as $122.77936 (treating comma as decimal)
  - Use the invoice total as a constraint to determine correct format
  - Example: If total is $122.04, but prices sum to $122,779.36, there's format confusion
  - Correct by swapping periods/commas until sum matches total

Return the CORRECT values as JSON:
{{
    "vendor_name": "correct vendor name",
    "invoice_number": "correct number",
    "po_number": "PO number or null",
    "invoice_date": "YYYY-MM-DD",
    "total_amount": correct_number,
    "currency": "USD",
    "line_items": [
        {{
            "line_no": 1,
            "description": "item description",
            "quantity": correct_quantity,
            "unit_price": correct_unit_price,
            "line_total": correct_line_total
        }}
    ],
    "reconciliation_notes": "Which model was most accurate and what errors were corrected"
}}

Return ONLY JSON."""

        try:
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
                result = self._parse_json_response(response.choices[0].message.content)
                result['raw_ocr'] = {
                    'source': 'ocr_agent_ensemble',
                    'reconciliation_method': 'llm_reasoning',
                    'models_used': [e.model_name for e, _ in validated_results],
                    'notes': result.pop('reconciliation_notes', None)
                }
                return result
                
        except Exception as e:
            logger.error(f"LLM reconciliation failed: {e}")
        
        # Fallback to voting
        return self._voting_reconciliation(validated_results)
    
    def _format_comparison_for_prompt(
        self,
        comparison: Dict,
        validated_results: List[Tuple[ExtractionResult, List[ValidationIssue]]]
    ) -> str:
        """Format comparison data for the reconciliation prompt"""
        
        lines = []
        
        # Model summary
        lines.append("MODELS AND THEIR ERROR COUNTS:")
        for model_info in comparison["models"]:
            lines.append(f"  {model_info['name']}: {model_info['error_count']} errors, {model_info['issue_count']} total issues")
        lines.append("")
        
        # Field comparisons
        lines.append("VENDOR NAME:")
        for model, value in comparison["vendor_name"].items():
            lines.append(f"  {model}: {value}")
        lines.append("")
        
        lines.append("DOCUMENT NUMBER:")
        for model, value in comparison.get("document_number", {}).items():
            lines.append(f"  {model}: {value}")
        lines.append("")
        
        lines.append("DOCUMENT DATE:")
        for model, value in comparison.get("document_date", {}).items():
            lines.append(f"  {model}: {value}")
        lines.append("")
        
        lines.append("TOTAL AMOUNT:")
        for model, value in comparison["total_amount"].items():
            lines.append(f"  {model}: ${value:,.2f}")
        lines.append("")
        
        # Line item comparisons
        lines.append("LINE ITEMS:")
        for line_key, model_data in comparison["line_items"].items():
            lines.append(f"  {line_key.upper()}:")
            for model, values in model_data.items():
                qty = values.get('qty')
                price = values.get('price')
                total = values.get('total')
                calc = qty * price if qty and price else None
                lines.append(
                    f"    {model}: qty={qty}, price=${price}, total=${total}, "
                    f"calculated={f'${calc:,.2f}' if calc else 'N/A'}"
                )
        lines.append("")
        
        # Validation issues
        lines.append("VALIDATION ISSUES:")
        for extraction, issues in validated_results:
            if issues:
                lines.append(f"  {extraction.model_name}:")
                for issue in issues:
                    lines.append(f"    [{issue.severity}] {issue.message}")
        
        return "\n".join(lines)
    
    def _voting_reconciliation(
        self,
        validated_results: List[Tuple[ExtractionResult, List[ValidationIssue]]]
    ) -> Dict:
        """Simple voting-based reconciliation (fallback)"""
        
        # Sort by error count (fewer errors = better)
        sorted_results = sorted(
            validated_results,
            key=lambda x: sum(1 for i in x[1] if i.severity == "error")
        )
        
        # Use the best result (fewest errors)
        best_extraction, issues = sorted_results[0]
        
        result = self._extraction_to_dict(best_extraction)
        result['raw_ocr'] = {
            'source': 'ocr_agent_ensemble',
            'reconciliation_method': 'voting',
            'selected_model': best_extraction.model_name,
            'models_compared': [e.model_name for e, _ in validated_results]
        }
        
        if any(i.severity == "error" for i in issues):
            result['needs_verification'] = True
        
        return result
    
    def _correct_number_format_with_total_constraint(
        self,
        result: Dict
    ) -> Dict:
        """
        Attempt to correct number format issues (period/comma confusion) using total as constraint.
        
        Common issue: OCR reads $33.48 as $33,48 (treating period as thousands separator)
        Solution: Use the total amount as a constraint to correct line item prices.
        """
        if not result.get('total_amount') or not result.get('line_items'):
            return result
        
        total_amount = float(result['total_amount'])
        line_items = result['line_items']
        
        if not line_items:
            return result
        
        # Calculate current sum
        current_sum = sum(
            (item.get('quantity') or 0) * (item.get('unit_price') or 0)
            for item in line_items
        )
        
        if current_sum == 0:
            return result
        
        # Check if sum matches total (within 1% tolerance)
        variance = abs(total_amount - current_sum) / total_amount
        if variance <= 0.01:  # Already correct
            return result
        
        logger.info(f"Line items sum (${current_sum:,.2f}) doesn't match total (${total_amount:,.2f}). "
                    f"Variance: {variance*100:.1f}%. Attempting number format correction...")
        
        # Try heuristic correction: if prices look like they might have comma/period confusion
        # This is a simple heuristic - the LLM verification pass will do better reasoning
        corrected_items = []
        for item in line_items:
            corrected_item = item.copy()
            price = item.get('unit_price')
            
            if price is not None and price > 0:
                # Heuristic: if price is between 0-1000 and has unusual decimal pattern
                # (e.g., 33.48 stored as 33,48.00 or similar), try basic correction
                # But this is limited - better to let LLM handle it
                pass
            
            corrected_items.append(corrected_item)
        
        # Store flag for LLM to handle in verification
        result['_needs_number_format_correction'] = True
        result['_current_sum'] = current_sum
        result['_total_amount'] = total_amount
        result['_variance_percent'] = variance * 100
        
        return result
    
    async def _verification_pass(
        self,
        file_content: bytes,
        filename: str,
        current_result: Dict,
        document_type: str = "invoice"
    ) -> Dict:
        """
        Final verification pass - explicitly verify suspicious values with total constraint
        """
        
        if not self.openai_client:
            return current_result
        
        # Convert PDF to image for GPT-4o vision
        if self._is_pdf(filename):
            try:
                image_content, mime_type = self._convert_pdf_to_image(file_content)
                base64_image = base64.b64encode(image_content).decode('utf-8')
            except Exception as e:
                logger.error(f"PDF conversion failed for verification: {e}")
                return current_result
        else:
            base64_image = base64.b64encode(file_content).decode('utf-8')
            mime_type = self._get_mime_type(filename)
        
        # Check if we need number format correction
        needs_correction = current_result.pop('_needs_number_format_correction', False)
        current_sum = current_result.pop('_current_sum', None)
        total_amount = current_result.get('total_amount', 0)
        variance_percent = current_result.pop('_variance_percent', None)
        
        # Calculate sum to check
        line_items = current_result.get('line_items', [])
        calculated_sum = sum(
            (item.get('quantity') or 0) * (item.get('unit_price') or 0)
            for item in line_items
        )
        
        # Build verification prompt with total constraint
        doc_type_label = {
            "invoice": "invoice",
            "purchase_order": "purchase order",
            "receipt": "receipt"
        }.get(document_type, "document")
        
        total_constraint_note = ""
        if needs_correction or (calculated_sum > 0 and abs(total_amount - calculated_sum) / total_amount > 0.01):
            total_constraint_note = f"""

⚠️ CRITICAL MATH CONSTRAINT:
- Current sum of line items: ${calculated_sum:,.2f}
- Document total: ${total_amount:,.2f}
- Difference: {abs(total_amount - calculated_sum):,.2f} ({abs(total_amount - calculated_sum) / total_amount * 100:.1f}%)

The sum of ALL line items MUST equal the document total. If it doesn't, there's likely a number format error."""

        doc_type_label = {
            "invoice": "invoice",
            "purchase_order": "purchase order",
            "receipt": "receipt"
        }.get(document_type, "document")
        
        prompt = f"""VERIFICATION REQUEST: Please verify the line items in this {doc_type_label}.

CURRENT EXTRACTED DATA:
{json.dumps(line_items, indent=2)}

DOCUMENT TOTAL: ${total_amount:,.2f}
{total_constraint_note}

VERIFICATION CHECKLIST:
1. Look at the table in the image
2. Identify EACH column header: Date? Description? Price? Qty? Total?
3. For each line item, verify:
   - Is the quantity correct?
   - Is the unit price correct (price for ONE unit)?
   - Does qty × unit_price ≈ line total shown on document?

4. COMMON OCR ERROR: Decimal point vs comma confusion
   - Example: OCR might read $33.48 as $33,48 (treating period as thousands separator)
   - If prices look like: $33,48, $28,28, $5,86, $55,42
   - But total is: $122.04 or $122,779.36
   - This suggests OCR misread periods as commas (or vice versa)
   - Correct prices should be: $33.48, $28.28, $5.86, $55.42
   - VERIFY: Sum of corrected prices should equal the invoice total

5. MATH CONSTRAINT (CRITICAL):
   - Sum of (quantity × unit_price) for ALL lines MUST equal invoice total
   - If it doesn't match, re-examine the number formatting
   - Try swapping periods and commas in prices
   - Use the total as a constraint to find correct values
   - Example: If total is $122.04, but prices sum to $122,779.36, there's a format error

6. If the current data shows qty=45000 and unit_price=45000, that's likely WRONG.
   The unit price column probably shows $1.00

Return CORRECTED line items as JSON:
{{
    "line_items": [
        {{
            "line_no": 1,
            "description": "verified description",
            "quantity": verified_quantity,
            "unit_price": verified_unit_price,
            "line_total": verified_total
        }}
    ],
    "verification_notes": "What was corrected and why. Include math check: sum of line items = total"
}}

IMPORTANT: After correction, verify that sum of all (quantity × unit_price) equals the document total.
Return ONLY JSON."""

        try:
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
                max_tokens=2048,
                temperature=0.0,
                timeout=self.timeout
            )
            
            if response.choices and response.choices[0].message.content:
                verification = self._parse_json_response(response.choices[0].message.content)
                
                if 'line_items' in verification:
                    current_result['line_items'] = verification['line_items']
                    
                    # Update raw_ocr with verification info
                    if 'raw_ocr' not in current_result:
                        current_result['raw_ocr'] = {}
                    current_result['raw_ocr']['verification_pass'] = True
                    current_result['raw_ocr']['verification_notes'] = verification.get('verification_notes')
                    
                    logger.info(f"Verification complete: {verification.get('verification_notes')}")
            
        except Exception as e:
            logger.error(f"Verification pass failed: {e}")
        
        return current_result
    
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

