```markdown
# TRNG Core Phase1 — VERIFY 验收测试清单

说明：每个场景为可执行的验收步骤说明，包含前置条件、输入、期望输出与失败判定。所有对 Drift 的引用包含代码锚点。

场景列表：V1 正常输入、V2 silence 相变、V3 冷却、V4 abort、V5 replay。

---

Scenario: V1 正常输入
Preconditions:
- Player 已进入关卡且 `committed_state` 与 `graph` 有一致的 last_node（参考 Drift 保存 player state 路径）。
- Drift apply API 可用：[backend/app/api/world_api.py](backend/app/api/world_api.py#L172-L176)
Input Event:
- 发起普通对话事件（say）经 `POST /world/apply` 到 `apply_action`。
Expected Nodes:
- 事务内应生成 1 个或多个 `node`，最终被标记为已提交并且可在审计中找到。
Expected State Changes:
- `committed_state` 的 `last_node_id` 更新为新节点 ID；领域数值（如 tension/silence）按事件 patch 变化。
Expected Graph Change:
- `graph` 追加新节点且 `graph.current_node_id == committed_state.last_node_id`。
Expected world_patch:
- 返回的 `world_patch` 包含合并后的 patch 对象（mc/variables 等）。
Invariant Checks Triggered:
- `verifyBuildInvariants(tx)` 与 `verifyCommitInvariants()` 执行并通过。
Failure Criteria:
- 任一不变量校验抛异常；或 `graph` 与 `committed_state` 不一致；或 API 返回错误状态。

Drift anchors (evidence):
- `apply` API: [backend/app/api/world_api.py](backend/app/api/world_api.py#L172-L176)
- `advance()` node append: [backend/app/core/story/story_engine.py](backend/app/core/story/story_engine.py#L1708-L1720)
- `graph.update_trajectory`: [backend/app/core/story/story_graph.py](backend/app/core/story/story_graph.py#L203-L214)

---

Scenario: V2 silence 相变
Preconditions:
- Player 的 `committed_state.silence_count` 接近阈值（例如 2），graph 与 committed_state 同步。
Input Event:
- 触发一个使 `silence_count` 增加的事件（例如 timeout 或 silence 类型节点），通过 `apply_action` 入口触发。
Expected Nodes:
- 事务内生成触发相变的节点，并在事务末尾包含一个 `phase_entry` 节点。
Expected State Changes:
- `committed_state.phase` 从原相变更为 `escalation`（或指定相）；`committed_state.last_node_id` 更新为 `phase_entry` 的 ID。
Expected Graph Change:
- `graph` 追加包含 `phase_entry` 的节点序列，且 `graph.current_node_id` 对应最新节点。
Expected world_patch:
- world_patch 中包含与相变相关的 mc/variables 或 scene 元数据（若有）。
Invariant Checks Triggered:
- `thresholdCheck(tx)` 在 build 内被触发并将 `tx.phaseChanged` 设为 true；`verifyBuildInvariants` 与 `verifyCommitInvariants` 通过。
Failure Criteria:
- 事务内发生第二次相变导致异常；或 `phase_entry` 未被追加到 graph；或 committed_state.phase 未更新。

Drift anchors (evidence):
- 原型相变逻辑对照：[MissionControllive/View/Model/GameEngine.swift](MissionControllive/View/Model/GameEngine.swift#L376-L384)
- Drift node 写入位置： [backend/app/core/story/story_engine.py](backend/app/core/story/story_engine.py#L1708-L1720)

---

Scenario: V3 冷却
Preconditions:
- Player 处于可以被触发冷却逻辑的状态（cooldown/capacity 值设定）。
Input Event:
- 在短时间内重复触发易导致冷却的事件（例如快速连续 say 或某技能触发），通过 `POST /world/apply`。
Expected Nodes:
- 多次调用产生多个事务，但在冷却约束生效期间后续事务应在 build 阶段被拒绝或产生不同的 world_patch（取决于策略）。
Expected State Changes:
- cooldown 计数/标志变化；若被拒绝则 committed_state 不发生不应有的推进。
Expected Graph Change:
- 仅允许在冷却允许时追加节点；冷却生效时 graph 不应出现不合规追加。
Expected world_patch:
- 若触发被拒绝，返回的 world_patch 显示 cooldown/拒绝信息或为空。
Invariant Checks Triggered:
- `verifyBuildInvariants` 校验 cooldown/inventory 约束。
Failure Criteria:
- 冷却逻辑被绕过导致不应发生的节点追加或资源负数；或不可接受的竞态导致 committed_state 与 graph 不一致。

Drift anchors (evidence):
- `advance()` 入口与 world_state 更新点：[backend/app/core/story/story_engine.py](backend/app/core/story/story_engine.py#L1618-L1626)

---

Scenario: V4 abort
Preconditions:
- 提供一个会触发 build 阶段验证失败的输入（例如 world_patch 含非法操作或超出白名单的变更）。
Input Event:
- 发送导致 `verifyBuildInvariants` 失败的事件到 `apply_action`。
Expected Nodes:
- 事务内生成的 `tx.nodes` 不应被提交到 `graph`；`graph` 保持原样。
Expected State Changes:
- `committed_state` 保持与 `snapshot_before` 一致；任何 `draft_state` 变更被丢弃。
Expected Graph Change:
- `graph` 不发生新增节点；`graph.current_node_id` 保持不变。
Expected world_patch:
- 返回状态应表明操作被 abort（或返回错误），且不要将非法 world_patch 应用到真相。
Invariant Checks Triggered:
- `verifyBuildInvariants` 失败并抛出，导致 `abort(tx, snapshot_before)` 被执行。
Failure Criteria:
- 事务失败后 `graph` 或 `committed_state` 发生变化；或系统记录不充分导致无法审计回滚。

Drift anchors (evidence):
- Drift 合并 pending_patches 与清空逻辑： [backend/app/core/story/story_engine.py](backend/app/core/story/story_engine.py#L1734-L1740)

---

Scenario: V5 replay
Preconditions:
- 可获取某一时刻的 `snapshot_before`（committed_state + graph）与对应的外部响应记录（若有 LLM 输出）。
Input Event:
- 在相同 snapshot 与相同外部响应输入下重复调用 `apply(event)` / `story_engine.advance`。
Expected Nodes:
- 重放结果应产生与原始执行相同的 `nodes` 列表与相同的 `world_patch`（在相同外部响应的前提下）。
Expected State Changes:
- `committed_state` 与原始执行后的状态一致。
Expected Graph Change:
- `graph` 的追加与原始执行一致，`last_node_id` 与 sequence 相同。
Expected world_patch:
- world_patch 与原始执行相同（若外部响应确定性），或在记录外部响应后可作为 replay 输入复现。
Invariant Checks Triggered:
- `verifyBuildInvariants` 与 `verifyCommitInvariants` 在 replay 中通过。
Failure Criteria:
- Replay 与原始执行输出不一致（nodes/state/world_patch 不匹配），且外部响应已被记录但仍无法复现。

Drift anchors (evidence):
- StoryState repository persistence（用于 snapshot）： [backend/app/core/ideal_city/story_state_repository.py](backend/app/core/ideal_city/story_state_repository.py#L1-L20)

```
