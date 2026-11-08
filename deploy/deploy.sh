#!/usr/bin/env bash
# DSH 云端一键部署脚本（Oracle Free Tier / 任意 Ubuntu arm64 或 amd64）
# 用法：bash deploy.sh
set -euo pipefail

echo "=== [1/6] 系统依赖 ==="
sudo apt-get update -qq
sudo apt-get install -y -qq curl git build-essential ufw

echo "=== [2/6] 安装 Node 24 ==="
if ! command -v node >/dev/null || [ "$(node -v | cut -d. -f1 | tr -d v)" -lt 24 ]; then
  curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
  sudo apt-get install -y -qq nodejs
fi
node -v

echo "=== [3/6] 安装 dsh CLI ==="
sudo npm install -g @deepseek-ai/dsh@latest
dsh --version || true

echo "=== [4/6] 初始化 profile ==="
mkdir -p ~/.dsh
dsh plugin --profile web list 2>/dev/null || dsh --profile web --help >/dev/null 2>&1 || true

echo "=== [5/6] 防火墙（只开 SSH，不开公网 web 端口）==="
sudo ufw --force reset >/dev/null 2>&1 || true
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw --force enable
sudo ufw status

echo "=== [6/6] 完成 ==="
echo "DSH_HOME: ${DSH_HOME:-$HOME/.dsh}"
echo "下一步："
echo "  1) 装 Tailscale: curl -fsSL https://tailscale.com/install.sh | sh && sudo tailscale up"
echo "  2) 启动 dsh web（仅监听 127.0.0.1）"
echo "  3) 手机装 Tailscale，用私有 IP 访问"
