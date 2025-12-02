#!/bin/bash

echo "=============================="
echo "🎮 启动 DriftSystem MC 服务端"
echo "=============================="

cd "$(dirname "$0")/server"

# 自动检测 jar 文件（Paper / Spigot / 其他）
JAR_FILE=$(ls | grep -E "paper|spigot|server.*\.jar" | head -n 1)

if [ -z "$JAR_FILE" ]; then
    echo "❌ 未找到 Minecraft 服务器 JAR 文件（paper/spigot）"
    exit 1
fi

echo "🔍 检测到服务器文件: $JAR_FILE"
echo "🧩 插件目录: plugins/"

# 检查插件是否存在
if [ ! -d "plugins" ]; then
    echo "⚠️ plugins 文件夹不存在，正在创建 ..."
    mkdir plugins
fi

echo "🚀 MC 服务器启动中..."
echo "（按 Ctrl+C 关闭）"

java -Xms2G -Xmx4G -jar "$JAR_FILE" nogui
