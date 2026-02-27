  
 
1. 四类世界要素在 TRNG-Core 里的归属

1) MC 方块结构（Structure）

归属：draftState / committedState 的 topology 子域
	•	在 DriftCore 里，方块结构不是“MC 的 chunk”
	•	而是抽象结构模型（例如：区域-对象-属性 / blueprint / delta-patch）

MC 只执行 world_patch，不当真相源。

Commit 时：
	•	committedState.topology 被更新
	•	同时输出 world_patch 给 MC 执行器

⸻

2) NPC 状态（Actors）

归属：draftState / committedState 的 actors 子域

NPC 的“位置、HP、对话阶段、任务状态、仇恨/信任”等，都是可序列化状态。

MC 里看到的 NPC 只是投影（spawn/move/say…）。

⸻

3) 技能冷却（Cooldown）

归属：draftState / committedState 的 regime/control_state 子域

冷却必须是离散事件驱动的，例如：
	•	tick 事件减少 cooldown
	•	或者每次 apply(event) 时按规则衰减

绝不能依赖“真实时间秒表”，否则不可复现、不可回放。

⸻

4) 资源系统（Economy）

归属：draftState / committedState 的 economy 子域

资源是最标准的因果变量：决定你下一步能不能 build/生成/召唤。

⸻

2. apply(event) 在 Drift 语境到底是什么？

你说得很对：apply(event) 是“世界入口”。

在 Drift（B）里，event 的来源会变成 3 类：
	1.	PlayerIntentEvent（输入框 / 对话框）
	2.	WorldObservationEvent（MC 监听到的事实：破坏方块、受伤、到达坐标、昼夜变化…）
	3.	SystemTickEvent（离散 tick / timeout / cooldown 衰减）

关键是：所有 event 都必须走同一个 apply，否则就会回到 Drift 旧问题（散写、半提交、多实例分叉）。

⸻

3. Transaction 在 Drift 里是什么？

你现在的直觉“Transaction = 预制 apply”可以更精确一点：

Transaction = 一次 event 的“因果结算容器”

它做三件事：
	1.	把 event 接进来（输入）
	2.	在 draftState 上演算（build）
	3.	产出两类结果（commit 输出）：
	•	StatePatch：更新 DriftCore 状态
	•	WorldPatch：投影到 MC 执行

⸻

4. draftState 在 Drift 里到底干什么？

一句话：

draftState 是“可回滚的世界草稿”。

它必须至少覆盖你那四个子域：
	•	topology
	•	actors
	•	economy
	•	regime（含 cooldown）

在 build 阶段你可以做的事（都只写 draft）：
	•	计算本次事件导致的结构变化（抽象）
	•	更新 NPC 状态（抽象）
	•	扣资源、检查资源是否足够
	•	冷却递减/设置
	•	推进 phase / tension / silence（如果你也要）

绝对禁止：
	•	build 阶段直接操作 MC 世界
	•	build 阶段直接写 committedState
	•	build 阶段写“不可撤销外部副作用”（比如真实发放奖励到链上/付费系统/不可逆写库）

⸻

5. thresholdCheck 在 Drift 里最自然是什么？

你之前把它理解成“并发过度/技能冷却”，这很合理，但更通用的定义是：

thresholdCheck = 在 build 中检测“是否发生模式切换/风险升级/相变”

在 Drift 里它可以包括：
	•	silenceCount 达阈值 → 进入 “escalation”
	•	tension 达阈值 → 进入 “crisis”
	•	cooldown 压力过高 → 进入 “overheat”
	•	资源耗尽 → 进入 “survival mode”
	•	NPC 好感降到阈值 → 进入 “hostile phase”

它的核心价值是：把“故事推进”从文本，转成“状态相变”。

⸻

6. invariantCheckBuild / invariantCheckCommit 在 Drift 里对应什么？

Build invariants（构建期）

保证你“草稿推演”是合法的，比如：
	•	world_patch 不包含越界坐标
	•	方块变更量不超过上限（防止一条指令炸图）
	•	资源不会变成负数
	•	cooldown 不会变成负数
	•	actor 的状态迁移合法（不能从 dead → alive 除非明确 revive patch）
	•	GraphLayer chain 连通（from 指向正确）

