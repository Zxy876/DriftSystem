# DRIFT_MEMORY_SYSTEM_PRODUCTION_PLAN_V3

## 1. SYSTEM INTENT（最终对齐）

Drift 的目标固定为三阶段运行模型：

- Stage 1：Shared World（共享空间）
  - 三人进入同一服务器
  - 低干预
  - 不推进剧情
  - 建立共同空间

- Stage 2：Personal Level（个人关卡）
  - 每人创建独立关卡容器
  - 场景通过 Scene Realization 生成（deterministic）
  - StoryEngine 仅在 Personal 模式运行
  - 每人关卡隔离，互不污染

- Stage 3：Return to Shared World（集合）
  - 退出个人关卡
  - 回到共享世界
  - 不自动合并剧情
  - 不自动生成总结
  - 仅保留真实对话

本文件是最终工程对齐版本，不新增架构、不引入 world model、不扩展 DSL。

---

## 2. CURRENT CODE STATE（保留 V2 审计）

### 2.1 隔离现状

1. world_state 当前为全局单例
   - `backend/app/api/world_api.py`：`world_engine = WorldEngine()`
   - `backend/app/core/world/engine.py`：`WorldEngine.state` 为单一状态对象。

2. story_state 当前主要按 player_id 分桶
   - `backend/app/core/story/story_engine.py`：`self.players: Dict[str, Dict[str, Any]]`。
   - 当前未采用 `story_state[level_id]` 主存储模型。

3. 全局共享风险客观存在
   - `world_engine` 单例
   - `story_engine` 单例
   - `creation_workflow` 中 `_command_runner/_plan_executor` 为模块级执行器。

### 2.2 Scene Realization 现状

1. drift 资产存在但命令未补齐
   - `backend/data/transformer/resource_catalog.json` 中多项 `drift:*` 为 `commands: []`。

2. `level.json` 已存在 `narrative + scene` 双区块实践
   - 例如 `backend/data/heart_levels/level_01.json`、`level_02.json`、`tutorial_level.json`。
   - `backend/app/core/story/level_schema.py` 的 `LevelExtensions.from_payload()` 已解析 `payload["narrative"]` 与 `payload["scene"]`。

3. 当前缺统一 Scene Realization 生产入口
   - 有 scene 相关代码与路由，但未形成“scene.json 唯一输入”的固定执行入口。

### 2.3 StoryEngine 行为现状

1. `/world/apply` 下，`say_text` 会触发 `story_engine.advance(...)`。
2. `should_advance()` 当前语义为始终允许推进。
3. 当前未见 Shared/Personal 显式模式开关。

### 2.4 Runtime Execution 现状

1. 运行时可触发执行链（非 CLI-only）
   - `/intent/execute`
   - `/world/apply` creation 分支

2. 执行链已存在
   - CreationPlan -> PatchExecutor -> PlanExecutor -> RCON

3. paced execution 尚未落地
   - 未见 `step_delay_ms` 执行参数。

---

## 3. FINAL EXECUTION CHAIN（自然语言到世界）

本项目最终执行链写死如下：

自然语言
-> 结构化生成 level.json
-> 从 level.json 提取 scene 区块
-> 生成 scene.json
-> POST /scene/realize
-> CreationPlan
-> PlanExecutor
-> RCON
-> Minecraft World

### 3.1 强制规则

1. `scene.json` 是 Scene Realization 唯一输入。
2. 未匹配资源必须返回 `needs_review`。
3. 禁止 LLM 直接生成 build 命令。
4. 禁止自然语言绕过结构层直接 build。

---

## 4. LEVEL.JSON 与 SCENE.JSON 结构约定（最终）

## 4.1 level.json 推荐结构（MVP）

`level.json` 固定为双区块：

- `narrative`：叙事内容与节拍
- `scene`：可执行场景描述（供 Scene Realization 提取）

示意：

