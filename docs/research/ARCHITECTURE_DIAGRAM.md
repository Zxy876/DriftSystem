# ARCHITECTURE_DIAGRAM.md
## DriftSystem 架构流程图（Mermaid Diagrams）

> **Research Task**: 使用 Mermaid 可视化"玩家 → 指令 → 路由 → 任务逻辑 → 执行器 → 世界变更"的完整路径

---

## 1. 系统总体架构（High-Level Architecture）

```mermaid
graph TB
    subgraph Player["玩家层 (Player Layer)"]
        MC[Minecraft Client]
    end
    
    subgraph Plugin["Paper Plugin Layer"]
        Chat[PlayerChatListener]
        CityPhone[CityPhoneManager]
        RuleListener[RuleEventListener]
        Atmosphere[SocialAtmosphereManager]
        SceneLoader[SceneLifecycleBridge]
    end
    
    subgraph Backend["FastAPI Backend"]
        IntentAPI[Intent API]
        IdealCityAPI[Ideal City API]
        QuestAPI[Quest API]
        WorldAPI[World API]
    end
    
    subgraph Processing["处理层 (Processing Layer)"]
        IntentClassifier[Intent Classifier]
        Adjudicator[Adjudicator]
        PlanGenerator[Plan Generator]
        PatchValidator[Patch Validator]
    end
    
    subgraph Execution["执行层 (Execution Layer)"]
        PatchExecutor[Patch Executor]
        RCON[RCON Client]
        TransactionLog[Transaction Log]
    end
    
    subgraph World["Minecraft Server"]
        PaperServer[Paper 1.20.1 Server]
        WorldEngine[World Engine]
    end
    
    MC -->|Chat/Action| Plugin
    Plugin -->|HTTP POST/GET| Backend
    Backend --> Processing
    Processing --> Execution
    Execution -->|RCON Protocol| World
    World -->|Events| Plugin
    Plugin -->|UI Update| MC
    Execution -->|Audit| TransactionLog
    
    style Player fill:#e1f5ff
    style Plugin fill:#fff4e1
    style Backend fill:#e8f5e9
    style Processing fill:#f3e5f5
    style Execution fill:#ffe0e0
    style World fill:#fce4ec
```

---

## 2. 玩家输入 → 世界变更完整流程

### 2.1 自然语言建造流程（Creation Workflow）

```mermaid
sequenceDiagram
    participant Player as 玩家
    participant Plugin as Paper Plugin
    participant IntentAPI as Intent API
    participant Classifier as Intent Classifier
    participant Transformer as Plan Transformer
    participant Validator as Patch Validator
    participant Executor as Patch Executor
    participant RCON as RCON Client
    participant Server as MC Server
    participant TxLog as Transaction Log
    
    Player->>Plugin: 聊天输入: "建造一个红砖房"
    activate Plugin
    Plugin->>Plugin: PlayerChatListener.onChat()
    Plugin->>Plugin: IntentRouter2.routeIntent()
    Plugin->>IntentAPI: POST /intent/recognize
    deactivate Plugin
    
    activate IntentAPI
    IntentAPI->>Classifier: classify_message(text)
    activate Classifier
    Classifier->>Classifier: Embedding Model 分类
    Classifier-->>IntentAPI: Intent Slots {structure_type, material, size}
    deactivate Classifier
    
    IntentAPI->>Transformer: load_default_transformer(slots)
    activate Transformer
    Transformer->>Transformer: 填充模板 → 生成 MC 指令
    Transformer-->>IntentAPI: CreationPlan {patches, commands}
    deactivate Transformer
    
    IntentAPI->>Validator: validate_patch_template(plan)
    activate Validator
    Validator->>Validator: 检查指令安全性
    Validator->>Validator: 分类 execution_tier
    Validator-->>IntentAPI: execution_tier = "safe_auto"
    deactivate Validator
    
    IntentAPI->>Executor: dry_run(plan)
    activate Executor
    Executor->>Executor: 模拟执行验证
    Executor->>TxLog: record(status="validated")
    Executor-->>IntentAPI: PatchExecutionResult {executed, skipped}
    deactivate Executor
    
    alt tier == "safe_auto"
        IntentAPI->>RCON: execute_command("fill ~ ~ ~ red_bricks")
        activate RCON
        RCON->>Server: RCON Protocol (port 25575)
        activate Server
        Server->>Server: 执行 fill 指令
        Server-->>RCON: Response: "Filled 125 blocks"
        deactivate Server
        RCON-->>IntentAPI: Success
        deactivate RCON
        
        IntentAPI->>TxLog: record(status="applied")
    else tier == "needs_confirm"
        IntentAPI-->>Plugin: 返回确认请求
    end
    
    IntentAPI-->>Plugin: ExecutionNotice + BuildPlan
    deactivate IntentAPI
    
    activate Plugin
    Plugin->>Player: 显示建造进度 + 粒子效果
    deactivate Plugin
```

