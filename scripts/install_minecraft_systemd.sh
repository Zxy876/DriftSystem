#!/usr/bin/env bash
set -euo pipefail

# Install minecraft.service for auto-start on boot.
# Run on the server (with sudo privileges).
#
# Usage:
#   sudo bash scripts/install_minecraft_systemd.sh \
#     --mc-dir /mc --mc-user ubuntu --start-cmd './start.sh'

MC_DIR="/mc"
MC_USER="ubuntu"
START_CMD="./start.sh"
STOP_CMD="pkill -f 'paper.*jar|minecraft_server.*jar' || true"
TEMPLATE_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/systemd/minecraft.service"
UNIT_PATH="/etc/systemd/system/minecraft.service"
ENV_PATH="/etc/default/drift-minecraft"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mc-dir)
      MC_DIR="$2"; shift 2 ;;
    --mc-user)
      MC_USER="$2"; shift 2 ;;
    --start-cmd)
      START_CMD="$2"; shift 2 ;;
    --stop-cmd)
      STOP_CMD="$2"; shift 2 ;;
    --template)
      TEMPLATE_PATH="$2"; shift 2 ;;
    --help|-h)
      cat <<'USAGE'
Install minecraft.service for boot auto-start.

Options:
  --mc-dir <path>      Minecraft working directory (default: /mc)
  --mc-user <user>     Service run user (default: ubuntu)
  --start-cmd <cmd>    Start command in working dir (default: ./start.sh)
  --stop-cmd <cmd>     Stop command (default: pkill ...)
  --template <path>    Service template path
USAGE
      exit 0 ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 1 ;;
  esac
done

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root (sudo)." >&2
  exit 1
fi

if [[ ! -f "$TEMPLATE_PATH" ]]; then
  echo "Template not found: $TEMPLATE_PATH" >&2
  exit 1
fi

if [[ ! -d "$MC_DIR" ]]; then
  echo "MC directory not found: $MC_DIR" >&2
  exit 1
fi

if ! id -u "$MC_USER" >/dev/null 2>&1; then
  echo "User not found: $MC_USER" >&2
  exit 1
fi

if [[ "$START_CMD" == "./start.sh" && ! -x "$MC_DIR/start.sh" ]]; then
  CANDIDATE_JAR="$(find "$MC_DIR" -maxdepth 1 -type f \( -name 'paper*.jar' -o -name 'minecraft_server*.jar' \) | head -n1)"
  if [[ -n "$CANDIDATE_JAR" ]]; then
    START_CMD="java -Xms2G -Xmx4G -jar $(basename "$CANDIDATE_JAR") nogui"
  fi
fi

TMP_UNIT="$(mktemp)"
trap 'rm -f "$TMP_UNIT"' EXIT

sed -e "s|{{MC_USER}}|$MC_USER|g" \
    -e "s|{{MC_DIR}}|$MC_DIR|g" \
    "$TEMPLATE_PATH" > "$TMP_UNIT"

install -m 0644 "$TMP_UNIT" "$UNIT_PATH"

cat > "$ENV_PATH" <<EOF
MC_START_CMD=$START_CMD
MC_STOP_CMD=$STOP_CMD
EOF
chmod 0644 "$ENV_PATH"

systemctl daemon-reload
systemctl enable minecraft.service
systemctl restart minecraft.service
sleep 2
systemctl --no-pager --full status minecraft.service | head -n 25 || true

echo "Installed: $UNIT_PATH"
echo "Env file:  $ENV_PATH"
echo "Done. Service will auto-start at boot."
