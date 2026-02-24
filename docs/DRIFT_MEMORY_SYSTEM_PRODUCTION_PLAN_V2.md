# DRIFT_MEMORY_SYSTEM_PRODUCTION_PLAN_V2

## 1. SYSTEM INTENT

Drift 的目标是三阶段运行模型（最终结构）：

- **Stage 1：Shared World（共享空间）**
  - 三人进入同一服务器
  - 低干预
  - 不推进剧情
  - 建立共同空间

- **Stage 2：Personal Level（个人关卡）**
  - 每人创建独立关卡容器
  - 场景通过 Scene Realization 生成（deterministic）
  - StoryEngine 仅在个人模式下运行（深度叙事）
  - 每人关卡完全隔离，互不污染

- **Stage 3：Return to Shared World（集合）**
  - 退出个人关卡
  - 回到共享世界
  - 不自动合并剧情
  - 不自动生成总结
  - 仅保留真实对话

本计划是系统认知对齐与工程落地文档，不做功能扩展与架构重写。

---

## 2. CURRENT CODE STATE

以下结论均来自当前代码审计。

### 2.1 个人关卡是否真正隔离

1. **world_state 当前不是按玩家隔离**
   - `backend/app/api/world_api.py` 中为全局单例：`world_engine = WorldEngine()`。
   - `backend/app/core/world/engine.py` 内 `WorldEngine.state` 是单一对象（`variables/entities`），`apply()` 不区分 `player_id`。
   - 结论：当前 world_state 为进程级共享状态，不是 per-player/per-level 隔离。

2. **story_state 当前主要按 player_id 存储，不是按 level_id 持久键空间**
   - `backend/app/core/story/story_engine.py` 中 `self.players: Dict[str, Dict[str, Any]]` 作为主状态容器。
   - `load_level_for_player()` 把 `p["level"] = level`，即当前激活关卡挂在玩家状态下。
   - 未看到 `story_state[level_id] = ...` 这一类主存储结构。
   - 结论：story_state 为 per-player current-level 形态，不是 per-level 独立存储模型。

3. **存在全局变量污染风险**
   - `world_engine` 为全局单例（共享变量/实体）。
   - `story_engine` 为模块级单例（`story_engine = StoryEngine()`），虽按玩家分桶，但仍共享同一实例生命周期。
   - `creation_workflow` 中 `_command_runner/_plan_executor` 为模块级全局执行器。

### 2.2 Scene Realization 当前缺失点

1. **drift:* prefab 数据存在但 commands 为空**
   - `backend/data/transformer/resource_catalog.json` 中 `drift:altar_frame / drift:exhibit_frame / drift:garden_bundle ...` 的 `commands: []`。

2. **deterministic 场景映射入口有“部分能力”，但未形成统一生产入口**
   - 已有规则映射：`backend/app/core/world/scene_generator.py`（关键词规则 -> `environment_builder`）。
   - 但该路径输出是 world patch 形状描述，不是 `drift:* prefab -> CreationPlan` 的标准 Scene Realization 层。
   - `backend/app/routers/scene.py` 存在，但 `backend/app/main.py` 未注册该 router。

3. **现有注入路径含 AI 生成世界逻辑**
   - `backend/app/api/story_api.py` 的 `/story/inject` 调用 `deepseek` 生成世界内容。
   - 该行为与本次目标（Scene Realization deterministic）不一致。

### 2.3 StoryEngine 当前能力与模式

1. **当前没有 Shared/Personal 运行模式开关**
   - 未看到 `shared_mode/personal_mode` 的显式状态机或路由门控。

2. **`/world/apply` 中说话默认推进 StoryEngine**
   - `backend/app/api/world_api.py` 在 `if say_text:` 分支直接调用 `story_engine.advance(...)`。
   - 即 Shared World 阶段若复用该入口，将推进剧情。

3. **StoryEngine 自身是“始终可推进”语义**
   - `story_engine.should_advance()` 当前直接返回 `True`。

### 2.4 Runtime Execution 当前能力

1. **支持运行时触发 build/plan 执行**
   - `POST /intent/execute`（`backend/app/api/intent_api.py`）可走 dry-run / auto-execute。
   - `POST /world/apply`（`backend/app/api/world_api.py`）在 creation 分支可触发 `auto_execute_plan()`。