**通信协议标注**:
- Plugin → Backend: **HTTP/JSON** (REST API)
- Backend → MC Server: **RCON Protocol** (port 25575, TCP)
- MC Server → Plugin: **Bukkit Event System** (内存事件总线)

---

### 2.2 CityPhone 档案馆提交流程（Ideal City Pipeline）

```mermaid
sequenceDiagram
    participant Player as 玩家
    participant CityPhone as CityPhone UI
    participant Plugin as Paper Plugin
    participant IdealCityAPI as Ideal City API
    participant Normalizer as Spec Normalizer
    participant Adjudicator as Adjudicator
    participant BuildAgent as Build Plan Agent
    participant BuildExecutor as Build Executor
    participant RCON as RCON Client
    participant Server as MC Server
    participant SocialFeedback as Social Feedback
    
    Player->>CityPhone: 右键 CityPhone 物品
    activate CityPhone
    CityPhone->>Plugin: CityPhoneManager.openInterface()
    Plugin->>IdealCityAPI: GET /ideal-city/cityphone/state/{player}
    IdealCityAPI-->>CityPhone: 返回档案馆状态 + 展品列表
    CityPhone->>Player: 显示 UI (展品/草稿/模板)
    deactivate CityPhone
    
    Player->>CityPhone: 点击"提交叙述"
    activate CityPhone
    CityPhone->>Plugin: 收集表单数据 (world_constraints, logic_outline, risk_register)
    Plugin->>IdealCityAPI: POST /ideal-city/cityphone/action
    deactivate CityPhone
    
    activate IdealCityAPI
    IdealCityAPI->>Normalizer: clean(device_spec)
    activate Normalizer
    Normalizer->>Normalizer: 去除占位符 + 标准化
    Normalizer-->>IdealCityAPI: DeviceSpec (cleaned)
    deactivate Normalizer
    
    IdealCityAPI->>Adjudicator: evaluate(spec, scenario)
    activate Adjudicator
    Adjudicator->>Adjudicator: 检查 required_sections
    Adjudicator->>Adjudicator: 应用规则逻辑
    
    alt 缺少必需字段
        Adjudicator-->>IdealCityAPI: AdjudicationRecord {verdict: REJECT}
    else 是草稿
        Adjudicator-->>IdealCityAPI: AdjudicationRecord {verdict: REVIEW_REQUIRED}
    else 结构完整
        Adjudicator-->>IdealCityAPI: AdjudicationRecord {verdict: ACCEPT}
    end
    deactivate Adjudicator
    
    alt verdict == ACCEPT
        IdealCityAPI->>BuildAgent: generate_plan(spec)
        activate BuildAgent
        BuildAgent->>BuildAgent: 生成 BuildPlan {patches}
        BuildAgent-->>IdealCityAPI: BuildPlan
        deactivate BuildAgent
        
        IdealCityAPI->>BuildExecutor: execute(plan)
        activate BuildExecutor
        BuildExecutor->>RCON: execute_commands(plan.patches)
        RCON->>Server: RCON Protocol
        Server-->>RCON: Response
        RCON-->>BuildExecutor: Success
        BuildExecutor-->>IdealCityAPI: ExecutionResult
        deactivate BuildExecutor
        
        IdealCityAPI->>SocialFeedback: record_feedback(player, spec, verdict)
        activate SocialFeedback
        SocialFeedback->>SocialFeedback: 生成社会反馈事件
        SocialFeedback-->>IdealCityAPI: FeedbackSnapshot
        deactivate SocialFeedback
    end
    
    IdealCityAPI-->>Plugin: ExecutionNotice {verdict, reasoning, build_plan}
    deactivate IdealCityAPI
    
    activate Plugin
    Plugin->>CityPhone: 更新 UI 显示裁决结果
    CityPhone->>Player: 显示 verdict + 建造进度
    deactivate Plugin
```

