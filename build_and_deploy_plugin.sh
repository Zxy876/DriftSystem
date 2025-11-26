#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/system/mc_plugin"
mvn clean package

cp target/DriftSystem-1.0.jar ../../server/plugins/

echo "✅ 插件已编译并复制到 server/plugins。"
