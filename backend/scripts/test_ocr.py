#!/usr/bin/env python3
"""
Test script for OCR service with local files
"""
import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.ocr_service import ocr_service
from app.config import settings
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_ocr_with_file(file_path: str):
    """Test OCR service with a local file"""
    print(f"\n{'='*60}")
    print(f"Testing OCR with file: {file_path}")
    print(f"{'='*60}\n")
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"ERROR: File not found: {file_path}")
        return None
    
    # Read file
    with open(file_path, 'rb') as f:
        file_content = f.read()
    
    filename = os.path.basename(file_path)
    file_size = len(file_content)
    print(f"File: {filename}")
    print(f"Size: {file_size:,} bytes ({file_size / 1024:.2f} KB)\n")
    
    # Check API configuration
    print("API Configuration:")
    print(f"  Base URL: {settings.clarifai_base_url}")
    print(f"  Model URL: {settings.clarifai_model_url}")
    print(f"  API Key (CLARIFAI_PAT): {'Set' if settings.clarifai_pat else 'NOT SET'}")
    print()
    
    if not settings.clarifai_pat:
        print("ERROR: CLARIFAI_PAT is not set!")
        print("Set it in your .env file or environment variables")
        return None
    
    # Test OCR
    try:
        print("Calling OCR service...")
        result = await ocr_service.process_file(file_content, filename)
        
        print("\n" + "="*60)
        print("OCR RESULT:")
        print("="*60)
        print(f"\nVendor Name: {result.get('vendor_name')}")
        print(f"Invoice Number: {result.get('invoice_number')}")
        print(f"PO Number: {result.get('po_number')}")
        print(f"Invoice Date: {result.get('invoice_date')}")
        print(f"Total Amount: {result.get('total_amount')}")
        print(f"Currency: {result.get('currency')}")
        print(f"Line Items: {len(result.get('line_items', []))}")
        
        if result.get('line_items'):
            print("\nLine Items:")
            for item in result.get('line_items', [])[:5]:  # Show first 5
                print(f"  - {item.get('description', 'N/A')} (Qty: {item.get('quantity')}, Price: {item.get('unit_price')})")
        
        print("\n" + "="*60)
        print("Full Result (JSON):")
        print("="*60)
        import json
        print(json.dumps(result, indent=2, default=str))
        
        return result
        
    except Exception as e:
        print(f"\nERROR: OCR processing failed")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        import traceback
        print("\nTraceback:")
        traceback.print_exc()
        return None


async def main():
    """Main test function"""
    # Get data directory
    data_dir = Path(__file__).parent.parent.parent / "data"
    
    # Test files
    invoice_file = data_dir / "Wanhua Chemical Invoice.pdf"
    po_file = data_dir / "Everchem PO.png"
    
    print("OCR Service Local Test")
    print("="*60)
    
    # Test invoice
    if invoice_file.exists():
        await test_ocr_with_file(str(invoice_file))
    else:
        print(f"Invoice file not found: {invoice_file}")
    
    # Test PO (if you want)
    # if po_file.exists():
    #     await test_ocr_with_file(str(po_file))
    
    print("\n" + "="*60)
    print("Test completed!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())

