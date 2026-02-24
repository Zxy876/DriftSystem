#!/bin/bash
# DriftSystem 功能演示脚本（Issue 7.1）
# 增加 --dry-run（默认）用于无后台环境下演示，仍写出日志。

BASE_URL="http://127.0.0.1:8000"
DRY_RUN=1
DEMO_DATE="${DEMO_DATE:-20260121}"
LOG_DIR="logs/demos/${DEMO_DATE}"
LOG_FILE="$LOG_DIR/demo.log"

mkdir -p "$LOG_DIR"

for arg in "$@"; do
    case "$arg" in
        --run)
            DRY_RUN=0
            ;;
        --dry-run)
            DRY_RUN=1
            ;;
    esac
done

log_line() {
    printf '[%s] %s\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$1" | tee -a "$LOG_FILE"
}

if [ "$DRY_RUN" -eq 1 ]; then
    log_line "dry-run 模式：不发出真实请求，仅记录计划"
    log_line "计划阶段：IMPORT → SET_DRESS → REHEARSE → TAKE"
    log_line "将调用接口：/story/levels, /tutorial/start, /story/load/<player>/<level>, /story/inject 等"
    log_line "如需真实演示请使用 --run 且确保后台可用"
    exit 0
fi
DRY_RUN=1
LOG_DIR="logs/demos/$(date -u +%Y%m%d)"

if [[ "$1" == "--apply" ]]; then
    DRY_RUN=0
fi

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

mkdir -p "$LOG_DIR"

clear

echo -e "${CYAN}"
cat << "EOF"
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║     ██████╗ ██████╗ ██╗███████╗████████╗              ║
║     ██╔══██╗██╔══██╗██║██╔════╝╚══██╔══╝              ║
║     ██║  ██║██████╔╝██║█████╗     ██║                 ║
║     ██║  ██║██╔══██╗██║██╔══╝     ██║                 ║
║     ██████╔╝██║  ██║██║██║        ██║                 ║
║     ╚═════╝ ╚═╝  ╚═╝╚═╝╚═╝        ╚═╝                 ║
║                                                          ║
║           心悦宇宙 - 功能演示                             ║
║     完全自然语言驱动的 AI 冒险系统                        ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

run_curl() {
    if [ $DRY_RUN -eq 1 ]; then
        echo "[dry-run] curl $*" | tee -a "$LOG_DIR/demo.log"
    else
        echo "[exec] curl $*" | tee -a "$LOG_DIR/demo.log"
        curl "$@" | tee -a "$LOG_DIR/demo.log"
    fi
}

# 检查后端
if [ $DRY_RUN -eq 0 ]; then
    if ! curl -s $BASE_URL/health >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠ 后端未运行，正在启动...${NC}"
        cd /Users/zxydediannao/DriftSystem
        ./start_all.sh
        sleep 5
    fi
    echo -e "${GREEN}✓ 后端运行中${NC}"
else
    echo -e "${YELLOW}dry-run：跳过后端连通性检查${NC}"
fi
echo ""

DEMO_PLAYER="demo_$(date +%s)"

# ============================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}演示 1: 心悦文集关卡系统${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${CYAN}📚 获取所有关卡列表...${NC}"
echo ""

