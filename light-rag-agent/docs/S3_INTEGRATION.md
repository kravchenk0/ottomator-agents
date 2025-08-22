# S3 Document Storage Integration

## Overview

LightRAG API теперь поддерживает интеграцию с AWS S3 для хранения и управления документами. Это обеспечивает:

- ✅ Масштабируемое хранение документов
- ✅ Автоматические lifecycle политики (IA → Glacier)
- ✅ Версионирование документов
- ✅ Presigned URLs для безопасного доступа
- ✅ Fallback к локальному хранению

## Terraform Infrastructure

### S3 Bucket Resources

```hcl
# S3 bucket with unique suffix
resource "aws_s3_bucket" "lightrag_documents"

# Versioning enabled
resource "aws_s3_bucket_versioning" "lightrag_documents"

# AES256 encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "lightrag_documents"

# Block public access
resource "aws_s3_bucket_public_access_block" "lightrag_documents"

# Lifecycle: Standard → IA (30d) → Glacier (90d)
resource "aws_s3_bucket_lifecycle_configuration" "lightrag_documents"
```

### IAM Permissions

```hcl
# EC2 instance role with S3 access
resource "aws_iam_role" "lightrag_ec2_role"

# S3 policy: GetObject, PutObject, DeleteObject, ListBucket
resource "aws_iam_policy" "lightrag_s3_policy"

# Instance profile for EC2
resource "aws_iam_instance_profile" "lightrag_profile"
```

### Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `s3_document_prefix` | S3 key prefix | `documents/` |
| `s3_document_retention_days` | Retention period (0=no expiry) | `0` |
| `s3_lifecycle_ia_days` | Days to IA transition | `30` |
| `s3_lifecycle_glacier_days` | Days to Glacier transition | `90` |

### Outputs

- `s3_bucket_name`: S3 bucket name
- `s3_bucket_arn`: S3 bucket ARN
- `iam_role_arn`: EC2 IAM role ARN

## API Endpoints

### Document Upload
```bash
POST /documents/upload
```
- **New behavior**: Uploads to S3 if configured, local storage as fallback
- **Response includes**: `storage_type`, `s3_bucket`, `s3_key`, `s3_url`

### S3-Specific Endpoints

#### List S3 Documents
```bash
GET /documents/s3/list?prefix=reports/&max_items=50
```

#### Generate Download URL
```bash
GET /documents/s3/download/{s3_key}?expiration=3600
```

#### Delete S3 Document
```bash
DELETE /documents/s3/{s3_key}
```

## Environment Variables

### Required (for S3 functionality)
```bash
# S3 bucket name (from Terraform output)
AWS_S3_BUCKET=lightrag-documents-production-abcd1234

# AWS region (must match Terraform)
AWS_REGION=me-south-1
```

### Optional
```bash
# S3 key prefix for organization
S3_DOCUMENT_PREFIX=documents/

# AWS credentials (automatically provided via IAM role in EC2)
# AWS_ACCESS_KEY_ID=... (not needed with IAM role)
# AWS_SECRET_ACCESS_KEY=... (not needed with IAM role)
```

## Deployment Steps

### 1. Update Terraform Configuration

```bash
cd terraform/

# Copy example configuration
cp terraform.tfvars.s3-example terraform.tfvars

# Edit with your values
vim terraform.tfvars

# Key S3 variables to configure:
# s3_document_prefix = "documents/"
# s3_document_retention_days = 0
# enable_s3_versioning = true
# s3_lifecycle_ia_days = 30
# s3_lifecycle_glacier_days = 90

# Initialize providers (needed for random provider)
terraform init

# Plan and apply
terraform plan
terraform apply
```

### 2. Install Dependencies

```bash
# Add to requirements.txt or install separately
pip install boto3==1.35.73
```

### 3. Update Environment Variables

