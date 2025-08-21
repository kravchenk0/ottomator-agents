variable "github_token" {
  description = "GitHub Personal Access Token for private repo access"
  type        = string
  sensitive   = true
}
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "me-south-1"
}

variable "aws_profile" {
  description = "AWS shared config credential profile name (from ~/.aws/credentials)."
  type        = string
  default     = "default"
}

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "lightrag"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "subnet_cidr" {
  description = "CIDR block for subnet"
  type        = string
  default     = "10.0.1.0/24"
}

variable "secondary_subnet_cidr" {
  description = "CIDR block for secondary subnet (used when enable_alb=true)"
  type        = string
  default     = "10.0.2.0/24"
}

variable "availability_zone" {
  description = "Availability zone"
  type        = string
  default     = "me-south-1a"
}

variable "secondary_availability_zone" {
  description = "Secondary availability zone (required when enable_alb=true)"
  type        = string
  default     = "me-south-1b"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.medium"
}

variable "volume_size" {
  description = "Size of the root volume in GB"
  type        = number
  default     = 20
}

variable "ami_id" {
  description = "(Optional) Override AMI ID for the EC2 instance. Leave empty to use latest Amazon Linux 2 (kernel 5.10 x86_64) via SSM parameter."
  type        = string
  default     = ""
}

variable "use_amazon_linux_2023" {
  description = "If true and ami_id not set, use latest Amazon Linux 2023 AMI (al2023) instead of Amazon Linux 2"
  type        = bool
  default     = false
}
variable "openai_api_key" {
  description = "OpenAI API key"
  type        = string
}

variable "rag_jwt_secret" {
  description = "RAG JWT secret"
  type        = string
}

variable "rag_api_keys" {
  description = "Comma-separated list of API keys for /auth/token (RAG_API_KEYS)"
  type        = string
  default     = "" # оставить пустым => выдача токенов отключится (strict зависимость вернёт 503)
}

variable "domain_name" {
  description = "Domain name for the app"
  type        = string
  default     = ""
}

variable "app_subdomain" {
  description = "Subdomain for the app"
  type        = string
  default     = ""
}

variable "route53_zone_id" {
  description = "Route53 zone ID"
  type        = string
  default     = ""
}

variable "enable_alb" {
  description = "Enable ALB and HTTPS"
  type        = bool
  default     = false
}

variable "certificate_domain" {
  description = "Certificate domain for ACM"
  type        = string
  default     = ""
}

variable "alb_health_check_interval" {
  description = "Interval (seconds) for ALB target group health checks (5-300). Lower = faster detection, higher = less cost/noise."
  type        = number
  default     = 15
}

variable "alb_idle_timeout" {
  description = "ALB idle timeout in seconds (default AWS = 60). Increase if backend responses can exceed a minute without streaming."
  type        = number
  default     = 120
}

variable "create_vpc" {
  description = "Whether to create a new VPC"
  type        = bool
  default     = true
}

variable "existing_vpc_id" {
  description = "ID of existing VPC to use"
  type        = string
  default     = ""
}

variable "existing_subnet_id" {
  description = "ID of existing subnet to use"
  type        = string
  default     = ""
}

variable "existing_security_group_id" {
  description = "ID of existing security group to use"
  type        = string
  default     = ""
}

variable "create_key_pair" {
  description = "Whether to create a new key pair"
  type        = bool
  default     = true
}

variable "existing_key_name" {
  description = "Name of existing key pair to use"
  type        = string
  default     = ""
}

variable "create_eip" {
  description = "Whether to create an Elastic IP"
  type        = bool
  default     = false
}

variable "allowed_ingress_cidrs" {
  description = "List of allowed ingress CIDRs"
  type        = list(string)
  default     = []
}

variable "ssh_public_key_path" {
  description = "Path to the SSH public key file"
  type        = string
  default     = "~/.ssh/id_rsa.pub"
}

variable "ssh_private_key_path" {
  description = "Path to the SSH private key file"
  type        = string
  default     = "~/.ssh/id_rsa"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "tags" {
  description = "Additional tags for resources"
  type        = map(string)
  default = {
    Environment = "production"
    Project     = "lightrag"
    ManagedBy   = "terraform"
  }
} 

variable "debug_open_app_port" {
  description = "TEMP: If true, always open port 8000 to 0.0.0.0/0 in instance SG for debugging ALB 504 issues. Turn OFF after troubleshooting."
  type        = bool
  default     = false
}