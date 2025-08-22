terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.1"
    }
  }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile
}

# Amazon Linux AMIs via SSM parameters (region-specific automatically).
#  - Amazon Linux 2 (kernel 5.10) default
#  - Amazon Linux 2023 (optionally via var.use_amazon_linux_2023)
# If var.ami_id provided (non-empty) it always takes precedence.
data "aws_ssm_parameter" "amzn2" {
  name = "/aws/service/ami-amazon-linux-latest/amzn2-ami-kernel-5.10-hvm-x86_64-gp2"
}

data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

# VPC and Networking
resource "aws_vpc" "lightrag_vpc" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.project_name}-vpc"
  }
}

resource "aws_subnet" "lightrag_subnet" {
  vpc_id            = aws_vpc.lightrag_vpc.id
  cidr_block        = var.subnet_cidr
  availability_zone = var.availability_zone

  tags = {
    Name = "${var.project_name}-subnet"
  }
}

resource "aws_subnet" "lightrag_subnet_secondary" {
  count             = var.enable_alb ? 1 : 0
  vpc_id            = aws_vpc.lightrag_vpc.id
  cidr_block        = var.secondary_subnet_cidr
  availability_zone = var.secondary_availability_zone

  tags = {
    Name = "${var.project_name}-subnet-secondary"
  }
}

resource "aws_internet_gateway" "lightrag_igw" {
  vpc_id = aws_vpc.lightrag_vpc.id

  tags = {
    Name = "${var.project_name}-igw"
  }
}

resource "aws_route_table" "lightrag_rt" {
  vpc_id = aws_vpc.lightrag_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.lightrag_igw.id
  }

  tags = {
    Name = "${var.project_name}-rt"
  }
}

resource "aws_route_table_association" "lightrag_rta" {
  subnet_id      = aws_subnet.lightrag_subnet.id
  route_table_id = aws_route_table.lightrag_rt.id
}

resource "aws_route_table_association" "lightrag_rta_secondary" {
  count          = var.enable_alb ? 1 : 0
  subnet_id      = aws_subnet.lightrag_subnet_secondary[0].id
  route_table_id = aws_route_table.lightrag_rt.id
}

# Security Group
locals {
  # Base ingress rules: always include SSH
  ingress_ports_base = [
    { from = 22, to = 22, description = "SSH" }
  ]
  
  # Add HTTP/HTTPS ports only if ALB is disabled (direct access mode)
  ingress_ports_web = var.enable_alb ? [] : [
    { from = 80,  to = 80,  description = "HTTP" },
    { from = 443, to = 443, description = "HTTPS" }
  ]
  
  # Add port 8000 if: ALB disabled (direct mode) OR enable_public_api is true OR debug_open_app_port is true
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
  
  # Combine all ingress rules
  ingress_ports = concat(
    local.ingress_ports_base,
    local.ingress_ports_web, 
    local.ingress_ports_app
  )
  
  effective_ingress_cidrs = length(var.allowed_ingress_cidrs) > 0 ? var.allowed_ingress_cidrs : ["0.0.0.0/0"]
}

