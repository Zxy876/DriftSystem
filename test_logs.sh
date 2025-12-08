#!/bin/bash
# 快速端到端日志验证脚本

echo "======================================"
echo "  DriftSystem 日志验证测试"
echo "======================================"
echo ""

BASE_URL="http://127.0.0.1:8000"
TEST_PLAYER="log_test_$$"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 检查后端
echo -e "${YELLOW}[1/4] 检查后端健康状态...${NC}"
HEALTH=$(curl -s $BASE_URL/health)
if echo "$HEALTH" | grep -q "ok"; then
    echo -e "${GREEN}✓ 后端运行正常${NC}"
else
    echo -e "${RED}✗ 后端未响应${NC}"
    exit 1
fi
echo ""

# 测试 /story/advance 日志
echo -e "${YELLOW}[2/4] 测试 /story/advance 端点...${NC}"
curl -s -X POST "$BASE_URL/story/advance/$TEST_PLAYER" \
  -H "Content-Type: application/json" \
  -d '{"world_state": {}, "action": {"say": "测试日志记录"}}' \
  > /tmp/story_response.json

if [ -s /tmp/story_response.json ]; then
    echo -e "${GREEN}✓ /story/advance 响应成功${NC}"
    echo "   Response: $(cat /tmp/story_response.json | python3 -c 'import sys,json; d=json.load(sys.stdin); print(f"status={d.get(\"status\")}, node={d.get(\"node\",{}).get(\"title\")}")')"
else
    echo -e "${RED}✗ /story/advance 无响应${NC}"
fi
echo ""

# 测试 /world/apply 日志
echo -e "${YELLOW}[3/4] 测试 /world/apply 端点...${NC}"
curl -s -X POST "$BASE_URL/world/apply" \
  -H "Content-Type: application/json" \
  -d "{\"player_id\": \"$TEST_PLAYER\", \"action\": {\"say\": \"测试世界应用\"}}" \
  > /tmp/world_response.json

if [ -s /tmp/world_response.json ]; then
    echo -e "${GREEN}✓ /world/apply 响应成功${NC}"
    echo "   Response: $(cat /tmp/world_response.json | python3 -c 'import sys,json; d=json.load(sys.stdin); print(f"status={d.get(\"status\")}, story_node={d.get(\"story_node\",{}).get(\"title\")}")')"
else
    echo -e "${RED}✗ /world/apply 无响应${NC}"
fi
echo ""

# 检查后端日志
echo -e "${YELLOW}[4/4] 检查后端日志文件...${NC}"
if [ -f "backend.log" ]; then
    echo "最近的日志条目："
    tail -n 20 backend.log | grep -E "\[/story/advance\]|\[/world/apply\]|\[HTTP" || echo "  (未找到相关日志)"
    echo ""
    
    # 统计日志
    STORY_LOGS=$(grep -c "\[/story/advance\]" backend.log 2>/dev/null || echo "0")
    WORLD_LOGS=$(grep -c "\[/world/apply\]" backend.log 2>/dev/null || echo "0")
    
    echo -e "${GREEN}✓ 后端日志统计:${NC}"
    echo "   /story/advance 调用: $STORY_LOGS 次"
    echo "   /world/apply 调用: $WORLD_LOGS 次"
else
    echo -e "${YELLOW}⚠ backend.log 不存在，可能后端未以后台模式启动${NC}"
fi

echo ""
echo "======================================"
echo "  日志验证测试完成"
echo "======================================"
