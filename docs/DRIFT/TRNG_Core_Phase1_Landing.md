 
⸻

📘 DRIFT TRNG-Core Phase1 合同规范

（单实例事务语义重构）

版本：v1.0
阶段：Phase1（单实例 / 不涉及分布式 / 不上云）
状态：设计冻结，等待文档落地

⸻

一、Phase1 的硬边界（必须遵守）

1.1 本阶段目标

在 Drift StoryEngine 内引入 TRNG 事务语义，使系统满足：
	1.	所有世界变化必须经 apply(event) 单入口。
	2.	每次 apply 必须生成一个 Transaction。
	3.	Transaction 必须遵循：
	•	build（仅演算，不写真相）
	•	commit（原子提交）
	•	abort（完整回滚）
	⸻

	📘 DRIFT TRNG-Core Phase1 工程落地说明

	（单实例事务语义重构 — 工程版）

	版本：v1.0
	阶段：Phase1（单实例 / 不涉及分布式 / 不上云）
	状态：设计冻结，进入文档化落地

	⸻

	一、Phase1 硬边界（必须遵守）

	目标（必须实现）
	- 在 Drift StoryEngine 内实现单实例事务化语义：
	  1) 所有世界变化必须经 `apply(event)` 单入口；
	  2) 每次 `apply` 必须生成并执行一个 `Transaction`；
	  3) `Transaction` 遵循三阶段：`build`（仅演算）→ `commit`（原子提交）→ `abort`（完整回滚）；
	  4) `commit` 完成后：
	     - 将节点追加到 `GraphLayer`；
	     - 把 `committedState` 替换为 `draftState`；
	     - 允许 `world_patch` 被 emit（作为投影）。

	禁止项（本阶段不做）
	- 不做分布式一致性改造；不改存储/云部署；不引入新 AI；不允许 UI/HTTP 绕过 `apply(event)` 写入真相状态。

	⸻

	二、合同级术语与数据模型（工程定义）

	2.1 `apply(event)`（定义）
	- 单一世界入口；所有来源（UI / MC 监听 / 系统 tick）必须被规范化为 `StoryEvent` 并进入此路径；`apply` 必须串行化处理单一 `player_id` 的事务。

	2.2 `StoryEvent`（最小 schema）
	```
	class StoryEvent:
	    event_id: str
	    player_id: str
	    type: str  # 枚举或字符串
	    payload: dict
	    source: str  # ui|mc|system
	    timestamp: int
	```

	2.3 `Transaction`（最小 schema）
	```
	class Transaction:
	    tx_id: str
	    player_id: str
	    root_from_node: Optional[str]
	    snapshot_digest: str

	    event: StoryEvent
	    draft_state: CommittedState  # deep copy
	    nodes: List[StoryNode]
	    world_patches: List[WorldPatch]

	    phase_changed: bool
	    status: str  # building|ready|committed|aborted
	    logs: dict
	```

	2.4 `CommittedState`（真相源 = InternalState + DomainState）
	- InternalState（叙事骨架）：`silence_count`, `tension`, `phase`, `memory_flags`, `last_node_id`。
	- DomainState（领域子域）：`topology`, `actors`, `regime`（cooldowns/heat）, `economy`。

	说明：`InternalState` 必须通过 `apply(patch)` 生成新副本（函数式），避免就地修改。

	⸻

	三、事务执行流程（工程步骤，必须不可变）

	流程（伪代码）
	```
	reentrancy_guard(player_id)

	snapshot_before = capture(graph, committed_state, optional_live)

	tx = Transaction(root_from_node=graph.current_node_id, draft_state=committed_state.clone(), event=evt)

	try:
	    build_phase(tx)
	    tx.status = "ready"
	    commit_phase(tx)
	    tx.status = "committed"
	except Exception as e:
	    abort(tx, snapshot_before, error=e)
	    tx.status = "aborted"
	finally:
	    release_reentrancy(player_id)
	```

	关键性质：`build` 期间仅修改 `tx.draft_state`、`tx.nodes`、`tx.world_patches`；所有外部副作用（包括对 `GraphLayer` 的写和 `world_patch` 的发出）必须在 `commit` 成功后执行。

	⸻

	四、Build 阶段（合同化约束）

	允许：修改 `tx.draft_state`、生成 `tx.nodes`、生成 `tx.world_patches`、执行 `thresholdCheck`、执行 `verifyBuildInvariants`。

	禁止：写 `committedState`、写 `GraphLayer`、执行 `world_patch`、执行不可回滚外部 IO。

	实现须点：
	- `append_node(kind,text,patch,tx,allow_phase_mutation)` 在 build 内部只对 `tx` 操作；当需要 phase 变更，设置 `tx.phase_changed` 并通过 `tx.draft_state = tx.draft_state.apply(patch)` 写入。

	⸻

	五、`thresholdCheck`（相变机制）

	定义：在 build 期间基于 `draft_state` 度量（如 `silence_count`、`tension`、`heat`）决定是否发生相变（phase 切换）。

	约束：
	- 单事务最多一次相变；若相变发生，应在事务尾部追加 `phase_entry` 节点；二次相变直接抛错导致 abort。

	参数（Phase1 建议默认）：`S = 3 (silence)`, `T = 5 (tension)`，可配置。

	⸻

	六、不变量（工程清单，必须实现并在对应阶段校验）

	6.1 Build 不变量（至少实现以下项并在 `verifyBuildInvariants(tx)` 中断言）
	1. `tx.nodes` 非空；
	2. 链连通：`nodes[i].from == nodes[i-1].id`；
	3. silence 节点：`state_patch.delta_silence > 0`；
	4. 经济系统不为负：`inventory >= 0`；
	5. cooldowns >= 0；
	6. topology delta 不越界；
	7. world_patch 动作在白名单内；
	8. 单事务内 `phase_changed` ≤ 1；
	9. `draft_state` 可序列化（JSON safe）；
	10. actor 状态迁移合法（如 dead→alive 需显式 revive）；
	11. heat 不超过上限；
	12. `last_node_id` 不被提前篡改。

	6.2 Commit 不变量（在 `verifyCommitInvariants()` 中断言）
	1. `tx.root_from_node == committed_state.last_node_id`；
	2. `tx.root_from_node == graph.current_node_id`；
	3. append 后 `graph.current_node_id == nodes[-1].id`；
	4. `committed_state.last_node_id == graph.current_node_id`；
	5. commit 原子性（不允许 graph 已 append 但 state 未更新，或反之）；
	6. abort 必须能恢复 snapshot。

	⸻

	七、Commit 阶段（严格顺序）

	在临界区（per-player lock）中按顺序执行：
	1. `final_patch.set_last_node_id = tx.nodes[-1].id`；
	2. `graph.append_committed(tx.nodes)`（可为 StoryGraph 新增 `append_committed(nodes)` 接口）；
	3. `committed_state = tx.draft_state.apply(final_patch)`；
	4. `verifyCommitInvariants()`；
	5. `emit world_patches`（异步交给 MC 执行器；执行失败不回滚 `committed_state`，但必须记录失败）。

	说明：`emit` 为投影动作，非真相写入；若投影执行失败，记录并上报，但不影响已提交的真相。

	⸻

	八、Abort（回滚）语义

	在 abort 路径中必须：
	- 恢复 `graph`、`committed_state`（使用 `snapshot_before`）；
	- 丢弃 `tx`（`draft_state`、`nodes`、`world_patches`）；
	- 记录审计日志与错误上下文（至少 `tx_id,event_id,player_id,error`）。

	不要求恢复：已 emit 的 `world_patch` 与任何外部 IO；对外必须保证真相不被半提交破坏。

	⸻

	九、GraphLayer（叙事真相层）

	职责：保存所有已提交节点（append-only），提供审计/回放能力。

	最小 API（Phase1）：
	```
	class StoryGraph:
	    def append_committed(self, player_id: str, nodes: List[StoryNode]) -> None: ...
	    def current_node_id(self) -> Optional[str]: ...
	```

	现状与落地：Drift 目前已有 `StoryGraph.update_trajectory` 与 `trajectory` 存储（见 `backend/app/core/story/story_graph.py`）；Phase1 建议增加 `append_committed` 或在 StoryEngine 层保证 append 与 state 替换为一个临界区操作。

	⸻

	十、重入保护（Reentrancy Guard）

	要求：同一 `player_id` 在任意时刻只能有一个活跃事务。

	实现建议（Phase1）:
	- 最小：`per-player lock` + `is_applying` 标志；
	- 更优：事件队列/actor 模型（串行执行）；
	- 若检测到重入：选择 `reject`（返回 busy）或 `queue`；绝不可同时执行多个事务导致 `draft_state` 互相覆盖。

	⸻

	十一、旧路径迁移策略（强制）

	新增开关：`ENABLE_TRNG_CORE_PHASE1 = True|False`
	- `False`：使用旧 `advance()` 路径；
	- `True`：强制所有入口走 TRNG.apply（拒绝任何绕过）。

	禁止双轨并存写入；在开关开启时必须禁止旧逻辑直接写 `self.players[player_id]` 的敏感字段（如 `nodes`、`committed_state` 等）。

	⸻

	十二、审计与回放（文档化要求）

	每次事务在 DB/log 中写入审计记录，最小字段：`tx_id, event_id, player_id, root_from_node, snapshot_digest, phase_before, phase_after, status, duration_ms, error`。

	回放要求（Phase1）：在单实例环境下，给定 `(snapshot + event + external_responses)` 能复现相同 `(nodes + state_patch + world_patch)`。

	若外部响应（如 LLM）非确定性，则必须记录其输出作为 replay 输入。

	⸻

	十三、验收场景（必须写入 VERIFY 文档）

	V1 正常输入：`say` → `graph` 增 1+ nodes → `committed_state` 更新 → `world_patch` emit。

	V2 silence 相变：连续 tick → `silence++` → `thresholdCheck` 触发 `escalation` → 事务末尾有 `phase_entry` node。

	V3 冷却限制：快速连续触发技能事件 → cooldown 限制生效，拒绝或限制 world_patch。

	V4 Abort：构造越界/非法 `world_patch` → build 失败 → graph/state 保持不变。

	V5 Replay：相同 snapshot+event+external_responses 在单实例上产生相同输出。

	⸻

	十四、Copilot 交付指令（按你要求的交付物）

	Copilot 必须生成三份文档（只写文档，不写实现代码）：
	- `docs/TRNG_CORE_PHASE1_MAPPING.md` — MAPPING：事实（含 MissionControllive 与 Drift 源码行号证据）与差距清单；
	- `docs/TRNG_CORE_PHASE1_SPEC.md` — SPEC：本合同级规范与工程实现要点（本文件即为工程版 SPEC）；
	- `docs/TRNG_CORE_PHASE1_VERIFY.md` — VERIFY：验收测试清单与步骤（按上节验收场景展开）；

	规则：MAPPING 只写事实与证据；SPEC 写合同；VERIFY 写可执行验收步骤；禁止包含实现代码或非必须建议。

	⸻

	结束语

	Phase1 的目标不是创作长文本，而是为 Drift 建立可原子提交、可回放、可审计的因果系统。实现后，Drift 将具备明确的事务语义、回滚能力与审计链路，从而为后续多实例/分布式阶段奠定基础。
	•	使用旧 advance()