```json
{
  "id": "flagship_xxx",
  "title": "...",
  "narrative": {
    "text": ["..."],
    "beats": [{"id": "beat_01", "goal": "..."}]
  },
  "scene": {
    "scene_id": "scene_xxx",
    "mode": "shared|personal",
    "domain": "S|P1|P2|P3",
    "anchor": {"x": 0, "y": 64, "z": 0},
    "assets": [
      {"resource_id": "drift:room_basic_7x5x7", "anchor": {"x": 0, "y": 64, "z": 0}}
    ]
  }
}
```

### 4.2 scene.json 最小字段集合（MVP）

`scene.json` 最小字段固定：

- `scene_id`
- `player_id`
- `mode`（shared 或 personal）
- `domain`（S / Pn）
- `anchor`（x,y,z）
- `assets[]`（每项至少 `resource_id + anchor`）

示意：

```json
{
  "scene_id": "scene_memory_001",
  "player_id": "player_001",
  "mode": "personal",
  "domain": "P1",
  "anchor": {"x": 1000, "y": 64, "z": 0},
  "assets": [
    {"resource_id": "drift:room_basic_7x5x7", "anchor": {"x": 1000, "y": 64, "z": 0}},
    {"resource_id": "drift:path_axis_1x1x15", "anchor": {"x": 1008, "y": 64, "z": 0}}
  ]
}
```

### 4.3 level.json 与 scene.json 关系（写死）

1. level.json 是上层关卡定义与叙事容器。
2. scene.json 是 Scene Realization 执行输入。
3. scene.json 由 level.json 的 `scene` 区块抽取/转写得到。
4. 任何 build 行为必须来源于 scene.json，不允许直接从自然语言或 narrative 执行。

---

## 5. SCENE REALIZATION EXECUTION SPEC（deterministic）

### 5.1 Endpoint

- `POST /scene/realize`（MVP 固定）

### 5.2 Request

- 仅支持 `scene.json`。
- 不接受纯自然语言作为 Scene Realization 直接输入。

### 5.2.1 mode / domain 强制一致性（MVP 硬约束）

服务端必须强制校验并绑定 mode/domain：

1. `mode=shared` 时，`domain` 必须为 `S`。
2. `mode=personal` 时，`domain` 必须为该 `player_id` 绑定的 `P{n}`。
3. 客户端提交的 `domain` 仅作为候选值，不作为最终执行依据。
4. 服务端可对请求中的 `domain` 进行 `validated/overridden`，以消除跨域污染风险。

### 5.3 Response（固定字段）

返回必须包含：

- `plan_id`
- `scene_id`
- `status`（`ok | needs_review | blocked`）
- `selected_assets`
- `patch_id`

### 5.4 needs_review 固定行为

当 `status=needs_review`：

1. 不自动补全
2. 不自动猜测
3. 不执行 build
4. 返回错误字段（缺失字段、未匹配资源、无效锚点等）

### 5.5 资产组合规则（固定）

1. 使用 asset anchor 做相对定位。
2. bbox 不得越出所属坐标域。
3. 路径类必须按 `start_*` 锚点展开。
4. NPC 必须落在可站立块。

---

## 6. A1 COORDINATE DOMAIN ISOLATION（固定实现）

MVP 固定采用 A1，不采用多 WorldEngine 实例。

### 6.1 空间域划分

- `S` 域：Shared World 主区域
- `P1, P2, P3...`：每名玩家一个独立 Personal 域

### 6.2 域间距离

- 域中心间距固定：`>= 1000 blocks`

### 6.2.1 Domain bbox（MVP 硬约束）

- 每个域采用固定方形边界：`512 x 512`（相对域中心 `x/z = ±256`）。
- Y 轴执行范围固定：`0–320`。
- 执行边界校验、资产 bbox 校验均以该域 bbox 为唯一判定基准。

### 6.3 玩家传送规则（写死）

1. 进入 Personal Level：自动 TP 到 `P{n}` 域中心。
2. 退出 Personal Level：自动 TP 回 `S` 域 spawn。

### 6.4 执行边界强制校验