**通信协议标注**:
- Plugin → Backend: **HTTP/JSON** (REST API)
- Backend → MC Server: **RCON Protocol**
- Backend → File System: **JSON File I/O** (protocol/cityphone/social-feed/)

---

### 2.3 Quest/Task 验证流程（Quest Runtime）

```mermaid
sequenceDiagram
    participant Player as 玩家
    participant Plugin as Paper Plugin
    participant RuleListener as RuleEventListener
    participant Canonicalizer as QuestEventCanonicalizer
    participant QuestAPI as Quest API
    participant QuestRuntime as QuestRuntime
    participant Matcher as Event Matcher
    participant RewardExecutor as Reward Executor
    participant Server as MC Server
    
    Player->>Server: 破坏方块 / 击杀实体 / 收集物品
    Server->>Plugin: Bukkit Event (BlockBreakEvent, EntityKillEvent)
    
    activate Plugin
    Plugin->>RuleListener: onEvent(event)
    RuleListener->>Canonicalizer: canonical(event)
    activate Canonicalizer
    Canonicalizer->>Canonicalizer: 标准化事件格式
    Canonicalizer-->>RuleListener: EventPayload {type, target, count}
    deactivate Canonicalizer
    
    RuleListener->>QuestAPI: POST /quest/event
    deactivate Plugin
    
    activate QuestAPI
    QuestAPI->>QuestRuntime: record_event(player, event)
    activate QuestRuntime
    QuestRuntime->>QuestRuntime: 查找活跃任务 (issued tasks)
    QuestRuntime->>Matcher: _match_event(event, milestone)
    
    activate Matcher
    Matcher->>Matcher: 比对 target + count
    alt 匹配成功
        Matcher-->>QuestRuntime: (True, milestone, token)
        QuestRuntime->>QuestRuntime: milestone.status = "completed"
        QuestRuntime->>QuestRuntime: 生成 completion_payload
    else 匹配失败
        Matcher-->>QuestRuntime: (False, None, None)
        QuestRuntime->>QuestRuntime: 记录为 orphan event
    end
    deactivate Matcher
    
    QuestRuntime->>QuestRuntime: check_completion(level, player)
    alt 所有任务完成
        QuestRuntime-->>QuestAPI: CompletionSummary {rewards, world_patch}
    else 任务未完成
        QuestRuntime-->>QuestAPI: EventRecorded {milestone_progress}
    end
    deactivate QuestRuntime
    
    QuestAPI->>RewardExecutor: execute_rewards(rewards)
    activate RewardExecutor
    RewardExecutor->>Server: RCON: "give @p diamond 10"
    RewardExecutor->>Server: RCON: "xp add @p 100"
    Server-->>RewardExecutor: Success
    RewardExecutor-->>QuestAPI: RewardResult
    deactivate RewardExecutor
    
    QuestAPI-->>Plugin: QuestEventResult {milestone_status, rewards}
    deactivate QuestAPI
    
    activate Plugin
    Plugin->>Player: 显示任务进度 + 奖励粒子
    deactivate Plugin
```

**通信协议标注**:
- Plugin → Backend: **HTTP/JSON**
- Backend → MC Server: **RCON Protocol**
- MC Server → Plugin: **Bukkit Event System**

