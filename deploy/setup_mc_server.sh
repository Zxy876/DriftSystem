#!/usr/bin/env bash
set -euo pipefail

RCON_PASSWORD="${RCON_PASSWORD:-change_me_strong_password}"
MC_DIR="/opt/minecraft"
PAPER_VERSION="1.20.1"
PAPER_BUILD="196"
PAPER_JAR="paper-${PAPER_VERSION}-${PAPER_BUILD}.jar"
PAPER_URL="https://api.papermc.io/v2/projects/paper/versions/${PAPER_VERSION}/builds/${PAPER_BUILD}/downloads/${PAPER_JAR}"

echo "[1/8] install openjdk-17"
apt-get update -y
apt-get install -y openjdk-17-jre-headless curl ufw

echo "[2/8] create ${MC_DIR}"
mkdir -p "${MC_DIR}"
cd "${MC_DIR}"

echo "[3/8] download Paper ${PAPER_VERSION}"
curl -fsSL "${PAPER_URL}" -o server.jar

echo "[4/8] write eula"
echo "eula=true" > eula.txt

echo "[5/8] write server.properties"
cat > server.properties <<EOF
enable-rcon=true
rcon.password=${RCON_PASSWORD}
rcon.port=25575
server-port=25565
online-mode=true
motd=Drift Production Server
max-players=20
view-distance=10
simulation-distance=8
EOF

echo "[6/8] write start.sh"
cat > start.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cd /opt/minecraft
exec java -Xms2G -Xmx4G -jar server.jar --nogui
EOF
chmod +x start.sh

echo "[7/8] open firewall ports"
ufw allow 25565/tcp || true
ufw allow 25575/tcp || true

echo "[8/8] done"
echo "Minecraft directory prepared at ${MC_DIR}"
