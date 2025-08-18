# ⚡ Быстрый старт: LightRAG на AWS

## 🚀 Развертывание за 10 минут

### Вариант 1: Автоматический скрипт (Рекомендуется)

```bash
# 1. Настройте AWS credentials
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
export OPENAI_API_KEY="your_openai_key"

# 2. Запустите автоматическое развертывание
cd LightRAG
./deploy_aws.sh
```

### Вариант 2: Docker Compose

```bash
# 1. Создайте EC2 инстанс (t3.medium)
# 2. Скопируйте файлы
scp -r . ec2-user@your-ec2-ip:~/lightrag

# 3. Подключитесь и запустите
ssh ec2-user@your-ec2-ip
cd ~/lightrag
cp env.production .env
# Отредактируйте .env
docker-compose -f docker-compose.prod.yml up -d
```

### Вариант 3: Terraform

```bash
cd LightRAG/terraform
terraform init
terraform plan
terraform apply
```

## 🔧 Что создается

✅ **EC2 инстанс** (t3.medium, 20GB)  
✅ **Security Group** (порты 22, 80, 443, 8000)  
✅ **Docker + Docker Compose**  
✅ **LightRAG API** на порту 8000  
✅ **Redis** для кэширования  
✅ **Nginx** (опционально)  

## 🌐 Доступ

- **API**: `http://your-ec2-ip:8000`
- **Health Check**: `http://your-ec2-ip:8000/health`
- **SSH**: `ssh -i lightrag-key.pem ec2-user@your-ec2-ip`

## 📝 Обновление Lovable

```javascript
// В вашем JavaScript коде
const client = new LightRAGClient('http://your-ec2-ip:8000');
// или
new LovableLightRAGIntegration('http://your-ec2-ip:8000');
```

## 🚨 Важно

1. **Сохраните ключ** `lightrag-key.pem`
2. **Обновите .env** с вашими API ключами
3. **Настройте CORS** для вашего домена
4. **Мониторьте затраты** в AWS Console

## 📖 Подробная документация

См. `AWS_DEPLOYMENT.md` для полного руководства.
