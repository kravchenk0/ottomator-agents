variable "github_token" {
  description = "GitHub Personal Access Token for private repo access"
  type        = string
  sensitive   = true
}
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-north-1"
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

variable "availability_zone" {
  description = "Availability zone"
  type        = string
  default     = "eu-north-1a"
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
  description = "AMI ID for the EC2 instance"
  type        = string
  default     = "ami-0b72d0ebb7e8a51a6" # Amazon Linux 2 in eu-north-1
}
variable "openai_api_key" {
  description = "OpenAI API key"
  type        = string
}

variable "rag_jwt_secret" {
  description = "RAG JWT secret"
  type        = string
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