2. **支持 RCON 实时执行与执行日志**
   - `creation_workflow -> PlanExecutor -> RconClient`。
   - 事务日志写入 `backend/data/patch_logs/transactions.log`。

3. **当前不支持 paced execution**
   - 未发现 `step_delay_ms` 或步骤节拍参数。
   - `PlanExecutor.auto_execute()` 为逐模板直接下发，无延迟控制参数。

---

## 3. GAP ANALYSIS

按 Shared / Personal 分开。

### 3.1 Shared World（Stage 1）缺口

目标要求：Shared 阶段不推进剧情，仅共享空间与低干预 Scene Realization。

当前缺口：

1. `/world/apply` 有 `say_text` 就推进 `story_engine.advance()`，与目标冲突。
2. world_state 为全局单态，无法给 Shared 与 Personal 做清晰边界。
3. Scene Realization 入口未独立治理（缺少“只执行场景实现、不触发剧情”的运行门禁）。

### 3.4 强制收敛决策（MVP 写死）

为避免实现期反复争论，本计划对 4 个关键点做固定决策：

1. **隔离策略固定为 A1（坐标域隔离）**
   - 不采用 A2（多 WorldEngine 实例）作为 MVP。
   - Shared 与 Personal 的隔离通过空间域边界 + 命令校验保证。

2. **Scene Realization MVP 入口固定**
   - 输入固定为 `scene.json`。
   - API 固定为 `POST /scene/realize`。
   - 纯文本输入放入 vNext，不纳入 MVP。

3. **Asset Layer 固定首批资源清单**
   - 必须按本文件第 9 章提供的 resource_id、bbox、anchor 交付。

4. **Shared 模式聊天策略固定**
   - Shared World 禁止 `story_engine.advance`。
   - Shared World 禁止任何 AI 回复。
   - 仅保留原生聊天与聊天记录。

### 3.2 Personal Level（Stage 2）缺口

目标要求：每人独立关卡容器，StoryEngine 全功能运行且互不污染。

当前缺口：

1. story_state 虽按 player_id 分桶，但 world_state 仍为全局共享，隔离不完整。
2. Scene Realization 尚未形成 `text/scene -> drift prefab -> CreationPlan` 的统一 deterministic 链路。
3. drift prefab commands 为空，导致个人关卡场景生成落地能力不足。
4. 无 paced execution，无法做可视化建造节奏。

### 3.3 Return（Stage 3）缺口

目标要求：返回共享世界，不自动合并、不自动总结、不改变共享世界结构。

当前缺口：

1. 退出流程已有 `story_end/exit_level_with_cleanup`，但缺少“Return 阶段行为约束开关”统一治理。
2. 若复用 `/world/apply` 对话入口，仍可能触发剧情推进逻辑。

---

## 4. SCENE REALIZATION LAYER DESIGN

本节为**基于现有代码的收敛设计**，不引入新架构。

### 4.1 目标

建立 deterministic 场景实现层：

`text/scene.json -> 规则映射 -> drift:* prefab 绑定 -> CreationPlan -> PlanExecutor`

### 4.2 约束

- 禁止 LLM。
- 禁止 embedding/向量检索作为执行决策。
- 禁止推理式世界生成。

### 4.3 复用现有组件

- `CreationPlan`/`PatchExecutor`/`PlanExecutor`（已存在）
- `resource_catalog.seed.json` + `resource_catalog.json`（已存在）
- `RconClient`（已存在）

### 4.4 最小入口策略

- Shared 阶段只允许 Scene Realization 入口执行（不调用 `story_engine.advance`）。
- Personal 阶段 Scene Realization + StoryEngine 可同时使用。

### 4.5 MVP 接口契约（写死）

#### Endpoint

- `POST /scene/realize`

#### Request（MVP 仅支持 scene.json）

```json
{
   "player_id": "player_001",
   "mode": "shared|personal",
   "scene": {
      "scene_id": "scene_memory_001",
      "layout": "room_path_open",
      "assets": [
         {"resource_id": "drift:room_basic_7x5x7", "anchor": {"x": 0, "y": 64, "z": 0}},
         {"resource_id": "drift:path_axis_1x1x15", "anchor": {"x": 8, "y": 64, "z": 0}},
         {"resource_id": "drift:npc_anchor_villager", "anchor": {"x": 2, "y": 64, "z": 2}}
      ]
   }
}
```

#### Response

