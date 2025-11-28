"""
Intelligent Vendor Matching Service

Uses LLM reasoning to correctly identify and match vendors from invoice data.
Handles common OCR issues like:
- Confusing "bill to" with vendor (sender)
- Vendor name format differences
- Multiple company names on invoice
- Abbreviations and variations (Inc, LLC, Corp, etc.)
"""

import logging
import json
import difflib
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from openai import AsyncOpenAI
from app.config import settings
from app.models.vendor import Vendor

logger = logging.getLogger(__name__)


class VendorMatchingService:
    """
    Intelligent vendor matching using fuzzy matching + LLM reasoning
    """
    
    def __init__(self):
        self.openai_client = None
        if settings.openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        
        # Gemini for vendor matching (optional)
        self.gemini_model = None
        if settings.gemini_api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.gemini_api_key)
                self.gemini_model = genai.GenerativeModel(settings.gemini_model)
            except ImportError:
                pass
    
    async def match_vendor(
        self, 
        ocr_data: Dict,
        db: Session,
        file_content: Optional[bytes] = None,
        filename: Optional[str] = None
    ) -> Dict:
        """
        Intelligently match the vendor from OCR data to existing vendors.
        
        Args:
            ocr_data: OCR extraction result containing vendor_name and other fields
            db: Database session
            file_content: Original file bytes (for image-based LLM verification)
            filename: Original filename
            
        Returns:
            Dict with:
                - vendor_id: Matched vendor ID or None
                - vendor_name: Matched vendor name or extracted name
                - confidence: Match confidence (0-1)
                - match_type: 'exact', 'fuzzy', 'llm_matched', 'llm_created', 'unmatched'
                - reasoning: Explanation of the match
                - suggested_vendor: If unmatched, suggested vendor to create
        """
        extracted_vendor = ocr_data.get('vendor_name', '').strip()
        
        if not extracted_vendor:
            return {
                'vendor_id': None,
                'vendor_name': None,
                'confidence': 0,
                'match_type': 'no_vendor_extracted',
                'reasoning': 'No vendor name was extracted from the document'
            }
        
        # Get all existing vendors
        existing_vendors = db.query(Vendor).all()
        vendor_list = [{'id': v.id, 'name': v.name} for v in existing_vendors]
        
        if not vendor_list:
            # No vendors in database - suggest creating one
            return {
                'vendor_id': None,
                'vendor_name': extracted_vendor,
                'confidence': 0.5,
                'match_type': 'no_vendors_in_db',
                'reasoning': 'No vendors exist in the database yet',
                'suggested_vendor': extracted_vendor
            }
        
        # Step 1: Try exact match (case-insensitive)
        for vendor in vendor_list:
            if vendor['name'].lower() == extracted_vendor.lower():
                return {
                    'vendor_id': vendor['id'],
                    'vendor_name': vendor['name'],
                    'confidence': 1.0,
                    'match_type': 'exact',
                    'reasoning': f"Exact match found: '{extracted_vendor}' = '{vendor['name']}'"
                }
        
        # Step 2: Fuzzy string matching
        fuzzy_match = self._fuzzy_match(extracted_vendor, vendor_list)
        
        if fuzzy_match and fuzzy_match['confidence'] >= 0.9:
            # High confidence fuzzy match
            return {
                'vendor_id': fuzzy_match['vendor_id'],
                'vendor_name': fuzzy_match['vendor_name'],
                'confidence': fuzzy_match['confidence'],
                'match_type': 'fuzzy',
                'reasoning': f"High-confidence fuzzy match: '{extracted_vendor}' ≈ '{fuzzy_match['vendor_name']}' ({fuzzy_match['confidence']:.0%} similar)"
            }
        
        # Step 3: LLM-based intelligent matching
        # This handles cases where fuzzy matching isn't enough
        llm_match = await self._llm_match_vendor(
            extracted_vendor, 
            vendor_list, 
            ocr_data,
            file_content,
            filename
        )
        
        if llm_match:
            return llm_match
        
        # Step 4: If fuzzy match exists but low confidence, return it with warning
        if fuzzy_match:
            return {
                'vendor_id': fuzzy_match['vendor_id'],
                'vendor_name': fuzzy_match['vendor_name'],
                'confidence': fuzzy_match['confidence'],
                'match_type': 'fuzzy_low_confidence',
                'reasoning': f"Low-confidence fuzzy match: '{extracted_vendor}' ≈ '{fuzzy_match['vendor_name']}' ({fuzzy_match['confidence']:.0%} similar). Manual verification recommended.",
                'suggested_vendor': extracted_vendor
            }
        
        # No match found
        return {
            'vendor_id': None,
            'vendor_name': extracted_vendor,
            'confidence': 0,
            'match_type': 'unmatched',
            'reasoning': f"No matching vendor found for '{extracted_vendor}'",
            'suggested_vendor': extracted_vendor
        }
    
    def _fuzzy_match(self, extracted_vendor: str, vendor_list: List[Dict]) -> Optional[Dict]:
        """
        Perform fuzzy string matching against vendor list.
        Handles common variations like Inc, LLC, Corp, etc.
        """
        # Normalize the extracted vendor name
        normalized_extracted = self._normalize_company_name(extracted_vendor)
        
        best_match = None
        best_score = 0
        
        for vendor in vendor_list:
            normalized_vendor = self._normalize_company_name(vendor['name'])
            
            # Calculate similarity score
            score = difflib.SequenceMatcher(
                None, 
                normalized_extracted.lower(), 
                normalized_vendor.lower()
            ).ratio()
            
            if score > best_score:
                best_score = score
                best_match = vendor
        
        if best_match and best_score >= 0.6:  # Minimum threshold
            return {
                'vendor_id': best_match['id'],
                'vendor_name': best_match['name'],
                'confidence': best_score
            }
        
        return None
    
    def _normalize_company_name(self, name: str) -> str:
        """
        Normalize company name by removing common suffixes and variations.
        """
        if not name:
            return ''
        
        name = name.strip()
        
        # Common suffixes to remove for comparison
        suffixes = [
            ', Inc.', ', Inc', ' Inc.', ' Inc',
            ', LLC', ' LLC',
            ', Corp.', ', Corp', ' Corp.', ' Corp',
            ', Ltd.', ', Ltd', ' Ltd.', ' Ltd',
            ', Co.', ', Co', ' Co.', ' Co',
            ' Corporation', ' Incorporated', ' Limited',
            ' Company', ' & Co', ' and Company',
            ', PLC', ' PLC', ' plc',
            ' GmbH', ' AG', ' S.A.', ' SA',
        ]
        
        normalized = name
        for suffix in suffixes:
            if normalized.lower().endswith(suffix.lower()):
                normalized = normalized[:-len(suffix)]
        
        # Remove extra whitespace
        normalized = ' '.join(normalized.split())
        
        return normalized
    
    async def _llm_match_vendor(
        self, 
        extracted_vendor: str, 
        vendor_list: List[Dict],
        ocr_data: Dict,
        file_content: Optional[bytes],
        filename: Optional[str]
    ) -> Optional[Dict]:
        """
        Use LLM reasoning to match vendor, considering full invoice context.
        """
        if not self.openai_client:
            return None
        
        try:
            # Build context about the invoice
            invoice_context = {
                'extracted_vendor': extracted_vendor,
                'invoice_number': ocr_data.get('invoice_number'),
                'po_number': ocr_data.get('po_number'),
                'total_amount': ocr_data.get('total_amount'),
                'currency': ocr_data.get('currency'),
            }
            
            # Add line item descriptions for context
            line_items = ocr_data.get('line_items', [])
            if line_items:
                descriptions = [item.get('description', '') for item in line_items[:5]]
                invoice_context['sample_items'] = descriptions
            
            vendor_names = [v['name'] for v in vendor_list]
            
            prompt = f"""You are an expert at matching vendor names from invoices to a database of known vendors.

TASK: Determine if the extracted vendor name matches any existing vendor in our database.

EXTRACTED VENDOR FROM INVOICE: "{extracted_vendor}"

EXISTING VENDORS IN DATABASE:
{json.dumps(vendor_names, indent=2)}

INVOICE CONTEXT:
{json.dumps(invoice_context, indent=2)}

IMPORTANT CONSIDERATIONS:
1. The "vendor" is the SELLER/SUPPLIER who sent the invoice, NOT the "Bill To" company (buyer)
2. Company names may have variations: "Acme Inc" = "ACME Corporation" = "Acme"
3. OCR may have misread characters: "Acme" might appear as "Acrne"
4. The vendor might be abbreviated: "ABC Manufacturing" could be "ABC Mfg"
5. Consider if the extracted name is actually the receiving company (wrong field)

Analyze and respond with JSON:
{{
    "matched_vendor": "exact name from database or null if no match",
    "confidence": 0.0-1.0,
    "reasoning": "detailed explanation of your analysis",
    "is_correct_vendor_field": true/false,
    "correction_note": "if extracted vendor seems wrong, explain what the actual vendor might be"
}}

Return ONLY the JSON, no markdown."""

            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Cost-effective for this task
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500
            )
            
            if response.choices and response.choices[0].message.content:
                result = self._parse_json(response.choices[0].message.content)
                
                if result.get('matched_vendor'):
                    # Find the vendor ID
                    matched_name = result['matched_vendor']
                    vendor_id = None
                    for v in vendor_list:
                        if v['name'].lower() == matched_name.lower():
                            vendor_id = v['id']
                            break
                    
                    if vendor_id:
                        return {
                            'vendor_id': vendor_id,
                            'vendor_name': matched_name,
                            'confidence': result.get('confidence', 0.8),
                            'match_type': 'llm_matched',
                            'reasoning': result.get('reasoning', 'LLM matched vendor')
                        }
                
                # LLM couldn't find a match
                if not result.get('is_correct_vendor_field', True):
                    # The OCR might have extracted the wrong field as vendor
                    return {
                        'vendor_id': None,
                        'vendor_name': extracted_vendor,
                        'confidence': 0.3,
                        'match_type': 'vendor_field_error',
                        'reasoning': result.get('correction_note', 'The extracted vendor may be incorrect'),
                        'suggested_vendor': extracted_vendor
                    }
        
        except Exception as e:
            logger.error(f"LLM vendor matching failed: {e}")
        
        return None
    
    async def verify_vendor_from_image(
        self, 
        file_content: bytes, 
        filename: str,
        extracted_vendor: str,
        vendor_list: List[Dict]
    ) -> Optional[Dict]:
        """
        Use vision model to verify vendor directly from document image.
        This is the most accurate but also most expensive method.
        """
        if not self.openai_client:
            return None
        
        import base64
        
        try:
            base64_image = base64.b64encode(file_content).decode('utf-8')
            mime_type = self._get_mime_type(filename)
            
            vendor_names = [v['name'] for v in vendor_list]
            
            prompt = f"""Look at this invoice/document and identify the VENDOR (the company who SENT this invoice, NOT the company receiving it).

The OCR extracted this vendor name: "{extracted_vendor}"

Our database has these vendors:
{json.dumps(vendor_names, indent=2)}

TASK:
1. Look at the letterhead, logo, return address, or "From" section
2. Identify the CORRECT vendor (seller/supplier) name
3. Match it to our database if possible

The vendor is typically:
- In the letterhead or logo at top
- In the "From" or "Remit To" section  
- The company whose address appears at top
- NOT the "Bill To" or "Ship To" company

Respond with JSON:
{{
    "identified_vendor": "what you see on the document",
    "matched_vendor": "exact name from database or null",
    "confidence": 0.0-1.0,
    "reasoning": "explanation",
    "ocr_was_correct": true/false
}}"""

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
                max_tokens=500,
                temperature=0.1
            )
            
            if response.choices and response.choices[0].message.content:
                result = self._parse_json(response.choices[0].message.content)
                
                if result.get('matched_vendor'):
                    vendor_id = None
                    for v in vendor_list:
                        if v['name'].lower() == result['matched_vendor'].lower():
                            vendor_id = v['id']
                            break
                    
                    return {
                        'vendor_id': vendor_id,
                        'vendor_name': result['matched_vendor'],
                        'confidence': result.get('confidence', 0.9),
                        'match_type': 'vision_verified',
                        'reasoning': result.get('reasoning', 'Verified from document image'),
                        'identified_vendor': result.get('identified_vendor'),
                        'ocr_was_correct': result.get('ocr_was_correct', True)
                    }
                else:
                    # Found vendor but not in database
                    return {
                        'vendor_id': None,
                        'vendor_name': result.get('identified_vendor', extracted_vendor),
                        'confidence': result.get('confidence', 0.7),
                        'match_type': 'vision_new_vendor',
                        'reasoning': result.get('reasoning', 'Vendor identified but not in database'),
                        'suggested_vendor': result.get('identified_vendor', extracted_vendor),
                        'ocr_was_correct': result.get('ocr_was_correct', True)
                    }
        
        except Exception as e:
            logger.error(f"Vision vendor verification failed: {e}")
        
        return None
    
    def _parse_json(self, content: str) -> Dict:
        """Parse JSON from LLM response"""
        import re
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```\s*', '', content)
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            content = match.group(0)
        try:
            return json.loads(content)
        except:
            return {}
    
    def _get_mime_type(self, filename: str) -> str:
        """Get MIME type from filename"""
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        return {
            'pdf': 'application/pdf',
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
        }.get(ext, 'application/octet-stream')


# Singleton instance
vendor_matching_service = VendorMatchingService()