---

## 3. 数据流架构图（Data Flow Architecture）

```mermaid
graph LR
    subgraph Input["输入层"]
        Chat[玩家聊天]
        CityPhoneUI[CityPhone UI]
        GameEvent[游戏事件]
    end
    
    subgraph Capture["捕获层"]
        ChatListener[Chat Listener]
        CPListener[CityPhone Listener]
        RuleListener[Rule Event Listener]
    end
    
    subgraph Router["路由层"]
        IntentRouter[Intent Router]
        IdealCityRouter[Ideal City Router]
        QuestRouter[Quest Router]
    end
    
    subgraph Processing["处理层"]
        IntentClassifier[Intent Classifier<br/>Embedding Model]
        Adjudicator[Adjudicator<br/>Rule-based Decision]
        QuestMatcher[Quest Matcher<br/>Event Matching]
    end
    
    subgraph Generation["生成层"]
        PlanGenerator[Plan Generator<br/>Template Filling]
        BuildPlanAgent[Build Plan Agent<br/>Patch Generation]
        RewardGenerator[Reward Generator<br/>Loot Table]
    end
    
    subgraph Validation["验证层"]
        CommandSafety[Command Safety<br/>Whitelist/Blacklist]
        TemplateValidator[Template Validator<br/>Structure Check]
        PatchExecutor[Patch Executor<br/>Dry-Run]
    end
    
    subgraph Execution["执行层"]
        RCONClient[RCON Client<br/>Command Dispatch]
        WorldEngine[World Engine<br/>MC Server]
    end
    
    subgraph Audit["审计层"]
        TransactionLog[Transaction Log<br/>Append-Only]
        SocialFeedback[Social Feedback<br/>Event Stream]
    end
    
    Chat --> ChatListener --> IntentRouter --> IntentClassifier
    CityPhoneUI --> CPListener --> IdealCityRouter --> Adjudicator
    GameEvent --> RuleListener --> QuestRouter --> QuestMatcher
    
    IntentClassifier --> PlanGenerator
    Adjudicator --> BuildPlanAgent
    QuestMatcher --> RewardGenerator
    
    PlanGenerator --> CommandSafety --> TemplateValidator --> PatchExecutor
    BuildPlanAgent --> TemplateValidator
    RewardGenerator --> RCONClient
    
    PatchExecutor --> RCONClient --> WorldEngine
    
    PatchExecutor --> TransactionLog
    Adjudicator --> SocialFeedback
    
    style Input fill:#e3f2fd
    style Capture fill:#f3e5f5
    style Router fill:#fff9c4
    style Processing fill:#c8e6c9
    style Generation fill:#ffccbc
    style Validation fill:#ffecb3
    style Execution fill:#f8bbd0
    style Audit fill:#d1c4e9
```

---

## 4. 验证门控流程图（Validation Gates Flow）

