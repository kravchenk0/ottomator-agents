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

# Security Group
locals {
  ingress_ports = [
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