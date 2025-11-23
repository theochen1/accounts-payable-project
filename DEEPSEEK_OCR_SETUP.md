# DeepSeek OCR Integration Setup

## Overview

This application uses DeepSeek's chat-completions API for OCR (Optical Character Recognition) to extract invoice data from images and PDFs. The integration uses OpenAI-compatible multimodal message format.

## API Endpoint

- **Endpoint**: `https://api.deepseek.com/v1/chat/completions`
- **Method**: POST
- **Format**: OpenAI-compatible chat completions API

## Environment Variables

Set these in Railway (or your `.env` file for local development):

### Required

- `DEEPSEEK_API_KEY` - Your DeepSeek API key (Bearer token)
  - Get it from: https://platform.deepseek.com
  - Format: `sk-...` (similar to OpenAI)

### Optional (with defaults)

- `DEEPSEEK_API_URL` - API endpoint (default: `https://api.deepseek.com/v1/chat/completions`)
- `DEEPSEEK_MODEL` - Model to use (default: `deepseek-chat`)
- `OCR_TIMEOUT_SECONDS` - Request timeout (default: `60`)
- `OCR_MAX_RETRIES` - Number of retry attempts (default: `3`)

## How It Works

1. **File Upload**: User uploads an image (PNG, JPG, etc.) or PDF
2. **Encoding**: File is converted to base64 and embedded as a data URL
3. **LLM Request**: Sent to DeepSeek chat-completions API with:
   - System prompt instructing extraction of invoice data
   - Image attached in OpenAI-compatible multimodal format
   - Request for JSON-structured response
4. **Response Parsing**: LLM response (JSON or text) is parsed to extract:
   - Vendor name
   - Invoice number
   - PO number
   - Invoice date
   - Total amount
   - Currency
   - Line items (SKU, description, quantity, unit price)
5. **Normalization**: Extracted data is normalized to internal format

## Supported File Formats

- **Images**: PNG, JPG, JPEG, GIF, BMP, WEBP, TIFF
- **PDFs**: Limited support (may need conversion to images first)

## Authentication

The API uses Bearer token authentication:

```
Authorization: Bearer ${DEEPSEEK_API_KEY}
```

## Request Format

The service sends requests in OpenAI-compatible format:

```json
{
  "model": "deepseek-chat",
  "messages": [
    {
      "role": "system",
      "content": "Extract all text from any attached image accurately..."
    },
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Please extract all invoice information..."
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "data:image/png;base64,..."
          }
        }
      ]
    }
  ],
  "stream": false,
  "temperature": 0.1
}
```

## Response Format

The LLM returns text/JSON that is parsed to extract structured data. The service handles:
- JSON objects (preferred)
- JSON wrapped in markdown code blocks
- Plain text with regex fallback extraction

## Migration from Old OCR Endpoint

If you were using the old `/v1/ocr` endpoint:

1. **Update Environment Variables**:
   - Old: `DEEPSEEK_OCR_API_URL` → New: `DEEPSEEK_API_URL` (optional, has default)
   - Old: `DEEPSEEK_OCR_API_KEY` → New: `DEEPSEEK_API_KEY` (required)

2. **No Code Changes Needed**: The service layer handles the API differences

3. **Verify API Key**: Make sure your DeepSeek API key is set in Railway Variables

## Troubleshooting

### 401 Unauthorized
- Check that `DEEPSEEK_API_KEY` is set correctly
- Verify the API key is valid and active

### 400 Bad Request
- Check that the image format is supported
- Verify the model name is correct (`deepseek-chat`)

### Timeout Errors
- Increase `OCR_TIMEOUT_SECONDS` if processing large images
- Check network connectivity

### JSON Parsing Errors
- The service has fallback regex extraction
- Check logs for the raw LLM response
- The LLM may need clearer instructions in the system prompt

## Testing

Test the integration by uploading an invoice image. The system will:
1. Extract text using DeepSeek
2. Parse invoice data
3. Save to database
4. Run matching against purchase orders

## Notes

- PDF support may be limited; consider converting PDFs to images first
- Large images may take longer to process
- The LLM response quality depends on image clarity and invoice format
- Temperature is set to 0.1 for more consistent, accurate extraction

