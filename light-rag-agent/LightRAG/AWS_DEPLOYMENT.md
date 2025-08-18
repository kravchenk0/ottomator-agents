# (Перемещено) Смотрите docs/AWS_DEPLOYMENT.md
# 🚀 LightRAG AWS Deployment Guide

Полное руководство по развертыванию LightRAG на AWS с использованием Docker и различных инструментов.

## 📋 Варианты развертывания

### 1. **Docker Compose (Рекомендуется для начала)**
- Простое развертывание
- Автоматическая настройка
- Подходит для MVP и тестирования

### 2. **Terraform (Production)**
- Инфраструктура как код
- Автоматическое создание ресурсов
- Легко масштабировать и управлять

### 3. **AWS CLI Script (Автоматизация)**
- Полностью автоматизированное развертывание
- Создание EC2, security groups, key pairs
- Автоматическая настройка Docker

## 🐳 Вариант 1: Docker Compose

### Быстрый старт

```bash
# 1. Скопируйте файлы на EC2
scp -r . ec2-user@your-ec2-ip:~/lightrag

# 2. Подключитесь к EC2
ssh ec2-user@your-ec2-ip

# 3. Перейдите в директорию
cd ~/lightrag

# 4. Настройте переменные окружения
cp env.production .env
# Отредактируйте .env с вашими ключами

# 5. Запустите сервисы
docker-compose -f docker-compose.prod.yml up -d
```

### Проверка статуса

```bash
# Проверьте статус контейнеров
docker-compose -f docker-compose.prod.yml ps

# Проверьте логи
docker-compose -f docker-compose.prod.yml logs -f

# Проверьте здоровье API
curl http://localhost:8000/health
```

## 🏗️ Вариант 2: Terraform

### Предварительные требования

```bash
# Установите Terraform
brew install terraform  # macOS
# или скачайте с https://terraform.io

# Установите AWS CLI
brew install awscli     # macOS
# или скачайте с https://aws.amazon.com/cli/
```

### Настройка AWS

```bash
# Настройте AWS credentials
aws configure

# Или используйте переменные окружения
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
export AWS_DEFAULT_REGION="us-east-1"
```

### Развертывание

```bash
# 1. Перейдите в terraform директорию
cd terraform

# 2. Инициализируйте Terraform
terraform init

# 3. Просмотрите план
terraform plan

# 4. Примените конфигурацию
terraform apply

# 5. Получите выходные данные
terraform output
```

### Уничтожение инфраструктуры

```bash
terraform destroy
```

## 🔧 Вариант 3: AWS CLI Script

### Автоматическое развертывание

```bash
# 1. Сделайте скрипт исполняемым
chmod +x deploy_aws.sh

# 2. Настройте переменные окружения
export OPENAI_API_KEY="your_openai_key"
export AWS_ACCESS_KEY_ID="your_aws_key"
export AWS_SECRET_ACCESS_KEY="your_aws_secret"

# 3. Запустите развертывание
./deploy_aws.sh
```

### Что делает скрипт

- ✅ Создает security group с нужными портами
- ✅ Создает key pair для SSH доступа
- ✅ Запускает EC2 инстанс (t3.medium)
- ✅ Устанавливает Docker и Docker Compose
- ✅ Копирует проект файлы
- ✅ Запускает LightRAG сервисы
- ✅ Проверяет работоспособность API

## 🌐 Настройка домена и SSL

### 1. Настройте DNS

```bash
# Создайте A запись, указывающую на ваш EC2 IP
# example.com -> your-ec2-ip
```

### 2. Получите SSL сертификат

```bash
# Используйте Let's Encrypt
sudo certbot --nginx -d example.com

# Или AWS Certificate Manager
aws acm request-certificate \
  --domain-name example.com \
  --validation-method DNS
```

### 3. Обновите Nginx конфигурацию

```bash
# Скопируйте сертификаты
sudo cp /etc/letsencrypt/live/example.com/fullchain.pem /etc/nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/example.com/privkey.pem /etc/nginx/ssl/key.pem

# Перезапустите Nginx
sudo systemctl restart nginx
```

## 🔒 Безопасность

### 1. Обновите CORS настройки

```bash
# В .env файле
CORS_ALLOWED_ORIGINS=https://your-domain.com,https://www.your-domain.com
```

### 2. Настройте API ключи

