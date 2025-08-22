#!/bin/bash
set -e

echo "🔧 Fixing Security Group for port 8000..."

# Получить данные из Terraform
cd "$(dirname "$0")"
if [ ! -f "terraform.tfstate" ]; then
    echo "❌ terraform.tfstate not found. Run terraform apply first."
    exit 1
fi

INSTANCE_ID=$(terraform output -raw instance_id 2>/dev/null || echo "")
PUBLIC_IP=$(terraform output -raw public_ip 2>/dev/null || echo "")

if [ -z "$INSTANCE_ID" ]; then
    echo "❌ Could not get instance_id from terraform output"
    exit 1
fi

# Получить Security Group ID
SG_ID=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID \
  --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' \
  --output text --region me-south-1)

echo "📋 Instance ID: $INSTANCE_ID"
echo "📋 Security Group ID: $SG_ID"
echo "📋 Public IP: $PUBLIC_IP"

# Проверить существующие правила для порта 8000
echo "🔍 Checking existing rules for port 8000..."
EXISTING_RULES=$(aws ec2 describe-security-groups --group-ids $SG_ID \
  --query 'SecurityGroups[0].IpPermissions[?FromPort==`8000`]' \
  --output json --region me-south-1)

if [ "$EXISTING_RULES" != "[]" ]; then
    echo "✅ Port 8000 rule already exists:"
    echo "$EXISTING_RULES" | jq . || echo "$EXISTING_RULES"
else
    echo "⚠️  Port 8000 rule does not exist. Adding..."
    
    # Добавить правило
    aws ec2 authorize-security-group-ingress \
      --group-id $SG_ID \
      --protocol tcp \
      --port 8000 \
      --cidr 0.0.0.0/0 \
      --region me-south-1 \
      --description "LightRAG API access (auto-fixed)" || {
        echo "❌ Failed to add Security Group rule. Possible reasons:"
        echo "   - Rule already exists"
        echo "   - Insufficient AWS permissions"
        echo "   - Invalid Security Group ID"
        exit 1
    }
    
    echo "✅ Port 8000 rule added successfully!"
fi

# Проверить доступность API
echo "🧪 Testing API availability..."
if [ -n "$PUBLIC_IP" ]; then
    sleep 2  # Дать время для применения правила
    if curl -s --connect-timeout 10 --max-time 20 http://$PUBLIC_IP:8000/health > /dev/null 2>&1; then
        echo "✅ API is accessible at http://$PUBLIC_IP:8000"
        echo "🎉 Security Group fix completed successfully!"
        
        # Показать краткую информацию о здоровье API
        echo ""
        echo "📊 API Health Check:"
        curl -s http://$PUBLIC_IP:8000/health | jq . 2>/dev/null || curl -s http://$PUBLIC_IP:8000/health
    else
        echo "⚠️  API still not accessible after fixing Security Group."
        echo "   This might be due to:"
        echo "   - Server not running inside instance"
        echo "   - Docker container issues"
        echo "   - Application startup problems"
        echo ""
        echo "🔍 Debugging steps:"
        echo "   1. SSH to instance: ssh -i ~/.ssh/id_rsa ec2-user@$PUBLIC_IP"
        echo "   2. Check docker: docker ps"
        echo "   3. Check logs: docker logs lightrag-api"
        echo "   4. Check port: netstat -tlnp | grep 8000"
    fi
else
    echo "⚠️  Public IP not available, check manually"
fi

echo ""
echo "📊 Final Security Group rules for port 8000:"
aws ec2 describe-security-groups --group-ids $SG_ID \
  --query 'SecurityGroups[0].IpPermissions[?FromPort==`8000`]' \
  --region me-south-1 --output table 2>/dev/null || \
aws ec2 describe-security-groups --group-ids $SG_ID \
  --query 'SecurityGroups[0].IpPermissions[?FromPort==`8000`]' \
  --region me-south-1

echo ""
echo "🚀 Next steps if API still not working:"
echo "   1. Check instance status: aws ec2 describe-instance-status --instance-ids $INSTANCE_ID --region me-south-1"
echo "   2. Check system logs: ssh ec2-user@$PUBLIC_IP 'sudo journalctl -u docker -n 50'"
echo "   3. Restart services: ssh ec2-user@$PUBLIC_IP 'sudo systemctl restart docker'"
echo "   4. Force container restart: ssh ec2-user@$PUBLIC_IP 'docker restart lightrag-api'"