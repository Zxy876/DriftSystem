#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/system/mc_plugin"
mvn clean package

PLUGIN_JAR="target/mc_plugin-1.0-SNAPSHOT.jar"
if [ ! -f "$PLUGIN_JAR" ]; then
	PLUGIN_JAR="$(find target -maxdepth 1 -type f -name '*.jar' ! -name 'original-*' | head -n 1)"
fi

if [ -z "${PLUGIN_JAR:-}" ] || [ ! -f "$PLUGIN_JAR" ]; then
	echo "❌ 未找到插件构建产物（target/*.jar）"
	exit 1
fi

TARGET_DIR="../../backend/server/plugins"
if [ ! -d "$TARGET_DIR" ]; then
	TARGET_DIR="../../server/plugins"
fi

cp "$PLUGIN_JAR" "$TARGET_DIR/DriftSystem.jar"

echo "✅ 插件已编译并复制到 server/plugins。"