Commit invariants（提交期）

保证“真相源闭环”，比如：
	•	graph.currentNodeID == graph.nodes.last.id
	•	committedState.lastNodeID == graph.currentNodeID
	•	committedState 与 world_patch 的摘要一致（可选：digest）
	•	不允许 graph/state 半提交

⸻

7. commit / abort 在 Drift 里怎么落地？

Commit（原子提交）

一次提交要同时完成三件事：
	1.	GraphLayer.appendCommitted(tx.nodes)
	2.	committedState = tx.draftState + finalPatch(lastNodeID)
	3.	emit WorldPatch（作为“待执行投影”）

注意：MC 执行器最好当成异步消费者，但它执行失败不能污染 committedState（否则你需要补偿事务）。

Abort（失败回滚）
	•	恢复 graph 与 committedState 快照
	•	丢弃 draft
	•	记录 abort node/日志（可选）

⸻

8. GraphLayer 在 Drift 里是什么？

你说“drift 的历史”，对。

但更关键的是：

GraphLayer = 可审计的因果轨迹（叙事本体）

节点不是长文本也没关系。

节点可以只包含：
	•	event 类型
	•	patch 摘要
	•	phase 变化
	•	关键指标（tension/silence/资源/冷却）
	•	少量 UI 文案

你之所以觉得太空直播“没长文本却有情景”，就是因为：

情景感来自“状态变化 + 反馈回路 + UI 投影”，而不是文学文本。

⸻

9. reentrancy guard 在 Drift 里必须怎么做？

一句话：

同一 player_id 任意时刻只能有一个活跃事务。

否则：
	•	draftState 会互相覆盖
	•	patch 会交错
	•	graph 会断链
	•	你会得到“半提交的不确定世界”

所以你至少需要：
	•	isApplying / per-player lock
	•	串行队列（Actor / 单线程执行器）
	•	或者 event queue（推荐）

⸻
 
0. Phase1 的边界与结论

Phase1 目标

在 Drift 的 StoryEngine 现有语义上，引入 TRNG Core 的“事务化因果结算”框架，使得：
	•	任意输入/监听事件都走 apply(event) 单入口
	•	每次 apply(event) 形成一个 Transaction
	•	Transaction 采用 build(draft) -> commit(atomic) 两阶段
	•	commit 产生 两类输出：
	1.	StatePatch：更新 Drift 的 committedState（真相源）
	2.	WorldPatch：给 MC/执行器的投影（可异步执行）
	•	保证 无半提交、可回滚、可审计、可回放（至少 deterministic replay in single instance）

Phase1 非目标（明确不做）
	•	不做分布式一致性（多实例/无 sticky session）
	•	不做跨会话强持久化改造（可以写日志/快照，但不要求完全接管）
	•	不接入新 AI 服务（沿用现状 deepseek_decide 等，只做边界契约化）
	•	不改变叙事内容（文本不是核心，状态轨迹才是核心）

⸻

1) 核心定义：B 路线的世界观

真相源（Source of Truth）：DriftCore 的 GraphLayer + InternalState（以及必要的业务态子域）
执行投影（Projection）：MC 世界（方块、实体、粒子、UI）只执行 WorldPatch，不当真相源。

换句话说：你在 MC 里看到的“场景”是投影；你在 GraphLayer 里记录的“因果轨迹”才是叙事本体。

⸻

2) 数据模型（Schema）——必须可序列化、可审计

2.1 GraphLayer（叙事真相 / 因果轨迹）

职责：保存所有已提交（committed）的因果节点序列；支持审计与回放。

字段
	•	nodes: List[StoryNode]（append-only）
	•	current_node_id: str | None
	•	version: int（可选：用于未来乐观并发/一致性）

规则
	•	只有 commit 才允许 append nodes
	•	必须满足：current_node_id == nodes[-1].id（若 nodes 非空）

⸻

2.2 StoryNode（一次事务内产生的可见节点）

职责：记录“这次结算发生了什么”，不要求长文本，但必须能审计。

