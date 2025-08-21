terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile
}

# Latest Amazon Linux 2 kernel 5.10 x86_64 AMI via public SSM parameter (region-specific automatically).
# If var.ami_id is provided (non-empty), that value takes precedence (e.g., for a custom baked image).
data "aws_ssm_parameter" "amzn2" {
  name = "/aws/service/ami-amazon-linux-latest/amzn2-ami-kernel-5.10-hvm-x86_64-gp2"
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
  # Если включён ALB, инстанс не должен быть публично доступен на 80/443/8000.
  # Оставляем только SSH (22) для администрирования. Доступ на 8000 даёт ALB через отдельное SG правило.
  ingress_ports = var.enable_alb ? [
    { from = 22, to = 22, description = "SSH" }
  ] : [
    { from = 22,  to = 22,  description = "SSH" },
    { from = 80,  to = 80,  description = "HTTP" },
    { from = 443, to = 443, description = "HTTPS" },
    { from = 8000, to = 8000, description = "LightRAG API" },
  ]
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

# Key Pair
resource "aws_key_pair" "lightrag_key" {
  key_name   = "${var.project_name}-key"
  public_key = file(var.ssh_public_key_path)
}

# EC2 Instance
resource "aws_instance" "lightrag_instance" {
  ami                    = var.ami_id != "" ? var.ami_id : data.aws_ssm_parameter.amzn2.value
  instance_type          = var.instance_type
  key_name               = aws_key_pair.lightrag_key.key_name
  subnet_id              = aws_subnet.lightrag_subnet.id
  vpc_security_group_ids = [aws_security_group.lightrag_sg.id]

  root_block_device {
    volume_size = var.volume_size
    volume_type = "gp3"
  }

  # user_data: НЕ base64encode — провайдер сам кодирует. Иначе размер удваивается и превышает лимит 16KB.
  user_data = templatefile("${path.module}/user_data.sh", {
    project_name                = var.project_name
    OPENAI_API_KEY              = var.openai_api_key
    OPENAI_MODEL                = "gpt-5-mini"
    OPENAI_TEMPERATURE          = 0.0
    RAG_WORKING_DIR             = "/app/documents"
    RAG_EMBEDDING_MODEL         = "gpt-5-mini"
    RAG_LLM_MODEL               = "gpt-5-mini"
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
    API_SECRET_KEY              = var.rag_jwt_secret
    CORS_ALLOWED_ORIGINS        = "*"
    GITHUB_TOKEN                = var.github_token
  RAG_JWT_SECRET              = var.rag_jwt_secret
  ALLOWED_INGRESS_CIDRS       = join(" ", var.allowed_ingress_cidrs)
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
    interval            = 30
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