```mermaid
graph TD
    Start[玩家输入] --> Gate1{Gate 1:<br/>Intent Valid?}
    
    Gate1 -->|No| Reject1[拒绝: 无法识别意图]
    Gate1 -->|Yes| Gate2{Gate 2:<br/>Command Safety?}
    
    Gate2 -->|Blacklist| Reject2[拒绝: 包含非法指令]
    Gate2 -->|Pass| Gate3{Gate 3:<br/>Template Valid?}
    
    Gate3 -->|Missing Fields| Reject3[拒绝: 缺少必需字段]
    Gate3 -->|Has Placeholders| NeedsConfirm[需确认: 含占位符]
    Gate3 -->|Valid| Gate4{Gate 4:<br/>Execution Tier?}
    
    Gate4 -->|blocked| Reject4[拒绝: 有错误]
    Gate4 -->|needs_confirm| NeedsConfirm
    Gate4 -->|safe_auto| Gate5{Gate 5:<br/>Dry-Run Pass?}
    
    Gate5 -->|Errors| Reject5[拒绝: 模拟执行失败]
    Gate5 -->|Warnings| Warning[警告: 继续执行]
    Gate5 -->|Success| Gate6{Gate 6:<br/>Adjudication<br/>Verdict?}
    
    Gate6 -->|REJECT| Reject6[拒绝: 裁决不通过]
    Gate6 -->|REVIEW_REQUIRED| Review[人工复核]
    Gate6 -->|ACCEPT| Gate7{Gate 7:<br/>Resource Available?}
    
    Gate7 -->|Insufficient| Reject7[拒绝: 资源不足]
    Gate7 -->|Available| Execute[执行世界变更]
    
    Execute --> TxLog[记录事务日志]
    TxLog --> Success[成功]
    
    Warning --> Gate6
    
    style Start fill:#e1f5ff
    style Success fill:#c8e6c9
    style Execute fill:#ffecb3
    style Reject1 fill:#ffcdd2
    style Reject2 fill:#ffcdd2
    style Reject3 fill:#ffcdd2
    style Reject4 fill:#ffcdd2
    style Reject5 fill:#ffcdd2
    style Reject6 fill:#ffcdd2
    style Reject7 fill:#ffcdd2
    style NeedsConfirm fill:#fff9c4
    style Review fill:#f3e5f5
    style Warning fill:#ffe0b2
    style TxLog fill:#d1c4e9
```

---

## 5. 系统分层架构（Layered Architecture）

```mermaid
graph TB
    subgraph Layer1["表现层 (Presentation Layer)"]
        UI1[Minecraft Client UI]
        UI2[CityPhone Interface]
        UI3[Chat Interface]
    end
    
    subgraph Layer2["插件层 (Plugin Layer)"]
        P1[Event Listeners]
        P2[UI Managers]
        P3[HTTP Client]
    end
    
    subgraph Layer3["API 层 (API Layer)"]
        API1[Intent API]
        API2[Ideal City API]
        API3[Quest API]
        API4[World API]
    end
    
    subgraph Layer4["服务层 (Service Layer)"]
        S1[Creation Workflow]
        S2[Ideal City Pipeline]
        S3[Quest Runtime]
        S4[Story Engine]
    end
    
    subgraph Layer5["核心层 (Core Layer)"]
        C1[Intent Classifier]
        C2[Adjudicator]
        C3[Plan Generator]
        C4[Patch Validator]
    end
    
    subgraph Layer6["执行层 (Execution Layer)"]
        E1[Patch Executor]
        E2[Build Executor]
        E3[RCON Client]
    end
    
    subgraph Layer7["持久层 (Persistence Layer)"]
        D1[Transaction Log]
        D2[Level Data]
        D3[Social Feedback]
        D4[Protocol Files]
    end
    
    subgraph Layer8["基础设施层 (Infrastructure Layer)"]
        I1[Minecraft Server]
        I2[World Engine]
        I3[Entity Manager]
    end
    
    Layer1 --> Layer2
    Layer2 --> Layer3
    Layer3 --> Layer4
    Layer4 --> Layer5
    Layer5 --> Layer6
    Layer6 --> Layer7
    Layer6 --> Layer8
    Layer7 --> Layer8
    
    style Layer1 fill:#e3f2fd
    style Layer2 fill:#f3e5f5
    style Layer3 fill:#fff9c4
    style Layer4 fill:#c8e6c9
    style Layer5 fill:#ffccbc
    style Layer6 fill:#ffecb3
    style Layer7 fill:#d1c4e9
    style Layer8 fill:#f8bbd0
```

---

## 6. 通信协议总览（Communication Protocols）

| 通信路径 | 协议 | 端口/方式 | 数据格式 | 示例 |
|----------|------|-----------|----------|------|
| **Player → Plugin** | Bukkit Event | 内存事件总线 | Java Objects | `PlayerChatEvent`, `PlayerMoveEvent` |
| **Plugin → Backend** | HTTP REST | 8000 | JSON | `POST /intent/recognize {"text": "建造房子"}` |
| **Backend → MC Server** | RCON | 25575 (TCP) | Plain Text | `fill 100 70 200 104 74 204 stone` |
| **MC Server → Plugin** | Bukkit Event | 内存事件总线 | Java Objects | `BlockBreakEvent`, `EntitySpawnEvent` |
| **Backend → File System** | File I/O | N/A | JSON/JSONL | `protocol/cityphone/social-feed/events.jsonl` |
| **Plugin → Player** | Bukkit API | 客户端 | Minecraft Packets | `player.sendTitle()`, `player.spawnParticle()` |

