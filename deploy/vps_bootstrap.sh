#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run as root: sudo bash deploy/vps_bootstrap.sh"
  exit 1
fi

# 1) 系统更新
apt update -y
apt upgrade -y

# 2) 安装 Java 17
apt install -y openjdk-17-jre-headless wget ufw

# 3) 创建目录
mkdir -p /opt/minecraft
cd /opt/minecraft

# 4) 下载 Paper 1.20.4
wget https://api.papermc.io/v2/projects/paper/versions/1.20.4/builds/569/downloads/paper-1.20.4-569.jar -O paper.jar

# 5) 自动生成 eula.txt
echo "eula=true" > eula.txt

# 6) 写入 server.properties（强随机密码）
if command -v openssl >/dev/null 2>&1; then
  RCON_PASSWORD="$(openssl rand -base64 32 | tr -d '\n' | tr '/+' 'AB' | cut -c1-32)"
else
  RCON_PASSWORD="$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32)"
fi

cat > /opt/minecraft/server.properties <<EOF
enable-rcon=true
rcon.password=${RCON_PASSWORD}
rcon.port=25575
server-port=25565
online-mode=true
EOF

# 7) 开放端口
ufw allow 25565/tcp
ufw allow 25575/tcp
ufw allow 22/tcp
ufw --force enable

# 8) 创建启动脚本
cat > /opt/minecraft/start.sh <<'EOF'
#!/bin/bash
java -Xms1G -Xmx1500M -jar paper.jar nogui
EOF
chmod +x /opt/minecraft/start.sh

# 二、生成 systemd 服务文件
cat > /etc/systemd/system/minecraft.service <<'EOF'
[Unit]
Description=Drift Minecraft Server
After=network.target

[Service]
User=root
WorkingDirectory=/opt/minecraft
ExecStart=/opt/minecraft/start.sh
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable minecraft
systemctl start minecraft

sleep 15

echo "================ DEPLOY RESULT ================"
echo "RCON_PASSWORD=${RCON_PASSWORD}"

echo "----- 启动状态 (systemctl) -----"
systemctl status minecraft --no-pager -l | sed -n '1,30p'

echo "----- 端口监听状态 (ss -tulpn) -----"
ss -tulpn | grep -E ':22|:25565|:25575' || true

echo "----- Java 版本 -----"
java -version

echo "----- Paper 启动判定 -----"
if journalctl -u minecraft -n 200 --no-pager | grep -E 'Done \([0-9.]+s\)!|For help, type "help"' >/dev/null 2>&1; then
  echo "Paper 启动成功"
else
  echo "Paper 启动日志未检测到完成标记，请继续查看: journalctl -u minecraft -f"
fi
