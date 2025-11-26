#!/bin/bash
set -e

echo "=== 正在修复 DriftSystem Java 目录结构 ==="

PLUGIN_SRC="system/mc_plugin/src/main/java/com/driftmc"
ROOT_SRC="com/driftmc"

echo
echo "[1] 删除旧的 Maven 代码目录..."
rm -rf "$PLUGIN_SRC"
mkdir -p "$PLUGIN_SRC"

echo
echo "[2] 将根目录 com/driftmc 移动进 Maven 项目..."
mv "$ROOT_SRC"/* "$PLUGIN_SRC"/

echo
echo "[3] 删除空的旧目录..."
rmdir "$ROOT_SRC"

echo
echo "[4] 显示最终目录结构："
tree system/mc_plugin/src/main/java

echo
echo "[5] 重新构建插件..."
cd system/mc_plugin
mvn -q clean package

echo
echo "=== 修复完成！JAR 已生成：system/mc_plugin/target/drift-mc-plugin-1.0-SNAPSHOT.jar ==="
