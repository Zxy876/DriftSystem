# DriftSystem 系统结构蓝图梳理报告

> 生成时间：2026-02-20  
> 用途：PPT 蓝图底稿 / 系统现状快照  
> 范围：`backend/` · `mc_plugin/` · `mods/` · `backend/app/instrumentation/`

---

## A. 功能域分层结构列表

### 1. 输入层（API / Intent）

| 项目 | 内容 |
|---|---|
| **主要文件** | `backend/app/api/intent_api.py` · `backend/app/core/ai/intent_engine.py` · `backend/app/core/ai/nlp.py` · `backend/app/api/ideal_city_api.py` |
| **核心职责** | 接收玩家自然语言输入，调用 DeepSeek 解析成结构化多意图列表（intents[]） |
| **依赖 LLM** | **是** — 全路径调用 DeepSeek Chat |
| **成熟度** | 🟡 黄色 — 多意图解析逻辑已可运行，但意图类型枚举（SAY_ONLY / IDEAL_CITY_SUBMIT 等）与下游处理的覆盖度不完整；`nlp.py` 与 `intent_engine.py` 存在职责重叠 |

---

### 2. 规划层（Planner / Patch 生成）

| 项目 | 内容 |
|---|---|
| **主要文件** | `backend/app/core/ideal_city/build_plan_agent.py` · `backend/app/core/ideal_city/build_plan.py` · `backend/app/core/ideal_city/spec_normalizer.py` · `backend/app/core/creation/transformer.py` · `backend/app/core/creation/validation.py` |
| **核心职责** | 将审定后的 DeviceSpec 通过 LLM 转成有序 BuildPlan，再由 Transformer 将每个步骤展开为带 world_patch 的 CreationPatchTemplate |
| **依赖 LLM** | **是** — `BuildPlanAgent` 完全依赖 DeepSeek；含确定性 fallback 逻辑 |
| **成熟度** | 🟡 黄色 — 主链路有 fallback；但 `CreationPatchTemplate.execution_tier` 分级逻辑（`safe_auto` / `needs_confirm`）在 LLM 回包格式不稳定时可能错误降级 |

---

### 3. 执行层（Executor / RCON）

| 项目 | 内容 |
|---|---|
| **主要文件** | `backend/app/core/world/plan_executor.py` · `backend/app/core/world/patch_executor.py` · `backend/app/core/minecraft/rcon_client.py` |
| **核心职责** | 对 dry-run 校验通过的模板执行 RCON 命令，将世界指令写入 Minecraft 服务端 |
| **依赖 LLM** | **否** |
| **成熟度** | 🟡 黄色 — `PlanExecutor.auto_execute` 成功写入世界，事务记录落盘；但执行后状态仍标记 `pending` 而非 `committed`（见 `plan_executor.py` L132），语义存在歧义；RCON 断线重试未实现 |

---

### 4. 状态层（StoryState / Repository）

| 项目 | 内容 |
|---|---|
| **主要文件** | `backend/app/core/ideal_city/story_state.py` · `backend/app/core/ideal_city/story_state_manager.py` · `backend/app/core/ideal_city/story_state_repository.py` · `backend/app/core/story/story_engine.py` · `backend/app/core/story/story_graph.py` · `backend/app/core/story/exhibit_instance_repository.py` |
| **核心职责** | 持久化每位玩家的叙事状态（DeviceSpec 填写进度、建造就绪标志），并驱动剧情图推进 |
| **依赖 LLM** | **部分** — `StoryStateAgent` 可选调用 LLM 补全缺失槽位 |
| **成熟度** | 🟢 绿色 — JSON 文件存储有锁保护，`StoryStateRepository` 带向后兼容反序列化；`StoryGraph` 关卡图有完整测试覆盖 |

---

### 5. 事务层（Transaction Log）

| 项目 | 内容 |
|---|---|
| **主要文件** | `backend/app/core/world/patch_transaction.py` |
| **核心职责** | 以 append-only JSONL 格式记录每次 Patch 执行的命令、undo_patch 与状态变更，提供可回查的操作日志 |
| **依赖 LLM** | **否** |
| **成熟度** | 🟡 黄色 — 写入逻辑完整；但无读取/回滚 API 暴露给上层，undo_patch 字段由调用方自填，实际回滚路径未闭环 |

---