字段（建议最小集）
	•	id: str（UUID）
	•	from: str | None（链路连通性）
	•	kind: Enum：
	•	normal
	•	silence
	•	phase_entry
	•	system（可选：用于内部维护节点）
	•	event_ref: EventRef（指向本次 apply 的输入事件元信息）
	•	text: str（可短：例如“NETWORK DROP / EMERGENCY / BUILD OK”）
	•	state_patch: StatePatch（对 committedState 的差异）
	•	world_patch_digest: str | None（对投影补丁的摘要，用于审计）
	•	meta: dict（可选：阈值触发、违规类型、耗时等）

⸻

2.3 InternalState（世界的“叙事结构状态”）

你在太空直播里看到的 silence/tension/phase/memory_flags/last_node_id 在 Drift 里依然适用，它们是“叙事结构的通用骨架”。

字段
	•	silence_count: int >= 0
	•	tension: int >= 0
	•	phase: str（例：intro|explore|challenge|crisis|escalation|resolution）
	•	memory_flags: Set[str]
	•	last_node_id: str | None

更新方式
	•	只能通过 InternalState.apply(patch) 得到新副本（函数式 / 不就地写）

⸻

2.4 DriftWorldState（领域状态：结构 / NPC / 冷却 / 资源）

这是 Phase1 最关键的一步：把你刚才列的四类要素变成 committedState 的可控子域。

建议把 committedState 扩展为：

CommittedState = InternalState + DomainState

DomainState 子域
	1.	topology（方块结构抽象）
	•	最小：regions / structures / blueprint_index / anchors
	•	允许只存“结构抽象”，不存全量方块
	2.	actors（NPC/实体状态抽象）
	•	actors[npc_id] = {pos, hp, mood, behavior_state, quest_state, tags...}
	3.	regime（控制态 / 冷却 / 超载 / 并发）
	•	cooldowns[skill_id] = int_ticks
	•	heat: int、rate_limit_state（可选）
	4.	economy（资源系统）
	•	inventory[item_id] = int
	•	energy: int、credits: int（可选）

注意：MC 真实方块不等于 topology。topology 是“你承认的结构事实”，MC 只是执行结果。

⸻

2.5 StatePatch（对 committedState 的差异表达）

必须是可组合、可校验**、可审计**的 patch。

建议最小支持：
	•	delta_silence: int
	•	delta_tension: int
	•	set_phase: str | None
	•	add_memory_flags: Set[str]
	•	set_last_node_id: str | None
	•	domain_patch: DomainPatch（关键）
	•	topology_delta
	•	actors_delta
	•	cooldowns_delta
	•	economy_delta

并提供：
	•	is_noop()
	•	apply_to(state) -> new_state

⸻

2.6 WorldPatch（投影到 MC 的补丁）

WorldPatch 只描述“要执行什么”，不描述“真相是什么”。

最小动作白名单（示例）：
	•	blocks: setblock/clear/fill（你之前 Drift 也有 patch executor）
	•	actors: spawn/move/despawn/say/animate
	•	ui: title/actionbar/sound/particle
	•	control: schedule(delay_ticks, action_id)（可选）

并要求：
	•	size_budget（体量上限）
	•	coord_bounds（边界）
	•	deterministic（同输入同输出）

⸻

3) 事件模型（apply(event) 的事件类型）

3.1 StoryEvent（统一入口事件）

所有来源都必须转成 StoryEvent：

A. PlayerIntentEvent（输入框 / 指令 / 对话）
	•	type = SAY | COMMAND | CHOOSE | BUILD_REQUEST
	•	payload：文本/参数/选择 id

B. WorldObservationEvent（MC 监听事实）
	•	type = BLOCK_BREAK | ENTITY_KILL | DAMAGE | ENTER_REGION | TIME_OF_DAY | WEATHER...
	•	payload：坐标、对象 id、数值

C. SystemTickEvent（离散 tick）
	•	type = TICK | TIMEOUT | COOLDOWN_TICK | NETWORK_TICK | EMERGENCY_TICK
	•	payload：tick_count、原因等

