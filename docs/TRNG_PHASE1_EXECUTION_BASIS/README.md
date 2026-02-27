# TRNG Phase1 — Execution Basis

Single Source of Truth (SSoT):

本文件夹（docs/TRNG_PHASE1_EXECUTION_BASIS/）内文档为 Phase1 唯一执行依据。
外部文档版本不得直接修改或引用为实现依据。
任何更新必须同步更新本文件夹版本并重新冻结。

Phase1 当前执行 Step: Step1 — 插入事务壳（apply shell + reentrancy + snapshot）

允许修改文件列表:
- docs/TRNG_PHASE1_EXECUTION_BASIS/* (本目录内文档)
- backend/config.py (仅用于添加 feature flag 描述)
- 与 Step1 明确列出的实现文件（在 PR 中声明）

禁止修改文件列表:
- 不得在本阶段修改持久层/分布式存储逻辑
- 不得在本阶段移除或绕过 `apply(event)` 入口
- 禁止在 Phase1 内新增会直接写入 committed_state 的外部模块（除非通过明确 PR 批准）

具体禁区（文件/模块级别）:
- `backend/app/core/story/story_engine.py` 内的 `advance()` 函数主体逻辑（Step1 不得改动）
- `backend/app/core/story/story_graph.py`（Graph 层相关实现）
- `backend/app/core/ideal_city/*`（与故事状态持久化/快照相关的模块）
- 与 `quest_runtime` 相关的模块（任务运行时、任务状态管理）
- `minimap` / `event_manager` 相关模块（UI 视图状态与事件协调器）
- 任何会直接写入 `self.players[player_id]` 的逻辑（除非在 Step2A 明确说明并获批）

当前启用 feature flag:
- `ENABLE_TRNG_CORE_PHASE1 = false` （默认禁用；每个 PR 必须说明如何打开并回退）

LLM 触发策略说明:
- LLM 只在 `build(tx)` 中调用
- 仅在 threshold/关键节点触发（应在 tx 中有明确 predicate 条件）
- LLM 输出必须被记录（input/output/model/temperature/timestamp/tx_id/player_id）
- Replay 不调用 LLM；重放使用已记录的 LLM 输出
- LLM 不参与 invariant 或 commit 判定

当前 minimal invariants 列表（Step4A）:
1. `tx.nodes` 非空（必要时）
2. 节点链连通：每个 `node.from` 指向前一个 `node.id` 或 root
3. `tx.rootFromNode` 与 `committed_state.last_node_id` 对齐

当前抽象的 `committed_state` 字段（Phase1 抽象）:
- 仅抽取并维护：`last_node_id`

每次 PR 必须在描述中引用此 README 并明确本 PR 属于哪个 Step。
