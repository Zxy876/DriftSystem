# DriftSystem 手画系统蓝图底稿

> **分支：scienceline**（本文档基于 scienceline 分支代码证据生成）

---

## 📋 摘要（10 行以内）

这张图表达的是 **DriftSystem** 从玩家输入到 Minecraft 世界落地的完整主链路，以及支撑它运转的关键旁路。

主链路方向：`玩家聊天/HTTP输入` → `意图识别(LLM)` → `规划生成(LLM)` → `Transformer 资源映射` → `Patch 模板` → `Dry-run 校验` → `RCON 命令下发` → `MC 世界`。

旁路系统包括：故事状态机（StoryStateManager）管控裁决前置条件、裁决合约（AdjudicationContract）把关 Accept/Reject、事务日志（PatchTransactionLog）保障可追溯性、命令安全过滤（CommandSafety）防止危险命令入场、ModManager 挂载 gm4 功能包、Embedding 语义索引辅助意图理解、Prometheus 指标采集（CityPhone Metrics）。

整个系统分 **5 层**：① 交互层 ② 核心业务层 ③ 执行与状态层 ④ 基础设施层 ⑤ 外部系统。

---

## 一、方块清单（按层）

### ① 交互层（用户/玩家与系统的接触面）

| 方块名（写进框里） | 代码路径 | 一句话职责 |
|---|---|---|
| **Intent API** | `backend/app/api/intent_api.py` | 暴露 `/intent/recognize`、`/intent/plan`、`/intent/execute` 三个 HTTP 端点，接收玩家聊天消息并返回意图/计划/执行结果 |
| **IdealCity API** | `backend/app/api/ideal_city_api.py` | 暴露 `/ideal-city/device-specs` 等端点，接收"理想之城"设备规格提案，串联审理→执行通知全链路 |
| **MC Plugin** | `mc_plugin/src/main/java/com/driftmc/DriftPlugin.java`<br>`mc_plugin/src/main/java/com/driftmc/BackendClient.java` | Bukkit 插件，注册 `/level`、`/next` 命令，通过 OkHttp 向后端 `http://127.0.0.1:8000` 发 POST 请求 |

---

### ② 核心业务层（LLM 意图理解 → 计划生成）

| 方块名（写进框里） | 代码路径 | 一句话职责 |
|---|---|---|
| **Intent Engine** | `backend/app/core/ai/intent_engine.py` | 多意图解析器：先调 DeepSeek LLM（`ai_parse_multi`），失败则走规则 fallback，输出 `intents[]` 列表（含 `world_patch` 补丁指令） |
| **Creation Classifier** | `backend/app/core/intent_creation.py`<br>`backend/app/services/creation_workflow.py` | 规则优先分类器，判断消息是否为"建造意图"，返回 `CreationIntentDecision`（含 `is_creation`/`confidence`/`slots`） |
| **BuildPlan Agent** | `backend/app/core/ideal_city/build_plan_agent.py`<br>`backend/app/core/ideal_city/build_plan.py` | LLM 驱动的建造计划生成器：将已通过裁决的 `DeviceSpec` + `StoryState` 转成 `BuildPlan`（steps/resource_ledger/mod_hooks），含 deterministic fallback |
| **Story Engine** | `backend/app/core/story/story_engine.py`<br>`backend/app/core/story/story_graph.py` | 关卡状态主控，管理 StoryGraph 有向图推进（BFS 下一关）、场景触发、NPC 行为，是交互层事件的上下文持有者 |

---

### ③ 执行与状态层（计划 → 校验 → 落地）

| 方块名（写进框里） | 代码路径 | 一句话职责 |
|---|---|---|
| **Transformer** | `backend/app/core/creation/transformer.py`<br>`backend/app/core/creation/validation.py` | 将 `CreationIntentDecision` + 资源快照 映射为 `CreationPlan`（含 `CreationPatchTemplate[]`），负责资源 token 解析与 patch 模板生成 |
| **Patch Executor / Dry-run** | `backend/app/core/world/patch_executor.py` | 对 `CreationPlan` 执行 dry-run：校验每个 patch 模板的合法性，输出 `PatchExecutionResult`（executed / skipped / errors），不真正写世界 |
| **Plan Executor** | `backend/app/core/world/plan_executor.py` | Dry-run 通过后调用 `CommandRunner` 协议真实下发命令，记录 `TemplateExecutionStatus`，输出 `PlanExecutionReport` |
| **StoryState Manager** | `backend/app/core/ideal_city/story_state_manager.py`<br>`backend/app/core/ideal_city/story_state_repository.py` | 累积校验叙事状态（goals/logic_outline/resources/success_criteria/risk_register），决定是否 `ready_for_build`，为 BuildPlanAgent 提供上下文 |
| **Adjudication Contract** | `backend/app/core/ideal_city/adjudication_contract.py`<br>`backend/app/core/ideal_city/pipeline.py` | 世界主权裁决层：对 DeviceSpec 签发 ACCEPT/PARTIAL/REJECT/REVIEW_REQUIRED，只有 ACCEPT/PARTIAL 才允许后续建造计划生成 |

