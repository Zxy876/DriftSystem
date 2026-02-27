**DRIFT Adapter Plan (Phase1) — 文档化适配设计（仅单实例语义）

目标：在不改动核心业务代码前提下，定义文档化的适配点与运行时约束，供后续按合同实现。所有位置均基于已读取源码引用。

引用证据：
- `backend/app/api/world_api.py`：入口处 `apply` -> `story_engine.advance` 调用（见 world apply 路径）[backend/app/api/world_api.py](backend/app/api/world_api.py#L1-L120)
- `backend/app/core/story/story_engine.py`：`advance()` 主路径及相关 helper（读写 `players[player_id]`）[backend/app/core/story/story_engine.py](backend/app/core/story/story_engine.py#L1600-L2448)

Adapter 插入位置（文档描述，不实际修改）
- 在 `world_api.apply` 的调用链中间：在调用 `story_engine.advance(player_id, world_state, action)` 之前提取 Snapshot（见 TRNG_CORE_CONTRACT_DRIFT.md 的 Snapshot 定义），并在 advance 返回之前把计算出的 Transaction.effects 收集为回写队列。该位置作为“Adapter 层”的逻辑包裹点（advance 包裹）。
- 备选插入：`story_engine.advance` 内部入口处（函数开始时）提取 snapshot 并在函数结束前做 effects 执行与状态签署；两者在文档中需明确差异点以便实现者选择。

feature-flag 设计（描述）
- 运行时特性开关名：`ENABLE_TRNG_ADAPTER_PHASE1`（布尔）
- 开关行为：关闭时行为与现状一致；开启时在 `world_api` 路径中启用 Snapshot 提取 -> Transaction 构建 -> Effects 顺序执行与回滚钩子（文档层面说明，不含代码）

Snapshot 提取位置
- 建议提取点：在 `world_api.apply` 中、在 `story_engine.get_runtime_mode` 与 `world_engine.apply` 之后、`story_engine.advance` 之前。
- 提取内容：参见 `TRNG_CORE_CONTRACT_DRIFT.md` 中的 Snapshot 字段集合（`level_id, internal_state, beat_state, pending_nodes, pending_patches, messages` 等）。

Effect 执行顺序（文档约定）
- 顺序（必须严格遵守）：
  1. `player_field_write`（将 snapshot 中的 field 更改反映到 `players[player_id]` 的内存）
  2. `graph_memory`（`graph.update_memory_flags`）
  3. `graph_append`（如需要将节点追加至 `GraphLayer`）
  4. `minimap_pos` / `minimap_unlock`
  5. `quest_update`（`quest_runtime` 的状态变更）
  6. `event_register` / `event_unregister`
  7. `exhibit_save`（持久化展品实例）
- 说明：以上顺序在单实例语义下可保证内存可见性；所有非幂等 effect 在 commit 前应被记录以便回滚时使用。

回滚策略（文档形式）
- 回滚触发条件：任何 effect 在执行时抛出异常或返回错误。
- 回滚步骤（文档化）：
  1. 停止执行剩余 effect
  2. 对已执行 effect，按逆序尝试撤销：若 effect 标记为 `idempotent=true`，则跳过或重复执行相应撤销操作；否 则记录失败并标记为需人工回退。
  3. 将 Transaction 标记为 `aborted` 并把 `external_responses` 与 partial effects 写入审计日志。
- 人工回退说明：应记录 `tx_id`, `player_id`, `executed_effects`, `error` 以便人工介入，并提供 `manual_replay` 指令集以重放或补偿变更（文档化需包含所需字段）。

日志设计（审计可回放）
- 日志条目最小字段：`tx_id`, `player_id`, `timestamp`, `snapshot_digest`, `external_responses`, `effects_executed`, `effect_outcomes`。
- Snapshot_digest 应为 snapshot 的可哈希摘要（例如 JSON Canonical + SHA256），用于回放时验证快照一致性。

注：以上内容为文档化适配计划（Phase1 单实例语义），仅描述 adapter 的职责、位置与行为约定，不涉及具体代码改动。实现时需按照 `TRNG_CORE_CONTRACT_DRIFT.md` 的字段级 schema 严格校验。
