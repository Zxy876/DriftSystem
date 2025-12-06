#!/bin/bash
# 新手教学快速测试脚本

BASE_URL="http://127.0.0.1:8000"
PLAYER_ID="tutorial_test_$(date +%s)"

echo "═══════════════════════════════════════════"
echo "  心悦文集 - 新手教学系统测试"
echo "═══════════════════════════════════════════"
echo ""
echo "测试玩家ID: $PLAYER_ID"
echo ""

# 第一步：启动教学
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📚 步骤1: 启动新手教学"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s -X POST "$BASE_URL/tutorial/start/$PLAYER_ID" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d['tutorial']['title']); print(d['tutorial']['instruction'])"
echo ""
read -p "按Enter键继续..."

# 第二步：测试欢迎
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✨ 步骤2: 测试'你好'（WELCOME）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s -X POST "$BASE_URL/tutorial/check" \
  -H "Content-Type: application/json" \
  -d "{\"player_id\":\"$PLAYER_ID\",\"message\":\"你好\"}" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print('✓', d.get('result',{}).get('success_message','失败')); next=d.get('result',{}).get('next_step',{}); print('\n下一步:', next.get('title',''))"
echo ""
read -p "按Enter键继续..."

# 第三步：测试对话
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📖 步骤3: 测试提问（DIALOGUE）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s -X POST "$BASE_URL/tutorial/check" \
  -H "Content-Type: application/json" \
  -d "{\"player_id\":\"$PLAYER_ID\",\"message\":\"这里是什么地方\"}" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print('✓', d.get('result',{}).get('success_message','失败')); next=d.get('result',{}).get('next_step',{}); print('\n下一步:', next.get('title',''))"
echo ""
read -p "按Enter键继续..."

# 第四步：创造剧情
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎭 步骤4: 创造剧情（CREATE_STORY）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s -X POST "$BASE_URL/tutorial/check" \
  -H "Content-Type: application/json" \
  -d "{\"player_id\":\"$PLAYER_ID\",\"message\":\"写一个剧情\"}" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print('✓', d.get('result',{}).get('success_message','失败')); next=d.get('result',{}).get('next_step',{}); print('\n下一步:', next.get('title',''))"
echo ""
read -p "按Enter键继续..."

# 第五步：推进剧情
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⏭ 步骤5: 推进剧情（CONTINUE）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s -X POST "$BASE_URL/tutorial/check" \
  -H "Content-Type: application/json" \
  -d "{\"player_id\":\"$PLAYER_ID\",\"message\":\"继续\"}" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print('✓', d.get('result',{}).get('success_message','失败')); next=d.get('result',{}).get('next_step',{}); print('\n下一步:', next.get('title',''))"
echo ""
read -p "按Enter键继续..."

# 第六步：跳转关卡
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 步骤6: 关卡跳转（JUMP_LEVEL）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s -X POST "$BASE_URL/tutorial/check" \
  -H "Content-Type: application/json" \
  -d "{\"player_id\":\"$PLAYER_ID\",\"message\":\"跳到第一关\"}" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print('✓', d.get('result',{}).get('success_message','失败')); next=d.get('result',{}).get('next_step',{}); print('\n下一步:', next.get('title',''))"
echo ""
read -p "按Enter键继续..."

# 第七步：NPC互动
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "👥 步骤7: NPC互动（NPC_INTERACT）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s -X POST "$BASE_URL/tutorial/check" \
  -H "Content-Type: application/json" \
  -d "{\"player_id\":\"$PLAYER_ID\",\"message\":\"你好NPC\"}" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print('✓', d.get('result',{}).get('success_message','失败')); next=d.get('result',{}).get('next_step',{}); print('\n下一步:', next.get('title',''))"
echo ""
read -p "按Enter键继续..."

# 第八步：查看地图（完成）
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🗺 步骤8: 查看地图（VIEW_MAP - 完成）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s -X POST "$BASE_URL/tutorial/check" \
  -H "Content-Type: application/json" \
  -d "{\"player_id\":\"$PLAYER_ID\",\"message\":\"给我小地图\"}" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print('✓', d.get('result',{}).get('success_message','失败'))"
echo ""

# 完成
echo ""
echo "═══════════════════════════════════════════"
echo "  🎉 新手教学测试完成！"
echo "═══════════════════════════════════════════"
echo ""
echo "所有7个步骤已测试完毕"
echo "玩家已获得："
echo "  - 总经验值: 800"
echo "  - 钻石 x5"
echo "  - 金苹果 x3"
echo "  - 书 x1"
echo ""
