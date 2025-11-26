#!/bin/bash

echo "🧹 开始清理错误目录 org/driftsystem..."

rm -rf src/main/java/org/driftsystem

echo "☑ 已删除 org/driftsystem 下所有残留旧代码"

echo "🧽 清理 target 编译缓存..."
rm -rf target

echo "📦 重新构建 Maven..."
mvn clean package -DskipTests

echo ""
echo "🎉 完成！现在项目中只剩统一包：com.driftmc"
