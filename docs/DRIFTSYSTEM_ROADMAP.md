# DriftSystem 开发路线图（v0.5 → v0.8）

> 更新时间：2026-03-07
> 目标：在 P1–P5 引擎与运行时工具完成的基础上，推进可玩 AI 叙事沙盒（P6–P8）。

## 1) 当前里程碑（P1–P5 已完成）

### 已完成阶段

- P1：Safe Ground Anchor
- P2：Inventory Canonical Mapping
- P3：NPC Behavior RuleEvents
- P4：Level Evolution Runtime（skeleton）
- P5：World Runtime Tools（Live Runtime Tooling）

### 当前闭环链路

`Minecraft Event → RuleEventBridge → TRNG → Quest Runtime → Level Evolution → Scene Generator → World Patch`

### P5 Runtime Tools（最终集合）

- Debug Tools：`/taskdebug`、`/worldstate`、`/leveldebug`、`/eventdebug`
- Runtime Control：`/spawnfragment`、`/storyreset`

---

## 2) P5 最终验收记录（2026-03-07）

### 服务可用性

- backend `:8000` 监听正常
- Paper `:25565` 监听正常

### 功能验收

- `/world/story/{player}/reset`：`200 ok`，返回 `Story runtime reset completed`
- `/world/story/{player}/spawnfragment`：
  - `fragment_count = 3`
  - `event_count = 3`
  - `world_patch = True`
  - 片段：`camp`、`fire`、`cooking_area`
- `/world/state/{player}`：`ok`
- `/world/story/{player}/debug/tasks`：`ok`

### 结论

P5 正式完成并收口，系统具备完整的 **观察 + 控制 + 复位 + 片段生成** 运行时能力。

---

## 3) 后续蓝图（P6–P8）

### P6-A：Scene Library（先做）

目标：先建立可组合的场景素材库，作为 AI 推理输入与输出空间。

首批建议片段：

- `camp`
- `forge`
- `market`
- `farm`
- `shrine`
- `watchtower`
- `village`

说明：没有 scene library，AI 无法稳定进行场景拼贴与推理。

### P6-B：Resource Semantics（资源语义层）

目标：把原始物品映射到语义标签，支持可解释推理。

当前基线（2026-03-07）：

- 已落地 `semantic_tags.json`（资源 -> 语义标签映射）
- 已落地 `semantic_scoring.json`（fragment 语义权重与打分参数）
- root fragment 由 `priority + semantic_score` 共同决策，保持 deterministic 输出

执行顺序（冻结）：

- P6-B-1：评分明细可解释化（`/eventdebug` 可见 `selected_root/candidate_scores/selected_children/blocked/reasons`）
- P6-B-2：稳定三组 deterministic 分支（camp/forge/village）
- P6-C：诗歌入口原型（仅在 P6-B-1/2 稳定后开启）

P6-B Runtime Verification（2026-03-07）：

- Probe 链路：`/story/inject -> /story/load/{player}/{level} -> /world/story/{player}/debug/tasks`
- Probe 场景：
  - `wood + light + food -> camp`
  - `metal + stone + fire -> forge`
  - `food + trade -> village`
- 运行态结果：
  - roots 三轮稳定：`camp/camp/camp`、`forge/forge/forge`、`village/village/village`
  - `/eventdebug` 同源字段可见：`selected_root` / `candidate_scores` / `selected_children` / `blocked` / `reasons`
  - 分支可分化：三组输入对应三条不同 root
- 证据文件：`logs/runtime_probe/p6b_runtime_probe_1772844803.json`
- 结论：**P6-B 已达到 runtime verified，可封板。**

示例映射：

- `oak_log/spruce_log/birch_log -> wood`
- `torch/lantern -> light`
- `raw_porkchop/beef -> food`

示例推理：

- `wood + light -> camp`
- `food + fire -> cooking_area`
- `stone + iron -> forge`

### P7：Scene Composition（场景拼贴层）

目标：从单片段生成升级为 `scene graph` 组合生成。

示例：

- `camp -> fire -> cooking_area -> watchtower`
- `village -> market -> forge -> farm -> shrine`

输出：稳定、可回放、可执行的 `event_plan/world_patch`。

P7.1 Layout Stabilization（2026-03-07）：

- 范围约束：**先不做 depth-2 graph expansion**，优先稳定 `layout_engine`
- 已实现：`radial_v1 + minimum distance` 防碰撞布局（避免节点重叠）
- 配置项：`DRIFT_LAYOUT_MIN_GAP`（默认 `2`，兼容 `MIN_LAYOUT_GAP`）
- 行为目标：保持 deterministic，同时保证 `scene_graph -> layout -> event_plan(offset)` 可解释
- 回归结果：
  - `python3 -m pytest tests/test_layout_engine.py tests/test_scene_assembler.py tests/test_story_scene_inject_phase7_m2.py -q` -> `34 passed`
  - `python3 tools/p6b_runtime_probe.py --runs 3` -> `overall_pass=True`
