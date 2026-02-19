# REPO_MAP.md
## DriftSystem 系统真实结构地图

> **Research Task**: 理解"Intent（意图）是在什么地方变成 World Mutation（世界改变）的？"

---

## 1. 运行时组件（Runtime Components）

### 1.1 FastAPI Backend
- **入口**: `/home/runner/work/DriftSystem/DriftSystem/backend/app/main.py`
- **端口**: 8000 (uvicorn)
- **启动命令**: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
- **配置文件**: `backend/.env` (API keys, secrets)
- **依赖**: `backend/requirements.txt`

**核心职责**:
- 意图分类与理解（Intent Recognition）
- 建造计划生成（Build Plan Generation）
- 裁决系统（Adjudication System）
- 世界补丁验证（Patch Validation）
- RCON 调度（Command Dispatch to MC Server）

---

### 1.2 Minecraft Paper Plugin (Java)
- **源码**: `/home/runner/work/DriftSystem/DriftSystem/system/mc_plugin/src/main/java/com/driftmc/`
- **入口类**: `DriftPlugin.java`
- **构建系统**: Maven (`pom.xml`)
- **构建命令**: `cd system/mc_plugin && mvn clean package`
- **部署路径**: `server/plugins/DriftSystem.jar`
- **配置文件**: `server/plugins/DriftSystem/config.yml`

**核心职责**:
- 玩家事件监听（Chat, Join, Move, Interact）
- CityPhone UI 渲染
- NPC 行为执行
- 粒子/音效/天气播放
- 世界传送与场景加载
- 后端 HTTP 调用

**关键 Java 包**:
```
com.driftmc.cityphone/     → CityPhone 档案馆终端
com.driftmc.atmosphere/    → 社会氛围（粒子/天气/音效）
com.driftmc.scene/         → 场景加载与生命周期管理
com.driftmc.minimap/       → 小地图与螺旋触发点
com.driftmc.dsl/           → DSL 解析与执行
com.driftmc.hud/           → HUD 渲染
com.driftmc.npc/           → NPC 行为引擎
```

---

### 1.3 Minecraft Paper Server
- **运行路径**: `backend/server/` 或 `server/`
- **可执行文件**: `paper-1.20.1.jar`
- **启动命令**: `java -Xmx4G -Xms2G -jar paper-1.20.1.jar`
- **配置**: `server.properties`, `bukkit.yml`, `paper.yml`, `spigot.yml`
- **数据**: `world/`, `world_nether/`, `world_the_end/`

**核心职责**:
- 原版 Minecraft 世界模拟
- 插件加载与事件分发
- RCON 服务器（接收后端指令）
- 玩家会话管理

---

### 1.4 启动脚本
| 脚本 | 作用 |
|------|------|
| `start_all.sh` | 同时启动后端 + MC Server |
| `backend/start_backend.sh` | 仅启动 FastAPI |
| `backend/start_mc.sh` | 仅启动 MC Server |
| `build_and_deploy.sh` | 完整构建 + 部署流程 |
| `build_plugin.sh` | 仅构建插件 |

---

## 2. 系统入口点（Entry Points）

### 2.1 玩家进入系统的路径
```
玩家打开 Minecraft
    ↓
连接到 Paper Server (localhost:25565)
    ↓
DriftPlugin.onEnable() 初始化
    ↓
PlayerJoinListener 触发
    ↓
GET /ideal-city/social-feedback/atmosphere (获取城市气氛)
    ↓
SocialAtmosphereManager 播放粒子/天气/音效
```

### 2.2 玩家输入 → 后端处理 → 世界修改的完整路径

