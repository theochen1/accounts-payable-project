import boto3
from botocore.exceptions import ClientError
from typing import Optional
import os
from datetime import datetime
from app.config import settings


class StorageService:
    """Service for handling object storage (S3-compatible) operations"""
    
    def __init__(self):
        self.bucket_name = settings.storage_bucket_name
        
        # Initialize S3 client
        s3_config = {}
        if settings.storage_endpoint_url:
            s3_config['endpoint_url'] = settings.storage_endpoint_url
        if settings.storage_access_key_id:
            s3_config['aws_access_key_id'] = settings.storage_access_key_id
        if settings.storage_secret_access_key:
            s3_config['aws_secret_access_key'] = settings.storage_secret_access_key
        if settings.storage_region:
            s3_config['region_name'] = settings.storage_region
        
        if s3_config:
            self.s3_client = boto3.client('s3', **s3_config)
        else:
            # Fallback to local filesystem if no S3 config
            self.s3_client = None
    
    def upload_pdf(self, file_content: bytes, filename: str) -> str:
        """
        Upload PDF file to object storage and return storage path
        
        Args:
            file_content: Binary content of the PDF file
            filename: Original filename
            
        Returns:
            Storage path (S3 key or local path)
        """
        # Generate unique storage path
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        file_ext = os.path.splitext(filename)[1] or ".pdf"
        storage_key = f"invoices/{timestamp}_{filename}"
        
        if self.s3_client:
            try:
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=storage_key,
                    Body=file_content,
                    ContentType='application/pdf'
                )
                return storage_key
            except ClientError as e:
                raise Exception(f"Failed to upload to S3: {str(e)}")
        else:
            # Fallback to local filesystem storage
            local_storage_dir = "local_storage/invoices"
            os.makedirs(local_storage_dir, exist_ok=True)
            local_path = os.path.join(local_storage_dir, f"{timestamp}_{filename}")
            with open(local_path, 'wb') as f:
                f.write(file_content)
            return local_path
    
    def get_pdf_url(self, storage_path: str, expires_in: int = 3600) -> str:
        """
        Get a URL to access the PDF file
        
        Args:
            storage_path: Storage path/key
            expires_in: URL expiration time in seconds (for presigned URLs)
            
        Returns:
            URL to access the file
        """
        if self.s3_client:
            try:
                url = self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.bucket_name, 'Key': storage_path},
                    ExpiresIn=expires_in
                )
                return url
            except ClientError as e:
                raise Exception(f"Failed to generate presigned URL: {str(e)}")
        else:
            # For local storage, return a relative path or file:// URL
            return f"/storage/{storage_path}"
    
    def download_pdf(self, storage_path: str) -> bytes:
        """
        Download PDF file from storage
        
        Args:
            storage_path: Storage path/key
            
        Returns:
            Binary content of the PDF file
        """
        if self.s3_client:
            try:
                response = self.s3_client.get_object(
                    Bucket=self.bucket_name,
                    Key=storage_path
                )
                return response['Body'].read()
            except ClientError as e:
                raise Exception(f"Failed to download from S3: {str(e)}")
        else:
            # For local storage
            if not os.path.exists(storage_path):
                raise FileNotFoundError(f"File not found: {storage_path}")
            with open(storage_path, 'rb') as f:
                return f.read()


storage_service = StorageService()

