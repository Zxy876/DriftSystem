📘 TRNG Core — Phase1 工程合同规范

版本: v1.0
范围: 单实例环境，局部改造，非分布式，非存储层改造。

概述
- 本文为 Phase1 的工程合同，明确定义实现必须遵守的语义、不变量与执行序列。所有条款以 MUST / MUST NOT / SHOULD 语义表达。

一、硬边界
- MUST: 本阶段仅在单实例进程内实现事务语义，不得对分布式或外部存储层做改造。
- MUST NOT: 在本阶段引入新的 AI 模块或允许 UI/HTTP 跳过 `apply(event)` 而直接修改真相状态。

二、术语
- `apply(event)`: 世界变化的唯一入口。
- `StoryEvent`: 标准化的事件载体。
- `Transaction` (`tx`): 每次 `apply` 产生的事务容器，包含 `draft_state`, `nodes`, `world_patches`, `status` 等字段。
- `committedState`: 真相状态，等于 `InternalState + DomainState`。

三、数据模型（最小要求）
- MUST: `Transaction` 包含 `tx_id, player_id, root_from_node, snapshot_digest, event, draft_state, nodes, world_patches, phase_changed, status, logs`。
- MUST: `CommittedState` 分为 `InternalState`（例: `silence_count,tension,phase,memory_flags,last_node_id`）与 `DomainState`（例: `topology,actors,regime,economy`）。
- MUST: `InternalState` 的更新通过纯函数式 `apply(patch)` 产生新副本，避免就地修改 committedState 对象。

四、执行流程（不可变序列）
- MUST: `apply(event)` 在进入时必须建立 `snapshot_before = capture(graph, committed_state, optional_live)` 并构建 `Transaction` 的初始 `draft_state` 为 `committed_state.clone()`。
- MUST: `apply` 的执行序列为：`build(tx)` → 若成功则 `commit(tx)`；若 `build` 或 `commit` 抛异常则走 `abort(tx, snapshot_before)`。
- MUST: `build` 阶段仅得修改 `tx.draft_state`, `tx.nodes`, `tx.world_patches`；不得写 `committedState`、不得写 `GraphLayer`、不得执行外部不可回滚 IO。
- MUST: `commit` 必须在临界区内按顺序执行：
  1) 设置 `final_patch.last_node_id = tx.nodes[-1].id`；
  2) `graph.append_committed(tx.nodes)`；
  3) `committed_state = tx.draft_state.apply(final_patch)`；
  4) `verifyCommitInvariants()`；
  5) `emit world_patches`（emit 为投影动作，非真相写入）。
- MUST: `abort` 必须恢复 `graph` 与 `committed_state` 到 `snapshot_before`，并记录审计日志；对已 emit 的投影或外部 IO 不做回滚。

五、不变量（必须校验）
- Build 阶段 MUST 校验（`verifyBuildInvariants(tx)`）：
  - `tx.nodes` 非空；
  - 链连通性：`nodes[i].from == nodes[i-1].id`；
  - 单事务内 `phase_changed` ≤ 1；
  - `draft_state` 可序列化；
  - 经济与冷却相关数值 >= 0；
  - `world_patch` 操作在白名单内；
  - `last_node_id` 未被提前篡改。
- Commit 阶段 MUST 校验（`verifyCommitInvariants()`）：
  - `tx.root_from_node == committed_state.last_node_id`；
  - `tx.root_from_node == graph.current_node_id`；
  - append 后 `graph.current_node_id == tx.nodes[-1].id`；
  - `committed_state.last_node_id == graph.current_node_id`；
  - commit 必须具有原子性；

六、相变（threshold）约束
- MUST: 在 `build` 期间基于 `tx.draft_state` 的指标进行相变判断（如 `silence_count`, `tension`），且单事务内最多一次相变。
- MUST: 若相变发生，必须在事务末尾追加 `phase_entry` 节点并将 `tx.phase_changed` 标记为 true。
- MUST NOT: 允许在同一事务内发生二次相变。

七、GraphLayer 最小 API 要求
- MUST: 提供 `append_committed(player_id, nodes)` 或在 StoryEngine 层以临界区保证 "append nodes + state replace" 为一个原子操作。
- MUST: GraphLayer 保持 append-only 语义并支持审计/回放。

八、重入保护
- MUST: 对同一 `player_id` 实施单线程/单事务执行策略（最小实现为 per-player lock 或 `is_applying` 标志）。
- MUST: 在检测到并发尝试时返回 busy 或将事件入队，绝不可并发执行多个事务导致 `draft_state` 覆盖。

九、旧路径迁移策略
- MUST: 引入开关 `ENABLE_TRNG_CORE_PHASE1 = True|False`。
- MUST: 当开关为 `True` 时，所有写入真相的路径必须走 TRNG apply 流程；禁止旧逻辑直接修改 `self.players[player_id]` 的敏感字段（如 `nodes`, `committed_state`）。

十、审计与回放
- MUST: 每次事务写入审计记录，包含至少 `tx_id,event_id,player_id,root_from_node,snapshot_digest,phase_before,phase_after,status,duration_ms,error`。
- SHOULD: 为非确定性外部响应（例如 LLM 输出）记录响应内容并将其作为 replay 的输入参数。

十一、验收交付物
- MUST: 提供 MAPPING（源码事实 + 行号证据）、SPEC（本合同）与 VERIFY（验收用例）三份文档，并在代码审计时提供对应代码锚点、证明差距已被覆盖。