```bash
# Get S3 bucket name from Terraform output
export AWS_S3_BUCKET=$(terraform output -raw s3_bucket_name)
export AWS_REGION="me-south-1"
export S3_DOCUMENT_PREFIX="documents/"

# Update .env file
echo "AWS_S3_BUCKET=$AWS_S3_BUCKET" >> .env
echo "AWS_REGION=$AWS_REGION" >> .env
echo "S3_DOCUMENT_PREFIX=$S3_DOCUMENT_PREFIX" >> .env
```

### 4. Restart Application

```bash
# The application will automatically detect S3 configuration on startup
sudo systemctl restart lightrag-api
```

## Usage Examples

### Upload Document to S3
```bash
curl -X POST "https://api.businessindunes.ai/documents/upload" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -F "file=@document.pdf" \
  -F "ingest=true"

# Response:
{
  "status": "ok",
  "file_size": 1048576,
  "filename": "document.pdf",
  "storage_type": "s3",
  "s3_bucket": "lightrag-documents-production-abcd1234",
  "s3_key": "documents/document.pdf",
  "s3_url": "s3://lightrag-documents-production-abcd1234/documents/document.pdf",
  "ingestion": { "added": 1, "skipped": 0 }
}
```

### List S3 Documents
```bash
curl -X GET "https://api.businessindunes.ai/documents/s3/list" \
  -H "Authorization: Bearer $JWT_TOKEN"

# Response:
{
  "status": "ok",
  "bucket": "lightrag-documents-production-abcd1234",
  "prefix": "",
  "count": 5,
  "objects": [
    {
      "key": "documents/document.pdf",
      "last_modified": "2024-01-21T10:30:00Z",
      "size": 1048576,
      "etag": "abc123def456"
    }
  ]
}
```

### Generate Download URL
```bash
curl -X GET "https://api.businessindunes.ai/documents/s3/download/documents/document.pdf" \
  -H "Authorization: Bearer $JWT_TOKEN"

# Response:
{
  "status": "ok",
  "s3_key": "documents/document.pdf",
  "download_url": "https://s3.me-south-1.amazonaws.com/bucket/documents/document.pdf?X-Amz-Algorithm=...",
  "expires_in_seconds": 3600
}
```

## Migration from Local Storage

1. **Keep existing local files** for backward compatibility
2. **New uploads** go to S3 automatically
3. **Gradual migration**: Upload existing local files to S3 via API
4. **Monitor logs** for S3 initialization success

## Troubleshooting

### Terraform Warnings
```
Warning: Invalid Attribute Combination ... No attribute specified when one (and only one) of [rule[0].filter,rule[0].prefix] is required
```
**Solution**: Fixed in latest configuration - S3 lifecycle rules now include proper filter

### S3 Not Initialized
```
S3 storage not configured - using local file storage
```
**Solution**: Check `AWS_S3_BUCKET` environment variable

### Missing AWS Credentials
```
AWS credentials not found. Configure with AWS CLI or IAM role.
```
**Solution**: Verify IAM instance profile is attached to EC2

### S3 Upload Failed
```
S3 upload failed: Access Denied
```
**Solution**: Check S3 bucket policy and IAM permissions

### Provider Initialization
```
Error: Failed to query available provider packages
```
**Solution**: Run `terraform init` to install random provider

### Check S3 Status
```bash
# Check application logs
sudo journalctl -u lightrag-api -f | grep -i s3

# Expected output:
# S3 storage initialized: bucket=lightrag-documents-production-abcd1234
```

## Security Considerations

- ✅ **Bucket is private** - public access blocked
- ✅ **IAM role** - no hardcoded credentials
- ✅ **Encryption at rest** - AES256
- ✅ **Presigned URLs** - temporary, expiring access
- ✅ **Lifecycle policies** - automatic cost optimization

## Cost Optimization

- **Standard**: First 30 days
- **Standard-IA**: Days 30-90 (50% cheaper)
- **Glacier**: After 90 days (80% cheaper)
- **Auto-expiry**: Optional retention policy