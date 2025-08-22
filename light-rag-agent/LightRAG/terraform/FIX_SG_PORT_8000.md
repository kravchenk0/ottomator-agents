# Исправление проблемы с портом 8000 в Security Group

## Проблема
Порт 8000 не добавляется в ingress правила Security Group, из-за чего API недоступен извне.

## ✅ Причина и исправление

### Причина:
В `terraform.tfvars` отсутствовала переменная `debug_open_app_port = true`, которая необходима для открытия порта 8000 когда включен ALB или для отладки.

### Исправления в конфигурации:

#### 1. В terraform.tfvars добавлена переменная:
```hcl
# === Networking Security ===
allowed_ingress_cidrs = ["0.0.0.0/0"]  # RESTRICT IN PRODUCTION
debug_open_app_port   = true           # Opens port 8000 for direct access
```

#### 2. В main.tf улучшена логика Security Group:
```hcl
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
  
  # Add port 8000 if: ALB disabled (direct mode) OR debug_open_app_port is true
  ingress_ports_app = (!var.enable_alb || var.debug_open_app_port) ? [
    { from = 8000, to = 8000, description = var.debug_open_app_port ? "DEBUG: Direct 8000 access" : "LightRAG API" }
  ] : []
  
  # Combine all ingress rules
  ingress_ports = concat(
    local.ingress_ports_base,
    local.ingress_ports_web, 
    local.ingress_ports_app
  )
}
```

#### 3. Обновлены переменные окружения для правильных моделей:
```hcl
OPENAI_MODEL           = "gpt-5-mini"
RAG_EMBEDDING_MODEL    = "text-embedding-3-large"  
RAG_LLM_MODEL          = "gpt-5-mini"
OPENAI_FALLBACK_MODELS = "gpt-4.1,gpt-4o-mini"
```

## 🚀 Как применить исправления

### Вариант 1: Terraform Apply (рекомендуется)
```bash
cd terraform/
terraform plan -var-file="secrets.tfvars"
terraform apply -var-file="secrets.tfvars"
```

### Вариант 2: Ручное изменение Security Group (быстро)
```bash
# Получить Security Group ID
INSTANCE_ID=$(terraform output -raw instance_id)
SG_ID=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' --output text)

# Добавить правило для порта 8000
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 8000 \
  --cidr 0.0.0.0/0 \
  --region me-south-1
```

### Вариант 3: Обновить только переменные (если Terraform уже запущен)
```bash
# Установить переменную и пересоздать план
cd terraform/
terraform apply -var="debug_open_app_port=true" -var-file="secrets.tfvars"
```

## 📊 Проверка результата

После применения исправлений:

### 1. Проверить Security Group Rules:
```bash
SG_ID=$(terraform output -json | jq -r '.lightrag_sg_id.value // empty')
if [ -z "$SG_ID" ]; then
  INSTANCE_ID=$(terraform output -raw instance_id)
  SG_ID=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' --output text)
fi

aws ec2 describe-security-groups --group-ids $SG_ID --query 'SecurityGroups[0].IpPermissions[?FromPort==`8000`]'
```

Должен показать:
```json
[
  {
    "FromPort": 8000,
    "IpProtocol": "tcp",
    "IpRanges": [
      {
        "CidrIp": "0.0.0.0/0",
        "Description": "DEBUG: Direct 8000 access"
      }
    ],
    "ToPort": 8000
  }
]
```

### 2. Проверить доступность API:
```bash
PUBLIC_IP=$(terraform output -raw public_ip)
curl -v http://$PUBLIC_IP:8000/health
```

Должен вернуть статус 200 и JSON с health информацией.

### 3. Проверить переменные окружения в контейнере:
```bash
ssh -i ~/.ssh/id_rsa ec2-user@$PUBLIC_IP "docker exec lightrag-api printenv | grep -E '(OPENAI_MODEL|RAG_.*_MODEL)'"
```

Должен показать:
```
OPENAI_MODEL=gpt-5-mini
RAG_LLM_MODEL=gpt-5-mini
RAG_EMBEDDING_MODEL=text-embedding-3-large
```

## 🛡️ Security Group Rules Matrix

После исправления, в зависимости от конфигурации:

| Scenario | ALB | debug_open_app_port | SSH (22) | HTTP (80) | HTTPS (443) | API (8000) |
|----------|-----|-------------------|----------|-----------|-------------|-------------|
| Direct Access | false | false | ✅ | ✅ | ✅ | ✅ |
| ALB Mode | true | false | ✅ | ❌ | ❌ | ❌ (ALB only) |
| ALB + Debug | true | true | ✅ | ❌ | ❌ | ✅ (Debug) |

## ⚠️ Важные заметки

1. **Производственная безопасность**: После отладки установите `debug_open_app_port = false` и используйте ALB с HTTPS
2. **CIDR ограничения**: Замените `0.0.0.0/0` на конкретные IP/подсети в производственной среде  
3. **ALB Health Checks**: Убедитесь что ALB может достучаться до инстанса на порту 8000 через внутреннее SG правило

## 🎯 Результат
После применения исправлений:
- ✅ Порт 8000 открыт для внешнего доступа
- ✅ Security Group правила корректно настроены
- ✅ API доступен по `http://PUBLIC_IP:8000`
- ✅ Используются правильные модели OpenAI