---

## 7. 关键路径时序图（Critical Path Timeline）

```mermaid
gantt
    title 玩家输入到世界变更的关键路径时间线
    dateFormat X
    axisFormat %L ms
    
    section 捕获层
    Chat Event Capture       :0, 5
    Intent Payload Build     :5, 10
    
    section 路由层
    HTTP Request Send        :10, 30
    API Route Dispatch       :30, 35
    
    section 处理层
    Intent Classification    :35, 150
    Plan Generation          :150, 250
    
    section 验证层
    Command Safety Check     :250, 270
    Template Validation      :270, 290
    Dry-Run Execution        :290, 320
    
    section 执行层
    RCON Connection          :320, 340
    Command Dispatch         :340, 360
    World Mutation           :360, 400
    
    section 审计层
    Transaction Log Write    :400, 420
    Response Build           :420, 450
    
    section 反馈层
    HTTP Response Send       :450, 480
    UI Update                :480, 500
```

**关键性能瓶颈**:
1. **Intent Classification** (115ms): Embedding model 推理
2. **Plan Generation** (100ms): 模板填充与指令生成
3. **World Mutation** (40ms): MC Server 执行方块放置

**总延迟**: ~500ms (从玩家输入到 UI 更新)

---

## 8. 错误处理流程图（Error Handling Flow）

```mermaid
graph TD
    Input[玩家输入] --> Try{Try Execute}
    
    Try -->|Success| LogSuccess[记录成功日志]
    LogSuccess --> Return[返回成功响应]
    
    Try -->|Exception| CatchError{错误类型}
    
    CatchError -->|ValidationError| Handle1[返回验证错误]
    Handle1 --> LogError1[记录错误日志]
    LogError1 --> Return1[返回错误响应<br/>status=validation_failed]
    
    CatchError -->|SafetyError| Handle2[返回安全错误]
    Handle2 --> LogError2[记录安全日志]
    LogError2 --> Return2[返回错误响应<br/>status=safety_blocked]
    
    CatchError -->|ExecutionError| Handle3[返回执行错误]
    Handle3 --> Rollback{是否需要回滚}
    Rollback -->|Yes| UndoPatch[执行 undo_patch]
    Rollback -->|No| LogError3[记录执行日志]
    UndoPatch --> LogError3
    LogError3 --> Return3[返回错误响应<br/>status=execution_failed]
    
    CatchError -->|NetworkError| Handle4[返回网络错误]
    Handle4 --> Retry{重试次数<3?}
    Retry -->|Yes| Wait[等待 1s]
    Wait --> Try
    Retry -->|No| LogError4[记录网络日志]
    LogError4 --> Return4[返回错误响应<br/>status=network_timeout]
    
    CatchError -->|UnknownError| Handle5[返回未知错误]
    Handle5 --> LogError5[记录完整堆栈]
    LogError5 --> Alert[发送告警]
    Alert --> Return5[返回错误响应<br/>status=internal_error]
    
    style Input fill:#e1f5ff
    style LogSuccess fill:#c8e6c9
    style Return fill:#c8e6c9
    style Handle1 fill:#fff9c4
    style Handle2 fill:#ffcdd2
    style Handle3 fill:#ffe0b2
    style Handle4 fill:#f3e5f5
    style Handle5 fill:#d1c4e9
    style Rollback fill:#ffccbc
    style Alert fill:#ef9a9a
```

---

## 9. 状态机图（State Machine Diagram）

### 9.1 Patch 执行状态机

