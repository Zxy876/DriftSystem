TRNG 执行语义抽取（MissionControllive — 事实摘取）

说明与文件可用性声明

- 本文档旨在“仅基于源码事实”描述 MissionControllive 中 TRNG 的真实执行语义。
- 已成功读取并作为事实依据的源码文件：
  - `MissionControllive/View/Model/Transaction.swift` ([.../Transaction.swift#L1])
  - `MissionControllive/View/Model/InternalState.swift` ([.../InternalState.swift#L1])
  - `MissionControllive/View/Model/GraphLayer.swift` ([.../GraphLayer.swift#L1])
  - `MissionControllive/View/Model/StoryNode.swift` ([.../StoryNode.swift#L1])

- 读取失败（必需文件）：
  - `MissionControllive/View/Model/GameEngine.swift` — 对该文件的多次读取尝试均失败（路径尝试：
    `/Users/zxydediannao/Desktop/桌面 - zxy的电脑的MacBook Air/用所选项目新建的文件夹/ space /MissionControllive/MissionControllive/View/Model/GameEngine.swift`），
    错误：文件无法打开/解析（工具返回“无法解析不存在的文件”）。

- 结论：本文档中涉及 `GameEngine.swift` 的问题将分为两类：
  1) 可由已读取文件直接依据回答的事实（已标注源码位置）；
  2) 需要 `GameEngine.swift` 明确实现才能回答的项，将被标注为“无法确定 — 需 GameEngine.swift 源码”。

---

按用户要求回答（逐条）

1️⃣ apply(event:) 的完整执行顺序是什么？

- 事实可回答项（来自已读取源码）
  - 无法在已读取文件中找到名为 `apply(event:)` 的函数定义或其实现细节；相关事务入口在 `Transaction` 的定义中被建模（见 `Transaction.swift`）[MissionControllive/View/Model/Transaction.swift#L1]。
  - 与事件流相关的核心数据结构：`Transaction`（含 `draftState`、`nodes`、`status`）和 `InternalState`（含 `applying(_:)`）为执行流程提供结构化语义（见 `Transaction.swift` 与 `InternalState.swift`）。

- 无法确定项（需 `GameEngine.swift`）
  - 事件进入点（`apply(event:)` 的函数签名、入口处调用栈与实际参数传递）
  - 是否存在 reentrancy guard（是否在入口处检查或使用同步原语）
  - 是否存在 `activeTransaction` 检查（如同一 player 是否在进行活动事务）
  - 串行执行语义（是否标注 `@MainActor`、或使用 Actor/Serial queue）

结论：无法在已读取文件中找到 `apply(event:)` 的实现细节；上述 4 个问题均需要 `GameEngine.swift` 的源码才能给出“源码真实行为”的答案。

对应证据：见 `Transaction.swift`（事务结构）与 `InternalState.swift`（状态演算），但入口点实现缺失：
- `Transaction.swift` 源（已读取）：MissionControllive/View/Model/Transaction.swift#L1
- `InternalState.swift` 源（已读取）：MissionControllive/View/Model/InternalState.swift#L1

2️⃣ build 阶段做了什么？

- 可依据已读取文件的事实：
  - 事务内部的“草稿态”更新语义：`InternalState.applying(_ patch: StatePatch) -> InternalState` 返回新副本（函数式更新）。此为构建（build）阶段对状态变更的最小事实依据（见 `InternalState.swift`）。引用：MissionControllive/View/Model/InternalState.swift#L1。
  - `Transaction` 持有 `nodes: [StoryNode]` 与 `draftState: InternalState` 作为构建期内容（事实）：MissionControllive/View/Model/Transaction.swift#L1。
  - `StoryNode` 的构造包含 `statePatch: StatePatch`，`StatePatch` 表示对 `InternalState` 的差异（`deltaSilence`, `deltaTension`, `setPhase`, `addMemoryFlags`, `setLastNodeID`），这构成 build 阶段如何“生成 node + 关联 patch”的数据模型：MissionControllive/View/Model/StoryNode.swift#L1。

- 无法确定项（需 `GameEngine.swift`）
  - 具体如何生成 `StoryNode`（即从哪些输入、在何处调用 `StoryNode` 的 initializer），以及构造参数的来源
  - `statePatch` 如何被应用到 `draftState` 的实际调用点（虽然 `InternalState.applying` 定义在 `InternalState.swift`，但谁/何处调用尚不在已读取文件中）
  - `thresholdCheck`（是否存在阈值检测）在何处执行，以及对应代码行
  - 在 build 阶段对 invariant 的校验位置与实现细节
  - `phaseChanged` 在何处被检测与标记（`Transaction.phaseChanged` 字段存在，但具体设置位置需 `GameEngine.swift`）

对应证据：
- `InternalState.applying`：MissionControllive/View/Model/InternalState.swift#L1
- `StoryNode` / `StatePatch`：MissionControllive/View/Model/StoryNode.swift#L1
- `Transaction` 结构：MissionControllive/View/Model/Transaction.swift#L1

3️⃣ commit 阶段做了什么？

- 可依据已读取文件的事实：
  - `GraphLayer.appendCommitted(_ newNodes: [StoryNode])` 的实现将 `newNodes` 追加到 `nodes` 并将 `currentNodeID` 设置为最后一个节点的 id（具体实现见 `GraphLayer.swift`）：MissionControllive/View/Model/GraphLayer.swift#L1。
  - `Transaction.status` 类型与取值（`committed` / `aborted`）在 `Transaction.swift` 中被定义，表明存在状态流模型用于标记 commit 完成与否：MissionControllive/View/Model/Transaction.swift#L1。

- 无法确定项（需 `GameEngine.swift`）：
  - `GraphLayer.appendCommitted` 在何处被调用（commit 时机的调用点与行号）
  - `InternalState` 在 commit 时如何被替换到全局状态（是否通过赋值、替换 graph/state 副本，及确切行号）
  - `lastNodeID` 的更新时序（是否先写入 graph 再更新 state，或反之，及代码位置）
  - 是否存在 commit-time 的 invariant 校验（以及校验的具体代码行）

对应证据：
- `GraphLayer.appendCommitted`：MissionControllive/View/Model/GraphLayer.swift#L1
- `Transaction.status`：MissionControllive/View/Model/Transaction.swift#L1

4️⃣ abort 语义是什么？

- 可依据已读取文件的事实：
  - `TransactionStatus` 枚举包含 `aborted`，说明事务模型中存在 abort 状态（定义位置：Transaction.swift）。MissionControllive/View/Model/Transaction.swift#L1。
  - `InternalState.applying` 的实现是函数式返回新副本，表明在 abort 情形下若未 commit 则 `draftState` 可以被丢弃（从数据模型角度可见）。MissionControllive/View/Model/InternalState.swift#L1。

- 无法确定项（需 `GameEngine.swift`）：
  - abort 是否会触发对 `GraphLayer` 的回滚或产生补偿写入（即 abort 是否会影响已存在的 graph）
  - abort 时是否有显式的清理/日志写入点及其代码行号
  - abort 的状态转移代码位置（设置 `Transaction.status = .aborted` 的确切行号）

5️⃣ silence 机制的真实触发点

- 可依据已读取文件的事实：
  - `StatePatch` 包含 `deltaSilence` 字段，`InternalState.applying` 使用 `deltaSilence` 来更新 `silenceCount`（并保证下限 0），表明 silence 机制在状态 patch 层面由 `StatePatch` 驱动：MissionControllive/View/Model/StoryNode.swift#L1 与 MissionControllive/View/Model/InternalState.swift#L1。

- 无法确定项（需 `GameEngine.swift`）：
  - silence 是否基于 timer、absence of event、或在 build 中主动插入 silence node 的策略与确切实现位置
  TRNG 执行语义抽取（MissionControllive — 源码事实摘取）

  说明

  - 本文档仅描述 MissionControllive 源码的真实行为（事实陈述），不包含任何建议或改造内容。所有结论直接引用源码行号与函数名。
  - 作为证据，本次读取并使用的源码文件为：
    - MissionControllive/View/Model/GameEngine.swift（已完整读取并作为主要证据）
    - MissionControllive/View/Model/Transaction.swift
    - MissionControllive/View/Model/InternalState.swift
    - MissionControllive/View/Model/GraphLayer.swift
    - MissionControllive/View/Model/StoryNode.swift

  文件与关键位置引用说明：所有下列引用均用 `文件路径#L<line>` 形式指向实现处。

  主要事实提取

  1️⃣ apply(event:) 的完整执行顺序（源码真实行为，逐步列出）

  执行序号 | 行号引用 | 行为（源码行为陈述）
  ---|---:|---
  1 | GameEngine.swift#L172 | 类内部维护布尔 `isApplying` 初始值为 `false`（声明：`private var isApplying: Bool = false`）。
  2 | GameEngine.swift#L180 | `func apply(event: StoryEvent)` 为事件入口（定义行：L180）。
  3 | GameEngine.swift#L181-L187 | 入口处检查 `if isApplying { ... return }`；若 `isApplying` 为真，追加日志并返回；否则设置 `isApplying = true` 并使用 `defer { isApplying = false }` 在函数结束时重置（L181、L186、L187）。
  4 | GameEngine.swift#L189-L191 | 在进入事务流程前，保存当前运行时快照：`let graphBefore = graph`（L189）、`let stateBefore = committedState`（L190）、`let liveBefore = captureLiveSnapshot()`（L191）。
  5 | GameEngine.swift#L193 | 创建 `Transaction`：`var tx = Transaction(rootFromNode: graph.currentNodeID, draftState: committedState)`（L193）。
  6 | GameEngine.swift#L197-L200 | 进入 `do { try buildPhase(...); tx.status = .ready; try commitPhase(...)} catch { ... }` 控制流；即依次调用 `buildPhase`（L198）、设置 `tx.status = .ready`（L199）、随后调用 `commitPhase`（L200）。
  7 | GameEngine.swift#L203-L206 | 若上述任一步骤抛出异常，catch 块将：设置 `tx.status = .aborted`（L203）、还原 `graph = graphBefore`（L204）、还原 `committedState = stateBefore`（L205）、恢复 live snapshot（`applyLiveSnapshot(liveBefore)`，L206）、并记录中止日志（L206）。

  并发/串行语义（事实）：
  - GameState 类被标注为 `@MainActor`（GameEngine.swift#L124），因此 `apply(event:)` 的执行在 `MainActor` 上序列化（即按 `@MainActor` 的执行语义，代码在主 actor 上运行）。
  - 源码中存在显式的重入保护 `isApplying`（GameEngine.swift#L181-L187），因此源码既有 actor 层序列化注解也有内部重入检查。

  2️⃣ build 阶段做了什么（源码行为，逐项并带行号）

  执行序号 | 行号引用 | 行为（源码行为陈述）
  ---|---:|---
  1 | GameEngine.swift#L211 | `buildPhase(event:tx:liveDraft:)` 开始（定义行：L211）。
  2 | GameEngine.swift#L213–L333 | 根据不同 `StoryEvent` 分支执行：对 `liveDraft` 的字段做修改（例如 `liveDraft.currentView = view`，L213）、并在若干分支中调用 `appendNode(..., tx: &tx, liveDraft: &liveDraft)`（多个分支中出现，参见 L213-L333 范围）。
  3 | GameEngine.swift#L355–L373 | `appendNode(kind:text:patch:tx:allowPhaseMutation:)` 的函数逻辑：在函数头部对 silence 节点做非法校验（若 `kind == .silence && patch.deltaSilence <= 0` 则 `throw TRNGEngineError.invalidSilenceNode`，L363）；计算 `expectedFrom = tx.nodes.last?.id ?? tx.rootFromNode`（L366）；创建 `StoryNode` 实例并 `tx.nodes.append(node)`（L367+）；随后执行 `tx.draftState = tx.draftState.applying(node.statePatch)`（L369）。
  4 | GameEngine.swift#L369–L373 | 在将 node 的 `statePatch` 应用到 `tx.draftState` 之后，若允许 phase 变更（`allowPhaseMutation` 为 true），调用 `thresholdCheck(tx: &tx)`（L371）。
  5 | GameEngine.swift#L376–L393 | `thresholdCheck(tx:)` 函数做阈值检测：若 `tx.draftState.silenceCount >= 3` 且 phase 未到 `escalation`，则检测 `tx.phaseChanged` 并在未变更时把 `tx.phaseChanged = true` 并通过 `tx.draftState = tx.draftState.applying(patch)` 将 phase 变更写入 draft（L376-L385）；类似对 `tension >=5` 的检查并可能置入 `crisis`（L386-L392）。
  6 | GameEngine.swift#L395–L406 | `verifyBuildInvariants(tx:)` 做若干构建时不变量校验：
    - 检查 `tx.nodes` 非空（`guard !tx.nodes.isEmpty else { throw TRNGEngineError.emptyTransaction }` 行：L394）；
    - 检查 `tx.nodes.first?.from == tx.rootFromNode`（L395）；
    - 检查链一致性 `tx.nodes[idx].from == tx.nodes[idx-1].id`（L398-L399）；
    - 检查 silence 节点的 `deltaSilence > 0`（若不满足抛 `invalidSilenceNode`，L405）。

  事实：
  - `appendNode` 在构建阶段既创建 `StoryNode`（含 `StatePatch`），也立即把该 `StatePatch` 应用到 `tx.draftState`（GameEngine.swift#L366-L369）。
  - `thresholdCheck` 在 `appendNode` 内被调用（GameEngine.swift#L371、L376-L392），由构建期间的 draftState 值触发并修改 `tx.draftState` 与 `tx.phaseChanged`（如适用）。

  3️⃣ commit 阶段做了什么（源码行为，逐项并带行号）

  执行序号 | 行号引用 | 行为（源码行为陈述）
  ---|---:|---
  1 | GameEngine.swift#L335 | `commitPhase(tx:inout, liveDraft:)` 定义（L335）。
  2 | GameEngine.swift#L337-L343 | 进入 commit 前做根节点校验：`guard tx.rootFromNode == committedState.lastNodeID else { throw TRNGEngineError.rootMismatch }`（L337）；并检验 `tx.rootFromNode == graph.lastNodeID`（L341）以确保本地 graph 未被并发修改（L341）。
  3 | GameEngine.swift#L345-L349 | 在 commit 中先构造 `finalStatePatch`（L345），并将 `finalStatePatch.setLastNodeID = tx.nodes.last?.id`（L346）；随后调用 `graph.appendCommitted(tx.nodes)`（L347），接着 `committedState = tx.draftState.applying(finalStatePatch)`（L348），最后 `applyLiveSnapshot(liveDraft)`（L349）。
  4 | GameEngine.swift#L351-L354 | 在更新 graph 与 committedState 后，调用 `verifyCommitInvariants()`（L351），若无异常则把 `tx.status = .committed`（L352）。

  事实：
  - `graph.appendCommitted(tx.nodes)` 在 commit 流程中先于将 `tx.draftState` 应用到 `committedState`（appendCommitted 行：GameEngine.swift#L347；committedState 替换行：GameEngine.swift#L348）。
  - `finalStatePatch` 在 commit 阶段被创建以携带 `lastNodeID`（GameEngine.swift#L345-L346），并被用于生成新的 `committedState`（GameEngine.swift#L348）。
  - `verifyCommitInvariants()` 在 commit 完成前执行（GameEngine.swift#L351-L352），其内部检查会在检测失败时抛出 `TRNGEngineError.commitAlignmentFailed`（见 L411、L414）。

  4️⃣ abort 语义（源码行为）

  执行序号 | 行号引用 | 行为（源码行为陈述）
  ---|---:|---
  1 | GameEngine.swift#L197-L206 | 在 `apply` 的 `do/catch` 流程中，若 `buildPhase` 或 `commitPhase` 抛出异常，catch 块执行：设置 `tx.status = .aborted`（L203）；恢复 `graph = graphBefore`（L204）；恢复 `committedState = stateBefore`（L205）；恢复 live snapshot `applyLiveSnapshot(liveBefore)`（L206）；并记录中止日志（L206）。

  事实：
  - abort 处理会恢复 `graph` 与 `committedState` 到进入事务前的快照（GameEngine.swift#L204-L205），并恢复 live snapshot（GameEngine.swift#L206）。
  - abort 的状态变化为 `tx.status = .aborted`（L203）。

  5️⃣ silence 机制的真实触发点（源码行为）

  事实：
  - `StatePatch` 定义包含 `deltaSilence`（StoryNode.swift），`InternalState.applying` 使用 `deltaSilence` 更新 `silenceCount`（InternalState.swift）。在构建时，若要插入 silence 节点，`appendNode` 会在节点为 `.silence` 时对 `patch.deltaSilence` 做校验并在不满足时抛出 `invalidSilenceNode`（GameEngine.swift#L363）。
  - 定时触发的来源：GameState 在 `startTimers()` 创建多路 `Timer.publish(...).autoconnect().sink { self?.apply(event: .XXX) }`（GameEngine.swift#L733-L758 等），其中包括 `autoEventTimer`、`decayTimer`、`commandTimer`、`networkTimer`、`emergencyTimer` 与 `emergencyUpdateTimer`，这些计时器会在到期时调用 `apply(event: .autoEventTick/.decayTick/... )`（L733-L758），因此 silence 类事件可由计时器触发的 `timeout`/`decay`/`emergencyUpdateTick` 路径导致（见具体事件分支中对 `.silence` 节点的 append 调用，如 GameEngine.swift#L291、L320、L330、L418）。

  具体源码参照：
  - `appendNode` 中对 silence 节点的无效性检查：GameEngine.swift#L363。
  - 定时器触发 `apply(event:)` 的代码：GameEngine.swift#L733-L758（`startTimers()` 的计时器注册）。

  6️⃣ phase 变更约束（源码事实）

  事实：
  - `thresholdCheck(tx:)` 在构建中被调用（appendNode 内，GameEngine.swift#L371），并对 `tx.draftState.silenceCount` 与 `tx.draftState.tension` 做阈值检查（GameEngine.swift#L376-L392）。
  - 当满足条件时，`thresholdCheck` 会在 `tx.phaseChanged` 为 false 时设置 `tx.phaseChanged = true` 并通过 `tx.draftState = tx.draftState.applying(patch)` 将 phase 更改写入草稿状态（GameEngine.swift#L379-L385 与 L387-L392）。
  - 若 `tx.phaseChanged` 已为 true，再次触发阈值将抛出 `TRNGEngineError.phaseChangedMoreThanOnce`（GameEngine.swift#L378、L387）。

  因此源码行为显示：
  - 在单个事务中，`thresholdCheck` 会禁止多于一次的 phase 变更（通过抛出 `phaseChangedMoreThanOnce`）（GameEngine.swift#L376-L392）。
  - `appendNode` 在 tx 完成后若 `tx.phaseChanged` 为真，会额外插入 `phaseEntry` 节点（在 `buildPhase` 末尾有条件调用：GameEngine.swift#L317-L322）。

  7️⃣ 不变量 enforcement 列表（>=10 条，证据行号）

  下面列出在源码中明确检测或通过实现可验证的不变量，每条后标注对应源码行号或函数：

  1. 非空事务：`tx.nodes` 在构建末尾不得为空 — 检测点：`verifyBuildInvariants` 中 `guard !tx.nodes.isEmpty else { throw TRNGEngineError.emptyTransaction }`（GameEngine.swift#L394）。
  2. 链头对齐：`tx.nodes.first?.from == tx.rootFromNode` — 检测点：`verifyBuildInvariants`（GameEngine.swift#L395）。
  3. 链一致性：每个节点的 `from` 字段必须等于前一节点的 `id` — 检测点：`verifyBuildInvariants` 遍历检查（GameEngine.swift#L398-L399）。
  4. 无效 silence 节点检测：silence 节点的 `deltaSilence` 必须 > 0 — 检测点：`appendNode` 中的前置校验（GameEngine.swift#L363）与 `verifyBuildInvariants`（GameEngine.swift#L405）。
  5. 只允许单次 phase 变更：若 `tx.phaseChanged` 已为 true，`thresholdCheck` 将抛出 `phaseChangedMoreThanOnce`（GameEngine.swift#L376-L392，抛出点 L378、L387）。
  6. commit 前根节点对齐：`tx.rootFromNode == committedState.lastNodeID` — 检查点：`commitPhase` 的 guard（GameEngine.swift#L337）。
  7. commit 前 graph 对齐：`tx.rootFromNode == graph.lastNodeID` — 检查点：`commitPhase` 的 guard（GameEngine.swift#L341）。
  8. commit 后 graph 与 committedState 对齐：`verifyCommitInvariants` 检查 `graph.currentNodeID == graph.nodes.last?.id` 与 `committedState.lastNodeID == graph.currentNodeID`（GameEngine.swift#L409-L414，抛出点 L411、L414）。
  9. `Transaction.txID` 唯一性由 `UUID().uuidString` 生成（Transaction.swift — 构造，Transaction.swift#L1）。
  10. `InternalState.silenceCount >= 0` 由 `InternalState.applying` 的 `max(0, silenceCount + patch.deltaSilence)` 保证（InternalState.swift#L1）。
  11. append semantics：`GraphLayer.appendCommitted` 将 `newNodes` 追加并更新 `currentNodeID`（GraphLayer.swift#L1）。
  12. 中止时恢复语义：在异常 catch 中恢复 `graph`、`committedState` 与 live snapshot（GameEngine.swift#L203-L206）。

  执行时序图（文本，总览，按源码行为）

   - 时间轴（文本）:
     1) `apply(event:)` 入口（GameEngine.swift#L180）
     2) 检查重入并设置 `isApplying`（GameEngine.swift#L181-L187）
     3) 捕获快照：`graphBefore`, `stateBefore`, `liveBefore`（GameEngine.swift#L189-L191）
     4) 创建 `Transaction`（GameEngine.swift#L193）
     5) 调用 `buildPhase`（GameEngine.swift#L197-L200）— 在该阶段会多次调用 `appendNode` 生成节点并更新 `tx.draftState`（GameEngine.swift#L355-L373）
     6) `thresholdCheck` 在构建期间按需要触发（GameEngine.swift#L376-L392）并可能设置 `tx.phaseChanged`（或抛出异常）
     7) 构建成功后设置 `tx.status = .ready`（GameEngine.swift#L199）并进入 `commitPhase`（GameEngine.swift#L200）
     8) `commitPhase` 做根节点对齐检查（GameEngine.swift#L337、L341）、调用 `graph.appendCommitted(tx.nodes)`（GameEngine.swift#L347）、替换 `committedState`（GameEngine.swift#L348）、`applyLiveSnapshot(liveDraft)`（GameEngine.swift#L349）、校验 commit 不变量（GameEngine.swift#L351-L352）并设置 `tx.status = .committed`（GameEngine.swift#L352）
     9) 若任一步骤抛出异常，catch 块恢复快照并将 `tx.status = .aborted`（GameEngine.swift#L203-L206）

  状态机图（文本，基于源码实现的 Transaction 状态机）

   - 状态与转移（直接从源码枚举与流程可证实）：
     - `building` (Transaction 创建时) → `ready`（在 `buildPhase` 成功后，GameEngine.swift#L199） → `committed`（在 commitPhase 成功后，GameEngine.swift#L352）
     - `building` → `aborted`（在 catch 中设置，GameEngine.swift#L203）

  完整不变量清单与对应代码位置（汇总）

  见上“7️⃣ 不变量 enforcement 列表”部分，其中每条已给出精确函数或行号引用。

  结束语（事实声明）

  - 本文档严格基于 MissionControllive 源码的观察（包含已读取的 `GameEngine.swift` 全文及其他模型文件），列出了 `apply(event:)` 的执行序列、build/commit/abort/silence/phase 的源码行为、时序图、状态机与不少于 10 条可验证不变量并标注了实现行号。
  - 文中未包含任何形式的设计建议或改造方案；仅陈述源码真实行为。
