# DRIFT_MEMORY_WORLD_PRODUCTION_PLAN

## 1. PROJECT INTENT

Drift 的目标不是 AI 自动生成世界，而是将人类写下的场景 / 记忆描述映射为可执行的 Minecraft 结构，并允许玩家在其中持续行动与交互。

这是 **Scene Realization（场景实现）**，不是 Scene Generation（AI 生成）。

系统职责（必须保持不变）：

`Natural Language / Imported Text`
`→ Scene Mapping（规则映射）`
`→ Asset Binding（资源绑定）`
`→ CreationPlan`
`→ 执行到 Minecraft 世界`
`→ 世界持续存在并允许互动`

本文件是工程落地蓝图（Production Enablement），不是研究方案或新架构设计。

---

## 2. CURRENT STATE ANALYSIS

以下为仓库已存在、可直接复用的基础能力（EXISTING FOUNDATION）：

1. **CreationPlan / Transformer 已存在**
   - `backend/app/core/creation/transformer.py`
   - 已有 `CreationPlan`、`CreationPlanStep`、`CreationPatchTemplate`、`execution_tier` 机制。

2. **PatchExecutor / PlanExecutor 已存在**
   - `backend/app/core/world/patch_executor.py`
   - `backend/app/core/world/plan_executor.py`
   - 支持 dry-run 校验、命令安全检查、事务记录、自动执行。

3. **RCON 执行链已存在**
   - `backend/app/core/minecraft/rcon_client.py`
   - `backend/app/services/creation_workflow.py` 中 `RconCommandRunner` + `_build_command_runner()`。

4. **运行时非 CLI 入口已存在（可触发 PlanExecutor）**
   - `POST /intent/execute`：`backend/app/api/intent_api.py`
   - `POST /world/apply`：`backend/app/api/world_api.py`（聊天流内可自动执行 creation plan）。

5. **执行日志能力已存在**
   - `backend/app/core/world/patch_transaction.py`
   - 写入 `backend/data/patch_logs/transactions.log`（JSONL）。

6. **ResourceCatalog 已建立，但 drift:* 命令为空**
   - `backend/data/transformer/resource_catalog.json`
   - `drift:altar_frame`、`drift:exhibit_frame` 等条目存在，`commands: []`。
   - 这导致 transformer 只能给出草案/待确认步骤，不能稳定产出可执行结构命令。

7. **场景相关能力已有部分基础但未形成 Scene Realization 闭环**
   - `scene_generator.py` + `environment_builder.py` 有规则构建能力。
   - `story_engine.enter_level_with_scene()` 仍是 stub（未把 scene 真实落地为统一执行链）。
   - `backend/app/routers/scene.py` 存在，但当前 `backend/app/main.py` 未注册该 router。

8. **当前剧情导入开关状态（本次任务已处理）**
   - 运行配置 `server/plugins/DriftSystem/config.yml` 已设为：
   - `world.allow_story_creation: true`

---

## 3. MINIMUM REQUIRED ADDITIONS

核心问题必须明确：**当前缺的不是 AI/NLP，而是 Scene Realization Layer（文本→资源→可执行结构）**。

本阶段只做最小增量，且仅三类：

### A. Scene Adapter（薄映射层，deterministic）

目标：把 `文本/scene.json` 映射成可执行 `CreationPlan`，不使用 LLM、embedding、推理。

最小实现要求：

- 输入：
  - `text: str`（导入记忆/场景描述）
  - 或 `scene: dict`（标准化 scene.json）
  - `player_context`（可选：世界、坐标、朝向）
- 处理：
  - 规则匹配（关键词/标签/枚举映射）
  - 资源绑定到 `resource_catalog` 中已定义资源
  - 生成 `CreationPlan` + `CreationPatchTemplate(mc.commands)`
- 输出：
  - `CreationPlanResult`（沿用已有结构）

建议落位：`backend/app/core/world/scene_adapter.py`（复用现有 plan/executor，不新建执行框架）。

### B. Asset Layer 补全（数据层，不是算法层）

目标：补齐 `drift:*` 的最小 commands，使映射后可执行。

仅允许命令：

- `setblock`
- `fill`
- `clone`
- `summon`
- `structure load`

必须覆盖最小资产类型：

1. 场景结构（房间 / 路径 / 开放空间）
2. NPC / 动物 spawn
3. 基础事件触发结构（可观察、可复现，不引入复杂函数链）

数据修改位置：

- 首选：`backend/data/transformer/resource_catalog.seed.json`（可维护源）
- 生成后：`backend/data/transformer/resource_catalog.json`

### C. Runtime Execution 能力（可视化节奏执行）

目标：在运行时（API）触发 `PlanExecutor`，并支持 paced execution。

最小实现要求：

- 不是 CLI-only：沿用 `POST /intent/execute` 或新增最小 `/scene/realize` API。
- 新增执行参数：`step_delay_ms`（模板/步骤间延迟）。
- 执行语义：
  - `step_delay_ms = 0`：现有立即执行模式
  - `step_delay_ms > 0`：按 step 顺序 sleep 后下发 commands（用于可见建造）

---

## 4. ASSET LAYER REQUIREMENTS

这是数据补全清单，不是代码重写。

### 4.1 drift:* 最小资产包（必须先补）

每个 drift 资源至少包含：

- `resource_id`
- `label`
- `aliases`
- `tags`
- `commands`（非空）

建议第一批（MVP）：

1. `drift:room_basic`
   - 房间壳体 + 门洞
   - `fill` + `setblock`