### 6. 安全层（Command Safety）

| 项目 | 内容 |
|---|---|
| **主要文件** | `backend/app/core/world/command_safety.py` · `backend/app/core/world/resource_sanitizer.py` |
| **核心职责** | 对每条 MC 命令执行白名单前缀检查、禁用 token 扫描、function 标识符合规验证，阻断危险指令进入 RCON |
| **依赖 LLM** | **否** |
| **成熟度** | 🟢 绿色 — 正则规则明确，`analyze_commands` 有独立单测；RCON 调用前强制过滤，不可绕过 |

---

### 7. 插件层（MC Plugin）

| 项目 | 内容 |
|---|---|
| **主要文件** | `mc_plugin/src/main/` · `mc_plugin/pom.xml` · `build_plugin.sh` · `rebuild_mc_plugin.sh` |
| **核心职责** | 运行在 Paper/Bukkit 服务端的 Java 插件，接收后端 RCON 指令并在游戏内执行事件、行为触发 |
| **依赖 LLM** | **否** |
| **成熟度** | 🔴 红色 — 源码目录 `mc_plugin/src/main/` 存在但内容未在本次扫描中找到完整 Java 实现；`plugin_bundle_20260110/` 为归档包；与后端的握手协议（健康检查、事件回调）无代码证据 |

---

### 8. 模组层（Mods Loader）

| 项目 | 内容 |
|---|---|
| **主要文件** | `backend/app/core/mods/manager.py` · `backend/app/core/mods/manifest.py` · `mods/` 目录（gm4.* 系列） |
| **核心职责** | 扫描 `mods/` 目录下的 `mod.json` manifest，动态注册可用 mod 并将 mod_hooks 注入 BuildPlan |
| **依赖 LLM** | **否** |
| **成熟度** | 🟡 黄色 — `ModManager.reload()` 可正常枚举模组；但 mod_hooks 注入 (`augment_mod_hooks`) 与实际 MC 端的 mod 激活之间无校验闭环；若 mod 未安装则静默跳过 |

---

### 9. 指标层（Metrics）

| 项目 | 内容 |
|---|---|
| **主要文件** | `backend/app/instrumentation/cityphone_metrics.py` |
| **核心职责** | 统计 CityPhone 端点的 state/action 请求量及错误码分布，支持 Prometheus 或本地计数器降级 |
| **依赖 LLM** | **否** |
| **成熟度** | 🔴 红色 — 当前仅覆盖 IdealCity 子路径；后端其余高频路径（intent、story、world）无任何 metrics 埋点；Prometheus endpoint 未在 `main.py` 中注册挂载 |

---

### 10. ML 层（Embedding）

| 项目 | 内容 |
|---|---|
| **主要文件** | `backend/app/ml/embedding_model.py` |
| **核心职责** | 将文本向量化，供语义候选检索使用；支持 HTTP 外部服务、OpenAI SDK 或确定性哈希降级 |
| **依赖 LLM** | **部分** — 生产模式调用 OpenAI Embeddings API；降级模式为纯哈希算法 |
| **成熟度** | 🔴 红色 — `EmbeddingModel` 本身实现完整；但在整个后端中**无调用点**（`grep` 全库未找到 `EmbeddingModel` 的业务层实例化），语义检索路径实际未接入主链 |

---

## B. 模块依赖关系（文字结构图）

```
[ 玩家输入 ]
     │
     ▼
[ 输入层 ]  intent_engine.py  ──→  DeepSeek LLM
     │               ↑
     │         (多意图解析)
     ▼
[ 规划层 ]  spec_normalizer → build_plan_agent → BuildPlanAgent ──→ DeepSeek LLM
               │                                     │
               │  (DeviceSpec 标准化)          (BuildPlan 生成)
               ▼                                     ▼
         story_state_manager ←───────────── transformer.py
               │                          (CreationPatchTemplate)
               │ (状态持久化)
               ▼
[ 状态层 ]  StoryStateRepository (JSON 文件存储)
               │
               │ (ready_for_build == True)
               ▼
[ 执行层 ]  PatchExecutor.dry_run()
               │  ↑
               │  └── command_safety.py ← [ 安全层 ]
               │
               ▼
          PlanExecutor.auto_execute()
               │
               │ (事务落盘)
               ▼
[ 事务层 ]  PatchTransactionLog (JSONL)
               │
               │ (命令列表)
               ▼
[ 执行层 ]  RconClient.run()  ──────────────────────────────→  [ MC 服务端 ]
                                                                      ↑
                                                              [ 插件层 ] Paper Plugin
                                                                      ↑
                                                              [ 模组层 ] ModManager
                                                              (gm4.* mods)

─────────────────────────── 独立模块 ───────────────────────────────
[ ML 层 ]  EmbeddingModel   ←── (生产未接入主链，当前孤立)
[ 指标层 ] cityphone_metrics ←── (仅覆盖 IdealCity 路径)
[ 剧情图 ] StoryGraph + StoryEngine ←── (并行运行，通过 EventManager 与主链交互)
```

