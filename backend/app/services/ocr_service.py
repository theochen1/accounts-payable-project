import httpx
from typing import Dict, Optional
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class OCRService:
    """Service for calling DeepSeek-OCR API"""
    
    def __init__(self):
        self.api_url = settings.deepseek_ocr_api_url
        self.api_key = settings.deepseek_ocr_api_key
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
    
    async def process_file(self, file_content: bytes, filename: str) -> Dict:
        """
        Process file (PDF or image) through DeepSeek-OCR API
        
        Args:
            file_content: Binary content of the file
            filename: Original filename
            
        Returns:
            Structured OCR data as dictionary
        """
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        content_type = self._get_content_type(filename)
        files = {
            "file": (filename, file_content, content_type)
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries):
                try:
                    response = await client.post(
                        self.api_url,
                        files=files,
                        headers=headers
                    )
                    response.raise_for_status()
                    ocr_data = response.json()
                    return self._normalize_ocr_response(ocr_data)
                except httpx.HTTPStatusError as e:
                    logger.error(f"OCR API error (attempt {attempt + 1}/{self.max_retries}): {e.response.status_code} - {e.response.text}")
                    if attempt == self.max_retries - 1:
                        raise Exception(f"OCR API failed after {self.max_retries} attempts: {e.response.status_code}")
                except httpx.TimeoutException as e:
                    logger.error(f"OCR API timeout (attempt {attempt + 1}/{self.max_retries}): {str(e)}")
                    if attempt == self.max_retries - 1:
                        raise Exception(f"OCR API timeout after {self.max_retries} attempts")
                except Exception as e:
                    logger.error(f"OCR API unexpected error (attempt {attempt + 1}/{self.max_retries}): {str(e)}")
                    if attempt == self.max_retries - 1:
                        raise
    
    def _normalize_ocr_response(self, ocr_data: Dict) -> Dict:
        """
        Normalize OCR response to our expected format
        
        This function maps the DeepSeek-OCR response to our internal structure.
        Adjust field mappings based on actual DeepSeek-OCR API response format.
        """
        normalized = {
            "vendor_name": ocr_data.get("vendor_name") or ocr_data.get("vendor", {}).get("name"),
            "invoice_number": ocr_data.get("invoice_number") or ocr_data.get("invoice_no"),
            "po_number": ocr_data.get("po_number") or ocr_data.get("purchase_order_number"),
            "invoice_date": ocr_data.get("invoice_date") or ocr_data.get("date"),
            "total_amount": self._parse_amount(ocr_data.get("total_amount") or ocr_data.get("total")),
            "currency": ocr_data.get("currency", "USD").upper(),
            "line_items": self._normalize_line_items(ocr_data.get("line_items", [])),
            "raw_ocr": ocr_data  # Store raw response for reference
        }
        
        return normalized
    
    def _parse_amount(self, amount: Optional[str]) -> Optional[float]:
        """Parse amount string to float"""
        if amount is None:
            return None
        if isinstance(amount, (int, float)):
            return float(amount)
        # Remove currency symbols and commas
        cleaned = str(amount).replace("$", "").replace(",", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    
    def _normalize_line_items(self, line_items: list) -> list:
        """Normalize line items from OCR response"""
        normalized = []
        for idx, item in enumerate(line_items, start=1):
            normalized.append({
                "line_no": item.get("line_no", idx),
                "sku": item.get("sku") or item.get("item_code") or item.get("product_code"),
                "description": item.get("description") or item.get("item_description") or item.get("name", ""),
                "quantity": self._parse_amount(item.get("quantity") or item.get("qty")),
                "unit_price": self._parse_amount(item.get("unit_price") or item.get("price") or item.get("rate"))
            })
        return normalized


ocr_service = OCRService()

