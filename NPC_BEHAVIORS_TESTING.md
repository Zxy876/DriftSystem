# NPC行为系统测试文档

## 📋 功能概述

### ✅ 已实现功能

#### 1. **NPC行为配置系统**
- 30个关卡的NPC都配置了特定行为
- 行为类型包括：
  - `patrol` - 巡逻
  - `stand` - 站立
  - `interact` - 互动对话
  - `quest` - 任务触发
  - `wander` - 漫步
  - `fish` - 钓鱼
  - `mine` - 挖矿
  - `garden` - 园艺
  - `float` - 悬浮

#### 2. **自然语言触发系统**
- 玩家可以用自然语言与NPC互动
- 关键词匹配触发任务
- AI上下文感知NPC性格和行为

#### 3. **核心组件**

**后端：**
- `npc_behavior_engine.py` - NPC行为引擎
- `npc_api.py` - NPC互动API
- `enhance_npc_behaviors.py` - 批量增强脚本

**API端点：**
- `GET /npc/behaviors/{level_id}` - 获取NPC行为列表
- `POST /npc/interact` - 与NPC互动
- `GET /npc/context/{level_id}` - 获取AI上下文

---

## 🧪 测试案例

### Test Case 1: 赛车手桃子（level_01）

**NPC行为：**
- 巡逻赛道
- 右键对话
- 任务：飘移入门

**测试步骤：**
```bash
# 1. 加载关卡
curl -X POST "http://127.0.0.1:8000/story/load/player1/level_01"

# 2. 查看NPC行为
curl "http://127.0.0.1:8000/npc/behaviors/level_01"

# 3. 触发任务（说"我想学习飘移技巧"）
curl -X POST "http://127.0.0.1:8000/npc/interact" \
  -H "Content-Type: application/json" \
  -d '{"player_id":"player1","level_id":"level_01","message":"我想学习飘移技巧"}'
```

**预期结果：**
```json
{
  "status": "ok",
  "interaction_type": "quest_trigger",
  "mc": [
    {"tell": "§e✨ 任务开始：飘移入门"},
    {"tell": "看来你对飘移入门感兴趣！让我来帮助你。"},
    {"effect": {"type": "SPEED", "duration": 600, "amplifier": 1}},
    {"give_xp": 100}
  ]
}
```

**奖励：**
- ⚡ 速度提升效果（10分钟）
- 📚 经验值+100

---

### Test Case 2: 诗人（level_10）

**NPC行为：**
- 在湖边漫步
- 吟诵诗歌
- 任务：诗意人生

**测试步骤：**
```bash
# 1. 加载关卡
curl -X POST "http://127.0.0.1:8000/story/load/player2/level_10"

# 2. 与诗人对话（说"我想听诗"）
curl -X POST "http://127.0.0.1:8000/npc/interact" \
  -H "Content-Type: application/json" \
  -d '{"player_id":"player2","level_id":"level_10","message":"我想听诗"}'
```

**预期结果：**
- 触发"诗意人生"任务
- 诗人会吟诵诗歌
- 获得灵感buff

---

### Test Case 3: 图书管理员（level_02）

**NPC行为：**
- 站在书架旁
- 提供知识查询
- 任务：知识探索

**触发关键词：**
- "书"
- "知识"
- "学习"

**测试：**
```bash
curl -X POST "http://127.0.0.1:8000/npc/interact" \
  -H "Content-Type: application/json" \
  -d '{"player_id":"player3","level_id":"level_02","message":"我想找关于数学的书"}'
```

---

## 🎮 游戏内使用示例

### 场景1：与NPC对话

**玩家输入（聊天框）：**
```
桃子，教我飘移技巧
```

**系统处理流程：**
1. IntentDispatcher识别为NPC_INTERACT意图
2. 调用 `/npc/interact` API
3. 检测关键词"飘移"、"技巧"
4. 触发"飘移入门"任务
5. 给予速度buff和经验值

**玩家看到：**
```
§e✨ 任务开始：飘移入门
§e[桃子]§r 看来你对飘移入门感兴趣！让我来帮助你。
§a你获得了速度提升效果！
§b+100 经验值
```

---

### 场景2：自然语言控制NPC

**玩家输入：**
```
让园丁浇花
```

**系统响应：**
- NPC执行浇花动作
- 播放浇水音效
- 显示水花粒子效果

---

### 场景3：剧情中的NPC互动

**AI剧情生成时：**
```
你来到赛道边，看到桃子正在调试赛车。他注意到你，热情地挥手打招呼。

桃子："嘿！想试试飘移吗？记住，关键是不要驻车！"

[提示] 你可以说"我想学习飘移技巧"来接受挑战
```

