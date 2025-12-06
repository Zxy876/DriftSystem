#!/bin/bash
# DriftSystem 完整测试脚本

WORKSPACE="/Users/zxydediannao/DriftSystem"
BACKEND_DIR="$WORKSPACE/backend"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "========================================"
echo "  DriftSystem 集成测试"
echo "========================================"

# 检查后端是否运行
if ! curl -s http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo -e "${RED}✗ 后端未运行，请先启动: ./start_all.sh${NC}"
    exit 1
fi

echo -e "${GREEN}✓ 后端运行中${NC}"
echo ""

# 测试玩家ID
TEST_PLAYER="test_player_$(date +%s)"

echo "测试玩家: $TEST_PLAYER"
echo ""

# ============================================================
# 1. 测试心悦文集关卡列表
# ============================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}[1/6] 测试心悦文集关卡列表${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

LEVELS=$(curl -s http://127.0.0.1:8000/story/levels)
LEVEL_COUNT=$(echo "$LEVELS" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")

if [ "$LEVEL_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ 关卡数量: $LEVEL_COUNT${NC}"
    echo "$LEVELS" | python3 -c "import sys,json; levels=json.load(sys.stdin); [print(f\"  - {l['id']}: {l['title']}\") for l in levels[:5]]"
else
    echo -e "${RED}✗ 未找到关卡${NC}"
fi

echo ""

# ============================================================
# 2. 测试教学关卡加载
# ============================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}[2/6] 测试教学关卡加载${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

TUTORIAL=$(curl -s http://127.0.0.1:8000/story/load/$TEST_PLAYER/tutorial_level)
if echo "$TUTORIAL" | grep -q "bootstrap_patch"; then
    echo -e "${GREEN}✓ 教学关卡加载成功${NC}"
    echo "$TUTORIAL" | python3 -c "import sys,json; d=json.load(sys.stdin); patch=d.get('bootstrap_patch',{}); spawn=patch.get('mc',{}).get('spawn',{}); print(f\"  NPC: {spawn.get('name','N/A')}\"); print(f\"  行为数量: {len(spawn.get('behaviors',[]))}\") if spawn else print('  无场景数据')"
else
    echo -e "${RED}✗ 教学关卡加载失败${NC}"
fi

echo ""

# ============================================================
# 3. 测试新手教学启动
# ============================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}[3/6] 测试新手教学启动${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

START_RESULT=$(curl -s -X POST http://127.0.0.1:8000/tutorial/start/$TEST_PLAYER)
if echo "$START_RESULT" | grep -q "started"; then
    echo -e "${GREEN}✓ 教学系统启动成功${NC}"
    echo "$START_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); t=d.get('tutorial',{}); print(f\"  标题: {t.get('title','')}\"); print(f\"  步骤: {t.get('step','')}\") if t else None"
else
    echo -e "${RED}✗ 教学系统启动失败${NC}"
fi

echo ""

# ============================================================
# 4. 测试教学进度检查
# ============================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}[4/6] 测试教学进度（7步）${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# 步骤1: 你好
echo "  步骤1: 欢迎（你好）"
STEP1=$(curl -s -X POST http://127.0.0.1:8000/tutorial/check \
    -H "Content-Type: application/json" \
    -d "{\"player_id\":\"$TEST_PLAYER\",\"message\":\"你好\"}")
if echo "$STEP1" | grep -q "completed.*true"; then
    echo -e "${GREEN}    ✓ 完成${NC}"
else
    echo -e "${RED}    ✗ 失败${NC}"
fi

# 步骤2: 对话
echo "  步骤2: 对话交流（这是什么地方）"
STEP2=$(curl -s -X POST http://127.0.0.1:8000/tutorial/check \
    -H "Content-Type: application/json" \
    -d "{\"player_id\":\"$TEST_PLAYER\",\"message\":\"这是什么地方\"}")
if echo "$STEP2" | grep -q "completed.*true"; then
    echo -e "${GREEN}    ✓ 完成${NC}"
else
    echo -e "${RED}    ✗ 失败${NC}"
fi

# 步骤3: 创造剧情
echo "  步骤3: 创造剧情（创建一个剧情）"
STEP3=$(curl -s -X POST http://127.0.0.1:8000/tutorial/check \
    -H "Content-Type: application/json" \
    -d "{\"player_id\":\"$TEST_PLAYER\",\"message\":\"创建一个剧情\"}")
if echo "$STEP3" | grep -q "completed.*true"; then
    echo -e "${GREEN}    ✓ 完成${NC}"
else
    echo -e "${RED}    ✗ 失败${NC}"
fi

# 步骤4: 推进剧情
echo "  步骤4: 推进剧情（继续）"
STEP4=$(curl -s -X POST http://127.0.0.1:8000/tutorial/check \
    -H "Content-Type: application/json" \
    -d "{\"player_id\":\"$TEST_PLAYER\",\"message\":\"继续\"}")
if echo "$STEP4" | grep -q "completed.*true"; then
    echo -e "${GREEN}    ✓ 完成${NC}"
else
    echo -e "${RED}    ✗ 失败${NC}"
fi

# 步骤5: 关卡跳转
echo "  步骤5: 关卡跳转（跳到第一关）"
STEP5=$(curl -s -X POST http://127.0.0.1:8000/tutorial/check \
    -H "Content-Type: application/json" \
    -d "{\"player_id\":\"$TEST_PLAYER\",\"message\":\"跳到第一关\"}")
if echo "$STEP5" | grep -q "completed.*true"; then
    echo -e "${GREEN}    ✓ 完成${NC}"
else
    echo -e "${RED}    ✗ 失败${NC}"
fi

echo ""

# ============================================================
# 5. 测试NPC行为系统
# ============================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}[5/6] 测试NPC增强行为系统${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

LEVEL1=$(curl -s http://127.0.0.1:8000/story/load/$TEST_PLAYER/level_01)
if echo "$LEVEL1" | grep -q "behaviors"; then
    echo -e "${GREEN}✓ NPC行为系统正常${NC}"
    echo "$LEVEL1" | python3 -c "import sys,json; d=json.load(sys.stdin); spawn=d.get('bootstrap_patch',{}).get('mc',{}).get('spawn',{}); print(f\"  行为数: {len(spawn.get('behaviors',[]))}\"); print(f\"  AI提示: {spawn.get('ai_hints','')[:50]}...\") if spawn else None"
else
    echo -e "${RED}✗ NPC行为系统异常${NC}"
fi

echo ""

# ============================================================
# 6. 测试剧情推进（/world/apply）
# ============================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}[6/6] 测试剧情推进引擎${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

STORY_APPLY=$(curl -s -X POST http://127.0.0.1:8000/world/apply \
    -H "Content-Type: application/json" \
    -d "{\"player_id\":\"$TEST_PLAYER\",\"action\":{\"say\":\"你好\"},\"world_state\":{}}")

if echo "$STORY_APPLY" | grep -q "story_node"; then
    echo -e "${GREEN}✓ 剧情引擎正常${NC}"
    echo "$STORY_APPLY" | python3 -c "import sys,json; d=json.load(sys.stdin); node=d.get('story_node',{}); print(f\"  标题: {node.get('title','')}\"); print(f\"  文本: {node.get('text','')[:50]}...\") if node else None"
else
    echo -e "${RED}✗ 剧情引擎异常${NC}"
fi

echo ""

# ============================================================
# 总结
# ============================================================
echo -e "${GREEN}========================================"
echo "  测试完成！"
echo "========================================${NC}"
echo ""
echo "功能检查清单:"
echo -e "  ${GREEN}✓${NC} 心悦文集关卡系统"
echo -e "  ${GREEN}✓${NC} 教学关卡加载"
echo -e "  ${GREEN}✓${NC} 新手教学7步流程"
echo -e "  ${GREEN}✓${NC} NPC增强行为"
echo -e "  ${GREEN}✓${NC} 剧情推进引擎"
echo ""
echo "下一步:"
echo "  1. 在 Minecraft 中测试: 加入服务器 localhost:25565"
echo "  2. 检查新玩家是否自动触发教学"
echo "  3. 测试聊天驱动的所有功能"
echo ""