---

### ④ 基础设施层（横切关注点）

| 方块名（写进框里） | 代码路径 | 一句话职责 |
|---|---|---|
| **RCON Client** | `backend/app/core/minecraft/rcon_client.py` | 实现 Minecraft RCON 协议（TCP 二进制帧），在命令下发前调用 `CommandSafety` 过滤，是唯一写入 MC 世界的通道 |
| **Command Safety** | `backend/app/core/world/command_safety.py` | 白名单前缀校验 + 黑名单 token 拦截，阻止 `op/stop/reload` 等危险命令，所有 MC 命令必须经此过滤 |
| **Patch Transaction Log** | `backend/app/core/world/patch_transaction.py` | Append-only JSONL 事务日志（`data/patch_logs/transactions.log`），记录每条 patch 的 undo_patch 和状态变更，支持回溯 |
| **CityPhone Metrics** | `backend/app/instrumentation/cityphone_metrics.py` | Prometheus Counter 采集（可 fallback 为本地计数器），追踪 state_requests / action_requests / action_errors |
| **Embedding Model** | `backend/app/ml/embedding_model.py` | 语义向量化模块（调用 OpenAI Embeddings API），为意图理解提供语义检索候选，不具执行权限 |
| **Mod Manager** | `backend/app/core/mods/manager.py`<br>`backend/app/core/mods/manifest.py` | 扫描 `mods/` 目录下的 `mod.json`，加载 gm4 功能包（如 balloon_animals、better_armour_stands），为 BuildPlan 提供 mod_hooks |

---

### ⑤ 外部系统（系统边界之外）

| 方块名（写进框里） | 说明 |
|---|---|
| **DeepSeek / OpenAI LLM** | `OPENAI_BASE_URL` / `OPENAI_API_KEY` 环境变量配置，用于意图解析（`intent_engine.py`）和建造计划生成（`build_plan_agent.py`、`deepseek_agent.py`） |
| **Minecraft Server** | 通过 RCON TCP 接收命令；Bukkit Plugin (`DriftPlugin`) 也从 MC 进程内反向调用后端 HTTP |
| **Prometheus / 监控系统** | 接收 `cityphone_metrics.py` 推送的 Counter 指标 |

---

## 二、箭头清单

### 主链路箭头（严格顺序）

```
① 玩家/HTTP 客户端
        │ POST /intent/execute  (或 /ideal-city/device-specs)
        ▼
② Intent API  (backend/app/api/intent_api.py)
        │ classify_message()
        ▼
③ Creation Classifier  (backend/app/core/intent_creation.py)
        │ CreationIntentDecision → generate_plan()
        ▼
④ Intent Engine / BuildPlan Agent  (LLM调用)
     [chat路径]                  [ideal-city路径]
     intent_engine.py            build_plan_agent.py
        │ intents[] / BuildPlan
        ▼
⑤ Transformer  (backend/app/core/creation/transformer.py)
        │ CreationPlan (含 CreationPatchTemplate[])
        ▼
⑥ Patch Executor — Dry-run  (backend/app/core/world/patch_executor.py)
        │ PatchExecutionResult (executed / skipped / errors)
        ▼
⑦ Plan Executor  (backend/app/core/world/plan_executor.py)
        │ CommandRunner.run(commands)
        ▼
⑧ RCON Client  (backend/app/core/minecraft/rcon_client.py)
        │ TCP RCON 帧
        ▼
⑨ Minecraft Server / MC World
```

---

### 旁路 / 依赖箭头

```
[LLM 旁路]
  Intent Engine ──────────────────→ DeepSeek/OpenAI API
  BuildPlan Agent ────────────────→ DeepSeek/OpenAI API
  (若 API_KEY 缺失，自动降级为规则 fallback)

[状态旁路]
  IdealCity API → StoryState Manager → StoryStateRepository
  StoryState Manager → BuildPlan Agent  (ready_for_build 门控)

[裁决旁路]
  IdealCity API → Adjudication Contract (pipeline.py)
  Adjudication Contract → BuildPlan Agent  (verdict=ACCEPT/PARTIAL 才放行)

[安全过滤旁路]
  Plan Executor → Command Safety (analyze_commands)
  RCON Client   → Command Safety (在 run() 前校验)

[事务日志旁路]
  Patch Executor → PatchTransactionLog.record()
  Plan Executor  → PatchTransactionLog.record_status_update()

[插件旁路]
  MC Plugin (DriftPlugin) ─HTTP POST→ Intent API / Story API
  (插件作为额外输入源，不绕过安全过滤)

[Metrics 旁路]
  IdealCity API → CityPhone Metrics (record_action_request / record_state_request)

[Embedding 旁路]
  Creation Classifier / Intent Engine → Embedding Model (语义候选检索，不触发执行)

[Mods 旁路]
  BuildPlan Agent → Mod Manager (mod_hooks 列表注入 BuildPlan)
  Build Scheduler → mods/*.mod.json (离线加载)
```