**玩家响应后：**
- 自动触发任务系统
- NPC行为改变（例如从站立变为演示飘移）
- 场景动态更新

---

## 🔧 NPC行为配置示例

### level_01.json - 赛车手桃子
```json
{
  "world_patch": {
    "mc": {
      "spawn": {
        "type": "villager",
        "name": "赛车手桃子",
        "offset": {"dx": 3, "dy": 0, "dz": 3},
        "behaviors": [
          {
            "type": "patrol",
            "path": [
              {"dx": 0, "dz": 5},
              {"dx": 5, "dz": 5},
              {"dx": 5, "dz": 0},
              {"dx": 0, "dz": 0}
            ],
            "speed": 1.2,
            "description": "在赛道周围巡逻"
          },
          {
            "type": "interact",
            "trigger": "right_click",
            "action": "dialogue",
            "messages": [
              "§e[桃子]§r 你好！想要挑战一百公里飘移吗？",
              "§e[桃子]§r 记住，不能驻车！提速就要全力以赴！"
            ]
          },
          {
            "type": "quest",
            "trigger_keywords": ["飘移", "赛车", "技巧"],
            "quest_name": "飘移入门",
            "rewards": ["speed_boost", "experience"]
          }
        ],
        "ai_hints": "桃子是热血的赛车手，对速度和技巧充满热情。"
      }
    }
  }
}
```

---

## 📊 NPC行为统计

| 关卡 | NPC | 行为数量 | 特色行为 |
|------|-----|----------|----------|
| level_01 | 赛车手桃子 | 3 | patrol, quest |
| level_02 | 图书管理员 | 3 | stand, knowledge |
| level_03 | 登山者 | 3 | climb |
| level_04 | 渔夫 | 3 | fish |
| level_05 | 护林员 | 3 | patrol, nature |
| level_06 | 商人 | 3 | trade |
| level_07 | 雪人 | 3 | particle(snow) |
| level_08 | 矿工 | 3 | mine |
| level_09 | 园丁 | 3 | garden |
| level_10 | 诗人 | 3 | wander, poetry |
| level_30 | 心悦守护者 | 3 | float, legendary |

---

## 🚀 插件端集成（待实现）

### IntentDispatcher2.java 需要添加：

```java
private void handleNpcInteract(Player player, String message, String levelId) {
    // 调用后端NPC API
    String url = backendUrl + "/npc/interact";
    
    JsonObject payload = new JsonObject();
    payload.addProperty("player_id", player.getUniqueId().toString());
    payload.addProperty("level_id", levelId);
    payload.addProperty("message", message);
    
    // 发送请求并处理响应
    backendClient.postAsync(url, payload.toString(), response -> {
        JsonObject result = JsonParser.parseString(response).getAsJsonObject();
        
        if ("ok".equals(result.get("status").getAsString())) {
            // 执行MC指令
            JsonArray mcCommands = result.getAsJsonArray("mc");
            for (JsonElement cmd : mcCommands) {
                executeMcCommand(player, cmd.getAsJsonObject());
            }
        }
    });
}
```

---

## 🎯 下一步开发计划

### Phase 1: 插件集成 ⏳
- [ ] 在IntentDispatcher中添加NPC互动处理
- [ ] 实现右键点击NPC触发对话
- [ ] 添加NPC任务追踪UI

### Phase 2: 高级行为 ⏳
- [ ] NPC动态寻路（A*算法）
- [ ] 情绪系统（根据互动改变态度）
- [ ] NPC间对话（多NPC场景）

### Phase 3: 可视化 ⏳
- [ ] NPC头顶状态显示
- [ ] 任务进度条
- [ ] 行为路径可视化

---

## 📝 API文档

### GET /npc/behaviors/{level_id}
获取指定关卡的NPC所有行为配置

**响应示例：**
```json
{
  "status": "ok",
  "level_id": "level_01",
  "behaviors": [
    {
      "type": "patrol",
      "description": "在赛道周围巡逻",
      "config": {...}
    }
  ]
}
```

### POST /npc/interact
处理玩家与NPC的自然语言互动

**请求体：**
```json
{
  "player_id": "uuid",
  "level_id": "level_01",
  "message": "我想学习飘移技巧"
}
```

**响应：**
```json
{
  "status": "ok",
  "interaction_type": "quest_trigger",
  "mc": [
    {"tell": "任务开始"},
    {"effect": {...}}
  ]
}
```

### GET /npc/context/{level_id}
获取NPC的AI上下文（用于对话生成）

**响应：**
```json
{
  "status": "ok",
  "ai_hints": "桃子是热血的赛车手...",
  "full_context": "【NPC性格与背景】..."
}
```

---

*生成时间: 2025-01-20*  
*后端版本: v2.stage + NPC System*  
*配置的NPC数量: 30*
