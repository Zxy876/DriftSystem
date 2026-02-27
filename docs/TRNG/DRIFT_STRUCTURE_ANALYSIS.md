**DRIFT 结构分析（针对 StoryEngine 的现状）**

引用（已读取并作为证据来源）：
- `backend/app/core/story/story_engine.py` (主要分析段，参见运行时 `advance` 行为)：[backend/app/core/story/story_engine.py](backend/app/core/story/story_engine.py#L1600-L2448)
- `backend/app/core/story/story_graph.py`（图与 trajectory/ memory 写入）：[backend/app/core/story/story_graph.py](backend/app/core/story/story_graph.py#L1-L400)
- `backend/app/core/ideal_city/story_state.py`（story state model）：[backend/app/core/ideal_city/story_state.py](backend/app/core/ideal_city/story_state.py#L1-L200)
- `backend/app/core/ideal_city/story_state_repository.py`（持久化接口）：[backend/app/core/ideal_city/story_state_repository.py](backend/app/core/ideal_city/story_state_repository.py#L1-L200)
- `backend/app/api/world_api.py`（外层调用链）：[backend/app/api/world_api.py](backend/app/api/world_api.py#L1-L120)

当前状态拓扑（文本图）

1) API 层
- `world_api.apply` 负责：世界物理更新（`WorldEngine.apply`）、意图解析（`parse_intent`）、并最终调用 `story_engine.advance(player_id, world_state, action)`（或在被触发情况下调用 `load_level_for_player`）。

2) StoryEngine（进程内单体）
- 主状态容器：`self.players`（按 `player_id` 的字典），每个 `player_state` 包含 `level`, `tree_state`, `beat_state`, `messages`, `nodes`, `pending_nodes`, `pending_patches`, `story_prebuffer`, `emotional_profile`, `choice_registry` 等。
- 决策路径：`advance()` 一次性执行读入（`p = self.players[player_id]`）、AI 调用（`deepseek_decide`）、beat 处理（`_process_beat_progress`、`_activate_beat`、`_queue_beat_update`）、合并 patch（`_merge_patch`）并在函数末尾调用 `_capture_exhibit_instance`。

3) 支撑组件（内存/外部）
- `self.graph` (`StoryGraph`)：维护 `trajectory` 与 memory flags，提供 `update_trajectory`, `update_memory_flags` 等写操作。
- `self.minimap`：位置与解锁标记写入（`update_player_pos`, `mark_unlocked`）。
- `quest_runtime`：任务系统（`check_completion`, `load_level_tasks`, `issue_tasks_on_beat`, `record_event` 等）。
- `event_manager`：事件注册/评估/注销。
- `exhibit` 存储：`_capture_exhibit_instance` 进行持久化/保存。

标注 — 无事务边界区域
- `advance()` 内对 `p`（`players[player_id]`）的散布写入：`p["messages"].append(...)`, `p["nodes"].append(...)`, `p["pending_patches"] = []`, `p["ended"] = True`, `p["last_time"]`, `p["beat_state"]` 的集合 add/discard、`choice_registry` 更新等。
- 这些写入没有单一的 draft/commit 隔离层；一旦执行便修改运行内存状态。

标注 — 半更新风险区域
- 在 `advance()` 中多处对 `p` 的字段进行部分更新后抛出异常或调用外部系统（例如 AI 调用抛出异常被 `fail-open` 或捕获处理），可能留下部分可见更新（如消息已 append，但 pending_patches 尚未写回）。
- `quest_runtime.check_completion` 返回值会触发 `apply_quest_updates`，该路径中对 `p` 的 `pending_nodes`/`pending_patches` 的部分写入存在中间态风险。

标注 — 外部副作用区域
- `graph.update_trajectory(...)` / `graph.update_memory_flags(...)` — 写入 `story_graph.trajectory` 与 `memory_snapshots`。
- `minimap.update_player_pos` / `minimap.mark_unlocked` — 外部可视化/地图状态写入。
- `quest_runtime.*` / `event_manager.*` / `_capture_exhibit_instance()` — 持久化或全局任务/事件系统写入。

可纯化核心区域（从代码可抽象出纯计算的部分）
- `_merge_patch(primary, secondary)` — 纯值合并函数（无副作用）。
- 决策合成：把 `beat_result` 与 `ai_result`、`quest_updates` 合成为最终 `option, node, patch` 的计算逻辑，本质为对输入的纯函数式组合（在不执行外部 I/O 的情况下可被抽象为纯函数）。

单实例语义问题总结
- StoryEngine 当前在同一函数调用内混合“读取→外部同步调用→就地写回内存→再读”的行为，缺乏明确的事务/草稿隔离层。结果包括：
  - 半更新可见性（当中间步骤失败或外部依赖异常）
  - 外部副作用在决策路径中即时执行，增加不确定性与回滚困难
  - `players[player_id]` 的字段数量与用途广泛（从展示性历史到 gating 集合），缺少统一的“快照/变更集” schema 导致难以在单实例内进行可验证的原子更新

证据快照（示例行号）
- `advance` 主路径读取/写入示例：[backend/app/core/story/story_engine.py#L1600-L2448](backend/app/core/story/story_engine.py#L1600-L2448)（内含 `messages.append`, `nodes.append`, `pending_patches` 操作、对 `quest_runtime` 与 `graph` 的调用）。
- `StoryGraph.update_trajectory` 与 `update_memory_flags`：[backend/app/core/story/story_graph.py#L1-L400](backend/app/core/story/story_graph.py#L1-L400)