---

## C. 系统主执行链（从输入到 MC 世界变更）

```
① 玩家通过 HTTP POST /intent/submit 发送自然语言
        ↓
② intent_api.py → intent_engine.py 调用 DeepSeek
   → 解析为 intents[] (e.g. IDEAL_CITY_SUBMIT)
        ↓
③ ideal_city_api.py 接收 IDEAL_CITY_SUBMIT
   → NarrativeChatIngestor 将输入注入 DeviceSpec
        ↓
④ spec_normalizer.py 标准化 DeviceSpec（补全缺失字段）
   → StoryStateManager.apply() 持久化状态
        ↓
⑤ 当 StoryState.ready_for_build == True
   → BuildPlanAgent 调用 DeepSeek 生成 BuildPlan (steps[])
        ↓
⑥ CreationWorkflow / transformer.py
   → 将 BuildPlan.steps → CreationPatchTemplate[]
   → 每个 template 含 world_patch.mc.commands[]
        ↓
⑦ PatchExecutor.dry_run(plan)
   → validate_patch_template() 校验 execution_tier
   → analyze_commands() 安全白名单过滤
   → 通过者记入 PatchTransactionLog (status=validated)
        ↓
⑧ PlanExecutor.auto_execute()
   → RconClient.run(commands)
   → TCP RCON 连接 Minecraft 服务端
        ↓
⑨ Minecraft 服务端执行 setblock / fill / summon 等指令
   → 世界结构发生实际变更
```

---

## D. 当前系统最核心的 3 个结构风险点

### 🔴 风险一：插件层与后端之间无握手协议（断链风险）

- **位置**：`mc_plugin/src/main/` ↔ `backend/app/core/minecraft/rcon_client.py`
- **具体问题**：
  - `RconClient` 仅实现 TCP 层的登录 + 命令发送，无心跳检测、无连接池、无重试。
  - MC Plugin 端的事件回调（玩家进入区域、建造完成确认）在后端无对应接收端点。
  - `PlanExecutor` 执行后状态停留在 `pending`，**从未收到来自游戏的确认信号**，无法判断指令是否真正生效。
- **后果**：整条链路在 RCON 超时或 Plugin 未加载时静默失败，后端误认为"执行成功"。

---

### 🔴 风险二：ML 层（Embedding）完全未接入主链（孤岛模块）

- **位置**：`backend/app/ml/embedding_model.py`
- **具体问题**：
  - 全库搜索无任何业务代码实例化 `EmbeddingModel`。
  - `BuildPlanAgent` 和 `IntentEngine` 均直接依赖 LLM 全文生成，**没有语义检索/候选过滤层**。
  - 意图匹配和资源候选完全依赖 DeepSeek 每次实时输出，无语义缓存、无相似度索引。
- **后果**：一旦 DeepSeek API 延迟或不可用，整个输入→规划链路无降级路径；embedding 的工程投入浪费。

---

### 🔴 风险三：事务层 undo_patch 无实际回滚路径（日志有写无读）

- **位置**：`backend/app/core/world/patch_transaction.py`
- **具体问题**：
  - `PatchTransactionLog` 提供 `record()` 和 `load()`，但全库中 `load()` 方法**无任何调用点**。
  - `undo_patch` 字段由调用方自填（多数为 `{"commands": []}`），并无自动生成逆操作命令的机制。
  - 没有任何 `/rollback` 或 `/undo` API endpoint 存在。
- **后果**：世界变更一旦执行，**无法通过系统手段撤销**；事务日志形同虚设，仅起审计作用，不具备回滚能力。
