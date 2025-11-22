from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://user:password@localhost/ap_platform"
    
    # OCR Configuration
    deepseek_ocr_api_url: str = "https://api.deepseek.com/ocr"  # Default placeholder
    deepseek_ocr_api_key: Optional[str] = None
    ocr_timeout_seconds: int = 30
    ocr_max_retries: int = 3
    
    # Storage Configuration (S3-compatible)
    storage_endpoint_url: Optional[str] = None
    storage_access_key_id: Optional[str] = None
    storage_secret_access_key: Optional[str] = None
    storage_bucket_name: str = "ap-invoices"
    storage_region: str = "us-east-1"
    
    # Matching Configuration
    matching_tolerance: float = 0.01  # 1% tolerance for total amount matching
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

