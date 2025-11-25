import asyncio
import base64
import json
import re
import os
from typing import Dict, Optional
from openai import AsyncOpenAI
from app.config import settings
import logging
from io import BytesIO
from pdf2image import convert_from_bytes
from PIL import Image
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, ContentType

logger = logging.getLogger(__name__)


class OCRService:
    """
    Two-step OCR service:
    1. Extract text using Azure Document Intelligence (prebuilt-invoice model)
    2. Parse text into structured JSON using OpenAI or DeepSeek chat API
    """
    
    def __init__(self):
        # Step 1: Azure Document Intelligence client
        self.azure_endpoint = settings.azure_doc_intelligence_endpoint or os.environ.get("AZURE_DOC_INTELLIGENCE_ENDPOINT")
        self.azure_key = settings.azure_doc_intelligence_key or os.environ.get("AZURE_DOC_INTELLIGENCE_KEY")
        self.azure_model = settings.azure_doc_intelligence_model
        
        # Step 2: LLM parsing client (OpenAI or DeepSeek)
        self.use_deepseek = settings.use_deepseek_for_parsing
        if self.use_deepseek:
            # Use DeepSeek chat API
            self.llm_base_url = settings.deepseek_api_url
            self.llm_api_key = settings.deepseek_api_key or os.environ.get("DEEPSEEK_API_KEY")
            self.llm_model = settings.deepseek_model
        else:
            # Use OpenAI API
            self.llm_base_url = "https://api.openai.com/v1"
            # Prioritize config value over environment variable to avoid old keys in .zshrc
            if settings.openai_api_key:
                self.llm_api_key = settings.openai_api_key
                logger.info(f"Using OpenAI API key from config (prefix: {settings.openai_api_key[:7]}...)")
            else:
                env_key = os.environ.get("OPENAI_API_KEY")
                if env_key:
                    self.llm_api_key = env_key
                    logger.warning(f"Using OpenAI API key from environment variable (prefix: {env_key[:7]}...). Consider setting it in .env file instead.")
                else:
                    self.llm_api_key = None
            self.llm_model = settings.openai_model
        
        self.timeout = settings.ocr_timeout_seconds
        self.max_retries = settings.ocr_max_retries
        
        # Initialize Azure Document Intelligence client
        if not self.azure_endpoint or not self.azure_key:
            logger.warning("Azure Document Intelligence credentials not set. OCR extraction will not function.")
            logger.warning("Set AZURE_DOC_INTELLIGENCE_ENDPOINT and AZURE_DOC_INTELLIGENCE_KEY environment variables.")
            self.azure_client = None
        else:
            logger.info(f"Initializing Azure Document Intelligence client")
            logger.info(f"Azure endpoint: {self.azure_endpoint}")
            logger.info(f"Azure model: {self.azure_model}")
            self.azure_client = DocumentIntelligenceClient(
                endpoint=self.azure_endpoint,
                credential=AzureKeyCredential(self.azure_key)
            )
        
        # Initialize LLM parsing client (OpenAI or DeepSeek)
        if not self.llm_api_key:
            logger.warning(f"{'DEEPSEEK_API_KEY' if self.use_deepseek else 'OPENAI_API_KEY'} not set. Text parsing will not function.")
            self.llm_client = None
        else:
            # Explicitly pass api_key to ensure it's used (not environment variable)
            # The OpenAI client may read from environment variables if api_key is not explicitly set
            self.llm_client = AsyncOpenAI(
                base_url=self.llm_base_url,
                api_key=self.llm_api_key,  # Explicitly set to override any environment variable
                timeout=self.timeout
            )
            logger.debug(f"Initialized LLM client with API key prefix: {self.llm_api_key[:7]}...")
    
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
        Two-step process:
        1. Extract text using DeepSeek-OCR
        2. Parse text into structured JSON using LLM
        
        Args:
            file_content: Binary content of the file
            filename: Original filename
            
        Returns:
            Structured OCR data as dictionary
        """
        # Step 1: Extract text using OCR
        logger.info("Step 1: Extracting text using Azure Document Intelligence...")
        raw_text = await self._extract_text_ocr(file_content, filename)
        
        if not raw_text or not raw_text.strip():
            logger.warning("OCR extraction returned empty text")
            # Return minimal structure
            return self._create_fallback_response("OCR extraction returned no text")
        
        logger.info(f"OCR extraction successful. Extracted {len(raw_text)} characters.")
        logger.debug(f"Extracted text (first 500 chars): {raw_text[:500]}")
        
        # Step 2: Parse text into structured JSON using LLM
        logger.info("Step 2: Parsing text into structured JSON using LLM...")
        structured_data = await self._parse_text_llm(raw_text)
        
        return structured_data
    
    async def _extract_text_ocr(self, file_content: bytes, filename: str) -> str:
        """
        Step 1: Extract raw text from image/PDF using Azure Document Intelligence
        
        Returns:
            Raw extracted text as string
        """
        if not self.azure_client:
            raise Exception("Azure Document Intelligence credentials not configured. Set AZURE_DOC_INTELLIGENCE_ENDPOINT and AZURE_DOC_INTELLIGENCE_KEY.")
        
        # Determine content type
        file_ext = filename.lower().split('.')[-1] if '.' in filename else ''
        is_pdf = file_ext == 'pdf'
        content_type = ContentType.APPLICATION_PDF if is_pdf else ContentType.IMAGE_PNG
        
        # Azure Document Intelligence can handle PDFs directly, no conversion needed
        logger.info(f"Processing {file_ext.upper()} file with Azure Document Intelligence (model: {self.azure_model})")
        logger.info(f"File size: {len(file_content)} bytes")
        
        # Retry logic for OCR
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                logger.info(f"OCR extraction attempt {attempt + 1}/{self.max_retries}")
                
                # Analyze document with Azure Document Intelligence
                # The prebuilt-invoice model extracts structured data, but we'll get the raw text too
                poller = await self.azure_client.begin_analyze_document(
                    model_id=self.azure_model,  # "prebuilt-invoice"
                    analyze_request=file_content,
                    content_type=content_type
                )
                
                # Wait for the result
                result = await poller.result()
                
                logger.info(f"Azure Document Intelligence analysis completed")
                
                # Extract text from the result
                # Azure DI provides structured fields AND raw content
                text_parts = []
                
                # Get the main content (all text from the document)
                if hasattr(result, 'content') and result.content:
                    text_parts.append(result.content)
                    logger.debug(f"Extracted content from result.content: {len(result.content)} characters")
                
                # Also extract from pages if available (more detailed)
                if hasattr(result, 'pages') and result.pages:
                    for page_idx, page in enumerate(result.pages):
                        if hasattr(page, 'lines') and page.lines:
                            for line in page.lines:
                                if hasattr(line, 'content') and line.content:
                                    text_parts.append(line.content)
                    logger.debug(f"Extracted text from {len(result.pages)} pages")
                
                # Combine all text parts
                extracted_text = "\n".join(text_parts)
                
                if not extracted_text or not extracted_text.strip():
                    raise Exception("Azure Document Intelligence returned no text")
                
                # Validate extracted text - check for repetitive/garbled output
                if len(extracted_text) > 100:
                    words = extracted_text.split()
                    if len(words) > 20:
                        first_phrase = ' '.join(words[:5])
                        occurrences = extracted_text.count(first_phrase)
                        if occurrences > 10:
                            logger.warning(f"OCR output appears to be repetitive/garbled. Pattern '{first_phrase[:50]}...' appears {occurrences} times.")
                            logger.warning(f"First 500 chars of OCR output: {extracted_text[:500]}")
                
                logger.info(f"OCR extracted text length: {len(extracted_text)} characters")
                logger.debug(f"OCR extracted text (first 500 chars): {extracted_text[:500]}")
                
                return extracted_text
                
            except Exception as e:
                last_exception = e
                error_str = str(e)
                
                # Log full error details
                error_details = {
                    "error_type": type(e).__name__,
                    "error_message": error_str,
                    "error_repr": repr(e)
                }
                
                # Check for Azure-specific error attributes
                if hasattr(e, 'status_code'):
                    error_details["status_code"] = e.status_code
                if hasattr(e, 'message'):
                    error_details["azure_message"] = e.message
                if hasattr(e, 'error'):
                    error_details["azure_error"] = e.error
                
                # Check if it's a rate limit error (429 or timeout)
                is_rate_limit = (
                    "429" in error_str or 
                    "rate_limit" in error_str.lower() or 
                    "throttl" in error_str.lower() or
                    error_details.get('status_code') == 429
                )
                is_timeout = (
                    "timeout" in error_str.lower() or
                    "timed out" in error_str.lower()
                )
                
                # Log full error details
                logger.error(f"OCR extraction error (attempt {attempt + 1}/{self.max_retries}):")
                logger.error(f"  Error Type: {error_details.get('error_type')}")
                logger.error(f"  Error Message: {error_details.get('error_message')}")
                if error_details.get('status_code'):
                    logger.error(f"  Status Code: {error_details.get('status_code')}")
                
                # Add exponential backoff for rate limits and timeouts
                if (is_rate_limit or is_timeout) and attempt < self.max_retries - 1:
                    wait_time = min(2 ** attempt, 10)  # Cap at 10 seconds
                    logger.warning(f"Rate limit/timeout detected. Waiting {wait_time} seconds before retry {attempt + 1}/{self.max_retries}...")
                    await asyncio.sleep(wait_time)
                
                if attempt == self.max_retries - 1:
                    raise Exception(f"OCR extraction failed after {self.max_retries} attempts: {str(e)}")
        
        raise Exception(f"OCR extraction failed: {str(last_exception)}")
    
    async def _parse_text_llm(self, raw_text: str) -> Dict:
        """
        Step 2: Parse extracted text into structured JSON using LLM
        
        Args:
            raw_text: Raw text extracted from OCR
            
        Returns:
            Structured invoice data as dictionary
        """
        if not self.llm_client:
            raise Exception(f"{'DEEPSEEK_API_KEY' if self.use_deepseek else 'OPENAI_API_KEY'} is not configured")
        
        # System prompt for structured data extraction
        system_prompt = """You are a data extraction specialist. Extract structured data from invoice or purchase order text and return it as valid JSON.

