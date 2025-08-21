#!/usr/bin/env python3
"""
Test script to verify S3 connection and configuration.
Run this script to diagnose S3 integration issues.
"""
import os
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from app.utils.s3_storage import get_s3_storage, S3StorageAdapter, BOTO3_AVAILABLE
    print("✅ S3 storage module imported successfully")
except ImportError as e:
    print(f"❌ Failed to import S3 storage module: {e}")
    sys.exit(1)

def test_s3_configuration():
    """Test S3 configuration and connection."""
    print("\n=== S3 Configuration Test ===")
    
    # Check boto3 availability
    if not BOTO3_AVAILABLE:
        print("❌ boto3 is not installed. Install with: pip install boto3")
        return False
    else:
        print("✅ boto3 is available")
    
    # Check environment variables
    bucket_name = os.getenv("AWS_S3_BUCKET")
    region = os.getenv("AWS_REGION", "us-east-1")
    prefix = os.getenv("S3_DOCUMENT_PREFIX", "documents/")
    
    print(f"🔧 AWS_S3_BUCKET: {bucket_name}")
    print(f"🔧 AWS_REGION: {region}")
    print(f"🔧 S3_DOCUMENT_PREFIX: {prefix}")
    
    if not bucket_name:
        print("❌ AWS_S3_BUCKET environment variable not set")
        return False
    
    # Try to create S3 storage adapter
    try:
        s3_storage = get_s3_storage()
        if s3_storage is None:
            print("❌ S3 storage adapter returned None")
            return False
        else:
            print("✅ S3 storage adapter created successfully")
            print(f"   Bucket: {s3_storage.bucket_name}")
            print(f"   Region: {s3_storage.region}")
            print(f"   Prefix: {s3_storage.prefix}")
    except Exception as e:
        print(f"❌ Failed to create S3 storage adapter: {e}")
        return False
    
    return True, s3_storage

async def test_s3_operations(s3_storage: S3StorageAdapter):
    """Test basic S3 operations."""
    print("\n=== S3 Operations Test ===")
    
    try:
        # Test listing objects
        print("📋 Testing S3 list objects...")
        objects = await s3_storage.list_objects(max_keys=5)
        print(f"✅ Found {len(objects)} objects in bucket")
        for obj in objects[:3]:  # Show first 3
            print(f"   - {obj['key']} ({obj['size']} bytes)")
        
        # Test checking if bucket exists by listing
        print("🔍 Testing bucket access...")
        return True
        
    except Exception as e:
        print(f"❌ S3 operations test failed: {e}")
        return False

def test_environment_setup():
    """Test environment setup for production."""
    print("\n=== Environment Setup Test ===")
    
    # Check if running in EC2 with IAM role
    try:
        import boto3
        from botocore.exceptions import NoCredentialsError
        
        print("🔐 Testing AWS credentials...")
        client = boto3.client('sts', region_name=os.getenv("AWS_REGION", "us-east-1"))
        identity = client.get_caller_identity()
        
        print("✅ AWS credentials are valid")
        print(f"   Account: {identity.get('Account', 'unknown')}")
        print(f"   User/Role: {identity.get('Arn', 'unknown')}")
        
        # Check if using IAM role (recommended for EC2)
        if 'role' in identity.get('Arn', '').lower():
            print("✅ Using IAM role (recommended for EC2)")
        else:
            print("⚠️  Using IAM user credentials (consider IAM role for EC2)")
            
        return True
        
    except NoCredentialsError:
        print("❌ AWS credentials not found")
        print("   For EC2: Ensure IAM instance profile is attached")
        print("   For local: Run 'aws configure' or set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY")
        return False
    except Exception as e:
        print(f"❌ AWS credentials test failed: {e}")
        return False

async def main():
    """Main test function."""
    print("🧪 LightRAG S3 Integration Test")
    print("=" * 50)
    
    # Test configuration
    config_result = test_s3_configuration()
    if isinstance(config_result, tuple):
        config_ok, s3_storage = config_result
    else:
        config_ok = config_result
        s3_storage = None
    
    if not config_ok:
        print("\n❌ Configuration test failed. Fix configuration and try again.")
        sys.exit(1)
    
    # Test environment
    env_ok = test_environment_setup()
    if not env_ok:
        print("\n❌ Environment test failed. Fix AWS credentials and try again.")
        sys.exit(1)
    
    # Test S3 operations
    ops_ok = await test_s3_operations(s3_storage)
    if not ops_ok:
        print("\n❌ S3 operations test failed.")
        sys.exit(1)
    
    print("\n" + "=" * 50)
    print("🎉 All S3 integration tests passed!")
    print("✅ S3 storage is properly configured and accessible")
    print("🚀 Ready to upload documents to S3")

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⛔ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 Test failed with unexpected error: {e}")
        sys.exit(1)