```mermaid
stateDiagram-v2
    [*] --> Draft: 创建 Patch
    Draft --> Validated: dry_run() 通过
    Draft --> Rejected: 验证失败
    
    Validated --> Pending: 加入执行队列
    Pending --> Executing: RCON 调度
    Executing --> Applied: 执行成功
    Executing --> Failed: 执行失败
    
    Applied --> RolledBack: undo_patch()
    Failed --> RolledBack: 回滚
    
    Rejected --> [*]
    Applied --> [*]
    RolledBack --> [*]
    
    note right of Draft
        status = "draft"
        execution_tier = unknown
    end note
    
    note right of Validated
        status = "validated"
        execution_tier = "safe_auto"
    end note
    
    note right of Applied
        status = "applied"
        transaction_id = UUID
    end note
```

---

### 9.2 Quest 任务状态机

```mermaid
stateDiagram-v2
    [*] --> Inactive: Level 加载
    Inactive --> Issued: 玩家触发任务
    
    Issued --> InProgress: 开始追踪事件
    InProgress --> MilestoneReached: 达成里程碑
    MilestoneReached --> InProgress: 继续下一里程碑
    MilestoneReached --> Completed: 所有里程碑完成
    
    InProgress --> Failed: 任务失败条件
    
    Completed --> RewardGranted: 发放奖励
    RewardGranted --> [*]
    
    Failed --> [*]
    
    note right of Issued
        task_session.status = "issued"
        milestones = [...]
    end note
    
    note right of Completed
        所有 milestones.status = "completed"
        exit_ready = true
    end note
```

---

## 10. 部署架构图（Deployment Architecture）

```mermaid
graph TB
    subgraph Client["客户端"]
        MC[Minecraft Client<br/>Java Edition 1.20+]
    end
    
    subgraph Server["服务器 (localhost / VPS)"]
        subgraph Backend["Backend 进程"]
            FastAPI[FastAPI App<br/>uvicorn<br/>Port 8000]
        end
        
        subgraph GameServer["游戏服务器进程"]
            Paper[Paper Server<br/>Java 17+<br/>Port 25565]
            RCON[RCON Service<br/>Port 25575]
        end
        
        subgraph Storage["存储层"]
            Data[Data Files<br/>JSON/JSONL]
            Logs[Log Files<br/>Transaction Logs]
            Protocol[Protocol Files<br/>CityPhone/Social]
        end
    end
    
    MC -->|TCP 25565| Paper
    MC -->|WebSocket/HTTP| FastAPI
    Paper -->|Plugin API| Plugin[DriftSystem Plugin<br/>JAR in plugins/]
    Plugin -->|HTTP 8000| FastAPI
    FastAPI -->|RCON 25575| RCON
    RCON --> Paper
    FastAPI -->|File I/O| Data
    FastAPI -->|File I/O| Logs
    FastAPI -->|File I/O| Protocol
    Paper -->|File I/O| Data
    
    style Client fill:#e3f2fd
    style Backend fill:#c8e6c9
    style GameServer fill:#ffecb3
    style Storage fill:#d1c4e9
```

---

## 总结

### 关键发现
1. **三层通信模式**: Client ↔ Plugin ↔ Backend ↔ MC Server
2. **四种协议**: Bukkit Event, HTTP/JSON, RCON, File I/O
3. **七个验证门控**: Intent Valid → Command Safety → Template Valid → Execution Tier → Dry-Run → Adjudication → Resource Check
4. **九个处理层**: Capture → Route → Process → Generate → Validate → Execute → Audit → Feedback → Presentation

### 数学验证插入点
- **Gate 3** (Template Validation): 可添加数学公式验证
- **Gate 6** (Adjudication): 可要求数学证明作为 verdict 条件
- **Transaction Log**: 可存储证明轨迹 (proof payload)
- **Quest Matcher**: 可要求数学条件匹配 (mathematical predicate)

### 性能瓶颈
- **Intent Classification**: 115ms (可优化为本地模型)
- **RCON 通信**: 20-40ms (无法优化，协议限制)
- **文件 I/O**: 变量 (可缓存 + 异步写入)
