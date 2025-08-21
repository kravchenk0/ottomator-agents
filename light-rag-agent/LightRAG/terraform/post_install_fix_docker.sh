#!/bin/bash
# Idempotent helper to fix docker group/socket for ec2-user after instance is already running.
set -euo pipefail
echo "[fix-docker] start"
if ! command -v docker >/dev/null 2>&1; then
  echo "[fix-docker] docker binary not found"; exit 1
fi
if ! getent group docker >/dev/null 2>&1; then
  sudo groupadd docker || true
fi
sudo usermod -aG docker ec2-user || true
for i in $(seq 1 10); do
  if [ -S /var/run/docker.sock ]; then
    sudo chgrp docker /var/run/docker.sock || true
    sudo chmod 660 /var/run/docker.sock || true
    command -v setfacl >/dev/null 2>&1 && sudo setfacl -m u:ec2-user:rw /var/run/docker.sock || true
    echo "[fix-docker] socket perms fixed"; break
  fi
  sleep 1
done
echo "[fix-docker] ec2-user groups before new login: $(id ec2-user)"
echo "[fix-docker] Done. Reconnect SSH to refresh group membership."