Extract the following information and return ONLY valid JSON (no markdown, no code blocks, just the JSON object):
{
  "vendor_name": "Name of the vendor/company or null",
  "invoice_number": "Invoice number or ID or null",
  "po_number": "Purchase order number if present or null",
  "invoice_date": "Date of the invoice in YYYY-MM-DD format or null",
  "total_amount": numeric_value_or_null,
  "currency": "Currency code like USD, EUR, etc. or null",
  "line_items": [
    {
      "line_no": number,
      "sku": "SKU or product code or null",
      "description": "Item description",
      "quantity": numeric_value_or_null,
      "unit_price": numeric_value_or_null
    }
  ]
}

IMPORTANT: 
- Return ONLY the JSON object, nothing else
- Use null for missing values (not empty strings)
- For invoice_date: Extract the EXACT date from the document text. If you see "Date: 07/07/2022", convert it to YYYY-MM-DD format as "2022-07-07" (assuming MM/DD/YYYY format). Do NOT change the date value, only reformat it to YYYY-MM-DD.
- Extract numeric values as numbers, not strings"""
        
        user_message = f"""Extract structured invoice data from the following text and return it as a JSON object:

{raw_text}

Return only the JSON object with no additional text or formatting."""
        
        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_message
            }
        ]
        
        # Retry logic for LLM parsing with exponential backoff
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"LLM parsing attempt {attempt + 1}/{self.max_retries}")
                
                response = await self.llm_client.chat.completions.create(
                    model=self.llm_model,
                    messages=messages,
                    temperature=0.1,  # Low temperature for consistent extraction
                    timeout=self.timeout,
                    # Removed max_tokens to allow full response - better for complex invoices
                    response_format={"type": "json_object"} if not self.use_deepseek else None  # OpenAI supports JSON mode
                )
                
                # Extract JSON from response
                if not response.choices or len(response.choices) == 0:
                    raise Exception("LLM API response has no choices")
                
                if not response.choices[0].message:
                    raise Exception("LLM API response choice has no message")
                
                content = response.choices[0].message.content
                
                if content is None:
                    raise Exception("LLM API response message content is None")
                
                logger.debug(f"LLM response (first 500 chars): {content[:500]}")
                
                # Parse JSON response
                parsed_data = self._parse_json_response(content, response)
                
                return parsed_data
                
            except Exception as e:
                error_str = str(e)
                last_exception = e
                
                # Log full error details
                error_details = {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "error_repr": repr(e)
                }
                
                # Try to extract full error object and headers from OpenAI SDK exceptions
                if hasattr(e, 'response'):
                    # OpenAI SDK error with response object
                    error_details["has_response"] = True
                    if hasattr(e.response, 'headers'):
                        headers = dict(e.response.headers)
                        error_details["response_headers"] = headers
                        # Log rate limit headers specifically
                        rate_limit_headers = {k: v for k, v in headers.items() if 'ratelimit' in k.lower()}
                        if rate_limit_headers:
                            error_details["rate_limit_headers"] = rate_limit_headers
                    
                    if hasattr(e.response, 'status_code'):
                        error_details["status_code"] = e.response.status_code
                    
                    if hasattr(e.response, 'json'):
                        try:
                            error_body = e.response.json()
                            error_details["response_body"] = error_body
                        except:
                            if hasattr(e.response, 'text'):
                                error_details["response_text"] = e.response.text
                
                # Check for OpenAI APIError attributes
                if hasattr(e, 'body'):
                    error_details["error_body"] = e.body
                
                if hasattr(e, 'code'):
                    error_details["error_code"] = e.code
                
                if hasattr(e, 'param'):
                    error_details["error_param"] = e.param
                
                if hasattr(e, 'type'):
                    error_details["error_type_field"] = e.type
                
                # Log full error details
                logger.error(f"LLM parsing error (attempt {attempt + 1}/{self.max_retries}):")
                logger.error(f"  Error Type: {error_details.get('error_type')}")
                logger.error(f"  Error Message: {error_details.get('error_message')}")
                if error_details.get('status_code'):
                    logger.error(f"  Status Code: {error_details.get('status_code')}")
                if error_details.get('error_code'):
                    logger.error(f"  Error Code: {error_details.get('error_code')}")
                if error_details.get('error_type_field'):
                    logger.error(f"  Error Type Field: {error_details.get('error_type_field')}")
                if error_details.get('rate_limit_headers'):
                    logger.error(f"  Rate Limit Headers: {error_details.get('rate_limit_headers')}")
                if error_details.get('response_headers'):
                    logger.error(f"  All Response Headers: {error_details.get('response_headers')}")
                if error_details.get('response_body'):
                    logger.error(f"  Response Body: {error_details.get('response_body')}")
                if error_details.get('error_body'):
                    logger.error(f"  Error Body: {error_details.get('error_body')}")
                
                # Check if it's a rate limit error (429 or quota-related)
                is_rate_limit = (
                    "429" in error_str or 
                    "rate_limit" in error_str.lower() or 
                    "quota" in error_str.lower() or
                    "insufficient_quota" in error_str.lower() or
                    error_details.get('status_code') == 429 or
                    error_details.get('error_code') == 'insufficient_quota' or
                    error_details.get('error_type_field') == 'insufficient_quota'
                )
                
                if is_rate_limit and attempt < self.max_retries - 1:
                    # Exponential backoff: wait 2^attempt seconds (1s, 2s, 4s)
                    wait_time = min(2 ** attempt, 10)  # Cap at 10 seconds
                    logger.warning(f"Rate limit detected. Waiting {wait_time} seconds before retry {attempt + 1}/{self.max_retries}...")
                    await asyncio.sleep(wait_time)
                
                if attempt == self.max_retries - 1:
                    # Fallback to regex extraction
                    logger.warning("LLM parsing failed after all retries, falling back to regex extraction")
                    return self._fallback_regex_extraction(raw_text)
    
    def _parse_json_response(self, content: str, raw_response) -> Dict:
        """
        Parse JSON from LLM response, handling markdown code blocks if present
        """
        # Try to extract JSON from markdown code blocks
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
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from LLM response: {e}")
            logger.debug(f"Content that failed to parse: {content[:1000]}")
            # Return empty structure
            ocr_data = {}
        
        # Convert OpenAI response object to dict for storage
        raw_response_dict = {
            "id": raw_response.id if hasattr(raw_response, 'id') else None,
            "model": raw_response.model if hasattr(raw_response, 'model') else None,
            "choices": [
                {
                    "message": {
                        "content": raw_response.choices[0].message.content if raw_response.choices else ""
                    }
                }
            ] if raw_response.choices else []
        }
        
        return self._normalize_ocr_response(ocr_data, raw_response_dict)
    
    def _fallback_regex_extraction(self, text: str) -> Dict:
        """Fallback: Extract invoice fields using regex if LLM parsing fails"""
        logger.info("Using regex fallback extraction")
        data = self._extract_fields_with_regex(text)
        
        return self._normalize_ocr_response(data, {"fallback": True, "raw_text": text[:1000]})
    
    def _extract_fields_with_regex(self, text: str) -> Dict:
        """Extract invoice fields using regex patterns"""
        data = {}
        
        # Extract vendor name
        vendor_match = re.search(r'(?:vendor|company|supplier|from)[\s:]+([^\n,]+)', text, re.IGNORECASE)
        if vendor_match:
            data['vendor_name'] = vendor_match.group(1).strip()
        
        # Extract invoice number
        invoice_match = re.search(r'(?:invoice\s*(?:number|#|no\.?))[\s:]+([^\n,]+)', text, re.IGNORECASE)
        if invoice_match:
            data['invoice_number'] = invoice_match.group(1).strip()
        
        # Extract PO number
        po_match = re.search(r'(?:po\s*(?:number|#|no\.?)|purchase\s*order\s*(?:number|#|no\.?))[\s:]+([^\n,]+)', text, re.IGNORECASE)
        if po_match:
            data['po_number'] = po_match.group(1).strip()
        
        # Extract invoice date
        date_match = re.search(r'(?:invoice\s*date|date\s*issued|date)[\s:]+([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})', text, re.IGNORECASE)
        if date_match:
            data['invoice_date'] = date_match.group(1).strip()
        
        # Extract total amount
        total_match = re.search(r'(?:total|amount\s*(?:due|owed)?)[\s:]+[\$]?([\d,]+\.?\d*)', text, re.IGNORECASE)
        if total_match:
            data['total_amount'] = total_match.group(1).replace(',', '')
        
        # Extract currency
        currency_match = re.search(r'(?:currency)[\s:]+([A-Z]{3})', text, re.IGNORECASE)
        if currency_match:
            data['currency'] = currency_match.group(1)
        else:
            data['currency'] = 'USD'
        
        return data
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[str]:
        """
        Parse and normalize date string to YYYY-MM-DD format
        
        Handles various date formats:
        - MM/DD/YYYY (e.g., "07/07/2022")
        - DD/MM/YYYY (e.g., "07/07/2022" - ambiguous, assumes MM/DD/YYYY)
        - YYYY-MM-DD (e.g., "2022-07-07")
        - YYYY/MM/DD (e.g., "2022/07/07")
        """
        if not date_str:
            return None
        
        date_str = date_str.strip()
        
        # If already in YYYY-MM-DD format, return as-is
        if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            return date_str
        
        try:
            from datetime import datetime
            
            # Try common date formats
            formats = [
                '%m/%d/%Y',  # MM/DD/YYYY (US format)
                '%d/%m/%Y',  # DD/MM/YYYY (European format)
                '%Y/%m/%d',  # YYYY/MM/DD
                '%m-%d-%Y',  # MM-DD-YYYY
                '%d-%m-%Y',  # DD-MM-YYYY
                '%Y-%m-%d',  # YYYY-MM-DD (already handled above, but just in case)
            ]
            
            for fmt in formats:
                try:
                    parsed_date = datetime.strptime(date_str, fmt)
                    # Return in YYYY-MM-DD format
                    return parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                    continue
            
            logger.warning(f"Could not parse date format: {date_str}")
            return None
        except Exception as e:
            logger.error(f"Error parsing date {date_str}: {str(e)}")
            return None
    
    def _normalize_ocr_response(self, ocr_data: Dict, raw_response: Dict) -> Dict:
        """
        Normalize OCR response to our expected format
        """
        # Parse and normalize the invoice date
        raw_date = ocr_data.get("invoice_date")
        normalized_date = self._parse_date(raw_date)
        
        # Log date parsing for debugging
        if raw_date:
            logger.info(f"Date parsing: raw='{raw_date}' -> normalized='{normalized_date}'")
        
        normalized = {
            "vendor_name": ocr_data.get("vendor_name"),
            "invoice_number": ocr_data.get("invoice_number"),
            "po_number": ocr_data.get("po_number"),
            "invoice_date": normalized_date,  # Use normalized date
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
    
    def _create_fallback_response(self, error_msg: str) -> Dict:
        """Create a minimal response structure when OCR fails"""
        return {
            "vendor_name": None,
            "invoice_number": None,
            "po_number": None,
            "invoice_date": None,
            "total_amount": None,
            "currency": "USD",
            "line_items": [],
            "raw_ocr": {
                "error": error_msg,
                "fallback": True
            }
        }


ocr_service = OCRService()