要求：每个 event 都有
	•	event_id（幂等键基础，Phase1 可先记录）
	•	player_id
	•	timestamp（可选：用于日志，不用于决定性逻辑）
	•	source（ui/mc/system）

⸻

4) Transaction（一次因果结算容器）

4.1 Transaction 字段
	•	tx_id: str
	•	player_id: str
	•	root_from_node: str | None
	•	snapshot_digest: str（对 committedState 快照做摘要）
	•	event: StoryEvent
	•	draft_state: CommittedState（build 在这里演算）
	•	nodes: List[StoryNode]
	•	world_patches: List[WorldPatch]（或合并为一个）
	•	phase_changed: bool
	•	status: building|ready|committed|aborted
	•	logs: dict（耗时、阈值命中、违规等）

4.2 两阶段执行流程（必须遵守）

apply(event):
  reentrancy_guard()
  snapshot_before = (graph, committed_state, optional_live_state)
  tx = new Transaction(root_from_node = graph.current_node_id,
                       draft_state = committed_state)

  try:
     build_phase(event, tx)
     tx.status = ready
     commit_phase(tx)
     tx.status = committed
  except:
     abort(tx, snapshot_before)
     tx.status = aborted


⸻

5) Build Phase（在 Drift 里做什么）

5.1 build 的产物
	•	生成 tx.nodes（至少 1 个）
	•	生成 tx.draft_state（通过 patch 演算得到）
	•	生成 tx.world_patches（投影补丁）
	•	进行 threshold_check（可能触发相变）
	•	执行 invariant_check_build

5.2 build 的基本纪律
	•	build 期间只能写 tx.draft_state / tx.nodes / tx.world_patches
	•	不允许写 committedState
	•	不允许 append graph
	•	不允许执行不可撤销外部副作用（例如真正写 MC 世界）
	•	build 产出 world_patch，但不执行

⸻

6) thresholdCheck（相变：让“情景”出现的核心）

在 Drift 里它是“叙事结构相变”的唯一入口（和太空直播一致）。

Phase1 建议至少支持三类阈值：
	1.	silence_count >= S → phase = escalation（或 danger）
	2.	tension >= T → phase = crisis
	3.	cooldown_pressure/heat >= H → phase = overheat（可选）

关键约束（复制太空直播）
	•	单事务内最多允许一次 phase 变更
	•	一旦触发 phase 变更，必须在本事务末尾追加 phase_entry 节点
	•	任何二次相变尝试：直接抛错 → abort（Phase1 先严格）

⸻

7) invariantCheckBuild / invariantCheckCommit（最少 12 条）

下面这 16 条是Phase1 推荐清单，你可以要求 Copilot 文档落地时逐条解释并对应 Drift 现状证据点。

7.1 Build invariants（构建期）

B1. tx.nodes 必须非空（每个事件至少产出 1 节点）
B2. tx.nodes[0].from == tx.root_from_node
B3. 链连通：nodes[i].from == nodes[i-1].id
B4. silence 节点必须满足 state_patch.delta_silence > 0
B5. StatePatch.apply(draft) 后 draft_state 必须可序列化（无不可 JSON 的对象）
B6. economy 不允许负数：inventory >= 0, energy >= 0
B7. cooldown 不允许负数：cooldowns[*] >= 0
B8. actor 状态迁移合法：例如 dead -> alive 必须显式 revive patch（否则违规）
B9. topology_delta 不允许越界坐标、不允许超过体量预算
B10. world_patch 只能使用白名单动作（禁止任意命令注入）
B11. 若 phase_changed == true，则事务尾部必须存在 phase_entry 节点
B12. 同事务 phase_changed 不得超过一次

7.2 Commit invariants（提交期）

C1. tx.root_from_node == committed_state.last_node_id（防止状态漂移）
C2. tx.root_from_node == graph.last_node_id（防止 graph 漂移）
C3. commit 后 graph.current_node_id == graph.nodes[-1].id
C4. commit 后 committed_state.last_node_id == graph.current_node_id
C5. commit 必须是原子：不允许 graph 已 append 但 state 未更新（或反之）
C6. abort 事务不得改变 graph/state（快照恢复必须成立）

⸻

8) Commit / Abort 语义（对 Drift 特别关键）