#### **路径 A: 自然语言聊天（Intent-Driven）**
```
1. 玩家在聊天框输入: "建造一个红砖房"
    ↓
2. PlayerChatListener.onChat() [Java Plugin]
    ↓
3. IntentRouter2.routeIntent() [Java]
    ↓
4. IntentDispatcher2.dispatchIntent() [Java]
    |
    | HTTP POST to Backend
    ↓
5. POST /intent/recognize [FastAPI]
    | app/api/intent_api.py:recognize_intent()
    ↓
6. creation_workflow.classify_message() [Python]
    | app/services/creation_workflow.py
    | → 使用 embedding model 分类
    | → 返回 slot 信息 (structure_type, material, size)
    ↓
7. load_default_transformer() [Python]
    | app/core/creation/transformer.py
    | → 生成 CreationPlan
    | → 包含多个 CreationPatchTemplate
    | → 每个 template 包含 MC 指令列表
    ↓
8. PatchExecutor.dry_run(plan) [Python]
    | app/core/world/patch_executor.py
    | → validate_patch_template() 检查 execution_tier
    | → analyze_commands() 检查命令安全性
    | → 返回 PatchExecutionResult
    ↓
9. IF tier == "safe_auto":
    |   PlanExecutor.execute(plan) [Python]
    |   | app/core/world/plan_executor.py
    |   | → RconClient.execute_command() [Python]
    |   | → 发送到 MC Server RCON
    |   ↓
    |   Minecraft 世界变更 (setblock, fill, summon)
    |   ↓
    |   PatchTransactionLog.record() 记录执行日志
    ELSE:
        返回 "needs_confirm" → 等待玩家确认
```

**关键文件**:
- Intent 识别: `backend/app/services/creation_workflow.py` (分类逻辑)
- Plan 生成: `backend/app/core/creation/transformer.py` (CreationPlan 构造)
- 安全验证: `backend/app/core/world/command_safety.py` (白名单/黑名单)
- 执行层: `backend/app/core/world/plan_executor.py` (RCON 调度)
- 日志审计: `backend/app/core/world/patch_transaction.py` (append-only log)

---

#### **路径 B: CityPhone 档案馆提交（Ideal City Pipeline）**
```
1. 玩家右键 CityPhone 物品
    ↓
2. CityPhoneManager.openInterface() [Java]
    ↓
3. CityPhoneUI 渲染档案馆界面 [Java]
    | → 显示展品列表、草稿、叙述模板
    ↓
4. 玩家点击"提交叙述"
    ↓
5. CityPhoneListener.onClick() [Java]
    | → 收集表单数据
    |
    | HTTP POST to Backend
    ↓
6. POST /ideal-city/cityphone/action [FastAPI]
    | app/api/ideal_city_api.py:cityphone_action()
    ↓
7. IdealCityPipeline.submit(device_spec) [Python]
    | app/core/ideal_city/pipeline.py
    | 
    | → SpecNormalizer.clean(spec) [去除占位符]
    | → IdealCityAdjudicator.evaluate(spec) [裁决]
    |    | → 检查 world_constraints, logic_outline, risk_register
    |    | → 返回 AdjudicationRecord (verdict: ACCEPT/REJECT/REVIEW_REQUIRED)
    | 
    | → IF verdict == ACCEPT:
    |      BuildPlanAgent.generate_plan(spec)
    |      | → 生成 BuildPlan
    |      | → 包含 patches (世界修改指令)
    |      ↓
    |      BuildExecutor.execute(plan)
    |      | → 通过 RCON 执行指令
    |      ↓
    |      SocialFeedbackRepository.record_feedback()
    |      | → 记录社会反馈事件
    |      ↓
    |      AtmosphereManager 更新城市气氛
    ↓
8. 返回 ExecutionNotice 给插件
    ↓
9. CityPhoneUI 显示裁决结果 + 建造进度
```

**关键文件**:
- 裁决入口: `backend/app/core/ideal_city/pipeline.py` (IdealCityPipeline)
- 裁决逻辑: `backend/app/core/ideal_city/adjudication_contract.py` (AdjudicationRecord)
- 建造计划: `backend/app/core/ideal_city/build_plan_agent.py` (BuildPlanAgent)
- 执行层: `backend/app/core/ideal_city/build_executor.py` (BuildExecutor)
- 社会反馈: `backend/app/core/ideal_city/social_feedback.py` (SocialFeedbackRepository)

---

