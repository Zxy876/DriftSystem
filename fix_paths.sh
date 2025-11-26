#!/bin/bash
set -e

echo "=== 修复 DriftSystem Java 目录结构（最终稳定版） ==="

ROOT_DIR="$(pwd)"

SRC_DIR="$ROOT_DIR/system/mc_plugin/src/main/java"
TARGET="$SRC_DIR/com/driftmc"

OLD="$ROOT_DIR/com/driftmc"

# 1) 检查旧目录是否存在
if [ ! -d "$OLD" ]; then
  echo "✘ 错误：未找到旧目录：$OLD"
  echo "请确认你的目录树里有 DriftSystem/com/driftmc"
  exit 1
fi

# 2) 创建目标目录
mkdir -p "$TARGET"

echo "[1] 移动 Java 文件到 Maven src/main/java..."
mv "$OLD"/* "$TARGET"/

# 3) 删除旧空目录
rmdir "$ROOT_DIR/com/driftmc" 2>/dev/null || true
rmdir "$ROOT_DIR/com" 2>/dev/null || true

echo "[2] 确认 DriftPlugin 是否存在..."

if [ ! -f "$TARGET/DriftPlugin.java" ]; then
  echo "✘ DriftPlugin.java 仍然不存在：$TARGET/DriftPlugin.java"
  exit 1
fi

echo "✔ DriftPlugin.java 已就位"

# 4) 重新编译
echo "[3] Maven clean package..."
cd "$ROOT_DIR/system/mc_plugin"
mvn -e clean package

echo "=== 目录修复成功！ 插件已可以被服务器加载 ==="
echo "插件路径：system/mc_plugin/target/drift-mc-plugin-1.0-SNAPSHOT.jar"