---

## 三、风险点（⚠️ 证据型，最多 3 条）

> ⚠️ **风险1：RCON 命令安全过滤存在绕过空间**
>
> - **定位**：`backend/app/core/world/command_safety.py` → `_ALLOWED_PREFIXES` 白名单
> - **证据**：`execute` 前缀被整体放行（`_ALLOWED_EXECUTE_PATTERN` 仅做宽泛正则），嵌套 `execute as @a run op` 等形式理论上可绕过黑名单
> - **风险**：LLM 生成的 patch 模板中若包含经特殊构造的 `execute` 子命令，可能导致危险命令下发至 MC Server

> ⚠️ **风险2：LLM 生成 BuildPlan 无输出长度与幂等性保证**
>
> - **定位**：`backend/app/core/ideal_city/build_plan_agent.py` → `generate()` / `_call_llm()`
> - **证据**：LLM 响应直接被 `BuildPlan.from_llm_response()` 解析，仅有 `_is_generic()` 过滤，无校验 steps 数量上限；重复提交相同 spec 时缓存 key 相同（`_cache_key`），但缓存为内存字典，重启即失效
> - **风险**：LLM 返回超大 step 列表或重复执行相同建造计划可能导致世界状态污染

> ⚠️ **风险3：PatchTransactionLog 仅 Append-only，无 Rollback 实现**
>
> - **定位**：`backend/app/core/world/patch_transaction.py` → `PatchTransactionEntry.undo_patch`
> - **证据**：`undo_patch` 字段存在于 `PatchTransactionEntry`，但 `PatchTransactionLog` 类没有 `rollback()` / `apply_undo()` 方法；`plan_executor.py` 中失败时仅记录 status="failed"，不触发 undo
> - **风险**：执行中途失败时，已写入的方块无法自动回滚，造成部分建造状态残留

---

## 四、演进点（✅ 挂载点已标注，最多 3 条）

> ✅ **演进1：Deterministic Planner（确定性建造计划降级）**
>
> - **现状**：`BuildPlanAgent.generate()` 在 LLM 返回空/泛化结果时已调用 `_deterministic_from_state()`
> - **挂载点**：`backend/app/core/ideal_city/build_plan_agent.py` → `_deterministic_from_state()` 方法
> - **演进方向**：补全该方法的规则库，使其能在无网络/LLM 不可用时完整生成 BuildPlan，实现完全离线运行

> ✅ **演进2：RCON Handshake / 连接池**
>
> - **现状**：`RconClient` 每次调用 `run()` 都新建 TCP 连接，无连接复用
> - **挂载点**：`backend/app/core/minecraft/rcon_client.py` → `run()` 方法 + `_lock` 字段
> - **演进方向**：实现连接池或长连接管理，并在 `creation_workflow.py` 的 `RconCommandRunner.verify_connection()` 中补全握手确认逻辑

> ✅ **演进3：Rollback API（PatchTransaction 回滚接口）**
>
> - **现状**：`PatchTransactionEntry` 已预留 `undo_patch` 字段，但无执行入口
> - **挂载点**：`backend/app/core/world/patch_transaction.py` → `PatchTransactionLog` 类 + `backend/app/core/world/plan_executor.py` → `PlanExecutor.execute()` 失败分支
> - **演进方向**：实现 `PatchTransactionLog.rollback(patch_id)` → 逆序读取 `undo_patch` 命令 → 经 CommandSafety 过滤 → 通过 RCON 下发还原命令

---

## 五、ASCII 布局草图