run_curl -s $BASE_URL/story/levels | python3 -c "
import sys, json
levels = json.load(sys.stdin)
print(f'共有 {len(levels)} 个关卡：\n')
for i, l in enumerate(levels[:5], 1):
    print(f\"  {i}. {l['id']}: {l['title']}\")
    print(f\"     章节: {l.get('chapter', 'N/A')} | 标签: {', '.join(l.get('tags', []))}\" )
    print()
if len(levels) > 5:
    print(f'  ... 还有 {len(levels) - 5} 个关卡')
"

read -p "按Enter继续..."

# ============================================================
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}演示 2: 新手教学系统${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${CYAN}🎓 启动新手教学...${NC}"
echo ""

run_curl -s -X POST $BASE_URL/tutorial/start/$DEMO_PLAYER | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data.get('status') == 'started':
    tut = data.get('tutorial', {})
    print(f\"✓ 教学已启动\")
    print(f\"\n{tut.get('title', '')}\")
    print(f\"{tut.get('instruction', '')}\")
"

echo ""
echo -e "${CYAN}📝 测试教学进度 (步骤1-3)...${NC}"
echo ""

# 步骤1
echo -e "${PURPLE}玩家: 你好${NC}"
RESULT=$(run_curl -s -X POST $BASE_URL/tutorial/check \
    -H "Content-Type: application/json" \
    -d "{\"player_id\":\"$DEMO_PLAYER\",\"message\":\"你好\"}")

echo "$RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data.get('completed'):
    result = data.get('result', {})
    print(f\"✓ {result.get('success_message', '')}\")
    if 'next_step' in result:
        next = result['next_step']
        print(f\"\n下一步: {next.get('title', '')}\")
" || echo "未完成"

sleep 1

# 步骤2
echo ""
echo -e "${PURPLE}玩家: 这是什么地方？${NC}"
RESULT=$(run_curl -s -X POST $BASE_URL/tutorial/check \
    -H "Content-Type: application/json" \
    -d "{\"player_id\":\"$DEMO_PLAYER\",\"message\":\"这是什么地方\"}")

echo "$RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data.get('completed'):
    result = data.get('result', {})
    print(f\"✓ {result.get('success_message', '')}\")
    if 'next_step' in result:
        next = result['next_step']
        print(f\"\n下一步: {next.get('title', '')}\")
" || echo "未完成"

sleep 1

# 步骤3
echo ""
echo -e "${PURPLE}玩家: 创建一个剧情${NC}"
RESULT=$(run_curl -s -X POST $BASE_URL/tutorial/check \
    -H "Content-Type: application/json" \
    -d "{\"player_id\":\"$DEMO_PLAYER\",\"message\":\"创建一个剧情\"}")

echo "$RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data.get('completed'):
    result = data.get('result', {})
    print(f\"✓ {result.get('success_message', '')}\")
" || echo "未完成"

read -p "按Enter继续..."

# ============================================================
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}演示 3: NPC增强行为系统${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${CYAN}🤖 加载第一关并查看NPC配置...${NC}"
echo ""

run_curl -s -X POST $BASE_URL/story/load/$DEMO_PLAYER/level_01 | python3 -c "
import sys, json
data = json.load(sys.stdin)
patch = data.get('bootstrap_patch', {})
spawn = patch.get('mc', {}).get('spawn', {})

if spawn:
    print(f\"NPC名称: {spawn.get('name', 'N/A')}\")
    print(f\"类型: {spawn.get('type', 'N/A')}\")
    print()
    
    behaviors = spawn.get('behaviors', [])
    print(f\"行为数量: {len(behaviors)}\")
    print()
    
    for i, b in enumerate(behaviors, 1):
        print(f\"  {i}. {b.get('type', 'unknown')}\")
        if b.get('action'):
            print(f\"     动作: {b.get('action')}\")
        if b.get('message'):
            print(f\"     消息: {b.get('message')[:50]}...\")
        print()
    
    ai_hints = spawn.get('ai_hints', '')
    if ai_hints:
        print(f\"AI提示: {ai_hints[:100]}...\")
else:
    print('未找到NPC配置')
"

read -p "按Enter继续..."

# ============================================================
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}演示 4: AI剧情生成${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${CYAN}✨ AI创建新剧情...${NC}"
echo ""

run_curl -s -X POST $BASE_URL/story/inject \
    -H "Content-Type: application/json" \
    -d '{"level_id":"demo_level","title":"月光探险","text":"在月光下的神秘探险..."}' | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data.get('status') == 'ok':
    print(f\"✓ 剧情创建成功！\")
    print(f\"关卡ID: {data.get('level_id')}\")
else:
    print(f\"创建失败: {data.get('detail', 'Unknown error')}\")
"

read -p "按Enter继续..."

# ============================================================
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}演示 5: 剧情推进引擎${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${CYAN}📖 推进剧情...${NC}"
echo ""

echo -e "${PURPLE}玩家: 你好，我是冒险者${NC}"
curl -s -X POST $BASE_URL/world/apply \
  -H "Content-Type: application/json" \
  -d "{\"player_id\":\"$DEMO_PLAYER\",\"action\":{\"say\":\"你好，我是冒险者\"},\"world_state\":{}}" | python3 -c "
import sys, json
data = json.load(sys.stdin)
node = data.get('story_node', {})
if node:
    print(f\"\n【{node.get('title', 'Story')}】\")
    print(f\"{node.get('text', '')[:200]}...\")
else:
    print('未返回剧情节点')
"

echo ""
read -p "按Enter继续..."

# ============================================================
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  演示完成！${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${CYAN}功能总结：${NC}"
echo -e "  ${GREEN}✓${NC} 心悦文集 - 30+精心设计的关卡"
echo -e "  ${GREEN}✓${NC} 新手教学 - 7步渐进式引导"
echo -e "  ${GREEN}✓${NC} NPC行为 - 增强的互动系统"
echo -e "  ${GREEN}✓${NC} AI生成 - 自动创建新剧情"
echo -e "  ${GREEN}✓${NC} 剧情引擎 - 智能推进故事"
echo ""
echo -e "${CYAN}下一步：${NC}"
echo "  1. 加入 Minecraft 服务器: localhost:25565"
echo "  2. 直接在聊天中说话即可开始游戏"
echo "  3. 新玩家会自动进入教学系统"
echo ""
echo -e "${YELLOW}提示：查看完整文档${NC}"
echo "  cat INTEGRATION.md"
echo "  cat README_NEW.md"
echo ""