- 证据文件：`logs/runtime_probe/p6b_runtime_probe_1772857725.json`

P7.2 Scene Evolution（2026-03-07）：

- 目标：引入 `SceneState + SceneDiff + EvolutionRule`，支持 `rule-event -> 增量扩图 -> 增量 world_patch`。
- 已实现：
  - 新增：`scene_state.py`、`scene_diff.py`、`scene_state_store.py`、`evolution_rules.py`、`scene_evolution.py`。
  - 新增规则：`evolution_rules.json`（v1 范围）
    - `camp: collect:wood -> watchtower`、`collect:stone -> road`
    - `village: collect:food -> farm`、`collect:metal -> forge`
  - `layout_engine.place_new_nodes` 复用最小间距布局，保证增量节点 deterministic 且无重叠。
  - `story/inject` 记录并持久化 `scene_state`，`scene_generation` 包含 `scene_state/scene_diff/incremental_event_plan`。
  - `story/rule-event` 接入演化流程并合并增量 `world_patch`，响应可回传 `scene_diff`。
  - `story/reset` 清理 `scene_state` 持久化，并回传 `cleared_scene_state`。
  - `/eventdebug` 可见 `scene_generation.scene_state` 与 `scene_generation.scene_diff`。
- 回归结果：
  - `python3 -m pytest -q tests/test_layout_engine.py tests/test_scene_assembler.py tests/test_story_scene_inject_phase7_m2.py tests/test_scene_evolution_phase7_p2.py` -> `39 passed`
  - `python3 tools/p6b_runtime_probe.py --runs 3` -> `overall_pass=True`
- 证据文件：`logs/runtime_probe/p6b_runtime_probe_1772860724.json`
- 结论：**P7.2 v1（Scene Evolution）已正式封板，可作为 P8 依赖层。**

### P8：Narrative Engine（叙事引擎）

目标：从任务点推进升级为叙事图推进（Narrative Graph）。

示例路径：

`forest -> camp -> village -> market -> kingdom`

输出：`quest_chain + level_state + narrative_transition` 联动更新。

P8-A Narrative Graph Skeleton（2026-03-07）：

- 本步定位：**只读骨架 + 可观测性**，不做自动推进。
- 已实现：
  - 新增 `narrative_state` 数据结构：`current_arc/current_node/unlocked_nodes/completed_nodes/transition_candidates/blocked_by`。
  - 新增规则文件：`backend/app/content/story/narrative_graph.json`。
  - 新增只读 evaluator：基于 `scene_state + level_state + recent_rule_events` 计算 `transition_candidates`。
  - 接入可观测：`/world/state` 与 `/eventdebug` 均返回
    - `narrative_state`
    - `current_node`
    - `transition_candidates`
    - `blocked_by`
- 约束保证：
  - **不自动推进 story node**
  - **不把 narrative transition 直接耦合到 world_patch**
  - 输出保持 deterministic（同输入同判定）
- 验证结果：
  - `python3 -m pytest -q tests/test_narrative_graph_skeleton_p8a.py` -> `4 passed`
  - `python3 -m pytest -q tests/test_layout_engine.py tests/test_scene_assembler.py tests/test_story_scene_inject_phase7_m2.py tests/test_scene_evolution_phase7_p2.py` -> `39 passed`
  - `python3 tools/p6b_runtime_probe.py --runs 3` -> `overall_pass=True`
- 证据文件：`logs/runtime_probe/p6b_runtime_probe_1772865583.json`

---

## 4) 推荐开发顺序（执行版）

1. P6-A Scene Library
2. P6-B Resource Semantics
3. P7 Scene Composition
4. P8 Narrative Engine

---

## 5) 下一迭代（P8-B）最小交付定义

### 最小目标

- 在 P8-A 只读骨架基础上，增加**受控**节点推进（显式触发，不自动跳转）
- 引入 `narrative_transition` 事件记录（审计可追踪）
- 将 `quest_chain + level_state + narrative_state` 的映射规则固化为可测试策略层
- 保持 `scene_state` 与 `narrative_state` 解耦，禁止跨层隐式写入

### 验收标准

- `deterministic`：同输入稳定得到同 `transition_candidates`
- `observable`：`/worldstate` 与 `/eventdebug` 持续可见 narrative 关键字段
- `non-intrusive`：无自动推进、无 world_patch 直接耦合（除非进入后续明确阶段）
- `regression-safe`：P7.2 回归与 runtime probe 持续通过

---

## 6) 回归基线（持续保持）

每轮迭代必须保留以下稳定性验证：

- 事件入口：`collect` / `npc_talk` / `npc_trigger`
- 运行态观测：`/taskdebug` / `/worldstate` / `/eventdebug`
- 控制能力：`/spawnfragment` / `/storyreset`
