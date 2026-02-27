**PHASE1 Acceptance Criteria & Verification — 单实例验证清单**

目的：在不改变源码的前提下，定义可执行的验证步骤，用于证明 Drift 在单实例下遵守 TRNG Core Contract（见 `TRNG_CORE_CONTRACT_DRIFT.md`）。

1) 单实例验证清单（逐项检验）
- [ ] Snapshot 提取：验证 `extract_minimal_snapshot(players[player_id])` 能产生与运行中 `players[player_id]` 对应的 JSON 且字段完全对齐（`level_id`, `internal_state`, `beat_state`, `pending_nodes`, `pending_patches`, `messages`）。
- [ ] Transaction 构建一致性：对相同 Snapshot + 相同 ExternalResponses（LLM/Quest/Event）重复运行纯计算逻辑应产生相同 `generated_nodes` 与 `generated_patches`。
- [ ] Effect 列表完整性：从 Transaction 派生的 `Effect` 列表中，每项 `payload` 字段均可映射回 Snapshot 的字段集合或 ExternalResponses。
- [ ] Commit 原子性断言（单实例）：在 commit 完成后 `GraphLayer.nodes` 包含 `generated_nodes`（且在 commit 前不包含）。
- [ ] Memory flags 一致性：Transaction 执行后，`graph.memory_snapshots[player_id]` 与 snapshot/tx 中记录的 memory flags 保持一致。
- [ ] Quest 更新一致性：由 `quest_runtime` 产生的补丁在 Effect 执行后被正确合并到返回给客户端的 patch 中。
- [ ] Exhibit 保存可见性：commit 后展品实例（若生成）在 `story_state_repository` 或相应持久层可查。
- [ ] 日志与可回放：每次 commit 生成的日志包含 `tx_id`, `snapshot_digest`, `external_responses`, `effects_executed`，并能驱动人工回放工具进行重放验证。

2) 行为一致性验证方法
- 回放测试：使用记录的 `snapshot` + `external_responses` 重放纯计算过程，验证 `generated_nodes` 与 `generated_patches` 与历史一致。
- 并发压力（单实例）：在本地多并发请求下运行多次 `apply`，比对日志 `snapshot_digest` 与 `GraphLayer` 结果，验证在无分布式干预情况下行为可重复。

3) Replay 验证方式（步骤）
- 步骤 A：从审计日志中选取某次成功 `tx_id`，取出 `snapshot`, `external_responses`。
- 步骤 B：在隔离环境执行纯计算函数（以 snapshot + external_responses 为输入），生成 `generated_*`。
- 步骤 C：对比 `generated_*` 与历史 `GraphLayer` 中被 commit 的节点与 patch；应一致。

4) invariant 检测方法（自动化断言）
- 为每个 invariant（见 `TRNG_CORE_CONTRACT_DRIFT.md` 的 12 条）实现自动化断言：
  - 对快照字段范围（如 `silence_count >= 0`）写单元断言
  - 对集合包含关系（`completed ⊆ order`）实现检查
  - 在 commit 后断言 `GraphLayer.currentNodeID == nodes.last.id`

5) 回退路径（单实例）
- 若 commit 失败或出现部分 effect 执行：
  - 标记 `tx.status = aborted` 并记录 `executed_effects` 与 `effect_outcomes`。
  - 对于易于撤销的 effect，自动按逆序执行撤销（如对 `player_field_write` 的撤销即重写旧 snapshot）；对于不可撤销 effect（如外部第三方服务），记录并报警人工处理。

6) 验证输出（必须可审计）
- 每次验证步骤须产出一份验证报告，包含：`tx_id`、`snapshot_digest`、`assertion_results`（逐项），`replay_diff`（若有差异），`manual_actions_required`（若有）。

注：以上 Acceptance 文档为 Phase1 单实例验证标准，不涉及分布式或云部署情形。所有步骤要求使用 `TRNG_CORE_CONTRACT_DRIFT.md` 中定义的字段级 schema 作为唯一来源保证一致性。