```json
{
   "plan_id": "plan_xxx",
   "scene_id": "scene_memory_001",
   "status": "ok|needs_review|blocked",
   "selected_assets": ["drift:room_basic_7x5x7", "drift:path_axis_1x1x15", "drift:npc_anchor_villager"],
   "patch_id": "patch_xxx"
}
```

#### needs_review 行为（强制）

- `status=needs_review` 时：
   - 不自动推断缺失资源
   - 不自动补全命令
   - 不执行 build
   - 返回缺失字段与未匹配 asset 列表，等待人工修正 scene.json

---

## 5. PERSONAL STORYENGINE MODE DESIGN

本节为运行策略对齐，不是 StoryEngine 结构改造。

### 5.1 模式边界

- **Shared mode**：StoryEngine 禁止推进剧情。
- **Personal mode**：StoryEngine 允许全流程推进。

### 5.2 现有代码落位点（用于门控）

- `backend/app/api/world_api.py`：当前 `if say_text: story_engine.advance(...)` 为主要门控点。
- `backend/app/api/world_api.py` 的 `/story/start`、`/story/end` 可作为 personal 生命周期入口。

### 5.3 最小治理原则

- 不改 StoryEngine 核心叙事算法。
- 仅做“入口门控与阶段路由约束”，把 StoryEngine 运行限定到 Personal 阶段。

---

## 6. ISOLATION GUARANTEE STRATEGY

### 6.1 必须保证的隔离对象

1. world_state
2. story_state
3. build execution side effects

### 6.2 基于当前代码的最小隔离策略

#### 6.2.1 选型结论（MVP）

- **固定采用 A1：坐标域隔离（物理隔离）**
- **A2：多 WorldEngine 实例不进入 MVP**（仅作为后续演进选项）

#### 6.2.2 A1 实现要点（写死）

1. **空间域划分**
   - `S`（Shared 域）：共享世界主坐标域。
   - `P1/P2/P3...`（Personal 域）：每名玩家一个独立坐标域。
   - 域中心相隔至少 `1000 blocks`（MVP 固定值）。

2. **执行边界强制校验**
   - 所有 build/spawn 指令在下发前必须通过域边界验证。
   - 指令目标超出所属域边界时，直接 `blocked`。
   - 校验层放在命令安全/执行前置阶段（与 `PatchExecutor/PlanExecutor` 串联）。

3. **模式与域绑定**
   - Shared 模式只能写 `S` 域。
   - Personal 模式只能写对应玩家 `P{n}` 域。
   - Return 后玩家恢复到 `S` 域交互，不回写其他玩家 Personal 域。

4. **状态现实说明**
   - world_state 仍是全局单态（不重构 WorldEngine）。
   - 隔离保证由“空间边界 + 执行校验”实现。

5. **执行日志按 patch_id/player_id/mode 追踪**
   - 复用 `patch_logs/transactions.log`，用于回放与审计。

---

## 7. EXECUTION FLOW（完整三阶段）

### Stage 1：Shared World

1. 三人进入同一服务器。
2. 使用 Shared 入口进行低干预交互。
3. 仅允许 Scene Realization 执行（deterministic build）。
4. 禁止 StoryEngine 推进剧情。
5. 禁止任何 AI 回复（仅原生聊天与记录）。

### Stage 2：Personal Level

1. 玩家发起进入个人关卡（`/story/start` 或等效 personal 入口）。
2. Scene Realization 根据文本/scene.json 生成个人场景结构。
3. StoryEngine 在 personal 模式下推进叙事。
4. 所有关卡状态仅作用于该玩家 personal 容器。

### Stage 3：Return to Shared World

1. 玩家退出个人关卡（`/story/end` + cleanup）。
2. 返回共享世界。
3. 不自动合并剧情。
4. 不自动生成总结。
5. 仅保留真实对话记录。
6. 继续禁止 Shared 阶段的 StoryEngine 推进与 AI 回复。

---

## 8. IMPLEMENTATION ORDER（优先级）

1. **P0：阶段门控先行**
   - 先确保 Shared 阶段不调用 StoryEngine 推进。

2. **P1：补齐 prefab 数据层**
   - `drift:*` 增补最小可执行 commands（结构/路径/NPC/动物/基础触发）。

3. **P2：打通 deterministic Scene Realization 入口**
   - 固定规则映射到 drift 资产。
   - 输出标准 CreationPlan 并执行。