#### **路径 C: Quest/Task 完成验证**
```
1. 玩家触发事件 (破坏方块, 击杀实体, 收集物品)
    ↓
2. RuleEventListener [Java Plugin]
    ↓
3. QuestEventCanonicalizer.canonical(event) [Java]
    | → 标准化事件格式
    |
    | HTTP POST to Backend
    ↓
4. POST /quest/event [FastAPI]
    | app/api/quest_api.py:submit_event()
    ↓
5. QuestRuntime.record_event(event) [Python]
    | app/core/quest/runtime.py
    | 
    | → _match_event(event, milestone) [匹配里程碑]
    | → IF 匹配成功:
    |      milestone.status = "completed"
    |      _completion_payload() 生成奖励
    |      ↓
    |      QuestRuntime.check_completion(level, player)
    |      | → 检查所有任务是否完成
    |      | → IF 全部完成:
    |           返回 completion_summary + rewards + world_patch
    ↓
6. 后端返回奖励指令 (give, xp, title)
    ↓
7. Plugin 执行奖励指令 + 播放粒子/音效
```

**关键文件**:
- Quest 运行时: `backend/app/core/quest/runtime.py` (QuestRuntime)
- 任务定义: Level JSON 文件中的 `tasks` 字段
- 规则监听: `system/mc_plugin/.../RuleEventListener.java`
- 事件标准化: `system/mc_plugin/.../QuestEventCanonicalizer.java`

---

## 3. 配置层 / Schema 层 / 执行层的位置

### 3.1 配置层（Configuration Layer）
| 配置类型 | 位置 | 作用 |
|----------|------|------|
| **Backend 环境变量** | `backend/.env` | OpenAI/Deepseek API keys, RCON credentials |
| **Plugin 配置** | `server/plugins/DriftSystem/config.yml` | Backend URL, debug token, feature flags |
| **MC Server 配置** | `server.properties` | 端口、难度、spawn protection |
| **Level 定义** | `backend/data/heart_levels/*.json` | 关卡叙事、任务、场景、规则 |
| **Phase 定义** | `phases/phase_N.md` | 开发阶段规划与路线图 |

---

### 3.2 Schema 层（Data Schema Layer）

#### **Level Schema**
**文件**: `backend/app/core/story/level_schema.py`

**关键类**:
- `Level`: 关卡定义
- `Beat`: 叙事节拍
- `MemoryCondition`: 记忆门控（AND/OR 逻辑）
- `MemoryMutation`: 状态变更
- `BeatChoice`: 玩家选择分支
- `Task`: 任务定义
- `Milestone`: 里程碑

**实例**: `backend/data/heart_levels/level_01.json`
```json
{
  "id": "level_1",
  "title": "心悦文集 第1章",
  "narrative": { "beats": [...] },
  "scene": { "teleport": {...}, "environment": {...} },
  "rules": { "listeners": [...] },
  "tasks": [ { "id": "...", "milestones": [...], "rewards": [...] } ],
  "exit": { "return_spawn": "...", "teleport": {...} }
}
```

---

#### **DeviceSpec Schema (Ideal City)**
**文件**: `backend/app/core/ideal_city/device_spec.py`

**字段**:
```python
class DeviceSpec:
    spec_id: str
    player_ref: str
    submission_text: str
    is_draft: bool
    world_constraints: str  # 世界约束（必需）
    logic_outline: List[str]  # 逻辑大纲（必需）
    risk_register: str  # 风险登记（必需）
    success_criteria: str  # 成功标准（可选）
    resource_ledger: str  # 资源账本（可选）
    timestamp: str
```

---

#### **AdjudicationRecord Schema**
**文件**: `backend/app/core/ideal_city/adjudication_contract.py`

```python
class AdjudicationRecord:
    ruling_id: str  # UUID
    verdict: VerdictEnum  # ACCEPT | REJECT | PARTIAL | REVIEW_REQUIRED
    reasoning: List[str]  # 裁决理由
    conditions: List[str]  # 后续条件（REJECT 时）
    memory_hooks: List[str]  # 状态变更标记
```

---

#### **CreationPlan Schema**
**文件**: `backend/app/core/creation/transformer.py`

```python
class CreationPlan:
    plan_id: str
    player_id: str
    intent: str  # 玩家原始意图
    patches: List[CreationPatchTemplate]  # 补丁模板列表
    metadata: Dict
```

```python
class CreationPatchTemplate:
    template_id: str
    status: str  # "draft" | "resolved"
    steps: List[PatchStep]
```

```python
class PatchStep:
    step_id: str
    step_type: str  # "block_placement" | "entity_spawn" | "mod_function"
    commands: List[str]  # MC 指令
    placeholders: Dict  # 占位符 {key: value}
```

---

### 3.3 执行层（Execution Layer）