```
┌─────────────────────────────────────────────────────────────────────┐  ┌────────────────────┐
│                        ① 交互层                                     │  │   ⑤ 外部系统        │
│  ┌────────────┐  ┌────────────────┐  ┌──────────────────────┐       │  │                    │
│  │ Intent API │  │ IdealCity API  │  │    MC Plugin         │       │  │ ┌────────────────┐ │
│  │/intent/*   │  │/ideal-city/*   │  │ DriftPlugin.java     │       │  │ │ DeepSeek/      │ │
│  └─────┬──────┘  └───────┬────────┘  └──────────┬───────────┘       │  │ │ OpenAI LLM     │ │
└────────┼─────────────────┼───────────────────────┼───────────────────┘  │ └────────────────┘ │
         │                 │                        │ HTTP POST             │                    │
┌────────▼─────────────────▼───────────────────────▼───────────────────┐  │ ┌────────────────┐ │
│                        ② 核心业务层                                   │  │ │ Prometheus /   │ │
│  ┌─────────────────┐  ┌───────────────────┐  ┌──────────────────┐    │  │ │ 监控系统        │ │
│  │ Intent Engine   │  │ BuildPlan Agent   │  │  Story Engine    │    │  │ └────────────────┘ │
│  │ intent_engine.py│  │build_plan_agent.py│  │ story_engine.py  │    │  │                    │
│  │ (LLM + fallback)│  │  (LLM + determ.) │  │  story_graph.py  │    │  │ ┌────────────────┐ │
│  └────────┬────────┘  └─────────┬─────────┘  └──────────────────┘    │  │ │ Minecraft      │ │
│           │                     │                                      │  │ │ Server         │ │
│  ┌────────▼────────┐  ┌─────────▼────────┐                            │  │ │ (RCON:25575)   │ │
│  │Creation Classif.│  │Adjudication      │                            │  │ └────────────────┘ │
│  │intent_creation.py│ │Contract/pipeline │                            │  └────────────────────┘
│  └────────┬────────┘  └─────────┬────────┘                            │
└───────────┼─────────────────────┼────────────────────────────────────┘
            │                     │
┌───────────▼─────────────────────▼────────────────────────────────────┐
│                        ③ 执行与状态层                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────────┐  │
│  │ Transformer  │  │StoryState    │  │  Patch Executor (dry-run)  │  │
│  │transformer.py│  │Manager       │  │  patch_executor.py         │  │
│  └──────┬───────┘  └──────────────┘  └──────────────┬─────────────┘  │
│         │                                             │                │
│         │            ┌───────────────────────────────▼──────────┐     │
│         └───────────▶│         Plan Executor                    │     │
│                      │         plan_executor.py                 │     │
│                      └──────────────────────┬────────────────────┘     │
└─────────────────────────────────────────────┼─────────────────────────┘
                                              │
┌─────────────────────────────────────────────▼─────────────────────────┐
│                        ④ 基础设施层                                    │
│  ┌──────────────┐  ┌─────────────────┐  ┌─────────────────────────┐  │
│  │ RCON Client  │  │Command Safety   │  │ Patch Transaction Log   │  │
│  │rcon_client.py│  │command_safety.py│  │ patch_transaction.py    │  │
│  └──────┬───────┘  └─────────────────┘  └─────────────────────────┘  │
│         │          ┌─────────────────┐  ┌─────────────────────────┐  │
│         │          │CityPhone Metrics│  │ Embedding Model         │  │
│         │          │cityphone_metrics│  │ embedding_model.py      │  │
│         │          └─────────────────┘  └─────────────────────────┘  │
│         │          ┌─────────────────┐                               │
│         │          │  Mod Manager    │                               │
│         │          │  mods/manager.py│                               │
│         │          └─────────────────┘                               │
└─────────┼──────────────────────────────────────────────────────────┘
          │ TCP RCON
          ▼
    [Minecraft Server]
```

---

## 六、与 main 的关键差异点（最多 5 条）

> **说明**：当前仓库仅可见 `scienceline` 分支（`copilot/add-architecture-blueprint-md` 从该分支衍生），无法直接访问 `main` 分支代码。以下差异点基于仓库内文档线索（`docs/DRIFT_SCIENCELINE.code-workspace`、`docs/IDEAL_CITY_*` 系列）推断，供参考：

1. **Ideal City 完整流水线**（`scienceline` 新增）：`backend/app/core/ideal_city/` 目录下的 `pipeline.py`、`build_plan_agent.py`、`story_state_manager.py`、`adjudication_contract.py` 等理想之城专属模块，在 `main` 中可能尚未合入或处于早期版本。

2. **Embedding 语义层**（`scienceline` 新增）：`backend/app/ml/embedding_model.py` 及其"不具执行权限"边界约定（见文件顶部模块说明注释，标注引入版本为 DriftSystem v1.18），`main` 分支中可能不存在该模块。

3. **StoryState 多阶段协议**（`scienceline` 扩展）：`story_state_phase.py`、`story_state_agent.py` 等阶段化状态机，以及 `STORYSTATE_TEMPLATE_ROADMAP.md` 路线图，是 scienceline 的重点演进内容。

4. **Patch 事务日志与 undo_patch 预留**（`scienceline` 扩展）：`patch_transaction.py` 中 `undo_patch` 字段的引入，以及 `docs/patch-execution-contract.md` 合约文档，属于 scienceline 执行层强化。

5. **理想之城裁决合约守卫**（`scienceline` 强化）：`docs/IDEAL_CITY_EXECUTION_GUARDRAILS.md` 与 `execution_boundary.py` 的"零 Mod 保证"约束，明确禁止直接世界 patch 和插件回调，是 scienceline 对执行层权限的收紧。
