# 🔧 Port 8000 Access Fix

## Problem
Ingress rules for port 8000 were not working automatically. Users had to manually add `0.0.0.0/0` CIDR rule in AWS Console to access the API.

## Root Cause
The Terraform configuration had this logic:
```hcl
# OLD LOGIC
ingress_ports_app = (!var.enable_alb || var.debug_open_app_port) ? [port 8000 rules] : []
```

With `enable_alb = true` and `debug_open_app_port` not set (defaults to `false`):
- `(!true || false)` = `(false || false)` = **false**
- Result: Port 8000 was NOT opened in Security Group

## Solution
Added new variable `enable_public_api` with proper production-ready logic:

### 1. New Variable in variables.tf
```hcl
variable "enable_public_api" {
  description = "Enable public access to port 8000 (even with ALB enabled). Useful for direct API access in production."
  type        = bool
  default     = true  # Default allows access for compatibility
}
```

### 2. Updated Logic in main.tf
```hcl
# NEW LOGIC - More flexible
should_open_port_8000 = !var.enable_alb || var.enable_public_api || var.debug_open_app_port

ingress_ports_app = local.should_open_port_8000 ? [
  { 
    from = 8000, 
    to = 8000, 
    description = (
      var.debug_open_app_port ? "DEBUG: Direct 8000 access" : 
      var.enable_public_api ? "Public API access" : 
      "LightRAG API"
    )
  }
] : []
```

### 3. Updated Configuration
**secrets.tfvars:**
```hcl
enable_alb        = true  # ALB for HTTPS
enable_public_api = true  # Direct API access
```

## Usage Scenarios

| Scenario | enable_alb | enable_public_api | debug_open_app_port | Port 8000 Access |
|----------|------------|-------------------|-------------------|------------------|
| **Production (Recommended)** | `true` | `true` | `false` | ✅ Both ALB + Direct |
| **ALB Only** | `true` | `false` | `false` | ✅ ALB Only |
| **Direct Only** | `false` | `true` | `false` | ✅ Direct Only |
| **Debug Mode** | `true` | `false` | `true` | ✅ Debug Access |

## Benefits

✅ **No More Manual Rules**: Port 8000 opens automatically  
✅ **Production Ready**: `enable_public_api` is the proper variable  
✅ **Backwards Compatible**: Existing setups continue working  
✅ **Flexible**: Can disable public access if needed  
✅ **Clear Intent**: Descriptive variable names  

## Migration

If you were using manual Security Group rules:
1. Remove manual `0.0.0.0/0` rule from AWS Console
2. Set `enable_public_api = true` in your tfvars
3. Run `terraform apply`

## Deployment

```bash
# Apply the fix
terraform apply -var-file="secrets.tfvars"

# Verify port 8000 is open
curl -v https://api.businessindunes.ai/health
curl -v http://YOUR-EIP:8000/health  # Direct access
```

## Security Notes

- **ALB + Direct**: Both work simultaneously, ALB provides HTTPS, direct provides HTTP
- **Production**: Use ALB for HTTPS certificates and load balancing
- **Development**: Direct access is fine for testing
- **Debug Flag**: Only use `debug_open_app_port = true` for temporary troubleshooting