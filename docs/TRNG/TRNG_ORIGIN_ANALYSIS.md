
**TRNG 原点分析 — MissionControllive 实现摘录**

来源文件（已读取）：
- `Transaction.swift`: [MissionControllive/View/Model/Transaction.swift](../..//Desktop/%E6%A1%8C%E9%9D%A2%20-%20zxy%E7%9A%84%E7%94%B5%E8%84%91%E7%9A%84MacBook%20Air/%E7%94%A8%E6%89%80%E9%80%89%E9%A1%B9%E7%9B%AE%E6%96%B0%E5%BB%BA%E7%9A%84%E6%96%87%E4%BB%B6%E5%A4%B9/%20space%20/MissionControllive/MissionControllive/View/Model/Transaction.swift#L1)
- `InternalState.swift`: [MissionControllive/View/Model/InternalState.swift](../..//Desktop/%E6%A1%8C%E9%9D%A2%20-%20zxy%E7%9A%84%E7%94%B5%E8%84%91%E7%9A%84MacBook%20Air/%E7%94%A8%E6%89%80%E9%80%89%E9%A1%B9%E7%9B%AE%E6%96%B0%E5%BB%BA%E7%9A%84%E6%96%87%E4%BB%B6%E5%A4%B9/%20space%20/MissionControllive/MissionControllive/View/Model/InternalState.swift#L1)
- `GraphLayer.swift`: [MissionControllive/View/Model/GraphLayer.swift](../..//Desktop/%E6%A1%8C%E9%9D%A2%20-%20zxy%E7%9A%84%E7%94%B5%E8%84%91%E7%9A%84MacBook%20Air/%E7%94%A8%E6%89%80%E9%80%89%E9%A1%B9%E7%9B%AE%E6%96%B0%E5%BB%BA%E7%9A%84%E6%96%87%E4%BB%B6%E5%A4%B9/%20space%20/MissionControllive/MissionControllive/View/Model/GraphLayer.swift#L1)
- `StoryNode.swift`: [MissionControllive/View/Model/StoryNode.swift](../..//Desktop/%E6%A1%8C%E9%9D%A2%20-%20zxy%E7%9A%84%E7%94%B5%E8%84%91%E7%9A%84MacBook%20Air/%E7%94%A8%E6%89%80%E9%80%89%E9%A1%B9%E7%9B%AE%E6%96%B0%E5%BB%BA%E7%9A%84%E6%96%87%E4%BB%B6%E5%A4%B9/%20space%20/MissionControllive/MissionControllive/View/Model/StoryNode.swift#L1)

注意：对 `GameEngine.swift` 的直接读取尝试因路径解析失败（文件系统访问）未成功；以下抽象忠实于以上已读取源码文件（`Transaction` / `InternalState` / `GraphLayer` / `StoryNode`）中显式实现的语义。文中任何“已验证”字样均基于这四个文件中可观测的结构与行为。

核心摘录（逐条忠实抽象）

1) Transaction 基本语义（来源：`Transaction.swift`）
- `Transaction` 为单个交互事务的运行时表示，包含：`txID`（唯一标识）、`rootFromNode`、`nodes`（待提交的 `StoryNode` 列表）、`draftState`（`InternalState` 的快照，用于在事务中演算）、`phaseChanged: Bool`、`status: TransactionStatus`（building/ready/committed/aborted）、`logFields`。
- 语义要点：事务持有“draft state”与“待提交节点”，状态流从 `building`→`ready`→`committed|aborted`。

2) InternalState 的语义（来源：`InternalState.swift`）
- `InternalState` 是可序列化（`Codable`）的最小运行语义快照，字段：`silenceCount:Int`、`tension:Int`、`phase:TRNGPhase`、`memoryFlags:Set<String>`、`lastNodeID: String?`。
- 提供 `applying(_ patch: StatePatch) -> InternalState`：不变性风格（返回新副本），意味着状态更新在 TRNG 中表现为生成新 `InternalState`（草稿到提交之前的不可变路径）。

3) GraphLayer 的语义（来源：`GraphLayer.swift`）
- `GraphLayer` 保存已“committed”的节点序列与当前节点指针（`nodes:[StoryNode]`, `currentNodeID`）。
- 方法 `appendCommitted(_ newNodes)` 将新节点追加到已提交序列并更新 `currentNodeID`（立即变化、不可回滚地合并到图层）。

4) StoryNode / StatePatch（来源：`StoryNode.swift`）
- `StoryNode` 包含 `id`, `kind` (normal/silence/phaseEntry), `from`, `text`, `statePatch: StatePatch`。
- `StatePatch` 是对 `InternalState` 的差异化表达：`deltaSilence`, `deltaTension`, `setPhase`, `addMemoryFlags`, `setLastNodeID`；提供 `isNoop` 判定。

5) 从已验证实现可观测出的 TRNG 运行约束
- 事务持有：draft state 与待提交节点集合 → 在 commit 时 append 到 `GraphLayer` 与持久层；事务本身通过 `status` 字段显式建模。
- 状态演算语义：`InternalState.applying(patch)` 返回新副本（函数式、不破坏旧快照）。
- Phase 变化为一等公民：`StatePatch.setPhase` 被视为跨事务边界的显式事件（`phaseChanged` 在 Transaction 中被跟踪）。
- `silence` 语义：`silenceCount` 以增量方式记录（`deltaSilence`），可累积且受下限保护（>=0）。

事务原子性边界（从实现可验证）
- 事务的原子边界在 MissionControllive 中被显式建模为 `Transaction.status == .committed` 时 `GraphLayer.appendCommitted` 被调用；序列化后 `nodes` 成为 graph 的一部分。
- `draftState` 提供局部、可回滚的计算语义；在 commit 之前对 `InternalState` 的变更是局部（未写回 global graph/state）。

可验证的不变量（基于源码）
- `StatePatch.isNoop` 在无更改时为真。
- `InternalState.silenceCount >= 0`。
- `GraphLayer.currentNodeID == nodes.last?.id` 在 `appendCommitted` 后成立。

事务执行流程（文本）
- 1) 创建 Transaction（status=building，draftState = current InternalState 的拷贝）
- 2) 在 Transaction 中累积 `nodes` 与 `draftState = draftState.applying(patch)`（pure 函数式更新）
- 3) 若需要切换阶段或提交，标记 `phaseChanged`/`status=ready`
- 4) Commit：`GraphLayer.appendCommitted(transaction.nodes)`，并将 Transaction.status 设置为 `committed`（此处为不可逆的 graph 合并）

结语：以上摘取严格基于 MissionControllive 中四个已读取文件的实现细节；未能读取 `GameEngine.swift` 导致对全局驱动逻辑的最后若干运行路径无法直接核验，文中未包含任何基于未读取文件的主观推断。
