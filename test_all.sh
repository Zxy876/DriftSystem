#!/bin/bash

HOST="http://127.0.0.1:8000"
PLAYER="zxy"

echo "=============================="
echo "🩺 DriftSystem 一键测试开始"
echo "=============================="

echo ""
echo "1️⃣ 检查后端在线状态..."
curl -s $HOST/world/state > /dev/null
if [ $? -ne 0 ]; then
    echo "❌ 后端未启动，请运行：uvicorn app.main:app --reload"
    exit 1
fi
echo "✔ 后端在线"

echo ""
echo "2️⃣ DSL：注入一个测试关卡 level_test"
curl -s -X POST $HOST/add \
    -H "Content-Type: application/json" \
    -d '{
        "content": "ADD level_test { title: 测试关卡, text: 这是自动注入的测试关卡 }"
    }'
echo ""
echo "✔ 关卡已注入"

echo ""
echo "3️⃣ DSL：自动生成一个玉兔 NPC"
curl -s -X POST $HOST/run \
    -H "Content-Type: application/json" \
    -d '{
        "script": "spawn rabbit name=玉兔 dx=1 dy=0 dz=1"
    }'
echo ""
echo "✔ NPC 已生成"

echo ""
echo "4️⃣ AI Intent：玩家说“生成一只小猫”"
AI_RESPONSE=$(curl -s -X POST $HOST/ai/intent \
    -H "Content-Type: application/json" \
    -d "{
        \"player_id\": \"$PLAYER\",
        \"text\": \"生成一只小猫\",
        \"world_state\": {}
    }")

echo "AI 返回：$AI_RESPONSE"

echo ""
echo "5️⃣ world/apply：执行 AI 造物命令"
curl -s -X POST $HOST/world/apply \
    -H "Content-Type: application/json" \
    -d "{
        \"player_id\": \"$PLAYER\",
        \"action\": { \"say\": \"生成一只小猫\" }
    }"
echo ""
echo "✔ AI 造物执行完成"

echo ""
echo "6️⃣ 模拟玩家移动触发地图关卡（x=212,z=225）"
curl -s -X POST $HOST/world/apply \
    -H "Content-Type: application/json" \
    -d "{
        \"player_id\": \"$PLAYER\",
        \"action\": {
            \"move\": { \"x\": 212, \"y\": 70, \"z\": 225, \"speed\": 0.3, \"moving\": true }
        }
    }"
echo ""
echo "✔ 地图触发事件已发送"

echo ""
echo "7️⃣ 导出 minimap PNG"
curl -s $HOST/minimap/png/$PLAYER -o minimap_test.png
echo "✔ minimap_test.png 已保存"

echo ""
echo "=============================="
echo "🎉 一键测试完成！"
echo "📌 输出文件： minimap_test.png"
echo "📌 请在终端检查是否有剧情触发 / 传送 / 造物输出"
echo "=============================="
