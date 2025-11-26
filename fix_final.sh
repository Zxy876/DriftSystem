#!/bin/bash
set -e

echo "=== DriftSystem 最终路径修复开始 ==="

BASE="$(pwd)"

MC="$BASE/system/mc_plugin/src/main/java"

SRC_OUTSIDE="$BASE/com/driftmc"

if [ ! -d "$SRC_OUTSIDE" ]; then
    echo "❌ 找不到目录：$SRC_OUTSIDE"
    echo "你的源码不在这里，无法继续"
    exit 1
fi

echo "✔ 找到源码：$SRC_OUTSIDE"

# 删除旧 Java 目录
echo "→ 清空 Maven java 目录..."
rm -rf "$MC"
mkdir -p "$MC"

# 移动源码
echo "→ 移动 com/driftmc 到 Maven 中..."
mv "$SRC_OUTSIDE" "$MC/"

echo "→ 成功移动到：$MC/driftmc"

# 修复 plugin.yml main 路径
PLUGIN_YML="$BASE/system/mc_plugin/src/main/resources/plugin.yml"

echo "→ 修复 plugin.yml..."
sed -i '' 's/main: .*/main: com.driftmc.DriftPlugin/' "$PLUGIN_YML"

# 安装 org.json 依赖
POM="$BASE/system/mc_plugin/pom.xml"

echo "→ 确保 pom.xml 包含 org.json 依赖..."
if ! grep -q "org.json" "$POM"; then
cat <<EOF >> "$POM"

    <dependencies>
        <dependency>
            <groupId>org.json</groupId>
            <artifactId>json</artifactId>
            <version>20231013</version>
        </dependency>
    </dependencies>
EOF
fi

echo "→ 正在构建 JAR..."

cd "$BASE/system/mc_plugin"
mvn -q clean package

echo "=== 修复完成！ ==="
echo "你的插件在：system/mc_plugin/target/drift-mc-plugin-1.0-SNAPSHOT.jar"
