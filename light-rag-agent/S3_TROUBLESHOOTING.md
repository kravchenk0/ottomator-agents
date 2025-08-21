# S3 Integration Troubleshooting Guide

## Issue: Files Upload to Local Storage Instead of S3

### Symptoms
- Upload response shows `"stored_as": "pydantic-docs/raw_uploads/filename"`
- S3 bucket remains empty
- No S3-related information in response

### Root Cause
S3 storage adapter is not initializing properly due to missing configuration.

## Step-by-Step Diagnosis

### 1. Check Environment Variables

```bash
# SSH to your server
ssh -i ~/.ssh/id_rsa ec2-user@YOUR_SERVER_IP

# Check if S3 variables are set
echo "AWS_S3_BUCKET: $AWS_S3_BUCKET"
echo "AWS_REGION: $AWS_REGION"
echo "S3_DOCUMENT_PREFIX: $S3_DOCUMENT_PREFIX"
```

**Expected output:**
```
AWS_S3_BUCKET: lightrag-documents-production-6eaefccb
AWS_REGION: me-south-1
S3_DOCUMENT_PREFIX: documents/
```

**If empty:** Add to your `.env` file:
```bash
sudo nano /app/LightRAG/.env

# Add these lines:
AWS_S3_BUCKET=lightrag-documents-production-6eaefccb
AWS_REGION=me-south-1
S3_DOCUMENT_PREFIX=documents/
```

### 2. Check boto3 Installation

```bash
# Check if boto3 is installed
python3 -c "import boto3; print(f'boto3 version: {boto3.__version__}')"
```

**If not installed:**
```bash
# Install boto3
pip3 install boto3==1.35.73 botocore==1.35.73

# Or if using virtual environment:
source /app/venv/bin/activate
pip install boto3==1.35.73 botocore==1.35.73
```

### 3. Verify AWS Credentials

```bash
# Test AWS credentials
aws sts get-caller-identity --region me-south-1
```

**Expected output:**
```json
{
    "UserId": "AIDACKCEVSQ6C2EXAMPLE",
    "Account": "123456789012", 
    "Arn": "arn:aws:iam::123456789012:role/lightrag-ec2-role"
}
```

**If fails:** Check IAM instance profile:
```bash
# Check if instance has IAM role attached
curl http://169.254.169.254/latest/meta-data/iam/security-credentials/
```

### 4. Test S3 Connection

Run the test script:
```bash
cd /app/LightRAG
python3 test_s3_connection.py
```

**Expected successful output:**
```
🧪 LightRAG S3 Integration Test
==================================================
✅ S3 storage module imported successfully

=== S3 Configuration Test ===
✅ boto3 is available
🔧 AWS_S3_BUCKET: lightrag-documents-production-6eaefccb
🔧 AWS_REGION: me-south-1
🔧 S3_DOCUMENT_PREFIX: documents/
✅ S3 storage adapter created successfully

=== Environment Setup Test ===
🔐 Testing AWS credentials...
✅ AWS credentials are valid
✅ Using IAM role (recommended for EC2)

=== S3 Operations Test ===
📋 Testing S3 list objects...
✅ Found 0 objects in bucket
🔍 Testing bucket access...

==================================================
🎉 All S3 integration tests passed!
```

### 5. Check Application Logs

```bash
# Check application startup logs
sudo journalctl -u lightrag-api -n 50 | grep -i s3

# Look for these messages:
# ✅ Good: "S3 storage initialized: bucket=lightrag-documents-production-6eaefccb"
# ❌ Bad: "S3 storage not configured - using local file storage"
# ❌ Bad: "S3 storage initialization failed: ..."
```

### 6. Restart Application

After fixing configuration:
```bash
# Restart the application to reload environment variables
sudo systemctl restart lightrag-api

# Check if it started successfully
sudo systemctl status lightrag-api

# Monitor logs during restart
sudo journalctl -u lightrag-api -f
```

## Common Issues & Solutions

### Issue: `boto3` Import Error
```
ImportError: No module named 'boto3'
```

**Solution:**
```bash
# Install in the correct Python environment
source /app/venv/bin/activate  # if using venv
pip install boto3==1.35.73 botocore==1.35.73
sudo systemctl restart lightrag-api
```

### Issue: AWS Credentials Not Found
```
AWS credentials not found. Configure with AWS CLI or IAM role.
```

**Solution:**
1. **Verify IAM role is attached to EC2:**
   ```bash
   # Check instance metadata
   curl http://169.254.169.254/latest/meta-data/iam/security-credentials/
   ```

2. **If no role attached, attach via AWS Console:**
   - EC2 → Instances → Select instance
   - Actions → Security → Modify IAM role
   - Select `lightrag-ec2-role`

### Issue: S3 Access Denied
```
S3 upload failed: Access Denied
```

**Solution:**
1. **Check IAM policy permissions:**
   ```bash
   aws iam get-policy-version \
     --policy-arn arn:aws:iam::ACCOUNT:policy/lightrag-s3-policy \
     --version-id v1
   ```

2. **Verify bucket exists and region is correct:**
   ```bash
   aws s3 ls s3://lightrag-documents-production-6eaefccb --region me-south-1
   ```

### Issue: Wrong Region
```
S3 operations test failed: The bucket is in this region: me-south-1
```

**Solution:**
```bash
# Ensure AWS_REGION matches your bucket region
export AWS_REGION=me-south-1
echo "AWS_REGION=me-south-1" >> /app/LightRAG/.env
sudo systemctl restart lightrag-api
```

## Verification: Test S3 Upload

After fixing issues:

```bash
# Test upload with proper S3 response
curl -X 'POST' \
  'https://api.businessindunes.ai/documents/upload?ingest=true' \
  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@test-document.pdf'
```

**Expected response with S3:**
```json
{
  "status": "ok",
  "file_size": 1048576,
  "filename": "test-document.pdf",
  "storage_type": "s3",
  "s3_bucket": "lightrag-documents-production-6eaefccb",
  "s3_key": "documents/test-document.pdf",
  "s3_url": "s3://lightrag-documents-production-6eaefccb/documents/test-document.pdf",
  "ingestion": {...}
}
```

## Prevention: Environment Validation

Add to your deployment script:
```bash
#!/bin/bash
# deploy_with_s3_validation.sh

echo "🔍 Validating S3 configuration..."

# Check required variables
if [[ -z "$AWS_S3_BUCKET" ]]; then
  echo "❌ AWS_S3_BUCKET not set"
  exit 1
fi

# Test S3 access
if ! aws s3 ls "s3://$AWS_S3_BUCKET" >/dev/null 2>&1; then
  echo "❌ Cannot access S3 bucket: $AWS_S3_BUCKET"
  exit 1
fi

echo "✅ S3 configuration valid"
```