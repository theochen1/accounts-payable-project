#!/usr/bin/env python3
"""
Simple test to verify DeepSeek API connection and check multimodal support
"""
import asyncio
import httpx
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
import base64
import json

async def test_basic_chat():
    """Test basic chat to verify API key works"""
    print("Testing basic DeepSeek chat API...")
    
    if not settings.deepseek_api_key:
        print("ERROR: DEEPSEEK_API_KEY not set!")
        print("Set it as an environment variable or in .env file")
        return False
    
    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "user", "content": "Say 'Hello, API is working' if you can read this."}
        ],
        "stream": False
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.deepseek_api_key}"
    }
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                settings.deepseek_api_url,
                json=payload,
                headers=headers
            )
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                print(f"Response: {content}")
                return True
            else:
                print(f"Error: {response.text}")
                return False
    except Exception as e:
        print(f"Exception: {e}")
        return False


async def test_multimodal_support():
    """Test if DeepSeek supports multimodal (image) inputs"""
    print("\nTesting multimodal (image) support...")
    
    if not settings.deepseek_api_key:
        print("ERROR: DEEPSEEK_API_KEY not set!")
        return False
    
    # Read a small test image
    data_dir = Path(__file__).parent.parent.parent / "data"
    test_image = data_dir / "Everchem PO.png"
    
    if not test_image.exists():
        print(f"Test image not found: {test_image}")
        return False
    
    with open(test_image, 'rb') as f:
        image_data = f.read()
    
    # Encode to base64
    base64_image = base64.b64encode(image_data).decode('utf-8')
    data_url = f"data:image/png;base64,{base64_image}"
    
    # Try OpenAI-compatible multimodal format
    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "What do you see in this image?"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": data_url
                        }
                    }
                ]
            }
        ],
        "stream": False
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.deepseek_api_key}"
    }
    
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                settings.deepseek_api_url,
                json=payload,
                headers=headers
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
            if response.status_code == 200:
                print("✓ Multimodal (image) support confirmed!")
                return True
            elif response.status_code == 404:
                print("✗ 404 Error: DeepSeek may not support multimodal inputs")
                print("  The chat API might be text-only")
                return False
            else:
                print(f"✗ Error: {response.status_code}")
                return False
    except Exception as e:
        print(f"Exception: {e}")
        return False


async def main():
    print("="*60)
    print("DeepSeek API Connection Test")
    print("="*60)
    print(f"\nAPI URL: {settings.deepseek_api_url}")
    print(f"Model: {settings.deepseek_model}")
    print(f"API Key: {'Set' if settings.deepseek_api_key else 'NOT SET'}\n")
    
    # Test 1: Basic chat
    basic_works = await test_basic_chat()
    
    if basic_works:
        # Test 2: Multimodal
        multimodal_works = await test_multimodal_support()
        
        print("\n" + "="*60)
        print("Summary:")
        print("="*60)
        print(f"Basic Chat API: {'✓ Working' if basic_works else '✗ Failed'}")
        print(f"Multimodal (Image) Support: {'✓ Supported' if multimodal_works else '✗ Not Supported'}")
        
        if not multimodal_works:
            print("\n⚠️  Recommendation:")
            print("   DeepSeek chat API may not support images.")
            print("   Consider using a dedicated OCR service:")
            print("   - Google Cloud Vision API")
            print("   - AWS Textract")
            print("   - Azure Form Recognizer")
            print("   - OCR.space API")
    else:
        print("\n✗ Cannot test multimodal - basic API connection failed")
        print("   Check your API key and network connection")


if __name__ == "__main__":
    asyncio.run(main())

