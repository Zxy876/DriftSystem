#!/bin/bash
set -e

echo "=== 修复 mc_plugin 目录结构（核心版） ==="

PLUGIN_DIR="system/mc_plugin"
SRC_JAVA="$PLUGIN_DIR/src/main/java"

# 1) 创建正确的包路径
mkdir -p $SRC_JAVA/com/driftmc

echo "[1] 移动所有 Java 文件到正确目录..."

# 2) 把根目录的 com/driftmc 全部移入 src/main/java/com/
if [ -d "com/driftmc" ]; then
    mv com/driftmc $SRC_JAVA/com/
    echo "    ✔ 已移动 com/driftmc → src/main/java/com/driftmc"
else
    echo "    ✘ 未找到根目录 com/driftmc（请确认树结构）"
fi

# 3) 检查 DriftPlugin 是否存在
echo "[2] 确认 DriftPlugin 是否就位..."
if [ -f "$SRC_JAVA/com/driftmc/DriftPlugin.java" ]; then
    echo "    ✔ DriftPlugin.java 已找到"
else
    echo "    ✘ DriftPlugin.java 不在正确目录！你必须把它放到："
    echo "      system/mc_plugin/src/main/java/com/driftmc/DriftPlugin.java"
    exit 1
fi

# 4) 清理空目录
echo "[3] 清理空目录..."
find . -type d -empty -delete

# 5) 重建插件
echo "[4] 运行 mvn clean package..."
cd $PLUGIN_DIR
mvn -q clean package

echo "=== 修复完成！插件 jar 路径如下：==="
echo "$PLUGIN_DIR/target/drift-mc-plugin-1.0-SNAPSHOT.jar"