**TRNG Core Contract for Drift — 字段级契约

此文档基于从 MissionControllive TRNG（已读取文件）抽象出的核心语义，并映射到 Drift 当前可观测结构（`story_engine` / `story_graph` / `story_state*`）。以下为字段级 schema、事件映射、事务/Effect 结构与不变量（>=12）。

1) Snapshot（最小快照：从 `players[player_id]` 提取）
- `snapshot_id: string` — 运行时唯一标识（建议从 player_id + timestamp 派生）
- `player_id: string` — 玩家标识
- `level_id: string|null` — 当前关卡标识（`p["level"].level_id`）
- `internal_state`:
  - `silence_count: int`
  - `tension: int`
  - `phase: string`（如 `intro/challenge/...`）
  - `memory_flags: List[string]`
  - `last_node_id: string|null`
- `beat_state`:
  - `order: List[string]`
  - `index: int`
  - `completed: List[string]`
  - `memory_locked: List[string]`
- `pending_nodes: List[Node]` — 本次事务内生成但未提交的节点快照
- `pending_patches: List[Patch]` — 本次事务内产生的世界补丁
- `messages: List[Message]` — 对话历史快照（本次事务视图）

（注：以上字段直接对应 `players[player_id]` 的最小子集，用于构成可序列化 Transaction.snapshot）

2) StoryEvent（从 `world.apply`/`advance` 映射）
- `WorldAction`（来自 API）
  - `type`: `move | say | trigger | system`
  - `payload`: `{x,y,z}` 或 `{say: string}` 等
- `DecisionResponse`（来自 LLM）
  - `option: Optional[str]`
  - `node: Node`（单个节点）
  - `world_patch: Patch`
- `QuestUpdate`（来自 quest_runtime）
  - `nodes: List[Node]`、`world_patch: Patch`、`summary` 等

3) ExternalResponses（边界上可视为“外部响应”）
- `LLMResponse` = `DecisionResponse`
- `QuestResponse` = `QuestUpdate`
- `EventEvalResponse` = `List[event_id]`（来自 event_manager.evaluate）

4) Transaction（字段级结构）
- `tx_id: string`
- `player_id: string`
- `snapshot: Snapshot`（按上文定义）
- `generated_nodes: List[Node]` — 在 transaction 中计算出的 nodes
- `generated_patches: List[Patch]` — 在 transaction 中计算出的 patches
- `external_responses: { llm?: LLMResponse, quest?: QuestResponse, events?: EventEvalResponse }` — 保存决策时点的外部返回以便可回溯
- `status: string` — `building | ready | committed | aborted`
- `meta: { created_at, actor, reason }`

5) Effect（字段级 schema）
- `Effect` 是在 commit 点需被顺序执行的副作用描述，每个 effect 包含：
  - `kind: string`（`graph_append|graph_memory|minimap_pos|minimap_unlock|quest_update|event_register|event_unregister|exhibit_save|player_field_write`）
  - `target: string`（例如 `player_id` 或 `graph`）
  - `payload: Dict`（effect-specific）
  - `idempotent: bool`

6) 不变量（>=12 条，均可在单实例验证下检测）
1. `snapshot.player_id` 与 `tx.player_id` 恒等。
2. `snapshot.internal_state.silence_count >= 0`。
3. `snapshot.beat_state.index` ∈ [0, len(snapshot.beat_state.order)]。
4. `snapshot.beat_state.completed` ⊆ `snapshot.beat_state.order`。
5. `generated_nodes` 中每个 `node.statePatch.isNoop == false` 时应对应对 `internal_state` 的非空变更。
6. 在 commit 之前，`GraphLayer.nodes` 不包含 `generated_nodes`（commit 原子性断言）。
7. commit 后 `GraphLayer.currentNodeID == GraphLayer.nodes.last.id`。
8. `external_responses`（LLM/Quest）在 Transaction 内被记录以支持可复现性：相同输入与相同 external_responses 应产生相同 `generated_nodes`/`generated_patches`。
9. `Effect.kind == player_field_write` 的 `payload` 仅包含 snapshot 可表示的字段列表（见 Snapshot 定义）。
10. `Effect` 列表中的非幂等 effect 在 commit 前必须按定义顺序执行或由回滚路径保证可撤销。
11. `snapshot.internal_state.memory_flags` 的变更应映射到 `graph.memory_snapshots` 的一致视图（单实例下可直接校验）。
12. `tx.status` 在 commit 成功时转为 `committed`；在失败时转为 `aborted` 并且不应对 `GraphLayer.nodes` 做出写入。

7) 事务执行（文本流程）
- 1) 提取 `snapshot = extract_minimal_snapshot(players[player_id])`
- 2) 创建 `tx` 并执行纯计算：`(generated_nodes, generated_patches, external_calls)`（纯函数，依赖 `external_responses`）
- 3) 将外部请求发出并收集 `external_responses` （LLM/quest/event eval），并把 `external_responses` 作为 `tx` 的一部分记录
- 4) 将纯计算结果转为 `Effect` 列表（按上文 `Effect.kind` 分类）
- 5) Commit：以定义顺序执行 `Effect`（本地 player_field_write 与 graph/minimap/quest/event/exhibit 写入）并在所有 effect 成功后将 `tx.status=committed`
- 6) 若任一 effect 失败：尝试按照 `Effect` 的 `idempotent` 与回滚设计撤销已执行 effect，并将 `tx.status=aborted`；在单实例 Phase1 下，必须提供完整检测与人工回退说明