resource "aws_security_group" "lightrag_sg" {
  name        = "${var.project_name}-sg"
  description = "Security group for LightRAG API"
  vpc_id      = aws_vpc.lightrag_vpc.id

  dynamic "ingress" {
    for_each = { for p in local.ingress_ports : p.from => p }
    content {
      description = ingress.value.description
      from_port   = ingress.value.from
      to_port     = ingress.value.to
      protocol    = "tcp"
      cidr_blocks = local.effective_ingress_cidrs
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-sg"
  }
}

# S3 Bucket for Document Storage
resource "aws_s3_bucket" "lightrag_documents" {
  bucket = "${var.project_name}-documents-${var.environment}-${random_id.bucket_suffix.hex}"

  tags = merge(var.tags, {
    Name        = "${var.project_name}-documents"
    Purpose     = "Document storage for LightRAG ingestion"
    Environment = var.environment
  })
}

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket_versioning" "lightrag_documents" {
  count  = var.enable_s3_versioning ? 1 : 0
  bucket = aws_s3_bucket.lightrag_documents.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "lightrag_documents" {
  bucket = aws_s3_bucket.lightrag_documents.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "lightrag_documents" {
  bucket = aws_s3_bucket.lightrag_documents.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "lightrag_documents" {
  bucket = aws_s3_bucket.lightrag_documents.id

  rule {
    id     = "document_lifecycle"
    status = "Enabled"

    # Apply to all objects with the document prefix
    filter {
      prefix = var.s3_document_prefix
    }

    # Move to Infrequent Access after configured days
    transition {
      days          = var.s3_lifecycle_ia_days
      storage_class = "STANDARD_IA"
    }

    # Move to Glacier after configured days  
    transition {
      days          = var.s3_lifecycle_glacier_days
      storage_class = "GLACIER"
    }

    # Delete after retention period (if configured)
    dynamic "expiration" {
      for_each = var.s3_document_retention_days > 0 ? [1] : []
      content {
        days = var.s3_document_retention_days
      }
    }
  }
}

# IAM Role for EC2 to access S3
resource "aws_iam_role" "lightrag_ec2_role" {
  name = "${var.project_name}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_policy" "lightrag_s3_policy" {
  name        = "${var.project_name}-s3-policy"
  description = "Policy for LightRAG to access S3 documents bucket"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject", 
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = [
          aws_s3_bucket.lightrag_documents.arn,
          "${aws_s3_bucket.lightrag_documents.arn}/*"
        ]
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "lightrag_s3_policy" {
  role       = aws_iam_role.lightrag_ec2_role.name
  policy_arn = aws_iam_policy.lightrag_s3_policy.arn
}

# Attach SSM policy for systems manager access
resource "aws_iam_role_policy_attachment" "lightrag_ssm_policy" {
  role       = aws_iam_role.lightrag_ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "lightrag_profile" {
  name = "${var.project_name}-profile"
  role = aws_iam_role.lightrag_ec2_role.name

  tags = var.tags
}

# Key Pair
resource "aws_key_pair" "lightrag_key" {
  key_name   = "${var.project_name}-key"
  public_key = file(var.ssh_public_key_path)
}

# EC2 Instance
resource "aws_instance" "lightrag_instance" {
  ami = var.ami_id != "" ? var.ami_id : (var.use_amazon_linux_2023 ? data.aws_ssm_parameter.al2023.value : data.aws_ssm_parameter.amzn2.value)
  instance_type               = var.instance_type
  key_name                    = aws_key_pair.lightrag_key.key_name
  subnet_id                   = aws_subnet.lightrag_subnet.id
  vpc_security_group_ids      = [aws_security_group.lightrag_sg.id]
  iam_instance_profile        = aws_iam_instance_profile.lightrag_profile.name
  user_data_replace_on_change = true

  root_block_device {
    volume_size = var.volume_size
    volume_type = "gp3"
  }

  # user_data: НЕ base64encode — провайдер сам кодирует. Иначе размер удваивается и превышает лимит 16KB.
  user_data = templatefile("${path.module}/user_data.sh", {
    project_name                = var.project_name
    OPENAI_API_KEY              = local.openai_api_key
    OPENAI_MODEL                = "gpt-5-mini"
    OPENAI_TEMPERATURE          = 0.1
    RAG_WORKING_DIR             = "/app/documents"
    RAG_EMBEDDING_MODEL         = "text-embedding-3-large"
    RAG_LLM_MODEL               = "gpt-5-mini"
    OPENAI_FALLBACK_MODELS      = "gpt-4.1,gpt-4o-mini"
    RAG_RERANK_ENABLED          = true
    RAG_BATCH_SIZE              = 20
    RAG_MAX_DOCS_FOR_RERANK     = 20
    RAG_CHUNK_SIZE              = 1000
    RAG_CHUNK_OVERLAP           = 200
    APP_DEBUG                   = false
    APP_LOG_LEVEL               = "INFO"
    APP_MAX_CONVERSATION_HISTORY = 100
    APP_ENABLE_STREAMING        = true
    API_HOST                    = "0.0.0.0"
    API_PORT                    = 8000
    API_CORS_ORIGINS            = "*"
    API_ENABLE_DOCS             = false
    API_RATE_LIMIT              = 100
    API_MAX_REQUEST_SIZE        = "10MB"
    API_SECRET_KEY              = local.rag_jwt_secret
    CORS_ALLOWED_ORIGINS        = "*"
    GITHUB_TOKEN                = var.github_token
  RAG_JWT_SECRET              = local.rag_jwt_secret
  RAG_API_KEYS                = local.rag_api_keys
  ALLOWED_INGRESS_CIDRS       = join(" ", var.allowed_ingress_cidrs)
  AWS_S3_BUCKET               = aws_s3_bucket.lightrag_documents.bucket
  AWS_REGION                  = var.aws_region
  S3_DOCUMENT_PREFIX          = var.s3_document_prefix
  })

  tags = {
    Name = "${var.project_name}-instance"
  }

  depends_on = [aws_internet_gateway.lightrag_igw]
}

# Elastic IP
resource "aws_eip" "lightrag_eip" {
  instance = aws_instance.lightrag_instance.id
  domain   = "vpc"

  tags = {
    Name = "${var.project_name}-eip"
  }
}

# Outputs
output "instance_id" {
  description = "ID of the EC2 instance"
  value       = aws_instance.lightrag_instance.id
}

output "public_ip" {
  description = "Public IP address of the EC2 instance"
  value       = aws_eip.lightrag_eip.public_ip
}

output "ssh_command" {
  description = "SSH command to connect to the instance"
  value       = "ssh -i ${var.ssh_private_key_path} ec2-user@${aws_eip.lightrag_eip.public_ip}"
}

output "api_endpoint" {
  description = "API endpoint URL"
  value       = "http://${aws_eip.lightrag_eip.public_ip}:8000"
}

output "health_check_url" {
  description = "Health check URL"
  value       = "http://${aws_eip.lightrag_eip.public_ip}:8000/health"
}

output "s3_bucket_name" {
  description = "S3 bucket name for documents"
  value       = aws_s3_bucket.lightrag_documents.bucket
}

output "s3_bucket_arn" {
  description = "S3 bucket ARN for documents"
  value       = aws_s3_bucket.lightrag_documents.arn
}

output "iam_role_arn" {
  description = "IAM role ARN for EC2 instance"
  value       = aws_iam_role.lightrag_ec2_role.arn
} 

# -----------------------------
# Optional DNS (Route53) setup
# Exposes the API via domain/subdomain if domain_name provided.
# Logic:
#  - If var.route53_zone_id supplied -> use existing hosted zone
#  - Else if var.domain_name set -> create a new public hosted zone
#  - Create A record pointing to instance (EIP if present)
# NOTE: variable create_eip currently not enforced in code above (EIP resource always created).
#       Record uses the Elastic IP for stability.
# -----------------------------

locals {
  fqdn = var.domain_name != "" ? (var.app_subdomain != "" ? "${var.app_subdomain}.${var.domain_name}" : var.domain_name) : ""
}

data "aws_route53_zone" "existing" {
  count  = var.route53_zone_id != "" && var.domain_name != "" ? 1 : 0
  zone_id = var.route53_zone_id
}

resource "aws_route53_zone" "this" {
  count = var.route53_zone_id == "" && var.domain_name != "" ? 1 : 0
  name  = var.domain_name
}

resource "aws_route53_record" "api_a" {
  # Создаём простую A-запись только если задан fqdn и ALB отключён
  count   = local.fqdn != "" && !var.enable_alb ? 1 : 0
  zone_id = var.route53_zone_id != "" ? data.aws_route53_zone.existing[0].zone_id : aws_route53_zone.this[0].zone_id
  name    = local.fqdn
  type    = "A"
  ttl     = 300
  records = [aws_eip.lightrag_eip.public_ip]

  depends_on = [aws_eip.lightrag_eip]
}

# Alias A record на ALB при включённом enable_alb
resource "aws_route53_record" "api_alias" {
  count   = local.fqdn != "" && var.enable_alb ? 1 : 0
  zone_id = var.route53_zone_id != "" ? data.aws_route53_zone.existing[0].zone_id : aws_route53_zone.this[0].zone_id
  name    = local.fqdn
  type    = "A"
  alias {
    name                   = aws_lb.lightrag_alb[0].dns_name
    zone_id                = aws_lb.lightrag_alb[0].zone_id
    evaluate_target_health = false
  }
}

output "api_fqdn" {
  description = "FQDN for the API (DNS record)"
  value       = local.fqdn != "" ? local.fqdn : null
}

output "api_fqdn_url" {
  description = "Base URL served over HTTP (enable ALB/HTTPS for TLS)"
  value       = local.fqdn != "" && !var.enable_alb ? "http://${local.fqdn}:8000" : null
}

# -----------------------------
# ALB + ACM (optional, enable with var.enable_alb=true)
# -----------------------------

locals {
  certificate_domain = var.certificate_domain != "" ? var.certificate_domain : local.fqdn
}

# Security group for ALB
resource "aws_security_group" "alb_sg" {
  count       = var.enable_alb ? 1 : 0
  name        = "${var.project_name}-alb-sg"
  description = "ALB SG"
  vpc_id      = aws_vpc.lightrag_vpc.id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${var.project_name}-alb-sg" }
}

# Suppress direct public ingress to port 8000 when ALB enabled by removing that rule from the dynamic block
# Additional SG rule to allow ALB -> Instance on 8000
resource "aws_security_group_rule" "instance_from_alb_8000" {
  count                    = var.enable_alb ? 1 : 0
  type                     = "ingress"
  from_port                = 8000
  to_port                  = 8000
  protocol                 = "tcp"
  security_group_id        = aws_security_group.lightrag_sg.id
  source_security_group_id = aws_security_group.alb_sg[0].id
  description              = "ALB to app port"
  # Явная зависимость: сначала должен существовать SG ALB, затем правило
  depends_on = [aws_security_group.alb_sg]
}

# ACM Certificate (DNS validation)
resource "aws_acm_certificate" "api_cert" {
  count                     = var.enable_alb && local.certificate_domain != "" ? 1 : 0
  domain_name               = local.certificate_domain
  validation_method         = "DNS"
  subject_alternative_names = local.certificate_domain == local.fqdn ? [] : [local.fqdn]
  lifecycle { create_before_destroy = true }
  tags = { Name = "${var.project_name}-cert" }
}

resource "aws_route53_record" "cert_validation" {
  for_each = var.enable_alb && local.certificate_domain != "" ? {
    for dvo in aws_acm_certificate.api_cert[0].domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      record = dvo.resource_record_value
    }
  } : {}
  name    = each.value.name
  type    = each.value.type
  zone_id = var.route53_zone_id != "" ? data.aws_route53_zone.existing[0].zone_id : aws_route53_zone.this[0].zone_id
  records = [each.value.record]
  ttl     = 300
}

resource "aws_acm_certificate_validation" "api_cert_validation" {
  count                   = var.enable_alb && local.certificate_domain != "" ? 1 : 0
  certificate_arn         = aws_acm_certificate.api_cert[0].arn
  validation_record_fqdns = [for r in aws_route53_record.cert_validation : r.fqdn]
}

# Target group
resource "aws_lb_target_group" "lightrag_tg" {
  count    = var.enable_alb ? 1 : 0
  name     = "${var.project_name}-tg"
  port     = 8000
  protocol = "HTTP"
  vpc_id   = aws_vpc.lightrag_vpc.id
  health_check {
  path                = "/health"
  matcher             = "200"
  interval            = var.alb_health_check_interval
  healthy_threshold   = 2
  unhealthy_threshold = 3
  timeout             = 5
  }
}

resource "aws_lb_target_group_attachment" "tg_attachment" {
  count            = var.enable_alb ? 1 : 0
  target_group_arn = aws_lb_target_group.lightrag_tg[0].arn
  target_id        = aws_instance.lightrag_instance.id
  port             = 8000
}

resource "aws_lb" "lightrag_alb" {
  count               = var.enable_alb ? 1 : 0
  name                = "${var.project_name}-alb"
  internal            = false
  load_balancer_type  = "application"
  security_groups     = [aws_security_group.alb_sg[0].id]
  subnets             = [aws_subnet.lightrag_subnet.id, aws_subnet.lightrag_subnet_secondary[0].id]
  enable_deletion_protection = false
  idle_timeout        = var.alb_idle_timeout
  tags = { Name = "${var.project_name}-alb" }
}

resource "aws_lb_listener" "http_redirect" {
  count             = var.enable_alb ? 1 : 0
  load_balancer_arn = aws_lb.lightrag_alb[0].arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  count             = var.enable_alb ? 1 : 0
  load_balancer_arn = aws_lb.lightrag_alb[0].arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-2016-08"
  certificate_arn   = aws_acm_certificate_validation.api_cert_validation[0].certificate_arn
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.lightrag_tg[0].arn
  }
  depends_on = [aws_acm_certificate_validation.api_cert_validation]
}

output "alb_dns_name" {
  value       = var.enable_alb ? aws_lb.lightrag_alb[0].dns_name : null
  description = "ALB DNS name"
}
output "api_https_url" {
  value       = var.enable_alb && local.fqdn != "" ? "https://${local.fqdn}" : null
  description = "HTTPS base URL via ALB"
}