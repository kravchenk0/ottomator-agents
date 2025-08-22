# 🔒 Исправление Security Group для порта 8000

## 🚨 Проблема
При использовании ALB или когда `debug_open_app_port = false`, порт 8000 не открывается в Security Group, что приводит к ошибке 502 в браузере.

## 🔍 Причина
В `main.tf` логика Security Group блокирует порт 8000:
```hcl
# Порт 8000 добавляется ТОЛЬКО если:
ingress_ports_app = (!var.enable_alb || var.debug_open_app_port) ? [
  { from = 8000, to = 8000, description = "..." }
] : []
```

**Если `enable_alb = true` И `debug_open_app_port = false` → порт 8000 ЗАКРЫТ**

## ✅ Решения

### Решение 1: Быстрое (изменить переменную)
```bash
cd terraform/
# Установить debug_open_app_port = true
terraform apply -var="debug_open_app_port=true" -var-file="secrets.tfvars"
```

### Решение 2: Ручное правило (мгновенно)
```bash
# Получить Security Group ID
INSTANCE_ID=$(terraform output -raw instance_id)
SG_ID=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' --output text --region me-south-1)

# Добавить правило для порта 8000
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 8000 \
  --cidr 0.0.0.0/0 \
  --region me-south-1 \
  --description "LightRAG API direct access"
```

### Решение 3: Улучшенная логика (рекомендуется для production)

**Обновить `main.tf`:**
```hcl
# Улучшенная логика для порта 8000
locals {
  # Порт 8000 добавляется если:
  # 1. ALB отключён (прямой доступ) ИЛИ
  # 2. debug_open_app_port = true ИЛИ  
  # 3. enable_public_api = true (новая переменная)
  should_open_port_8000 = !var.enable_alb || var.debug_open_app_port || var.enable_public_api
  
  ingress_ports_app = local.should_open_port_8000 ? [
    { 
      from = 8000, 
      to = 8000, 
      description = var.enable_alb ? "API access via ALB" : "Direct API access"
    }
  ] : []
}
```

**Добавить в `variables.tf`:**
```hcl
variable "enable_public_api" {
  description = "Enable public access to port 8000 (even with ALB enabled)"
  type        = bool
  default     = true  # По умолчанию разрешить доступ
}
```

## 🚀 Применение исправлений

### Шаг 1: Проверить текущее состояние
```bash
cd terraform/
terraform output | grep -E "(public_ip|instance_id)"

# Проверить доступность API
PUBLIC_IP=$(terraform output -raw public_ip)
curl -v --connect-timeout 10 http://$PUBLIC_IP:8000/health
```

### Шаг 2: Применить быстрое решение
```bash
# Вариант A: Через Terraform
terraform apply -var="debug_open_app_port=true" -var-file="secrets.tfvars" -auto-approve

# Вариант B: Ручное правило (если нужно срочно)
./add_sg_rule.sh  # см. скрипт ниже
```

### Шаг 3: Проверить результат
```bash
# Проверить Security Group
INSTANCE_ID=$(terraform output -raw instance_id)
SG_ID=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID \
  --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' \
  --output text --region me-south-1)

aws ec2 describe-security-groups --group-ids $SG_ID \
  --query 'SecurityGroups[0].IpPermissions[?FromPort==`8000`]' \
  --region me-south-1

# Тест API
curl -s http://$PUBLIC_IP:8000/health | jq .
```

## 📋 Скрипт автоматического исправления

**Создать `fix_sg_port_8000.sh`:**
```bash
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
    echo "$EXISTING_RULES" | jq .
else
    echo "⚠️  Port 8000 rule does not exist. Adding..."
    
    # Добавить правило
    aws ec2 authorize-security-group-ingress \
      --group-id $SG_ID \
      --protocol tcp \
      --port 8000 \
      --cidr 0.0.0.0/0 \
      --region me-south-1 \
      --description "LightRAG API access (fixed)"
    
    echo "✅ Port 8000 rule added successfully!"
fi

# Проверить доступность API
echo "🧪 Testing API availability..."
if [ -n "$PUBLIC_IP" ]; then
    if curl -s --connect-timeout 10 http://$PUBLIC_IP:8000/health > /dev/null; then
        echo "✅ API is accessible at http://$PUBLIC_IP:8000"
        echo "🎉 Security Group fix completed successfully!"
    else
        echo "⚠️  API still not accessible. Check server status:"
        echo "   ssh -i ~/.ssh/id_rsa ec2-user@$PUBLIC_IP"
        echo "   docker logs lightrag-api"
    fi
else
    echo "⚠️  Public IP not available, check manually"
fi

echo ""
echo "📊 Final Security Group rules for port 8000:"
aws ec2 describe-security-groups --group-ids $SG_ID \
  --query 'SecurityGroups[0].IpPermissions[?FromPort==`8000`]' \
  --region me-south-1 --output table
```

## 🔒 Security рекомендации

### Для production среды:
1. **Ограничить CIDR**: Замените `0.0.0.0/0` на конкретные IP
2. **Использовать ALB + HTTPS**: Включите `enable_alb = true`
3. **Закрыть прямой доступ**: Установите `debug_open_app_port = false`

### Рекомендуемая конфигурация:
```hcl
# terraform.tfvars для production
enable_alb                = true
debug_open_app_port       = false
enable_public_api         = true    # Новая переменная
allowed_ingress_cidrs     = ["YOUR_OFFICE_IP/32", "YOUR_VPN_CIDR/24"]
domain_name               = "api.yourdomain.com"
certificate_domain        = "yourdomain.com"
```

## ✅ Проверка исправлений

После применения любого решения:

```bash
# 1. Проверить SG правила
aws ec2 describe-security-groups --group-ids <SG_ID> \
  --query 'SecurityGroups[0].IpPermissions[?FromPort==`8000`]'

# 2. Тест доступности
curl -v http://<PUBLIC_IP>:8000/health

# 3. Тест функциональности
curl -X POST http://<PUBLIC_IP>:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "test"}'
```

**Ожидаемый результат:** Статус 200, JSON ответ без ошибок 502.