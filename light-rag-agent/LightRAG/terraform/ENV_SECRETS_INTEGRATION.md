# 🔑 ENV Secrets Integration with Terraform

## Overview

Terraform now automatically reads OpenAI secrets from the `.env` file to avoid duplication between application configuration and infrastructure deployment.

## How it Works

### 1. Automatic .env File Reading

The `read_env_secrets.tf` file contains logic to:
- Read the `../.env` file (relative to terraform directory)
- Parse environment variables 
- Extract `OPENAI_API_KEY`, `RAG_API_KEYS`, and optionally `RAG_JWT_SECRET`
- Use these values in infrastructure deployment

### 2. Fallback Mechanism

The system provides multiple fallback options:
```hcl
local {
  # Read from .env file, fallback to terraform variables, then empty string
  openai_api_key = lookup(local.env_vars, "OPENAI_API_KEY", var.openai_api_key != "" ? var.openai_api_key : "")
  rag_api_keys   = lookup(local.env_vars, "RAG_API_KEYS", var.rag_api_keys != "" ? var.rag_api_keys : "")
  
  # JWT secret: env file > terraform var > auto-generated
  rag_jwt_secret = var.rag_jwt_secret != "" ? var.rag_jwt_secret : (
    lookup(local.env_vars, "RAG_JWT_SECRET", "") != "" ? 
    lookup(local.env_vars, "RAG_JWT_SECRET", "") : 
    sha256("${local.openai_api_key}-${timestamp()}")
  )
}
```

## Usage

### Option 1: Use .env Only (Recommended)

1. Configure your `.env` file:
```bash
OPENAI_API_KEY=sk-proj-your-key-here
RAG_API_KEYS=your-api-keys-here
```

2. Run Terraform with minimal secrets.tfvars:
```bash
terraform apply -var-file="secrets.tfvars"
```

Your `secrets.tfvars` only needs:
```hcl
github_token = "your-github-token"
# OpenAI secrets automatically read from .env
```

### Option 2: Override in Terraform

If you need different values for infrastructure vs local development:

```hcl
# secrets.tfvars
github_token = "your-github-token"
openai_api_key = "sk-proj-production-key"  # Override .env value
rag_api_keys = "production-api-keys"       # Override .env value
```

### Option 3: Auto-generated JWT Secret

If you don't provide `rag_jwt_secret` in either .env or terraform vars, it will be auto-generated based on:
```
sha256(openai_api_key + timestamp)
```

## File Structure

```
LightRAG/
├── .env                              # Application secrets (NOT committed)
└── terraform/
    ├── read_env_secrets.tf          # .env parsing logic  
    ├── variables.tf                 # Now all secrets optional with defaults
    ├── main.tf                      # Uses local.* instead of var.*
    ├── secrets.tfvars               # Your actual secrets (NOT committed)
    └── secrets.tfvars.example       # Template with new approach
```

## Benefits

✅ **No Duplication**: Single source of truth for API keys in `.env`  
✅ **Flexibility**: Override in Terraform if needed  
✅ **Security**: Secrets marked as sensitive in Terraform  
✅ **Auto-generation**: JWT secrets generated if not provided  
✅ **Backwards Compatible**: Old secrets.tfvars still work  

## Migration Guide

### From Old Approach:
```hcl
# secrets.tfvars (OLD)
openai_api_key = "sk-proj-..."
rag_api_keys = "key1,key2,key3" 
rag_jwt_secret = "generated-secret"
github_token = "github_pat_..."
```

### To New Approach:
```hcl
# secrets.tfvars (NEW - minimal)
github_token = "github_pat_..."
# OpenAI secrets read from .env automatically!
```

```bash
# .env file (same as used by application)
OPENAI_API_KEY=sk-proj-...
RAG_API_KEYS=key1,key2,key3
```

## Testing

Validate the configuration:
```bash
cd terraform
terraform validate
terraform plan -var="github_token=test" -out=/dev/null
```

Check parsed values:
```bash
terraform console
> local.openai_api_key
> local.rag_api_keys
```

## Security Notes

- `.env` file should never be committed to git
- All secret variables marked as `sensitive = true`
- Terraform state file contains secrets - secure it appropriately
- Use different .env files for different environments if needed

## Troubleshooting

### Empty Values
If secrets appear empty, check:
1. `.env` file exists and is readable
2. Values don't have quotes in .env: `KEY=value` not `KEY="value"`
3. No spaces around `=`: `KEY=value` not `KEY = value`

### Permission Issues
Ensure Terraform can read `../.env` from the terraform directory:
```bash
cd terraform
ls -la ../.env  # Should be readable
```