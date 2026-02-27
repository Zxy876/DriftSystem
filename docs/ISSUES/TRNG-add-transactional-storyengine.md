Title: TRNG: Blocker — StoryEngine structure prevents safe cloud multi-instance deployment

Status: Draft

Related: docs/ADR-TRNG-001.md

Owner: @（待认领，可填写老师或自己）

Labels: bug, blocker, research, infra

---

## 待解决的问题（明确且可验证）

- 问题概述：当前 `StoryEngine` 将玩家运行时状态保存在进程内单例（`story_engine`），`advance()` 在一次请求流程中对多处内存与模块（`players` dict、`StoryGraph.trajectory`、`MiniMap`、`quest_runtime` 等）进行就地更新，缺乏事务边界、原子提交与统一事件日志，导致无法安全部署为无 sticky-session 的云端多实例（见 ADR-TRNG-001）。
- 阻塞性质：High — 会导致跨实例状态分叉、非幂等请求副作用、以及在中途异常时的半更新不一致。

## 目标

将 TRNG 风格的“理想事务语义”引入并在仓库内验证：先在单实例上复刻并验证行为一致性（不破坏当前外部行为），再推进到分布式改造。最终目标是具备可审计、可回放、原子推进的 StoryEngine 行为模型。

## 推荐路线（Step 1 — Step 4，明确、可执行）

Step 1 — 定义 TRNG 理想事务语义（文档化）
- 产出：`docs/TRNG/transaction_semantics.md`
- 内容要点：Transaction 定义、`StoryNode` 结构、`draftState` vs `committedState`、`build -> commit` 流程、`PhaseEntryNode` 语义、`thresholdCheck` 与 `violation` 报告、失败时 abort 语义与可检测信号。

Step 2 — 在 `StoryEngine` 单实例环境下复刻事务语义（原型，非破坏性）
- 产出：本地原型实现（可放在 `backend/app/core/story/trng_prototype.py` 或 `docs/TRNG/` 下的可执行示例），要求：
  - 保持对外 API（如 `/world/apply`）兼容或提供开关（feature-flag）以便回归测试；
  - 引入单入口 `apply_event(player_id, event)`，内部使用 `draftState` 构建变更链并在 commit 时一次性写入 `players` 与 `graph`；
  - 在 build 阶段收集 `nodes`、`statePatch`、`phaseChanged` 标志并做 `thresholdCheck`，若失败则 abort（不变更 committed state）；
  - 记录每次 Transaction 的可序列化元数据（txID、timestamp、nodes、patch），用于后续 replay/审计。

Step 3 — 验证与回归
- 产出：测试脚本与用例（`tests/trng/`）：
  - 正常推进场景（文本/移动触发）；
  - LLM 异常/超时降级（fail-open/fallback）场景；
  - 多事件并发快速到达（单实例串行化验证）；
  - Phase 违例与 abort 用例；
  - 重放与幂等性验证（对序列化 tx 重放应能恢复相同 committed state）。

Step 4 — 分布式改造（设计稿）
- 产出：`docs/TRNG/distributed_design.md`（设计草案）包含：
  - 事件采集/append-only log（建议格式化 tx payload），可存于外部持久层（Redis streams / Kafka / DB append）；
  - 协调层选择：乐观合并 vs leader-based serialization；幂等键与重试策略；
  - 迁移步骤：先在单实例通过事件日志启用 replay，再逐步把 commit 写入外部存储并在其他实例读取回放以保持一致。

## Acceptance Criteria（明确可验证）

- Step 1 文档通过 review（定义清晰、示例完整）
- Step 2 原型在本地运行并能被测试套件调用（feature-flag 可切换）
- Step 3 测试覆盖率包含上述场景且通过（回归证明行为一致或记录差异）
- Step 4 提交分布式设计草案并通过初步评审（评估迁移风险/里程碑）

## 可行性与风险点评（审阅后结论）

- Step 1（易，文档化）：可行，短期内完成，无代码风险。
- Step 2（中等）：在单实例内部通过引入 `draftState` 与 `apply_event` 单入口实现可行，需注意与现有模块（quest_runtime、minimap、exhibit repo）的集成点并编写保护/异常处理。建议在原型中通过 feature-flag 隔离。
- Step 3（中等）：测试需要构建若干回归与异常模拟，涉及 LLM 降级模拟（可 mock `deepseek_decide`）与 timer 触发模拟。可行但需较完善测试用例。
- Step 4（较难）：分布式改造依赖外部基础设施（消息/持久化层）与一致性设计决策（leader vs event-sourcing）。可行但工作量与运维成本显著，需评估并分阶段执行。

## 下一步（建议的可执行动作）

1. 认领者批准并开始 Step 1（文档化）——预计 1-2 天。
2. 完成 Step 1 后在本 Issue 更新原型实现计划与里程碑。

---

Files referenced:
- docs/ADR-TRNG-001.md
- backend/app/core/story/story_engine.py
- backend/app/api/world_api.py

请在此 Issue 评论以认领或调整优先级／里程碑。
