#!/usr/bin/env bash
set -euo pipefail
IP="${1:-}"  # целевой IP
if [[ -z "$IP" ]]; then
  echo "Usage: $0 <ip_or_hostname>" >&2
  exit 1
fi
KNOWN_HOSTS_FILE="$HOME/.ssh/known_hosts"
TS=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="${KNOWN_HOSTS_FILE}.backup-${TS}"
if [[ ! -f "$KNOWN_HOSTS_FILE" ]]; then
  echo "[INFO] known_hosts не найден, создаю пустой." >&2
  mkdir -p "$HOME/.ssh"
  touch "$KNOWN_HOSTS_FILE"
  chmod 600 "$KNOWN_HOSTS_FILE"
fi
cp "$KNOWN_HOSTS_FILE" "$BACKUP_FILE"
echo "[INFO] Резервная копия: $BACKUP_FILE"
# Найти существующие совпадения
if ssh-keygen -F "$IP" >/dev/null 2>&1; then
  echo "[INFO] Удаляю старые записи для $IP"
  ssh-keygen -R "$IP" >/dev/null
else
  echo "[INFO] Старых записей для $IP не найдено"
fi
# Скан новых ключей (ED25519 и RSA)
SCAN_OUTPUT=$(ssh-keyscan -T 5 -H "$IP" 2>/dev/null || true)
if [[ -z "$SCAN_OUTPUT" ]]; then
  echo "[ERROR] Не удалось получить новые ключи по адресу $IP" >&2
  exit 2
fi
# Фильтруем только известные типы
FILTERED=$(echo "$SCAN_OUTPUT" | grep -E 'ssh-ed25519|ssh-rsa' || true)
if [[ -z "$FILTERED" ]]; then
  echo "[ERROR] ssh-keyscan вернул неожиданные данные:\n$SCAN_OUTPUT" >&2
  exit 3
fi
echo "$FILTERED" >> "$KNOWN_HOSTS_FILE"
chmod 600 "$KNOWN_HOSTS_FILE"
echo "[INFO] Добавлены новые ключи:" >&2
echo "$FILTERED"
# Показать diff (опционально)
if command -v diff >/dev/null 2>&1; then
  echo "[INFO] Изменения в known_hosts:" >&2
  diff -u "$BACKUP_FILE" "$KNOWN_HOSTS_FILE" || true
fi
# Показать fingerprint нового ED25519
ED_KEY=$(echo "$FILTERED" | grep ssh-ed25519 | head -n1 || true)
if [[ -n "$ED_KEY" ]]; then
  FINGERPRINT=$(echo "$ED_KEY" | awk '{print $2}' | base64 -d 2>/dev/null | sha256sum 2>/dev/null | awk '{print $1}' || true)
  echo "[INFO] (Примерная) SHA256 fingerprint (raw decode) = $FINGERPRINT (сравни с предупреждением)." >&2
fi
echo "[DONE] Теперь можно пробовать: ssh ec2-user@$IP"