#### **A. 指令验证层（Command Validation）**
**文件**: `backend/app/core/world/command_safety.py`

**功能**: 白名单/黑名单检查
```python
ALLOWED_PREFIXES = ["setblock", "fill", "clone", "summon", "execute", "function", "particle", "title", "tellraw"]
BLACKLIST_TOKENS = [";", "&&", "||", "`", "$(", "\n"]
BLACKLIST_COMMANDS = ["op", "deop", "stop", "reload"]

def analyze_commands(commands) -> CommandSafetyReport:
    # 检查每条指令
    # 返回 errors (阻断) 和 warnings (非阻断)
```

---

#### **B. Patch 验证层（Patch Validation）**
**文件**: `backend/app/core/creation/validation.py`

**功能**: 结构完整性检查
```python
def validate_patch_template(template: Dict) -> PatchTemplateValidationResult:
    # 检查 execution_tier:
    #   "safe_auto"      → 可自动执行
    #   "needs_confirm"  → 需要玩家确认
    #   "blocked"        → 有错误，禁止执行
```

---

#### **C. Patch 执行层（Patch Execution）**
**文件**: `backend/app/core/world/patch_executor.py`

**功能**: Dry-run 模拟执行
```python
class PatchExecutor:
    def dry_run(self, plan: CreationPlan) -> PatchExecutionResult:
        # 1. 验证每个 template
        # 2. 分类: executed (通过) vs skipped (跳过)
        # 3. 生成 transaction log
        # 4. 返回执行结果
```

**返回值**:
```python
class PatchExecutionResult:
    executed: List[Template]  # 通过验证的
    skipped: List[SkipRecord]  # 跳过的 (带原因)
    errors: List[str]  # 错误
    warnings: List[str]  # 警告
    transactions: List[TransactionEntry]  # 审计日志
```

---

#### **D. RCON 调度层（RCON Dispatch）**
**文件**: `backend/app/core/minecraft/rcon_client.py`

**功能**: 发送指令到 MC Server
```python
class RconClient:
    def execute_command(self, command: str) -> str:
        # 通过 RCON 协议发送指令
        # 返回服务器响应
```

**配置**:
```python
RCON_HOST = "localhost"
RCON_PORT = 25575
RCON_PASSWORD = "your_rcon_password"
```

---

#### **E. 事务日志层（Transaction Log）**
**文件**: `backend/app/core/world/patch_transaction.py`

**功能**: Append-only 审计日志
```python
class PatchTransactionLog:
    def record(self, patch_id, template_id, step_id, commands, status, metadata):
        # 写入 JSON 日志
        # 状态: "pending" → "validated" → "applied" → "rolled_back"
```

**日志结构**:
```json
{
  "patch_id": "uuid",
  "template_id": "uuid",
  "step_id": "step_1",
  "commands": ["setblock ~ ~ ~ stone"],
  "status": "applied",
  "created_at": "2026-01-09T12:34:56Z",
  "metadata": { "mode": "auto", "summary": "建造红砖房" }
}
```

---

## 4. 关键问题解答: "Intent 是在什么地方变成 World Mutation 的？"

### 答案: **Intent → Mutation 的 9 个关键转换点**

| # | 层级 | 位置 | 输入 | 输出 | 关键逻辑 |
|---|------|------|------|------|----------|
| 1 | **Intent Capture** | `PlayerChatListener.java` | 玩家聊天文本 | HTTP JSON Payload | 事件监听 → 封装为 IntentPayload |
| 2 | **Intent Classification** | `creation_workflow.classify_message()` | 自然语言 | Intent Slots (structure_type, material) | Embedding model 分类 |
| 3 | **Plan Generation** | `transformer.load_default_transformer()` | Intent Slots | CreationPlan (patches) | 模板填充 → 生成 MC 指令 |
| 4 | **Command Safety Check** | `command_safety.analyze_commands()` | 指令列表 | SafetyReport (errors/warnings) | 白名单/黑名单验证 |
| 5 | **Template Validation** | `validation.validate_patch_template()` | PatchTemplate | execution_tier (safe_auto/needs_confirm/blocked) | 结构完整性检查 |
| 6 | **Dry-Run Execution** | `PatchExecutor.dry_run()` | CreationPlan | PatchExecutionResult | 模拟执行 → 生成 transaction log |
| 7 | **RCON Dispatch** | `RconClient.execute_command()` | MC Command | Server Response | RCON 协议 → 发送到 MC Server |
| 8 | **World Mutation** | Minecraft Server | MC Command | 世界状态变更 | setblock/fill/summon 执行 |
| 9 | **Transaction Record** | `PatchTransactionLog.record()` | Execution Result | Audit Log Entry | 写入 append-only log |

---

### 流程图
```
玩家输入 "建造红砖房"
    ↓ [1. Intent Capture - PlayerChatListener]
Intent JSON { "player": "steve", "text": "建造红砖房" }
    ↓ [2. Intent Classification - classify_message()]
Intent Slots { "structure_type": "house", "material": "red_bricks" }
    ↓ [3. Plan Generation - load_default_transformer()]
CreationPlan { 
  patches: [
    { step_type: "block_placement", commands: ["fill ~-2 ~ ~-2 ~2 ~4 ~2 red_bricks"] }
  ]
}
    ↓ [4. Command Safety Check - analyze_commands()]
SafetyReport { errors: [], warnings: [] }  ✓ 通过
    ↓ [5. Template Validation - validate_patch_template()]
execution_tier = "safe_auto"  ✓ 通过
    ↓ [6. Dry-Run Execution - PatchExecutor.dry_run()]
PatchExecutionResult { 
  executed: [template_1], 
  skipped: [],
  transactions: [{ status: "validated" }]
}
    ↓ [7. RCON Dispatch - RconClient.execute_command()]
RCON → "fill 100 70 200 104 74 204 red_bricks"
    ↓ [8. World Mutation - Minecraft Server]
世界坐标 (100,70,200) 至 (104,74,204) 填充红砖
    ↓ [9. Transaction Record - PatchTransactionLog.record()]
Audit Log { 
  status: "applied", 
  created_at: "2026-01-09T12:34:56Z"
}
```

---

## 5. 数据流动图（Data Flow Diagram）

```
┌────────────────────────────────────────────────────────────┐
│                        玩家层（Player）                      │
│  Minecraft Client → Paper Server → DriftPlugin              │
└──────────────────────┬─────────────────────────────────────┘
                       │ HTTP POST
                       ↓
┌────────────────────────────────────────────────────────────┐
│                    FastAPI 后端（Backend）                   │
│                                                              │
│  ┌──────────────────┐      ┌──────────────────┐            │
│  │  Intent Router   │ →    │ Creation Workflow│            │
│  └──────────────────┘      └──────────────────┘            │
│           ↓                         ↓                       │
│  ┌──────────────────┐      ┌──────────────────┐            │
│  │ Adjudication     │      │ Plan Transformer │            │
│  │ (Ideal City)     │      │ (CreationPlan)   │            │
│  └──────────────────┘      └──────────────────┘            │
│           ↓                         ↓                       │
│  ┌──────────────────────────────────────────┐              │
│  │        Patch Validation & Safety         │              │
│  │  (command_safety + validation.py)        │              │
│  └──────────────────────────────────────────┘              │
│           ↓                                                 │
│  ┌──────────────────────────────────────────┐              │
│  │         Patch Executor (Dry-Run)         │              │
│  └──────────────────────────────────────────┘              │
│           ↓                                                 │
│  ┌──────────────────────────────────────────┐              │
│  │        RCON Client (Command Dispatch)    │              │
│  └──────────────────────────────────────────┘              │
│           │                                                 │
└───────────┼─────────────────────────────────────────────────┘
            │ RCON Protocol (port 25575)
            ↓
┌────────────────────────────────────────────────────────────┐
│                  Minecraft Server (Paper)                   │
│  World Engine → Block Updates → Entity Spawns              │
└────────────────────────────────────────────────────────────┘
            ↓
┌────────────────────────────────────────────────────────────┐
│                    Transaction Log                          │
│  Append-only audit trail (JSON files)                      │
└────────────────────────────────────────────────────────────┘
```

---

## 6. 关键发现（Key Findings）

### 6.1 Intent → Mutation 的 **Transformation Layers**
1. **Natural Language** (玩家聊天) → 字符串
2. **Intent Payload** (JSON) → 结构化数据
3. **Intent Slots** (语义标签) → 分类结果
4. **CreationPlan** (建造计划) → 步骤序列
5. **MC Commands** (Minecraft 指令) → 可执行命令
6. **RCON Protocol** (网络协议) → 二进制数据流
7. **World State Change** (世界状态) → 方块/实体变更

### 6.2 **Validation Gates** (验证门控)
- **Gate 1**: Command Safety (白名单/黑名单)
- **Gate 2**: Template Validation (结构完整性)
- **Gate 3**: Execution Tier (safe_auto/needs_confirm/blocked)
- **Gate 4**: Dry-Run Simulation (模拟执行)
- **Gate 5**: Adjudication Verdict (ACCEPT/REJECT)
- **Gate 6**: Quest Milestone Match (任务匹配)
- **Gate 7**: Memory Condition (记忆门控)

### 6.3 **Proof Points** (可审计点)
1. **Intent Log**: 玩家原始输入
2. **Classification Result**: Intent slots
3. **Generated Plan**: CreationPlan JSON
4. **Safety Report**: 安全检查结果
5. **Validation Result**: execution_tier
6. **Transaction Log**: 执行记录
7. **RCON Response**: 服务器响应
8. **World State Snapshot**: 世界状态快照 (未实现)

---

## 7. 文件索引（File Index）

### Backend Core Files
```
backend/app/main.py                              # FastAPI 入口
backend/app/api/intent_api.py                    # Intent 识别 API
backend/app/api/ideal_city_api.py                # Ideal City 裁决 API
backend/app/api/quest_api.py                     # Quest 任务 API

backend/app/services/creation_workflow.py        # Intent 分类
backend/app/core/creation/transformer.py         # Plan 生成
backend/app/core/creation/validation.py          # Template 验证
backend/app/core/world/command_safety.py         # 指令安全检查
backend/app/core/world/patch_executor.py         # Patch 执行器
backend/app/core/world/plan_executor.py          # Plan 执行器
backend/app/core/world/patch_transaction.py      # 事务日志
backend/app/core/minecraft/rcon_client.py        # RCON 客户端

backend/app/core/ideal_city/pipeline.py          # Ideal City 管线
backend/app/core/ideal_city/adjudication_contract.py  # 裁决合约
backend/app/core/ideal_city/build_plan_agent.py  # 建造计划生成
backend/app/core/ideal_city/build_executor.py    # 建造执行器
backend/app/core/ideal_city/social_feedback.py   # 社会反馈

backend/app/core/quest/runtime.py                # Quest 运行时
backend/app/core/story/story_engine.py           # Story 引擎
backend/app/core/story/level_schema.py           # Level Schema
```

### Plugin Core Files
```
system/mc_plugin/src/main/java/com/driftmc/
    DriftPlugin.java                             # 插件入口
    PlayerChatListener.java                      # 聊天监听
    cityphone/CityPhoneManager.java              # CityPhone 管理
    cityphone/CityPhoneUI.java                   # UI 渲染
    scene/SceneLifecycleBridge.java              # 场景加载
    scene/RuleEventListener.java                 # 规则事件监听
    atmosphere/SocialAtmosphereManager.java      # 社会氛围
    npc/NPCBehaviorEngine.java                   # NPC 行为
```

### Data Files
```
backend/data/heart_levels/level_01.json          # Level 定义示例
backend/data/ideal_city/device_specs/            # 设备规格存档
backend/data/ideal_city/build_queue/             # 建造队列
backend/data/protocol/cityphone/                 # CityPhone 协议数据
```

---

## 8. 总结

**核心发现**:
- Intent 在 **9 个层级** 中逐步转换为 World Mutation
- 有 **7 个验证门控** 防止非法操作
- 有 **8 个可审计点** 记录完整执行轨迹
- **关键瓶颈**: RCON 调度层是唯一的世界修改入口

**数学验证的插入点**:
- **Gate 3** (Execution Tier): 可添加 "math_proof_required" tier
- **Gate 5** (Adjudication): 可嵌入数学公式验证
- **Transaction Log**: 可存储验证证明（proof payload）

**下一步研究方向**:
- 如何在 Command Safety 层插入数学公式验证？
- 如何在 Adjudication 层要求数学证明？
- 如何在 Transaction Log 中记录可重放的证明轨迹？
