#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "请使用 root 执行: sudo bash deploy_minecraft.sh"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

MC_DIR="/mc"
PAPER_JAR="paper.jar"
SERVICE_FILE="/etc/systemd/system/minecraft.service"

# 1) 安装 openjdk-17-jdk
apt update -y
apt install -y openjdk-17-jdk

# 2) 安装 screen
apt install -y screen curl python3

# 3) 创建目录 /mc
mkdir -p "${MC_DIR}"
cd "${MC_DIR}"

# 4) 下载 Paper 最新 1.20.x 稳定构建
PAPER_URL="$(python3 - <<'PY'
import json
import urllib.request

base = "https://api.papermc.io/v2/projects/paper"
with urllib.request.urlopen(base, timeout=20) as r:
    project = json.load(r)
versions = project.get("versions", [])
filtered = [v for v in versions if v.startswith("1.20")]
if not filtered:
    raise SystemExit("No Paper 1.20.x versions found")

def key(ver: str):
    return [int(x) if x.isdigit() else x for x in ver.replace('-', '.').split('.')]

latest_ver = sorted(filtered, key=key)[-1]
with urllib.request.urlopen(f"{base}/versions/{latest_ver}", timeout=20) as r:
    ver_data = json.load(r)
builds = ver_data.get("builds", [])
if not builds:
    raise SystemExit(f"No builds found for {latest_ver}")
latest_build = builds[-1]
jar = f"paper-{latest_ver}-{latest_build}.jar"
print(f"{base}/versions/{latest_ver}/builds/{latest_build}/downloads/{jar}")
PY
)"

curl -fL "${PAPER_URL}" -o "${PAPER_JAR}"

# 5) 首次运行生成 eula.txt
if [[ ! -f eula.txt ]]; then
  timeout 25s java -Xms1G -Xmx1G -jar "${PAPER_JAR}" nogui || true
fi

# 6) 自动修改 eula=true
if [[ -f eula.txt ]]; then
  sed -i 's/^eula=.*/eula=true/' eula.txt || true
else
  echo "eula=true" > eula.txt
fi

# 7) 写入 server.properties
RCON_PASSWORD="$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 16)"
cat > server.properties <<EOF
online-mode=true
enable-rcon=true
rcon.password=${RCON_PASSWORD}
rcon.port=25575
server-port=25565
EOF

# 8) JVM 参数使用 -Xms4G -Xmx6G
cat > "${MC_DIR}/start.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cd /mc
exec java -Xms4G -Xmx6G -jar paper.jar nogui
EOF
chmod +x "${MC_DIR}/start.sh"

# 9) 创建 systemd 服务 minecraft.service 并开机自启
cat > "${SERVICE_FILE}" <<'EOF'
[Unit]
Description=Minecraft Paper Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/mc
ExecStart=/mc/start.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable minecraft.service
systemctl restart minecraft.service

# 10) 输出信息
SERVER_IP="$(curl -4 -s --max-time 8 ifconfig.me || hostname -I | awk '{print $1}')"

echo "========================================"
echo "Minecraft Paper 部署完成"
echo "服务器 IP: ${SERVER_IP}"
echo "RCON 密码: ${RCON_PASSWORD}"
echo "systemd 状态检查: systemctl status minecraft.service --no-pager"
echo "实时日志查看: journalctl -u minecraft.service -f"
echo "========================================"
