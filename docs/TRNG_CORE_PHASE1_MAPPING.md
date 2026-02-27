## Concept: apply(event)

### Prototype Fact
- File: [MissionControllive/MissionControllive/View/Model/GameEngine.swift](MissionControllive/MissionControllive/View/Model/GameEngine.swift#L176-L186)
- Code:
```
    func apply(event: StoryEvent) {
        if isApplying {
            addToLog("⛔️ 忽略重入事件: \(event.name)")
            return
        }

        isApplying = true
        defer { isApplying = false }
```
- Fact: `apply(event)` 在原型中为单一入口，并使用 `isApplying` 重入保护以拒绝并发执行；在进入时创建了事务快照（graphBefore/stateBefore/liveBefore）。

### Drift Fact
- File: [backend/app/api/world_api.py](backend/app/api/world_api.py#L172-L176)
- Code:
```
def apply_action(inp: ApplyInput):

    player_id = inp.player_id
    act = inp.action.model_dump(exclude_none=True)
```
- Fact: 在 Drift 中，HTTP `POST /world/apply` 的入口位于 `apply_action`，它先处理世界物理更新并在后续调用 `story_engine.advance(player_id, new_state, act)`。

### Gap Statement
- 原型在 `apply(event)` 內實施了 per-player 重入保護與本地事務快照；Drift 的 HTTP 接口將請求規範化並委託到 `story_engine.advance`，但 `apply_action` 本身未展示等價的 per-player 重入保護或在 API 層的事務快照行為。

---

## Concept: build-phase — appendNode 对 draft_state 的变更

### Prototype Fact
- File: [MissionControllive/MissionControllive/View/Model/GameEngine.swift](MissionControllive/MissionControllive/View/Model/GameEngine.swift#L355-L373)
- Code:
```
    private func appendNode(
        kind: StoryNodeKind,
        text: String,
        patch: StatePatch,
        tx: inout Transaction,
        allowPhaseMutation: Bool = true
    ) throws {

        let expectedFrom = tx.nodes.last?.id ?? tx.rootFromNode
        let node = StoryNode(kind: kind, from: expectedFrom, text: text, statePatch: patch)
        tx.nodes.append(node)
        tx.draftState = tx.draftState.applying(node.statePatch)
```
- Fact: 原型的 `appendNode` 仅修改 `tx.nodes` 与 `tx.draftState`（draft），并在 build 阶段内累积变更；未直接写入已提交的 `committedState` 或 graph。

### Drift Fact
- File: [backend/app/core/story/story_engine.py](backend/app/core/story/story_engine.py#L1708-L1720)
- Code:
```
        if primary_node:
            node = primary_node
            try:
                pending_nodes.remove(primary_node)
            except ValueError:
                pass
            p["nodes"].append(primary_node)
```
- Fact: Drift 目前在 `advance()` 执行期间直接向 `self.players[player_id]["nodes"]` 做出原地 append，并同时更新其它玩家状态字段（如 messages、minimap）。

### Gap Statement
- 原型在 build 阶段将节点与 draft_state 的修改限定为事务内缓冲；Drift 在 `advance()` 中执行相应节点的原地追加到全局 player state（`p["nodes"].append`），二者在写时机与隔离性上存在差距。

---

## Concept: commit ordering — append_committed(graph) then state replace

### Prototype Fact
- File: [MissionControllive/MissionControllive/View/Model/GameEngine.swift](MissionControllive/MissionControllive/View/Model/GameEngine.swift#L335-L351)
- Code:
```
    private func commitPhase(tx: inout Transaction, liveDraft: LiveDraft) throws {
        guard tx.rootFromNode == committedState.lastNodeID else {
            throw TRNGEngineError.rootMismatch
        }

        var finalStatePatch = StatePatch.empty
        finalStatePatch.setLastNodeID = tx.nodes.last?.id

        graph.appendCommitted(tx.nodes)
        committedState = tx.draftState.applying(finalStatePatch)
        applyLiveSnapshot(liveDraft)
```
- Fact: 原型在 commit 阶段显式先将节点 append 到 `graph`（appendCommitted），随后以原子顺序用 `tx.draftState` 更新 `committedState`，并随后恢复/应用 liveSnapshot。

### Drift Fact
- File: [backend/app/core/story/story_graph.py](backend/app/core/story/story_graph.py#L203-L214)
- Code:
```
    def update_trajectory(self, player_id: str, level_id: Optional[str], action: str,
                          meta: Optional[Dict[str, Any]] = None) -> None:
        """Append a trajectory entry for a player's storyline."""

        if not player_id:
            return
```
- File: [backend/app/core/story/story_engine.py](backend/app/core/story/story_engine.py#L1708-L1716)
- Code:
```
            p["nodes"].append(primary_node)
            p["messages"].append(
                {
```
- Fact: Drift 的 graph 层提供 `update_trajectory` 用于记录轨迹，但当前 `advance()` 中对玩家节点与状态的写是通过直接修改 `self.players[player_id]`（例如 `p["nodes"].append`）完成，而不是通过单点的 `append_committed` 与随后原子替换 `committedState` 的顺序。

### Gap Statement
- 原型在 commit 时保证 "graph.append_committed(nodes) 然后 committedState 替换" 的原子顺序；Drift 将轨迹/节点写入与状态更新分散为对 `self.players` 的直接修改，缺乏对应的单点原子 commit 顺序。

---

## Concept: thresholdCheck / phase change

### Prototype Fact
- File: [MissionControllive/MissionControllive/View/Model/GameEngine.swift](MissionControllive/MissionControllive/View/Model/GameEngine.swift#L376-L384)
- Code:
```
    private func thresholdCheck(tx: inout Transaction) throws {
        if tx.draftState.silenceCount >= 3, tx.draftState.phase != .escalation {
            if tx.phaseChanged { throw TRNGEngineError.phaseChangedMoreThanOnce }
            tx.phaseChanged = true
            let patch = StatePatch(deltaSilence: 0, deltaTension: 1, setPhase: .escalation, addMemoryFlags: ["phase_escalation"], setLastNodeID: nil)
            tx.draftState = tx.draftState.applying(patch)
            return
        }
```
- Fact: 原型在 build 过程中基于 `tx.draftState` 的数值（如 `silenceCount`、`tension`）决定相变，并在事务内部将 `tx.phaseChanged` 标记且把相变作为 `draftState` 的变更纳入事务。

### Drift Fact
- File: [backend/app/core/story/story_engine.py](backend/app/core/story/story_engine.py#L1708-L1742)
- Code:
```
            p["nodes"].append(primary_node)
            p["messages"].append(
                {
                    "role": "assistant",
                    "content": f"{primary_node.get('title', '')}\n{primary_node.get('text', '')}".strip(),
                }
            )
```
- Fact: Drift 在 `advance()` 中基于 AI 结果与 beat 结果直接生成并合并 `world_patch` 与节点到 `p`（player state），并在合并 `pending_patches` 后置空 `p["pending_patches"]`；没有在代码中看到将相变检测与 `draftState` 内部原子处理绑定到事务性的 draft/commit 流程的等效实现。

### Gap Statement
- 原型将相变检测与 `tx.draftState` 的变更限定在事务內（单次事务内最多一次相变）；Drift 将节点与 patch 原地合并到 player state，未展示相同的事务內相变计量与限制控制点。

---

## Concept: reentrancy guard (per-player)

### Prototype Fact
- File: [MissionControllive/MissionControllive/View/Model/GameEngine.swift](MissionControllive/MissionControllive/View/Model/GameEngine.swift#L172-L187)
- Code:
```
    private var isApplying: Bool = false

    func apply(event: StoryEvent) {
        if isApplying {
            addToLog("⛔️ 忽略重入事件: \(event.name)")
            return
        }

        isApplying = true
        defer { isApplying = false }
```
- Fact: 原型使用 `isApplying` 作为重入保护，在 `apply` 入口拒绝重入并在退出时重置标志。

### Drift Fact
- File: [backend/app/api/world_api.py](backend/app/api/world_api.py#L172-L176)
- Code:
```
def apply_action(inp: ApplyInput):

    player_id = inp.player_id
    act = inp.action.model_dump(exclude_none=True)
```
- File: [backend/app/core/story/story_engine.py](backend/app/core/story/story_engine.py#L1-L12)
- Code:
```
class StoryEngine:
    def __init__(self):
        # 每个玩家的剧情状态
        self.players: Dict[str, Dict[str, Any]] = {}
```
- Fact: Drift 的 API 层负责接收并规范化请求后调用 `story_engine.advance`；`StoryEngine` 使用 `self.players` 管理玩家状态；当前代码路径中未见 API 层或 `StoryEngine` 内明确定义的 per-player `isApplying` 重入拒绝标志的实现。

### Gap Statement
- 原型在 `apply` 内置简单且明确的重入拒绝；Drift 的 `apply_action` + `StoryEngine` 代码未显示等价的 API 层重入拒绝或显式 per-player 临界区实现。