1. 所有 `build / summon / clone` 指令执行前必须过域边界校验。
2. 坐标不在所属域 bbox 内：直接 `blocked`。
3. 校验放在 PatchExecutor / PlanExecutor 前置阶段。
4. `scene.json` 中所有 asset 的 bbox 若越出域 bbox：直接 `blocked`。

### 6.5 world_state 约束

1. `world_state` 维持单例，不重构。
2. 隔离通过“空间域 + 执行校验”实现。
3. 禁止引入多 WorldEngine 实例（MVP 明确禁止）。

---

## 7. MODE LOCK（Shared / Personal / Return）

### 7.1 Shared 模式（锁死）

- 禁止 `story_engine.advance`
- 禁止 AI 回复
- 仅允许 Scene Realization
- 仅允许原生聊天记录

### 7.2 Personal 模式（锁死）

- 允许 StoryEngine 全推进
- 允许 `scene_realize`
- 状态只作用于该玩家 `P{n}` 域

### 7.3 Return 阶段（锁死）

- 禁止自动合并
- 禁止自动总结
- 返回后遵循 Shared 模式规则

---

## 8. MVP ASSET BASELINE（沿用并固化）

首批资产维持 V2 基线（10 个）：

1. drift:room_basic_7x5x7
2. drift:room_small_5x4x5
3. drift:path_axis_1x1x15
4. drift:path_axis_3x1x15
5. drift:open_field_15x1x15
6. drift:open_field_9x1x9
7. drift:npc_anchor_villager
8. drift:animal_pair_sheep
9. drift:event_marker_pressure_plate
10. drift:event_marker_beacon

每个资产必须在 catalog 中具备：

- resource_id
- bbox
- anchor
- allowed commands（仅白名单）
- 非空 commands

---

## 9. IMPLEMENTATION ORDER（最终）

1. P0：锁模式门控
   - Shared 禁 StoryEngine/AI 回复
   - Personal 允许 StoryEngine

2. P1：锁输入结构
   - 自然语言先落 level.json
   - scene 从 level.json 抽取
   - 仅 scene.json 可进入 `/scene/realize`

3. P2：锁 A1 隔离
   - S/Pn 域划分
   - TP 规则
   - 边界校验阻断越界

4. P3：补齐资产数据
   - drift 10 项资源命令补齐

5. P4：端到端验证
   - Shared -> Personal -> Return 三阶段跑通

---

## 10. DEPLOYMENT CHECKLIST（最终）

1. 三人进入 Shared 正常。
2. Shared 对话不触发 StoryEngine，不触发 AI 回复。
3. 进入 Personal 自动 TP 到对应 `P{n}` 域。
4. `/scene/realize` 仅接受 scene.json。
5. `mode/domain/player_id` 绑定校验生效（shared->S，personal->绑定 P{n}）。
6. `ok|needs_review|blocked` 状态返回完整。
7. needs_review 不执行 build。
8. 域 bbox（x/z ±256, y 0–320）越界会 blocked。
9. 退出 Personal 自动 TP 回 `S` 域。
10. Return 阶段无自动合并、无自动总结。
11. 执行日志可按 player_id/patch_id/mode 追溯。

---

## 11. DO NOT TOUCH LIST

- 不新增架构
- 不引入 world model
- 不扩展 DSL
- 不做 StoryEngine 核心重构
- 不做 IntentEngine 重写
- 不把自然语言直接连到 build 命令

---

## 12. FIRST REAL EXECUTE RUNBOOK（生产执行手册）

首次真实 execute 必须严格按独立手册执行：

- `docs/DRIFT_FIRST_REAL_EXECUTE_RUNBOOK.md`

执行顺序固定为：

1. readiness 检查
2. 1~2 次 dry-run 手动模拟
3. 打开 execute 开关
4. 单次 personal 真实 execute
5. 失败立即回退 dry-run

本版本为 DRIFT_MEMORY_SYSTEM 最终对齐文档。
完成后不继续扩展范围。