8.1 Commit（原子提交顺序）

必须在一个不可打断的临界区完成：
	1.	final_state_patch.set_last_node_id = tx.nodes.last.id
	2.	graph.append_committed(tx.nodes)
	3.	committed_state = tx.draft_state.apply(final_state_patch)
	4.	verify_commit_invariants()
	5.	emit world_patches（交给执行器；执行失败不回滚 committedState，但要记录执行失败事件/节点）

这里的 “emit” 是投影输出，不是业务真相提交的一部分。

8.2 Abort（回滚）
	•	恢复 (graph_before, committed_before, optional_live_before)
	•	记录 abort 日志（至少 tx_id/event_id/error）
	•	可选：追加 system node 记录 abort（但不能污染 graph 的连通性规则；建议只写日志，Phase1 先不写 node）

⸻

9) Reentrancy guard（单实例必须先做到）

Phase1 的底线之一：
	•	同一 player_id：任意时刻只允许一个 active transaction
	•	apply(event) 必须串行

你可以允许两级 guard：
	1.	执行上下文串行（单线程/actor/队列）
	2.	逻辑 guard：is_applying 或 per-player lock

并规定：如果重入发生，必须返回可观测结果（拒绝/排队/合并），不能产生半提交。

⸻

10) 旧路径安置（你要求的“安置好旧路径和资源”）

Phase1 的迁移必须具备“旧逻辑仍可跑”的退路：

10.1 运行开关（feature flag）
	•	ENABLE_TRNG_CORE_PHASE1 = true|false
	•	false：走现有 story_engine.advance
	•	true：走 TRNG.apply(event)（但仍允许内部调用现有模块作为 external response）

10.2 双轨期间的禁止项
	•	禁止 UI/HTTP 层绕过 apply 直接写 state
	•	禁止在 TRNG 开启时再调用旧逻辑的“就地写 players dict”路径（否则契约失效）
	•	Phase1 允许“读取旧逻辑输出作为 external response”，但必须通过 adapter 变成 patch/effect

⸻

11) 日志与审计（Phase1 必须交付）

每次事务都要落一条审计记录（哪怕 abort）。

11.1 审计日志字段（最小）
	•	tx_id, event_id, player_id, timestamp
	•	root_from_node
	•	snapshot_digest
	•	phase_before -> phase_after
	•	nodes_digest（或 node 列表简化）
	•	world_patch_digest
	•	status = committed|aborted
	•	error（若 aborted）
	•	duration_ms

11.2 回放要求（Phase1 级别）

至少满足：
	•	给定 (snapshot + event + external_responses) 能复算出相同的 (nodes + state_patch + world_patch)

如果 external response（LLM）不稳定，就必须记录它的输出作为 replay 输入。

⸻

12) 验证计划（你录 demo 也能直接用）

Phase1 的验证，不需要“长剧情”，只需要稳定复现“情景感”：

场景 V1：输入驱动
	•	输入框 say/command → tx → graph 增 1+ nodes → committed 更新 → world_patch 输出

场景 V2：监听事件驱动
	•	玩家破坏方块（BLOCK_BREAK event）→ 资源系统变化（economy）→ graph 节点记录 → 投影提示

场景 V3：silence / timeout
	•	连续 timeout → silence_count 累积 → thresholdCheck 触发 escalation → 自动生成 phase_entry node

场景 V4：冷却/超载
	•	快速连续触发技能事件 → cooldown/heat 累积 → thresholdCheck 触发 overheat（可选）→ 限制投影输出体量

场景 V5：abort 回滚
	•	构造一个必失败 world_patch（越界/超预算）→ build invariant fail → abort → graph/state 不变

⸻

13) Drift 与 MissionControllive（太空直播） 
你可以用一句最强的解释：

MissionControllive 是 TRNG 的“可视化实验台”：用 UI + 仪表盘把事务化叙事结构显影出来；Drift 是把同一套结构落到 Minecraft 世界的因果引擎。
太空直播证明：不靠长文本也能有情景，因为情景来自 状态轨迹 + 阈值相变 + 原子提交 + 可审计反馈。

⸻

 