2. `drift:path_basic`
   - 地面路径
   - `fill`
3. `drift:open_space_basic`
   - 开放平台
   - `fill`
4. `drift:npc_villager_basic`
   - `summon villager`
5. `drift:animal_cow_basic`
   - `summon cow`
6. `drift:event_marker_basic`
   - 基础事件触发标记结构（方块/实体标记）

### 4.2 命令约束

- 禁止复杂函数链（不依赖 `function ...` 作为主路径）。
- 禁止一次性超大范围命令（避免多人服卡顿）。
- 所有命令必须可被当前 `command_safety` 接受。

### 4.3 命名与版本

- 使用 `drift:*` 命名空间。
- 资产变更先入 `seed`，再生成 catalog，保证可追溯。

---

## 5. SCENE ADAPTER SPEC

### 5.1 Input Contract

- `source_type`: `"text" | "scene_json"`
- `text`: 人类描述（可选）
- `scene`: 标准场景对象（可选）
- `context`:
  - `world`
  - `anchor`（x,y,z）
  - `yaw/pitch`（可选）

### 5.2 Output Contract

- `CreationPlanResult`
  - `plan.action`
  - `plan.materials`
  - `plan.steps`
  - `plan.patch_templates[].world_patch.mc.commands`
  - `execution_tier = safe_auto | needs_confirm`

### 5.3 Deterministic Mapping Rules

- 仅规则匹配（关键词→资源ID映射表）。
- 同一输入在同一版本资产下必须得到同一 plan。
- 未命中规则时返回 `needs_review`，不做自动推断。

---

## 6. EXECUTION FLOW

目标链路（上线后）：

1. 导入文本或 scene.json
2. Scene Adapter 做规则映射，生成 `CreationPlanResult`
3. `PatchExecutor.dry_run()` 校验命令安全与执行层级
4. `PlanExecutor.auto_execute()` 通过 RCON 下发
5. 事务日志写入 `patch_logs/transactions.log`
6. Minecraft 世界出现结构，玩家可持续互动

运行入口建议（最小改造）：

- 方案 1（最小侵入）：在 `POST /intent/execute` 增加 Scene Adapter 触发分支
- 方案 2（更清晰）：注册并使用 `/scene/*` 路由（当前代码存在但未挂载）

---

## 7. IMPLEMENTATION ORDER

严格按顺序执行，避免“代码先行但数据不可用”：

1. **确认运行前提**
   - RCON 可连通（host/port/password）。
   - `DRIFT_CREATION_AUTO_EXEC` 未关闭。

2. **先补 Asset 数据（第一优先级）**
   - 给 `drift:*` 写入非空 `commands`。
   - 产出最小 6 类资源（结构/路径/开放空间/NPC/动物/事件标记）。

3. **实现 Scene Adapter（薄层）**
   - 输入文本/scene.json。
   - 规则映射到上述 drift 资源。
   - 输出标准 `CreationPlanResult`。

4. **接入 Runtime 执行入口**
   - 复用现有 `PlanExecutor`。
   - 增加 `step_delay_ms`。

5. **端到端验证（单人）**
   - 文本导入→Plan→执行→日志→世界结构出现。

6. **多人服验证（最小并发）**
   - 2~3 玩家同服，确认结构可见、状态一致、执行可重放。

---

## 8. DEPLOYMENT REQUIREMENTS

多人进服运行的最小条件：

1. **Minecraft 服务端**
   - RCON 开启并可从 backend 访问。
   - 固定世界与权限策略（避免 OP 命令依赖）。

2. **Backend 服务**
   - 路由已加载（`/intent/*` 必须可用；如启用 `/scene/*` 需在 `main.py` 注册）。
   - `creation_workflow` 能成功握手 RCON。

3. **资源数据**
   - `resource_catalog` 已包含非空 drift 资产命令。
   - 资产版本固定（避免不同环境映射漂移）。

4. **观测与回滚**
   - `patch_logs/transactions.log` 持续可写。
   - 失败命令可追踪到 patch_id/template_id/step_id。

---

## 9. FIRST DRY RUN PROCEDURE

首次验证仅关注“文本→结构出现→可互动”。

1. 启动 Minecraft + backend，确认 RCON 正常。
2. 准备一条文本（例：
   - “在我前方生成一个小房间，旁边放一条路径，并召唤一个村民”）。
3. 调用运行时入口（建议 `POST /intent/execute`）：
   - 第一次 `dry_run_only=true`，检查返回 `plan.patch_templates` 与 `commands`。
4. 确认命令仅包含允许集合（setblock/fill/clone/summon/structure load）。
5. 第二次执行真实下发（`dry_run_only=false`）。
6. 观察 Minecraft 世界：
   - 结构已出现；
   - NPC/动物可见；
   - 玩家可进入并持续互动。
7. 检查事务日志：
   - 有对应 patch_id 记录；
   - 每个 step 有状态。
8. 若失败：按 patch_id 回溯失败 step，修正资产数据后重试。

---

## 10. DO NOT TOUCH LIST

以下全部 **OUT OF SCOPE**（本阶段禁止）：

- IntentEngine 修改
- StoryEngine 扩展
- 新 DSL 设计
- AI 剧情生成
- embedding / 向量检索优化
- 世界模型（Genie 等）
- 架构重构
- 性能优化
- 任何研究性功能

本阶段定位：**Production Enablement**。
衡量标准：团队能按此蓝图补齐资源、接入适配层、运行服务器、导入文本、在世界中稳定看到并互动结构。
