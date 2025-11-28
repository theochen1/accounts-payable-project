"""
Hybrid OCR Service - Gemini Primary + GPT-4o Validator

This service implements a robust two-model approach for document OCR:
1. Primary extraction with Gemini 1.5 Pro (excellent multimodal capabilities, cost-effective)
2. Validation and correction with GPT-4o (strong reasoning, catches edge cases)

The hybrid approach only calls GPT-4o when validation issues are detected,
keeping costs low while maximizing accuracy.
"""

import asyncio
import base64
import json
import logging
import re
from typing import Dict, List, Optional, Tuple
from decimal import Decimal

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


class HybridOCRService:
    """
    Hybrid OCR service using Gemini for primary extraction 
    and GPT-4o for validation/correction
    """
    
    def __init__(self):
        # Gemini client (primary extraction)
        self.gemini_api_key = settings.gemini_api_key
        self.gemini_model_name = settings.gemini_model
        self.gemini_model = None
        
        if self.gemini_api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_api_key)
                self.gemini_model = genai.GenerativeModel(self.gemini_model_name)
                logger.info(f"Initialized Gemini {self.gemini_model_name} for primary OCR")
            except ImportError:
                logger.warning("google-generativeai not installed. Gemini OCR disabled.")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")
        else:
            logger.warning("GEMINI_API_KEY not set. Gemini OCR disabled.")
        
        # OpenAI GPT-4o client (validation + fallback)
        self.openai_api_key = settings.openai_api_key
        if self.openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=self.openai_api_key)
            self.openai_model = "gpt-4o"  # Vision-capable model
            logger.info("Initialized GPT-4o for OCR validation")
        else:
            self.openai_client = None
            logger.warning("OPENAI_API_KEY not set. GPT-4o validation disabled.")
        
        # Validation thresholds from config
        self.suspicious_qty_threshold = settings.ocr_suspicious_qty_threshold
        self.suspicious_price_threshold = settings.ocr_suspicious_price_threshold
        self.line_total_tolerance = settings.ocr_line_total_tolerance
        self.validation_confidence_threshold = settings.ocr_validation_threshold
        
        # Timeouts and retries
        self.timeout = settings.ocr_timeout_seconds
        self.max_retries = settings.ocr_max_retries
    
    async def process_file(self, file_content: bytes, filename: str) -> Dict:
        """
        Process document with hybrid Gemini + GPT-4o approach
        
        Flow:
        1. Try Gemini extraction first (cost-effective, good accuracy)
        2. Validate Gemini's result
        3. If validation issues, use GPT-4o to verify/correct
        4. If Gemini fails entirely, fall back to GPT-4o direct extraction
        """
        logger.info(f"Processing {filename} with hybrid OCR (provider: {settings.ocr_provider})")
        
        # Check which provider to use
        if settings.ocr_provider == "gpt4o":
            # Direct GPT-4o extraction
            logger.info("Using GPT-4o direct extraction (provider=gpt4o)")
            return await self._extract_with_gpt4o(file_content, filename)
        
        if settings.ocr_provider == "gemini":
            # Direct Gemini extraction (no validation)
            logger.info("Using Gemini direct extraction (provider=gemini)")
            result = await self._extract_with_gemini(file_content, filename)
            if result:
                result['extraction_source'] = 'gemini_direct'
                return result
            # Fall back to GPT-4o if Gemini fails
            logger.warning("Gemini extraction failed, falling back to GPT-4o")
            return await self._extract_with_gpt4o(file_content, filename)
        
        # Hybrid mode (default or provider=hybrid)
        # Step 1: Primary extraction with Gemini
        if self.gemini_model:
            logger.info("Step 1: Extracting with Gemini 1.5 Pro...")
            gemini_result = await self._extract_with_gemini(file_content, filename)
            
            if gemini_result and (gemini_result.get('vendor_name') or gemini_result.get('invoice_number')):
                # Step 2: Validate Gemini's result
                validation_issues = self._validate_extraction(gemini_result)
                
                if not validation_issues:
                    # No issues - return Gemini result
                    logger.info("Gemini extraction validated successfully - no issues detected")
                    gemini_result['extraction_source'] = 'gemini_primary'
                    gemini_result['raw_ocr'] = {
                        'source': 'gemini',
                        'model': self.gemini_model_name,
                        'validated': True,
                        'validation_issues': []
                    }
                    return gemini_result
                
                # Step 3: GPT-4o validation/correction
                if self.openai_client:
                    logger.info(f"Validation issues detected: {len(validation_issues)} issues")
                    for issue in validation_issues:
                        logger.info(f"  - {issue.get('message', issue)}")
                    
                    logger.info("Step 2: Validating with GPT-4o...")
                    corrected_result = await self._validate_with_gpt4o(
                        file_content, 
                        filename, 
                        gemini_result, 
                        validation_issues
                    )
                    
                    if corrected_result:
                        corrected_result['extraction_source'] = 'gemini_gpt4o_hybrid'
                        corrected_result['raw_ocr'] = {
                            'source': 'hybrid',
                            'primary_model': self.gemini_model_name,
                            'validation_model': 'gpt-4o',
                            'validation_issues_detected': validation_issues,
                            'corrected': True
                        }
                        return corrected_result
                else:
                    # No GPT-4o available, return Gemini result with warnings
                    logger.warning("GPT-4o not available for validation. Returning Gemini result with issues.")
                    gemini_result['extraction_source'] = 'gemini_unvalidated'
                    gemini_result['validation_issues'] = validation_issues
                    return gemini_result
            else:
                logger.warning("Gemini extraction returned incomplete data")
        else:
            logger.info("Gemini not available, using GPT-4o directly")
        
        # Fallback: Direct GPT-4o extraction
        if self.openai_client:
            logger.info("Using GPT-4o direct extraction as fallback")
            return await self._extract_with_gpt4o(file_content, filename)
        
        # No OCR providers available
        logger.error("No OCR providers available (neither Gemini nor GPT-4o)")
        return self._create_fallback_response("No OCR providers configured")
    
    async def _extract_with_gemini(self, file_content: bytes, filename: str) -> Optional[Dict]:
        """
        Extract structured data using Gemini 1.5 Pro Vision
        """
        if not self.gemini_model:
            return None
        
        try:
            import google.generativeai as genai
            
            # Prepare image for Gemini
            base64_image = base64.b64encode(file_content).decode('utf-8')
            mime_type = self._get_mime_type(filename)
            
            # Structured extraction prompt
            prompt = """Analyze this invoice or purchase order document and extract all data.

Return a JSON object with EXACTLY this structure:
{
    "vendor_name": "string or null",
    "invoice_number": "string or null",
    "po_number": "string or null", 
    "invoice_date": "YYYY-MM-DD format or null",
    "total_amount": number or null,
    "currency": "USD/EUR/GBP/etc or null",
    "line_items": [
        {
            "line_no": number,
            "sku": "string or null",
            "description": "string",
            "quantity": number,
            "unit_price": number
        }
    ],
    "confidence": {
        "vendor_name": 0.0-1.0,
        "invoice_number": 0.0-1.0,
        "total_amount": 0.0-1.0,
        "line_items": 0.0-1.0
    }
}

CRITICAL INSTRUCTIONS:
1. READ NUMBERS CAREFULLY:
   - Don't confuse decimal separators (.) with thousands separators (,)
   - "1,000.00" = one thousand, "1.000,00" (European) = one thousand
   - A unit price of "45,000.00" for a single item is likely $45,000.00 not $45.00

2. VERIFY LINE ITEM MATH:
   - quantity × unit_price should approximately equal the line total
   - If the math doesn't work, re-read the numbers

3. CONFIDENCE SCORING:
   - Set confidence score lower (< 0.7) if a value is unclear or you're uncertain
   - Set confidence score high (> 0.9) if clearly visible and readable

4. DATES:
   - Convert all dates to YYYY-MM-DD format
   - "07/15/2024" becomes "2024-07-15"

Return ONLY the JSON object, no markdown code blocks, no explanation."""

            # For PDFs, we need to handle them differently
            if mime_type == 'application/pdf':
                # Gemini can handle PDFs directly with the File API
                # For simplicity, we'll use base64 encoding which works for images
                # For production, consider using Gemini's File API for PDFs
                logger.info("Processing PDF with Gemini...")
            
            # Call Gemini with retry logic
            last_exception = None
            for attempt in range(self.max_retries):
                try:
                    logger.info(f"Gemini extraction attempt {attempt + 1}/{self.max_retries}")
                    
                    # Create the image part
                    image_part = {
                        "mime_type": mime_type,
                        "data": base64_image
                    }
                    
                    response = self.gemini_model.generate_content(
                        [prompt, image_part],
                        generation_config={
                            "temperature": 0.1,
                            "max_output_tokens": 4096,
                        }
                    )
                    
                    # Parse response
                    if response and response.text:
                        result = self._parse_json_response(response.text)
                        
                        if result:
                            logger.info(f"Gemini extracted: vendor={result.get('vendor_name')}, "
                                       f"invoice={result.get('invoice_number')}, "
                                       f"total={result.get('total_amount')}, "
                                       f"lines={len(result.get('line_items', []))}")
                            return result
                    
                    logger.warning(f"Gemini returned empty or invalid response on attempt {attempt + 1}")
                    
                except Exception as e:
                    last_exception = e
                    logger.warning(f"Gemini attempt {attempt + 1} failed: {str(e)}")
                    
                    # Exponential backoff for rate limits
                    if "429" in str(e) or "quota" in str(e).lower():
                        wait_time = min(2 ** attempt, 10)
                        logger.info(f"Rate limit detected, waiting {wait_time}s...")
                        await asyncio.sleep(wait_time)
            
            logger.error(f"Gemini extraction failed after {self.max_retries} attempts: {last_exception}")
            return None
            
        except Exception as e:
            logger.error(f"Gemini extraction error: {str(e)}")
            return None
    
    async def _extract_with_gpt4o(self, file_content: bytes, filename: str) -> Dict:
        """
        Direct extraction with GPT-4o Vision (fallback when Gemini fails)
        """
        if not self.openai_client:
            return self._create_fallback_response("OpenAI API key not configured")
        
        base64_image = base64.b64encode(file_content).decode('utf-8')
        mime_type = self._get_mime_type(filename)
        
        prompt = """Extract all data from this invoice or purchase order document.

Return a JSON object with this structure:
{
    "vendor_name": "string or null",
    "invoice_number": "string or null",
    "po_number": "string or null",
    "invoice_date": "YYYY-MM-DD or null",
    "total_amount": number or null,
    "currency": "USD/EUR/GBP/etc",
    "line_items": [
        {
            "line_no": number,
            "sku": "string or null",
            "description": "string",
            "quantity": number,
            "unit_price": number
        }
    ]
}

IMPORTANT INSTRUCTIONS:
1. Read numbers very carefully - don't confuse decimal and thousands separators
2. Verify: quantity × unit_price should approximately equal line total
3. Convert dates to YYYY-MM-DD format
4. Use null for missing values, not empty strings

Return ONLY the JSON object, no markdown, no explanation."""

        last_exception = None
        for attempt in range(self.max_retries):
            try:
                logger.info(f"GPT-4o extraction attempt {attempt + 1}/{self.max_retries}")
                
                response = await self.openai_client.chat.completions.create(
                    model=self.openai_model,
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
                    temperature=0.1,
                    timeout=self.timeout
                )
                
                if response.choices and response.choices[0].message.content:
                    result = self._parse_json_response(response.choices[0].message.content)
                    result['extraction_source'] = 'gpt4o_direct'
                    result['raw_ocr'] = {
                        'source': 'gpt-4o',
                        'model': self.openai_model,
                        'direct_extraction': True
                    }
                    
                    logger.info(f"GPT-4o extracted: vendor={result.get('vendor_name')}, "
                               f"invoice={result.get('invoice_number')}, "
                               f"total={result.get('total_amount')}")
                    return result
                
            except Exception as e:
                last_exception = e
                logger.warning(f"GPT-4o attempt {attempt + 1} failed: {str(e)}")
                
                if "429" in str(e) or "rate" in str(e).lower():
                    wait_time = min(2 ** attempt, 10)
                    await asyncio.sleep(wait_time)
        
        logger.error(f"GPT-4o extraction failed: {last_exception}")
        return self._create_fallback_response(f"GPT-4o extraction failed: {last_exception}")
    
    async def _validate_with_gpt4o(
        self, 
        file_content: bytes, 
        filename: str, 
        gemini_result: Dict,
        issues: List[Dict]
    ) -> Optional[Dict]:
        """
        Use GPT-4o to validate and correct Gemini's extraction
        """
        if not self.openai_client:
            return None
        
        base64_image = base64.b64encode(file_content).decode('utf-8')
        mime_type = self._get_mime_type(filename)
        
        # Remove confidence and raw_ocr from the data we send to GPT-4o
        data_to_validate = {k: v for k, v in gemini_result.items() 
                          if k not in ['confidence', 'raw_ocr', 'extraction_source']}
        
        # Build validation prompt
        prompt = f"""I extracted this data from an invoice/PO document using OCR, but there may be errors.

EXTRACTED DATA:
{json.dumps(data_to_validate, indent=2, default=str)}

DETECTED ISSUES:
{json.dumps(issues, indent=2)}

Please look at the original document image and:
1. VERIFY each field against the actual document
2. CORRECT any values that appear wrong
3. Pay special attention to:
   - Line item quantities and unit prices (check the math: qty × price ≈ line total)
   - The total amount
   - Number formatting (is 45,000 forty-five thousand or forty-five with European decimals?)

Return the CORRECTED JSON in the same format:
{{
    "vendor_name": "string or null",
    "invoice_number": "string or null", 
    "po_number": "string or null",
    "invoice_date": "YYYY-MM-DD or null",
    "total_amount": number or null,
    "currency": "USD/EUR/etc",
    "line_items": [...]
}}

If a value was correct, keep it unchanged.
Return ONLY the JSON, no explanation or markdown."""

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.openai_model,
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
                temperature=0.1,
                timeout=self.timeout
            )
            
            if response.choices and response.choices[0].message.content:
                result = self._parse_json_response(response.choices[0].message.content)
                logger.info(f"GPT-4o validation result: vendor={result.get('vendor_name')}, "
                           f"total={result.get('total_amount')}")
                return result
            
        except Exception as e:
            logger.error(f"GPT-4o validation failed: {str(e)}")
        
        return None
    
    def _validate_extraction(self, data: Dict) -> List[Dict]:
        """
        Validate extracted data and return list of issues
        
        Checks for:
        1. Suspicious quantities (unusually high)
        2. Suspicious unit prices (unusually high)
        3. Line items total doesn't match invoice total
        4. Low confidence scores from Gemini
        """
        issues = []
        
        line_items = data.get('line_items', [])
        
        # Check for suspicious quantities and prices
        for idx, item in enumerate(line_items):
            qty = item.get('quantity')
            price = item.get('unit_price')
            
            if qty is not None and qty > self.suspicious_qty_threshold:
                issues.append({
                    "type": "suspicious_quantity",
                    "line": idx + 1,
                    "value": qty,
                    "threshold": self.suspicious_qty_threshold,
                    "message": f"Line {idx+1} quantity {qty:,.0f} seems unusually high (threshold: {self.suspicious_qty_threshold:,})"
                })
            
            if price is not None and price > self.suspicious_price_threshold:
                issues.append({
                    "type": "suspicious_price",
                    "line": idx + 1,
                    "value": price,
                    "threshold": self.suspicious_price_threshold,
                    "message": f"Line {idx+1} unit price ${price:,.2f} seems unusually high (threshold: ${self.suspicious_price_threshold:,})"
                })
            
            # Check if quantity * price math seems reasonable
            if qty is not None and price is not None and qty > 0 and price > 0:
                line_total = qty * price
                # If line total is extremely high (> $1M), flag it
                if line_total > 1000000:
                    issues.append({
                        "type": "suspicious_line_total",
                        "line": idx + 1,
                        "calculated_total": line_total,
                        "quantity": qty,
                        "unit_price": price,
                        "message": f"Line {idx+1} total ${line_total:,.2f} (qty={qty:,.0f} × price=${price:,.2f}) is very high"
                    })
        
        # Check if line items sum to total
        total = data.get('total_amount')
        if total and line_items:
            calculated_total = sum(
                (item.get('quantity') or 0) * (item.get('unit_price') or 0)
                for item in line_items
            )
            if calculated_total > 0:
                variance = abs(total - calculated_total) / max(total, calculated_total)
                if variance > self.line_total_tolerance:
                    issues.append({
                        "type": "total_mismatch",
                        "expected": total,
                        "calculated": calculated_total,
                        "variance_pct": variance * 100,
                        "tolerance_pct": self.line_total_tolerance * 100,
                        "message": f"Line items total ${calculated_total:,.2f} differs from invoice total ${total:,.2f} by {variance*100:.1f}%"
                    })
        
        # Check confidence scores (if Gemini provided them)
        confidence = data.get('confidence', {})
        for field, score in confidence.items():
            if score is not None and score < self.validation_confidence_threshold:
                issues.append({
                    "type": "low_confidence",
                    "field": field,
                    "confidence": score,
                    "threshold": self.validation_confidence_threshold,
                    "message": f"Low confidence ({score:.0%}) for field '{field}' (threshold: {self.validation_confidence_threshold:.0%})"
                })
        
        # Check for missing critical fields
        if not data.get('vendor_name'):
            issues.append({
                "type": "missing_field",
                "field": "vendor_name",
                "message": "Vendor name is missing"
            })
        
        if not data.get('total_amount'):
            issues.append({
                "type": "missing_field", 
                "field": "total_amount",
                "message": "Total amount is missing"
            })
        
        return issues
    
    def _parse_json_response(self, content: str) -> Dict:
        """Parse JSON from LLM response, handling various formats"""
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
            logger.error(f"Failed to parse JSON: {e}")
            logger.debug(f"Content that failed to parse: {content[:500]}")
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
            "extraction_source": "fallback",
            "raw_ocr": {
                "error": error_msg,
                "fallback": True
            }
        }


# Singleton instance
hybrid_ocr_service = HybridOCRService()