4. **P3：Personal 生命周期固化**
   - 进入/退出流程与清理边界明确。

5. **P4：paced execution**
   - 在现有 PlanExecutor 调用链增加 `step_delay_ms`。

6. **P5：三人联机验收**
   - Shared 建立共同空间。
   - 三人各自进入 personal 关卡推进。
   - 全员返回 Shared，无自动融合与总结。

---

## 9. DATA LAYER REQUIREMENTS（prefab / mapping）

### 9.1 prefab MVP 清单（固定首批 10 个）

必须在 `resource_catalog.seed.json` + 生成后的 `resource_catalog.json` 中提供以下资源，且 `commands` 非空：

1. `drift:room_basic_7x5x7`
   - bbox: `7x5x7`
   - anchor: `floor_center`
   - 用途: 基础房间壳体

2. `drift:room_small_5x4x5`
   - bbox: `5x4x5`
   - anchor: `floor_center`
   - 用途: 紧凑室内空间

3. `drift:path_axis_1x1x15`
   - bbox: `1x1x15`
   - anchor: `start_point`
   - 用途: 单向路径连接

4. `drift:path_axis_3x1x15`
   - bbox: `3x1x15`
   - anchor: `start_center`
   - 用途: 宽路径连接

5. `drift:open_field_15x1x15`
   - bbox: `15x1x15`
   - anchor: `center`
   - 用途: 开放活动区

6. `drift:open_field_9x1x9`
   - bbox: `9x1x9`
   - anchor: `center`
   - 用途: 小型开放区

7. `drift:npc_anchor_villager`
   - bbox: `1x2x1`
   - anchor: `feet`
   - 用途: 村民 NPC 生成点

8. `drift:animal_pair_sheep`
   - bbox: `3x2x3`
   - anchor: `center_ground`
   - 用途: 双羊群体生成

9. `drift:event_marker_pressure_plate`
   - bbox: `1x1x1`
   - anchor: `block_origin`
   - 用途: 基础事件触发标记

10. `drift:event_marker_beacon`
    - bbox: `1x4x1`
    - anchor: `base_center`
    - 用途: 可视化事件信标

### 9.2 命令白名单

仅允许：

- `setblock`
- `fill`
- `clone`
- `summon`
- `structure load`

每个 prefab 只允许使用上述命令；禁止 function 链作为主执行路径。

### 9.3 资产组合约定（MVP）

1. 组合时统一使用 asset anchor 做相对定位。
2. 路径类 asset 必须从 `start_*` 锚点向前展开。
3. 房间与开放区资产允许拼接，但 bbox 不能越出所属坐标域边界。
4. NPC/动物锚点必须落在可站立方块上（scene 校验阶段检查）。

### 9.4 mapping 规则要求

- 规则映射必须 deterministic。
- 同输入同资产版本输出同 CreationPlan。
- 未匹配返回 needs_review，不做自动推断。

---

## 10. DEPLOYMENT CHECKLIST（多人服务器）

1. 三人可同时进入同一 Shared World。
2. Shared 入口验证：发送对话不会触发 StoryEngine 推进，也不会触发 AI 回复。
3. Personal 入口验证：每人可进入独立关卡并推进剧情。
4. 隔离验证：P1/P2/P3 坐标域互不越界，越界命令会被 blocked。
5. prefab 验证：第 9 章 MVP 10 个 drift 资源 commands 非空并可执行。
6. Scene Realization 验证：`POST /scene/realize` 可返回 `ok|needs_review|blocked`。
7. 执行链验证：`CreationPlan -> PatchExecutor -> PlanExecutor -> RCON` 正常。
8. paced 验证：支持 `step_delay_ms`（若为 0 则即时执行）。
9. Return 验证：退出后回 Shared，无自动融合、无自动总结。
10. 追踪验证：`patch_logs/transactions.log` 可按玩家与 patch_id 追溯。

---

## 11. DO NOT TOUCH LIST

以下内容本任务禁止：

- 新架构设计
- AI world model / 自动生成世界方案
- DSL 重写
- StoryEngine 核心重构
- IntentEngine 重写
- embedding/向量检索优化作为核心执行路径
- 性能优化专项
- 研究性扩展

本任务定位：**系统目标重对齐 + 生产可落地蓝图**。
成功标准：三人可共享进入、各自进入个人关卡、deterministic 场景实现、个人剧情推进、退出集合且互不污染。
