from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://user:password@localhost/ap_platform"
    
    # OCR Configuration (Two-step process: OCR extraction + LLM parsing)
    # Step 1: OCR extraction using Azure Document Intelligence
    azure_doc_intelligence_endpoint: Optional[str] = None  # e.g., "https://your-resource.cognitiveservices.azure.com/"
    azure_doc_intelligence_key: Optional[str] = None  # Azure API key
    azure_doc_intelligence_model: str = "prebuilt-invoice"  # Prebuilt invoice model
    
    # Step 2: LLM parsing (OpenAI or DeepSeek chat API)
    openai_api_key: Optional[str] = None  # OpenAI API key for text parsing
    openai_model: str = "gpt-4o-mini"  # Model for structured data extraction (better accuracy than gpt-3.5-turbo)
    # Alternative: Use DeepSeek chat API instead
    use_deepseek_for_parsing: bool = False  # If True, use DeepSeek chat API
    deepseek_api_url: str = "https://api.deepseek.com/v1/chat/completions"
    deepseek_api_key: Optional[str] = None
    deepseek_model: str = "deepseek-chat"
    
    ocr_timeout_seconds: int = 60  # Timeout for OCR processing
    ocr_max_retries: int = 3
    
    # Storage Configuration (S3-compatible)
    storage_endpoint_url: Optional[str] = None
    storage_access_key_id: Optional[str] = None
    storage_secret_access_key: Optional[str] = None
    storage_bucket_name: str = "ap-invoices"
    storage_region: str = "us-east-1"
    
    # Matching Configuration
    matching_tolerance: float = 0.01  # 1% tolerance for total amount matching
    
    # Agent Configuration
    agent_model: str = "gpt-4o-mini"  # Cost-effective for MVP
    agent_temperature: float = 0.0
    agent_max_retries: int = 3
    
    # Confidence thresholds
    agent_auto_apply_threshold: float = 0.9  # High confidence → auto-apply
    agent_suggest_threshold: float = 0.7     # Medium → suggest to user
    agent_escalate_threshold: float = 0.5    # Low → escalate to human
    
    # CORS Configuration
    cors_origins: str = "http://localhost:3000,http://localhost:3001,https://*.vercel.app"
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields in .env file


settings = Settings()

