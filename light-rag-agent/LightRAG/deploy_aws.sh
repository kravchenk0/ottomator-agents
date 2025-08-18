#!/bin/bash

# LightRAG AWS Deployment Script
# This script helps deploy LightRAG to AWS EC2

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="lightrag"
DOCKER_IMAGE_NAME="lightrag-api"
EC2_INSTANCE_TYPE="t3.medium"
EC2_VOLUME_SIZE="20"
AWS_REGION="us-east-1"
SECURITY_GROUP_NAME="lightrag-sg"
KEY_PAIR_NAME="lightrag-key"

echo -e "${BLUE}🚀 LightRAG AWS Deployment Script${NC}"
echo "=================================="

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI is not installed. Please install it first.${NC}"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo -e "${RED}❌ Docker is not running. Please start Docker first.${NC}"
    exit 1
fi

# Function to check if file exists
check_file() {
    if [ ! -f "$1" ]; then
        echo -e "${RED}❌ File not found: $1${NC}"
        exit 1
    fi
}

# Check required files
echo -e "${BLUE}📁 Checking required files...${NC}"
check_file "Dockerfile"
check_file "docker-compose.prod.yml"
check_file "env.production"

# Load environment variables
echo -e "${BLUE}🔧 Loading environment variables...${NC}"
if [ -f "env.production" ]; then
    export $(cat env.production | grep -v '^#' | xargs)
else
    echo -e "${YELLOW}⚠️  env.production not found, using default values${NC}"
fi

# Check required environment variables
if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${RED}❌ OPENAI_API_KEY is not set${NC}"
    exit 1
fi

if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo -e "${RED}❌ AWS credentials are not set${NC}"
    exit 1
fi

# Build Docker image
echo -e "${BLUE}🐳 Building Docker image...${NC}"
docker build -t $DOCKER_IMAGE_NAME .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Docker image built successfully${NC}"
else
    echo -e "${RED}❌ Failed to build Docker image${NC}"
    exit 1
fi

# Create security group
echo -e "${BLUE}🔒 Creating security group...${NC}"
aws ec2 create-security-group \
    --group-name $SECURITY_GROUP_NAME \
    --description "Security group for LightRAG API" \
    --region $AWS_REGION 2>/dev/null || echo -e "${YELLOW}⚠️  Security group already exists${NC}"

# Add security group rules
echo -e "${BLUE}🔓 Adding security group rules...${NC}"
aws ec2 authorize-security-group-ingress \
    --group-name $SECURITY_GROUP_NAME \
    --protocol tcp \
    --port 22 \
    --cidr 0.0.0.0/0 \
    --region $AWS_REGION 2>/dev/null || echo -e "${YELLOW}⚠️  SSH rule already exists${NC}"

aws ec2 authorize-security-group-ingress \
    --group-name $SECURITY_GROUP_NAME \
    --protocol tcp \
    --port 80 \
    --cidr 0.0.0.0/0 \
    --region $AWS_REGION 2>/dev/null || echo -e "${YELLOW}⚠️  HTTP rule already exists${NC}"

aws ec2 authorize-security-group-ingress \
    --group-name $SECURITY_GROUP_NAME \
    --protocol tcp \
    --port 443 \
    --cidr 0.0.0.0/0 \
    --region $AWS_REGION 2>/dev/null || echo -e "${YELLOW}⚠️  HTTPS rule already exists${NC}"

aws ec2 authorize-security-group-ingress \
    --group-name $SECURITY_GROUP_NAME \
    --protocol tcp \
    --port 8000 \
    --cidr 0.0.0.0/0 \
    --region $AWS_REGION 2>/dev/null || echo -e "${YELLOW}⚠️  API port rule already exists${NC}"

# Create key pair
echo -e "${BLUE}🔑 Creating key pair...${NC}"
aws ec2 create-key-pair \
    --key-name $KEY_PAIR_NAME \
    --query 'KeyMaterial' \
    --output text \
    --region $AWS_REGION > $KEY_PAIR_NAME.pem 2>/dev/null || echo -e "${YELLOW}⚠️  Key pair already exists${NC}"

if [ -f "$KEY_PAIR_NAME.pem" ]; then
    chmod 400 $KEY_PAIR_NAME.pem
    echo -e "${GREEN}✅ Key pair created: $KEY_PAIR_NAME.pem${NC}"
fi

# Get latest Amazon Linux 2 AMI
echo -e "${BLUE}🖼️  Getting latest Amazon Linux 2 AMI...${NC}"
AMI_ID=$(aws ec2 describe-images \
    --owners amazon \
    --filters "Name=name,Values=amzn2-ami-hvm-*-x86_64-gp2" "Name=state,Values=available" \
    --query "sort_by(Images, &CreationDate)[-1].ImageId" \
    --output text \
    --region $AWS_REGION)

echo -e "${GREEN}✅ Using AMI: $AMI_ID${NC}"

