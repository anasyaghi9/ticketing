#!/usr/bin/env bash
# Run ONCE as root on a fresh Ubuntu 24.04 server:
#   sudo ./server_setup.sh /path/to/your_public_key.pub
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run as root"; exit 1; }
PUB="${1:?Usage: server_setup.sh <public_key_file>}"
U="${DEPLOY_USER:-deploy}"
ssh-keygen -lf "$PUB" > /dev/null || { echo "Invalid public key"; exit 1; }

export DEBIAN_FRONTEND=noninteractive
apt-get update -y && apt-get upgrade -y
apt-get install -y ufw fail2ban unattended-upgrades nginx curl git ca-certificates
dpkg-reconfigure -f noninteractive unattended-upgrades

command -v docker > /dev/null || curl -fsSL https://get.docker.com | sh

id "$U" > /dev/null 2>&1 || adduser --disabled-password --gecos "" "$U"
usermod -aG docker "$U"
install -d -m 700 -o "$U" -g "$U" "/home/$U/.ssh"
install -m 600 -o "$U" -g "$U" "$PUB" "/home/$U/.ssh/authorized_keys"

# 00- prefix: sshd uses the first value it reads, so this beats cloud-init's 50- file
cat > /etc/ssh/sshd_config.d/00-hardening.conf <<CONF
PasswordAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
CONF
sshd -t

ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
systemctl enable --now fail2ban

if [ "$(swapon --show | wc -l)" = 0 ]; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo "/swapfile none swap sw 0 0" >> /etc/fstab
fi

systemctl reload ssh
echo "DONE. Do NOT close this session. In a NEW terminal run: ssh $U@<server-ip>"
