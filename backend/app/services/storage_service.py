import boto3
from botocore.exceptions import ClientError
from typing import Optional
import os
from datetime import datetime
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class StorageService:
    """Service for handling object storage (S3-compatible) operations"""
    
    def __init__(self):
        self.bucket_name = settings.storage_bucket_name
        
        # Initialize S3 client only if we have credentials
        # Require both access key and secret key to use S3
        if settings.storage_access_key_id and settings.storage_secret_access_key:
            s3_config = {
                'aws_access_key_id': settings.storage_access_key_id,
                'aws_secret_access_key': settings.storage_secret_access_key,
            }
            if settings.storage_endpoint_url:
                s3_config['endpoint_url'] = settings.storage_endpoint_url
            if settings.storage_region:
                s3_config['region_name'] = settings.storage_region
            
            try:
                self.s3_client = boto3.client('s3', **s3_config)
                logger.info("S3 storage initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize S3 client, falling back to local storage: {str(e)}")
                self.s3_client = None
        else:
            # Fallback to local filesystem if no S3 credentials
            logger.info("No S3 credentials found, using local filesystem storage")
            self.s3_client = None
    
        # Initialize local storage directory
        self.local_storage_dir = os.path.abspath("local_storage/invoices")
        try:
            os.makedirs(self.local_storage_dir, exist_ok=True)
            logger.info(f"Local storage directory initialized: {self.local_storage_dir}")
        except Exception as e:
            logger.error(f"Failed to create local storage directory: {str(e)}")
            raise
    
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
    
    def upload_file(self, file_content: bytes, filename: str) -> str:
        """
        Upload file (PDF or image) to object storage and return storage path
        
        Args:
            file_content: Binary content of the file
            filename: Original filename
            
        Returns:
            Storage path (S3 key or local path)
        """
        # Generate unique storage path
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        file_ext = os.path.splitext(filename)[1] or ".pdf"
        storage_key = f"invoices/{timestamp}_{filename}"
        content_type = self._get_content_type(filename)
        
        if self.s3_client:
            try:
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=storage_key,
                    Body=file_content,
                    ContentType=content_type
                )
                return storage_key
            except ClientError as e:
                raise Exception(f"Failed to upload to S3: {str(e)}")
        else:
            # Fallback to local filesystem storage
            try:
                # Use absolute path for file operations
                local_path = os.path.join(self.local_storage_dir, f"{timestamp}_{filename}")
                with open(local_path, 'wb') as f:
                    f.write(file_content)
                logger.info(f"File saved to local storage: {local_path}")
                # Return relative path for storage_key (same format as S3)
                return storage_key
            except Exception as e:
                logger.error(f"Failed to save file to local storage: {str(e)}")
                raise Exception(f"Failed to save file: {str(e)}")
    
    def upload_pdf(self, file_content: bytes, filename: str) -> str:
        """Legacy method for backward compatibility"""
        return self.upload_file(file_content, filename)
    
    def get_pdf_url(self, storage_path: str, expires_in: int = 3600) -> str:
        """
        Get a URL to access the PDF file
        
        Args:
            storage_path: Storage path/key (relative path like "invoices/timestamp_filename.pdf")
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
            # For local storage, return a relative path for the API route
            # storage_path is already in format "invoices/timestamp_filename.pdf"
            return f"/api/storage/{storage_path}"
    
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
            # storage_path is in format "invoices/timestamp_filename.pdf"
            # Convert to absolute path
            if os.path.isabs(storage_path):
                # If it's already absolute, use it as-is
                local_file_path = storage_path
            else:
                # Extract filename from storage_path (format: "invoices/timestamp_filename.pdf")
                filename = os.path.basename(storage_path)
                local_file_path = os.path.join(self.local_storage_dir, filename)
            
            if not os.path.exists(local_file_path):
                raise FileNotFoundError(f"File not found: {local_file_path}")
            
            try:
                with open(local_file_path, 'rb') as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Failed to read file from local storage: {str(e)}")
                raise Exception(f"Failed to read file: {str(e)}")
    
    def download_file(self, storage_path: str) -> bytes:
        """Alias for download_pdf - works for any file type"""
        return self.download_pdf(storage_path)


storage_service = StorageService()

