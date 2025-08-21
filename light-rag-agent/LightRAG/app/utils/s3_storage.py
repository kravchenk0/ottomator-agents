"""
S3 storage adapter for LightRAG document management.

This module provides functionality to upload, download, and manage documents
stored in AWS S3 for use with the LightRAG system.
"""
import os
import logging
import asyncio
from typing import List, Dict, Optional, BinaryIO
from pathlib import Path
from datetime import datetime

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    boto3 = None  # type: ignore
    ClientError = Exception  # type: ignore
    NoCredentialsError = Exception  # type: ignore

logger = logging.getLogger(__name__)


class S3StorageAdapter:
    """
    AWS S3 storage adapter for LightRAG documents.
    
    Provides async interface for uploading, downloading, and managing
    documents stored in S3 bucket.
    """
    
    def __init__(
        self,
        bucket_name: str,
        prefix: str = "documents/",
        region: str = "us-east-1"
    ):
        """
        Initialize S3 storage adapter.
        
        Args:
            bucket_name: Name of S3 bucket for document storage.
            prefix: S3 key prefix for organizing documents.
            region: AWS region for S3 bucket.
            
        Raises:
            ImportError: If boto3 is not installed.
            NoCredentialsError: If AWS credentials are not configured.
        """
        if not BOTO3_AVAILABLE:
            raise ImportError(
                "boto3 is required for S3 storage. Install with: pip install boto3"
            )
        
        self.bucket_name = bucket_name
        self.prefix = prefix.rstrip('/') + '/' if prefix else ''
        self.region = region
        
        try:
            # Reason: Create S3 client with region for better performance
            self.s3_client = boto3.client('s3', region_name=region)
            self.s3_resource = boto3.resource('s3', region_name=region)
            self.bucket = self.s3_resource.Bucket(bucket_name)
        except NoCredentialsError as e:
            logger.error("AWS credentials not found. Configure with AWS CLI or IAM role.")
            raise e
    
    async def upload_file(
        self, 
        file_path: str, 
        s3_key: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Upload file to S3 bucket.
        
        Args:
            file_path: Path to local file to upload.
            s3_key: S3 key (filename) for uploaded object. If None, uses basename.
            metadata: Optional metadata dict to attach to S3 object.
            
        Returns:
            str: S3 key of uploaded object.
            
        Raises:
            FileNotFoundError: If local file doesn't exist.
            ClientError: If S3 upload fails.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if s3_key is None:
            s3_key = os.path.basename(file_path)
        
        # Add prefix to S3 key
        full_s3_key = f"{self.prefix}{s3_key}"
        
        # Prepare metadata
        upload_metadata = {
            'upload_timestamp': datetime.utcnow().isoformat(),
            'original_path': file_path,
            'file_size': str(os.path.getsize(file_path))
        }
        if metadata:
            upload_metadata.update(metadata)
        
        try:
            # Reason: Run S3 upload in thread executor to avoid blocking event loop
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                self._upload_file_sync,
                file_path,
                full_s3_key,
                upload_metadata
            )
            
            logger.info(f"Uploaded {file_path} to s3://{self.bucket_name}/{full_s3_key}")
            return full_s3_key
            
        except ClientError as e:
            logger.error(f"Failed to upload {file_path} to S3: {e}")
            raise e
    
    def _upload_file_sync(self, file_path: str, s3_key: str, metadata: Dict[str, str]):
        """Synchronous S3 upload helper."""
        self.s3_client.upload_file(
            file_path,
            self.bucket_name,
            s3_key,
            ExtraArgs={'Metadata': metadata}
        )
    
    async def upload_file_obj(
        self,
        file_obj: BinaryIO,
        s3_key: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Upload file object to S3 bucket.
        
        Args:
            file_obj: File-like object to upload.
            s3_key: S3 key (filename) for uploaded object.
            metadata: Optional metadata dict to attach to S3 object.
            
        Returns:
            str: S3 key of uploaded object.
            
        Raises:
            ClientError: If S3 upload fails.
        """
        full_s3_key = f"{self.prefix}{s3_key}"
        
        upload_metadata = {
            'upload_timestamp': datetime.utcnow().isoformat(),
        }
        if metadata:
            upload_metadata.update(metadata)
        
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                self._upload_fileobj_sync,
                file_obj,
                full_s3_key,
                upload_metadata
            )
            
            logger.info(f"Uploaded file object to s3://{self.bucket_name}/{full_s3_key}")
            return full_s3_key
            
        except ClientError as e:
            logger.error(f"Failed to upload file object to S3: {e}")
            raise e
    
    def _upload_fileobj_sync(
        self, 
        file_obj: BinaryIO, 
        s3_key: str, 
        metadata: Dict[str, str]
    ):
        """Synchronous S3 file object upload helper."""
        self.s3_client.upload_fileobj(
            file_obj,
            self.bucket_name,
            s3_key,
            ExtraArgs={'Metadata': metadata}
        )
    
    async def download_file(self, s3_key: str, local_path: str) -> str:
        """
        Download file from S3 to local path.
        
        Args:
            s3_key: S3 key of object to download.
            local_path: Local path to save downloaded file.
            
        Returns:
            str: Local path of downloaded file.
            
        Raises:
            ClientError: If S3 download fails.
        """
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                self.s3_client.download_file,
                self.bucket_name,
                s3_key,
                local_path
            )
            
            logger.info(f"Downloaded s3://{self.bucket_name}/{s3_key} to {local_path}")
            return local_path
            
        except ClientError as e:
            logger.error(f"Failed to download {s3_key} from S3: {e}")
            raise e
    
    async def list_objects(
        self, 
        prefix_filter: Optional[str] = None,
        max_keys: int = 1000
    ) -> List[Dict[str, any]]:
        """
        List objects in S3 bucket.
        
        Args:
            prefix_filter: Additional prefix filter (appended to self.prefix).
            max_keys: Maximum number of objects to return.
            
        Returns:
            List[Dict]: List of object metadata dicts.
        """
        search_prefix = self.prefix
        if prefix_filter:
            search_prefix += prefix_filter
        
        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                self._list_objects_sync,
                search_prefix,
                max_keys
            )
            
            objects = []
            for obj in response.get('Contents', []):
                objects.append({
                    'key': obj['Key'],
                    'last_modified': obj['LastModified'],
                    'size': obj['Size'],
                    'etag': obj['ETag'].strip('"')
                })
            
            logger.debug(f"Listed {len(objects)} objects with prefix {search_prefix}")
            return objects
            
        except ClientError as e:
            logger.error(f"Failed to list objects in S3: {e}")
            raise e
    
    def _list_objects_sync(self, prefix: str, max_keys: int) -> Dict:
        """Synchronous S3 list objects helper."""
        return self.s3_client.list_objects_v2(
            Bucket=self.bucket_name,
            Prefix=prefix,
            MaxKeys=max_keys
        )
    
    async def delete_object(self, s3_key: str) -> bool:
        """
        Delete object from S3 bucket.
        
        Args:
            s3_key: S3 key of object to delete.
            
        Returns:
            bool: True if deletion successful.
            
        Raises:
            ClientError: If S3 deletion fails.
        """
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                self.s3_client.delete_object,
                self.bucket_name,
                s3_key
            )
            
            logger.info(f"Deleted s3://{self.bucket_name}/{s3_key}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to delete {s3_key} from S3: {e}")
            raise e
    
    async def object_exists(self, s3_key: str) -> bool:
        """
        Check if object exists in S3 bucket.
        
        Args:
            s3_key: S3 key to check.
            
        Returns:
            bool: True if object exists.
        """
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                self.s3_client.head_object,
                self.bucket_name,
                s3_key
            )
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise e
    
    def get_presigned_url(
        self, 
        s3_key: str, 
        expiration: int = 3600,
        http_method: str = 'GET'
    ) -> str:
        """
        Generate presigned URL for S3 object.
        
        Args:
            s3_key: S3 key of object.
            expiration: URL expiration time in seconds.
            http_method: HTTP method for presigned URL.
            
        Returns:
            str: Presigned URL.
        """
        try:
            if http_method.upper() == 'GET':
                url = self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.bucket_name, 'Key': s3_key},
                    ExpiresIn=expiration
                )
            elif http_method.upper() == 'PUT':
                url = self.s3_client.generate_presigned_url(
                    'put_object',
                    Params={'Bucket': self.bucket_name, 'Key': s3_key},
                    ExpiresIn=expiration
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {http_method}")
                
            return url
            
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL for {s3_key}: {e}")
            raise e


def get_s3_storage() -> Optional[S3StorageAdapter]:
    """
    Factory function to create S3 storage adapter from environment variables.
    
    Returns:
        S3StorageAdapter: Configured adapter, or None if not configured.
        
    Environment Variables:
        AWS_S3_BUCKET: S3 bucket name (required).
        S3_DOCUMENT_PREFIX: S3 key prefix (default: 'documents/').
        AWS_REGION: AWS region (default: 'us-east-1').
    """
    bucket_name = os.getenv("AWS_S3_BUCKET")
    if not bucket_name:
        logger.warning("AWS_S3_BUCKET not configured. S3 storage disabled.")
        return None
    
    if not BOTO3_AVAILABLE:
        logger.warning("boto3 not installed. S3 storage disabled.")
        return None
    
    prefix = os.getenv("S3_DOCUMENT_PREFIX", "documents/")
    region = os.getenv("AWS_REGION", "us-east-1")
    
    try:
        return S3StorageAdapter(bucket_name, prefix, region)
    except Exception as e:
        logger.error(f"Failed to initialize S3 storage: {e}")
        return None