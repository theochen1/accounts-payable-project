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

logger = logging.getLogger(__name__)


class OCRService:
    """
    Two-step OCR service:
    1. Extract text using DeepSeek-OCR (via Clarifai)
    2. Parse text into structured JSON using OpenAI or DeepSeek chat API
    """
    
    def __init__(self):
        # Step 1: OCR client (Clarifai)
        self.ocr_base_url = settings.clarifai_base_url
        self.ocr_api_key = settings.clarifai_pat or os.environ.get("CLARIFAI_PAT")
        self.ocr_model_url = settings.clarifai_model_url
        
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
        
        # Initialize OCR client (Clarifai)
        if not self.ocr_api_key:
            logger.warning("CLARIFAI_PAT not set. OCR extraction will not function.")
            self.ocr_client = None
        else:
            # Log API key format for debugging (first few chars only)
            logger.info(f"Initializing Clarifai OCR client with API key prefix: {self.ocr_api_key[:10]}...")
            logger.info(f"Clarifai base URL: {self.ocr_base_url}")
            logger.info(f"Clarifai model URL: {self.ocr_model_url}")
            self.ocr_client = AsyncOpenAI(
                base_url=self.ocr_base_url,
                api_key=self.ocr_api_key,
                timeout=self.timeout
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
        logger.info("Step 1: Extracting text using DeepSeek-OCR...")
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
        Step 1: Extract raw text from image/PDF using DeepSeek-OCR
        
        Returns:
            Raw extracted text as string
        """
        if not self.ocr_client:
            raise Exception("Clarifai PAT (CLARIFAI_PAT) is not configured")
        
        # Check if file is PDF
        file_ext = filename.lower().split('.')[-1] if '.' in filename else ''
        is_pdf = file_ext == 'pdf'
        
        # If PDF, convert to image first (Clarifai OCR can't process PDFs directly)
        if is_pdf:
            logger.info("Processing PDF file. Converting PDF to image...")
            try:
                # Convert PDF to images (first page only for now)
                images = convert_from_bytes(file_content, first_page=1, last_page=1, dpi=300)
                if not images:
                    raise Exception("PDF conversion produced no images")
                
                # Convert first page to bytes
                img_buffer = BytesIO()
                images[0].save(img_buffer, format='PNG')
                file_content = img_buffer.getvalue()
                filename = filename.replace('.pdf', '.png')  # Update extension for content type
                logger.info(f"PDF converted to image. Image size: {len(file_content)} bytes")
            except Exception as e:
                logger.error(f"Failed to convert PDF to image: {str(e)}")
                raise Exception(f"PDF to image conversion failed: {str(e)}")
        
        # Create the image data URL
        image_data_url = self._get_data_url(file_content, filename)
        
        # Simple prompt for OCR - just extract text
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Extract all text from this document. Return only the extracted text, preserving the original formatting and structure."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_data_url
                        }
                    }
                ]
            }
        ]
        
        # Retry logic for OCR
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                logger.info(f"OCR extraction attempt {attempt + 1}/{self.max_retries}")
                logger.info(f"Using model URL: {self.ocr_model_url}")
                logger.info(f"Messages: {len(messages)} message(s)")
                
                # Use the model URL as-is since it works locally
                # Clarifai's OpenAI-compatible API accepts the full model URL
                response = await self.ocr_client.chat.completions.create(
                    model=self.ocr_model_url,
                    messages=messages,
                    temperature=0.0,  # Deterministic OCR output
                    timeout=self.timeout
                )
                
                logger.debug(f"OCR API call completed. Response received.")
                
                # Log response structure for debugging (always log, not just on error)
                logger.info(f"OCR API response type: {type(response)}")
                logger.info(f"OCR API response has 'choices' attribute: {hasattr(response, 'choices')}")
                
                if hasattr(response, 'choices'):
                    logger.info(f"OCR API response.choices type: {type(response.choices)}")
                    logger.info(f"OCR API response.choices value: {response.choices}")
                    logger.info(f"OCR API response.choices length: {len(response.choices) if response.choices else 0}")
                    if response.choices and len(response.choices) > 0:
                        logger.info(f"OCR API response.choices[0]: {response.choices[0]}")
                        if hasattr(response.choices[0], 'message'):
                            logger.info(f"OCR API response.choices[0].message: {response.choices[0].message}")
                else:
                    # Log detailed response info when choices is missing
                    logger.error(f"OCR API response has no 'choices' attribute")
                    logger.error(f"Response type: {type(response)}")
                    if hasattr(response, '__dict__'):
                        logger.error(f"Response attributes: {list(response.__dict__.keys())}")
                        logger.error(f"Response dict: {response.__dict__}")
                
                # Also log other response attributes that might be useful
                if hasattr(response, 'id'):
                    logger.info(f"OCR API response.id: {response.id}")
                if hasattr(response, 'model'):
                    logger.info(f"OCR API response.model: {response.model}")
                if hasattr(response, 'object'):
                    logger.info(f"OCR API response.object: {response.object}")
                
                # Log the model URL being used
                logger.info(f"OCR model URL used: {self.ocr_model_url}")
                
                # Check if there's an error in the response
                if hasattr(response, 'error'):
                    logger.error(f"OCR API response has error: {response.error}")
                if hasattr(response, 'usage'):
                    logger.info(f"OCR API response usage: {response.usage}")
                
                # Log all response attributes to see what we have
                logger.info(f"OCR API response all attributes: {[attr for attr in dir(response) if not attr.startswith('_')]}")
                
                # Try to serialize response to see its structure
                try:
                    import json
                    # Try to convert response to dict
                    if hasattr(response, 'model_dump'):
                        response_dict = response.model_dump()
                        logger.info(f"OCR API response as dict: {json.dumps(response_dict, indent=2, default=str)[:1000]}")
                    elif hasattr(response, 'dict'):
                        response_dict = response.dict()
                        logger.info(f"OCR API response as dict: {json.dumps(response_dict, indent=2, default=str)[:1000]}")
                except Exception as e:
                    logger.debug(f"Could not serialize response: {e}")
                
                # Extract text from response
                if not hasattr(response, 'choices') or not response.choices or len(response.choices) == 0:
                    error_msg = "OCR API response has no choices"
                    logger.error(f"{error_msg}. This usually means the API returned an unexpected response structure.")
                    logger.error(f"Full response details logged above. Check response structure.")
                    raise Exception(error_msg)
                
                if not response.choices[0].message:
                    raise Exception("OCR API response choice has no message")
                
                extracted_text = response.choices[0].message.content
                
                if extracted_text is None:
                    raise Exception("OCR API response message content is None")
                
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
                
                # Check if it's a rate limit error (429 or timeout)
                is_rate_limit = (
                    "429" in error_str or 
                    "rate_limit" in error_str.lower() or 
                    error_details.get('status_code') == 429
                )
                is_timeout = (
                    "timeout" in error_str.lower() or
                    "APITimeoutError" in error_str
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
- Extract dates in YYYY-MM-DD format if possible
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
    
    def _normalize_ocr_response(self, ocr_data: Dict, raw_response: Dict) -> Dict:
        """
        Normalize OCR response to our expected format
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