```bash
# Сгенерируйте секретный ключ
openssl rand -hex 32

# Добавьте в .env
API_SECRET_KEY=your_generated_secret
```

### 3. Ограничьте доступ к EC2

```bash
# Обновите security group
aws ec2 revoke-security-group-ingress \
  --group-name lightrag-sg \
  --protocol tcp \
  --port 22 \
  --cidr 0.0.0.0/0

# Добавьте доступ только с вашего IP
aws ec2 authorize-security-group-ingress \
  --group-name lightrag-sg \
  --protocol tcp \
  --port 22 \
  --cidr your-ip/32
```

## 📊 Мониторинг

### 1. CloudWatch метрики

```bash
# Создайте dashboard для мониторинга
aws cloudwatch put-dashboard \
  --dashboard-name "LightRAG-Monitoring" \
  --dashboard-body file://cloudwatch-dashboard.json
```

### 2. Логирование

```bash
# Настройте CloudWatch Logs
aws logs create-log-group --log-group-name /lightrag/api
aws logs create-log-group --log-group-name /lightrag/nginx
```

### 3. Алерты

```bash
# Создайте SNS topic для алертов
aws sns create-topic --name lightrag-alerts

# Подпишитесь на уведомления
aws sns subscribe \
  --topic-arn your-topic-arn \
  --protocol email \
  --notification-endpoint your-email@example.com
```

## 💰 Оптимизация затрат

### 1. Выберите правильный тип инстанса

- **t3.micro** - для тестирования (бесплатный tier)
- **t3.small** - для небольшой нагрузки
- **t3.medium** - для production
- **c5.large** - для высокой производительности

### 2. Используйте Spot Instances

```bash
# В Terraform
resource "aws_spot_instance_request" "lightrag" {
  spot_price = "0.05"  # Максимальная цена
  # ... остальные настройки
}
```

### 3. Автоматическое масштабирование

```bash
# Создайте Auto Scaling Group
aws autoscaling create-auto-scaling-group \
  --auto-scaling-group-name lightrag-asg \
  --min-size 1 \
  --max-size 3 \
  --desired-capacity 1
```

## 🚨 Troubleshooting

### Частые проблемы

1. **API не отвечает**
   ```bash
   # Проверьте статус контейнеров
   docker ps
   
   # Проверьте логи
   docker logs lightrag-api-prod
   
   # Проверьте порты
   netstat -tlnp | grep 8000
   ```

2. **CORS ошибки**
   ```bash
   # Обновите CORS настройки в .env
   CORS_ALLOWED_ORIGINS=https://your-domain.com
   
   # Перезапустите сервисы
   docker-compose restart
   ```

3. **Недостаточно памяти**
   ```bash
   # Увеличьте размер инстанса
   aws ec2 modify-instance-attribute \
     --instance-id your-instance-id \
     --instance-type Value=t3.large
   ```

### Полезные команды

```bash
# SSH в инстанс
ssh -i your-key.pem ec2-user@your-ec2-ip

# Проверьте использование ресурсов
htop
df -h
free -h

# Проверьте Docker
docker system df
docker stats

# Перезапустите сервисы
docker-compose -f docker-compose.prod.yml restart
```

## 📈 Масштабирование

### 1. Горизонтальное масштабирование

```bash
# Увеличьте количество API контейнеров
docker-compose -f docker-compose.prod.yml up -d --scale lightrag-api=3
```

### 2. Load Balancer

```bash
# Создайте Application Load Balancer
aws elbv2 create-load-balancer \
  --name lightrag-alb \
  --subnets subnet-12345678 subnet-87654321
```

### 3. Auto Scaling

```bash
# Создайте Launch Template
aws ec2 create-launch-template \
  --launch-template-name lightrag-lt \
  --version-description v1
```

## 🎯 Следующие шаги

1. **Настройте CI/CD pipeline**
2. **Добавьте мониторинг и алерты**
3. **Настройте backup стратегию**
4. **Реализуйте disaster recovery**
5. **Оптимизируйте производительность**

## 📞 Поддержка

- Создайте Issue в репозитории
- Проверьте AWS CloudTrail для отладки
- Используйте AWS Support (если у вас есть план)
- Обратитесь к сообществу DevOps

## 📚 Дополнительные ресурсы

- [AWS EC2 Documentation](https://docs.aws.amazon.com/ec2/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/) 