#!/bin/bash
set -e

echo "=== DriftSystem FINAL STRUCTURE FIX ==="

PLUGIN_DIR="system/mc_plugin"
SRC_MAIN="$PLUGIN_DIR/src/main/java"
NESTED="$PLUGIN_DIR/DriftSystem/system/mc_plugin/src/main/java/com"

# 1️⃣ 找到真正的源码目录
if [ -d "$NESTED" ]; then
    echo "✔ 找到 nested 源码目录：$NESTED"
else
    echo "❌ 未找到 nested 目录，请给我发 com/driftmc 的完整截图"
    exit 1
fi

# 2️⃣ 删除错误的空代码目录
echo "✔ 清理错误的 src/main/java/com ..."
rm -rf "$SRC_MAIN/com"

# 3️⃣ 创建正确目录
mkdir -p "$SRC_MAIN"

# 4️⃣ 将 com/driftmc 整个挪到正确位置
echo "✔ 移动 com/driftmc → src/main/java ..."
mv "$NESTED/driftmc" "$SRC_MAIN"

# 5️⃣ 删除嵌套目录
echo "✔ 清理 nested 多余目录"
rm -rf "$PLUGIN_DIR/DriftSystem"

# 6️⃣ 查看结果
echo "=== 结果目录结构："
tree "$SRC_MAIN" | head -n 30

echo "=== 目录修复完成 ==="
echo "✔ 现在运行："
echo "cd system/mc_plugin"
echo "mvn clean package"
