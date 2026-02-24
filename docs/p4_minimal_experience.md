# P4 最小体验脚本（Soul Lantern / Chest / Clarification）

## 目标
- 验证 CreationWorkflow 在 P4 阶段的“可解释、可审计、可回滚”能力。
- 采用最小可用脚本覆盖三条典型路径：放置灵魂灯、投放箱子、澄清流程。
- 确认在冻结阶段不触发自动落地，仅返回审计友好的计划与日志证据。

## 前置条件
- 后端运行在 P4 调试模式：`DRIFT_P4_DEBUG_MODE=1`。
- Minecraft 服务器可选（脚本不依赖自动执行）。
- 已启用 `start_all.sh`，确认 `backend.log` 可写。

## 流程 A：灵魂灯请求
1. 玩家输入：“在我面前放一个灵魂灯”。
2. 预期响应：
   - `creation_result.status == "validated"`，`auto_execute == False`。
   - `creation_result.plan.semantic_candidates` 列出至少一个“soul_lantern”候选。
   - `creation_result.debug_observability.blocked_reason == "auto_execute_disabled"` 或 `"manual_review_required"`。
3. 预期日志：
   - `creation_intent_classified`、`creation_forced_by_p4_rule`（命中 P4 关键字时）。
   - `creation_semantic_candidates_collected`。
   - `creation_p4_debug_snapshot` 记录 `blocked_reason` 与候选数量。
4. 回滚确认：`creation_result.plan.patch_templates` 仅提供指令草稿，不直接执行。

## 流程 B：箱子投放
1. 玩家输入：“帮我放一个箱子当作临时仓库”。
2. 预期响应：
   - `creation_result.status == "validated"`。
   - 语义候选包含 `minecraft:chest` 或近似资源。
   - `creation_result.debug_observability.blocked_reason == "manual_review_required"`。
3. 预期日志同流程 A。
4. 审计要点：确认 `semantic_candidates` 与 `notes` 解释材料出处。

## 流程 C：澄清连锁
1. 玩家输入模糊请求：“帮我设计个灯光装饰？”
2. 预期响应：
   - 若分类为非创建，`creation_result` 为空，故事线请求继续。
   - 在 P4 调试模式下，`backend.log` 仍会出现 `creation_p4_debug_snapshot`，`blocked_reason == "plan_missing"` 或 `"auto_execute_gate"`。
3. 玩家补充：“就在我脚下放一个灵魂灯，坐标和刚才一样”。重复流程 A 验证。

## 明确不做
- 不启用自动落地或硬路径执行。
- 不调整执行分层（执行能力扩展推迟到 P4.5）。

## 审计自查清单
- [ ] `backend.log` 中存在三类关键行：`creation_semantic_candidates_collected`、`creation_p4_debug_snapshot`、`creation_forced_by_p4_rule`（如命中）。
- [ ] API 返回包含 `creation_result.debug_observability`，且 `semantic_candidates`、`blocked_reason` 与日志一致。
- [ ] `creation_result.plan` 中的 `patch_templates` 不包含自动执行凭证（只读）。
- [ ] 若需澄清，流程 C 的首次请求不会强制创建，回合内可回滚至故事线。