# Create EC2 instance
echo -e "${BLUE}🖥️  Creating EC2 instance...${NC}"
INSTANCE_ID=$(aws ec2 run-instances \
    --image-id $AMI_ID \
    --count 1 \
    --instance-type $EC2_INSTANCE_TYPE \
    --key-name $KEY_PAIR_NAME \
    --security-group-ids $(aws ec2 describe-security-groups --group-names $SECURITY_GROUP_NAME --query 'SecurityGroups[0].GroupId' --output text --region $AWS_REGION) \
    --block-device-mappings "[{\"DeviceName\":\"/dev/xvda\",\"Ebs\":{\"VolumeSize\":$EC2_VOLUME_SIZE,\"VolumeType\":\"gp3\",\"DeleteOnTermination\":true}}]" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$PROJECT_NAME}]" \
    --query 'Instances[0].InstanceId' \
    --output text \
    --region $AWS_REGION)

echo -e "${GREEN}✅ EC2 instance created: $INSTANCE_ID${NC}"

# Wait for instance to be running
echo -e "${BLUE}⏳ Waiting for instance to be running...${NC}"
aws ec2 wait instance-running --instance-ids $INSTANCE_ID --region $AWS_REGION

# Get public IP
echo -e "${BLUE}🌐 Getting public IP...${NC}"
PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids $INSTANCE_ID \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text \
    --region $AWS_REGION)

echo -e "${GREEN}✅ Instance IP: $PUBLIC_IP${NC}"

# Wait for SSH to be available
echo -e "${BLUE}⏳ Waiting for SSH to be available...${NC}"
until ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -i $KEY_PAIR_NAME.pem ec2-user@$PUBLIC_IP "echo 'SSH is ready'" 2>/dev/null; do
    echo "Waiting for SSH..."
    sleep 10
done

# Install Docker on EC2
echo -e "${BLUE}🐳 Installing Docker on EC2...${NC}"
ssh -i $KEY_PAIR_NAME.pem ec2-user@$PUBLIC_IP << 'EOF'
    # Update system
    sudo yum update -y
    
    # Install Docker
    sudo yum install -y docker
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -a -G docker ec2-user
    
    # Install Docker Compose
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    
    # Install git
    sudo yum install -y git
EOF

# Copy project files to EC2
echo -e "${BLUE}📁 Copying project files to EC2...${NC}"
scp -i $KEY_PAIR_NAME.pem -r . ec2-user@$PUBLIC_IP:~/lightrag

# Create production environment file on EC2
echo -e "${BLUE}🔧 Creating production environment file...${NC}"
ssh -i $KEY_PAIR_NAME.pem ec2-user@$PUBLIC_IP << EOF
    cd ~/lightrag
    cp env.production .env
    echo "OPENAI_API_KEY=$OPENAI_API_KEY" >> .env
    echo "AWS_REGION=$AWS_REGION" >> .env
    echo "API_CORS_ORIGINS=*" >> .env
    echo "APP_DEBUG=false" >> .env
    echo "API_ENABLE_DOCS=false" >> .env
EOF

# Start services on EC2
echo -e "${BLUE}🚀 Starting LightRAG services...${NC}"
ssh -i $KEY_PAIR_NAME.pem ec2-user@$PUBLIC_IP << 'EOF'
    cd ~/lightrag
    
    # Create necessary directories
    mkdir -p documents logs config
    
    # Start services
    docker-compose -f docker-compose.prod.yml up -d
    
    # Wait for services to be ready
    sleep 30
    
    # Check service status
    docker-compose -f docker-compose.prod.yml ps
EOF

# Test the API
echo -e "${BLUE}🧪 Testing the API...${NC}"
sleep 10
if curl -f "http://$PUBLIC_IP:8000/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ API is responding!${NC}"
else
    echo -e "${YELLOW}⚠️  API might still be starting up...${NC}"
fi

# Display deployment information
echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
echo "=================================="
echo -e "${BLUE}Instance ID:${NC} $INSTANCE_ID"
echo -e "${BLUE}Public IP:${NC} $PUBLIC_IP"
echo -e "${BLUE}SSH Command:${NC} ssh -i $KEY_PAIR_NAME.pem ec2-user@$PUBLIC_IP"
echo -e "${BLUE}API Health Check:${NC} http://$PUBLIC_IP:8000/health"
echo -e "${BLUE}API Endpoint:${NC} http://$PUBLIC_IP:8000"
echo ""
echo -e "${YELLOW}⚠️  Important:${NC}"
echo "1. Keep your key file safe: $KEY_PAIR_NAME.pem"
echo "2. Update your Lovable integration to use: http://$PUBLIC_IP:8000"
echo "3. Consider setting up a domain name and SSL certificate"
echo "4. Monitor your AWS costs and usage"
echo ""
echo -e "${BLUE}📚 Next steps:${NC}"
echo "1. Test the API endpoints"
echo "2. Insert your documents using the API"
echo "3. Update your website's JavaScript client"
echo "4. Set up monitoring and logging"
echo "5. Configure auto-scaling if needed" 