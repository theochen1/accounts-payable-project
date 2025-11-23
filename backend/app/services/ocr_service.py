import httpx
import base64
import json
import re
from typing import Dict, Optional
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class OCRService:
    """Service for calling DeepSeek chat-completions API for OCR"""
    
    def __init__(self):
        self.api_url = settings.deepseek_api_url
        self.api_key = settings.deepseek_api_key
        self.model = settings.deepseek_model
        self.timeout = settings.ocr_timeout_seconds
        self.max_retries = settings.ocr_max_retries
    
    def _get_content_type(self, filename: str) -> str:
        """Determine content type based on file extension"""
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        content_types = {
            'pdf': 'application/pdf',
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'gif': 'image/gif',
            'bmp': 'image/bmp',
            'webp': 'image/webp',
            'tiff': 'image/tiff',
            'tif': 'image/tiff',
        }
        return content_types.get(ext, 'application/octet-stream')
    
    def _encode_file_to_base64(self, file_content: bytes) -> str:
        """Encode file content to base64 string"""
        return base64.b64encode(file_content).decode('utf-8')
    
    def _get_data_url(self, file_content: bytes, filename: str) -> str:
        """Create data URL for image (base64 encoded)"""
        content_type = self._get_content_type(filename)
        base64_content = self._encode_file_to_base64(file_content)
        return f"data:{content_type};base64,{base64_content}"
    
    async def process_file(self, file_content: bytes, filename: str) -> Dict:
        """
        Process file (PDF or image) through DeepSeek chat-completions API
        
        Args:
            file_content: Binary content of the file
            filename: Original filename
            
        Returns:
            Structured OCR data as dictionary
        """
        if not self.api_key:
            raise Exception("DeepSeek API key is not configured")
        
        # Check if file is PDF (PDFs may need different handling)
        file_ext = filename.lower().split('.')[-1] if '.' in filename else ''
        is_pdf = file_ext == 'pdf'
        
        if is_pdf:
            # For PDFs, we'll need to convert to images first or use a different approach
            # For now, we'll try to send as base64, but PDF support may be limited
            logger.warning("PDF files may not be fully supported by DeepSeek chat API. Consider converting to images first.")
        
        # Create the image data URL
        image_data_url = self._get_data_url(file_content, filename)
        
        # System prompt for OCR extraction
        system_prompt = """Extract all text from any attached image accurately, preserving formatting when possible. 
        For invoices, extract the following information in JSON format:
        - vendor_name: Name of the vendor/company
        - invoice_number: Invoice number or ID
        - po_number: Purchase order number (if present)
        - invoice_date: Date of the invoice
        - total_amount: Total amount (numeric value only, no currency symbols)
        - currency: Currency code (USD, EUR, etc.)
        - line_items: Array of line items, each with:
          - line_no: Line number
          - sku: SKU or product code (if present)
          - description: Item description
          - quantity: Quantity (numeric)
          - unit_price: Unit price (numeric)
        
        Return the data as a JSON object. If any field is not found, use null."""
        
        # User message with image
        user_message = {
            "type": "text",
            "text": "Please extract all invoice information from this image and return it as JSON."
        }
        
        # Try OpenAI-compatible multimodal format first
        # If DeepSeek doesn't support images, we'll fall back to text-only
        # Note: DeepSeek may not support multimodal inputs - if this fails, consider using a different OCR service
        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": [
                    user_message,
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_data_url
                        }
                    }
                ]
            }
        ]
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "temperature": 0.1,  # Low temperature for more accurate extraction
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries):
                try:
                    response = await client.post(
                        self.api_url,
                        json=payload,
                        headers=headers
                    )
                    response.raise_for_status()
                    response_data = response.json()
                    
                    # Extract the text content from the response
                    content = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    
                    # Parse the JSON response from the LLM
                    return self._parse_llm_response(content, response_data)
                    
                except httpx.HTTPStatusError as e:
                    error_text = e.response.text
                    logger.error(f"DeepSeek API error (attempt {attempt + 1}/{self.max_retries}): {e.response.status_code} - {error_text}")
                    
                    # If 404, DeepSeek might not support multimodal inputs
                    if e.response.status_code == 404:
                        logger.warning("DeepSeek API returned 404. This may indicate that multimodal (image) inputs are not supported.")
                        logger.warning("Consider using a different OCR service or converting images to text descriptions first.")
                    
                    if attempt == self.max_retries - 1:
                        raise Exception(f"DeepSeek API failed after {self.max_retries} attempts: {e.response.status_code} - {error_text}")
                except httpx.TimeoutException as e:
                    logger.error(f"DeepSeek API timeout (attempt {attempt + 1}/{self.max_retries}): {str(e)}")
                    if attempt == self.max_retries - 1:
                        raise Exception(f"DeepSeek API timeout after {self.max_retries} attempts")
                except Exception as e:
                    logger.error(f"DeepSeek API unexpected error (attempt {attempt + 1}/{self.max_retries}): {str(e)}")
                    if attempt == self.max_retries - 1:
                        raise
    
    def _parse_llm_response(self, content: str, raw_response: Dict) -> Dict:
        """
        Parse the LLM response text to extract structured invoice data
        
        The LLM should return JSON, but we need to handle cases where it's wrapped in markdown or text
        """
        # Try to extract JSON from the response
        # The LLM might return JSON wrapped in markdown code blocks or plain text
        
        # Remove markdown code blocks if present
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        else:
            # Try to find JSON object in the text
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                content = json_match.group(0)
        
        try:
            # Parse the JSON
            ocr_data = json.loads(content)
        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract fields using regex
            logger.warning("Failed to parse JSON from LLM response, attempting regex extraction")
            ocr_data = self._extract_fields_with_regex(content)
        
        # Normalize the response
        return self._normalize_ocr_response(ocr_data, raw_response)
    
    def _extract_fields_with_regex(self, text: str) -> Dict:
        """Fallback: Extract invoice fields using regex if JSON parsing fails"""
        data = {}
        
        # Extract vendor name
        vendor_match = re.search(r'(?:vendor|company|supplier)[\s:]+([^\n,]+)', text, re.IGNORECASE)
        if vendor_match:
            data['vendor_name'] = vendor_match.group(1).strip()
        
        # Extract invoice number
        invoice_match = re.search(r'(?:invoice\s*(?:number|#|no\.?))[\s:]+([^\n,]+)', text, re.IGNORECASE)
        if invoice_match:
            data['invoice_number'] = invoice_match.group(1).strip()
        
        # Extract PO number
        po_match = re.search(r'(?:po\s*(?:number|#|no\.?)|purchase\s*order)[\s:]+([^\n,]+)', text, re.IGNORECASE)
        if po_match:
            data['po_number'] = po_match.group(1).strip()
        
        # Extract total amount
        total_match = re.search(r'(?:total|amount)[\s:]+[\$]?([\d,]+\.?\d*)', text, re.IGNORECASE)
        if total_match:
            data['total_amount'] = total_match.group(1).replace(',', '')
        
        # Extract currency
        currency_match = re.search(r'(?:currency)[\s:]+([A-Z]{3})', text, re.IGNORECASE)
        if currency_match:
            data['currency'] = currency_match.group(1)
        else:
            data['currency'] = 'USD'
        
        return data
    
    def _normalize_ocr_response(self, ocr_data: Dict, raw_response: Dict) -> Dict:
        """
        Normalize OCR response to our expected format
        
        Maps the LLM-extracted data to our internal structure.
        """
        normalized = {
            "vendor_name": ocr_data.get("vendor_name"),
            "invoice_number": ocr_data.get("invoice_number"),
            "po_number": ocr_data.get("po_number"),
            "invoice_date": ocr_data.get("invoice_date"),
            "total_amount": self._parse_amount(ocr_data.get("total_amount")),
            "currency": (ocr_data.get("currency") or "USD").upper(),
            "line_items": self._normalize_line_items(ocr_data.get("line_items", [])),
            "raw_ocr": {
                "llm_response": raw_response,
                "extracted_data": ocr_data
            }
        }
        
        return normalized
    
    def _parse_amount(self, amount: Optional[str]) -> Optional[float]:
        """Parse amount string to float"""
        if amount is None:
            return None
        if isinstance(amount, (int, float)):
            return float(amount)
        # Remove currency symbols and commas
        cleaned = str(amount).replace("$", "").replace(",", "").replace("€", "").replace("£", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    
    def _normalize_line_items(self, line_items: list) -> list:
        """Normalize line items from OCR response"""
        if not line_items:
            return []
        
        normalized = []
        for idx, item in enumerate(line_items, start=1):
            if isinstance(item, dict):
                normalized.append({
                    "line_no": item.get("line_no", idx),
                    "sku": item.get("sku"),
                    "description": item.get("description", ""),
                    "quantity": self._parse_amount(item.get("quantity")),
                    "unit_price": self._parse_amount(item.get("unit_price"))
                })
        return normalized


ocr_service = OCRService()
