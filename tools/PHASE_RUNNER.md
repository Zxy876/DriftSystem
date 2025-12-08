# PHASE RUNNER — Autonomous AI Development Pipeline

## Objective
Use Copilot to execute each phase incrementally based on STATE.md and /phases/*.md.

## Rules
1. STATE.md 是唯一判断当前阶段的来源。
2. 读取 CURRENT_PHASE → 加载对应 /phases/phase_x.md。
3. 执行前必须输出 PLAN（entry conditions + diff skeleton summary）。
4. 满足 entry conditions 才能执行，否则停止。
5. 根据 pseudo-diff 修改项目（真实代码变更）。
6. 汇总 diff。
7. 在 STATE.md 写 Success Flag。
8. 将 Current Phase 更新为 Next Phase。
9. 停止并等待开发者输入 “继续下一阶段”。

## Execution Prompt (Developer Issues This)
"Run Phase Runner"

## Internal Execution Steps
1. Read /docs/STATE.md → determine CURRENT_PHASE.
2. Load /phases/phase_<CURRENT>.md.
3. Validate entry conditions.
4. Generate PLAN summary.
5. Apply pseudo-diff to produce real code changes.
6. Show unified diff.
7. Update STATE.md (success flag + next phase).
8. Stop with message:
   "Phase <x> complete. Type 'continue' to move to next phase."

## End
If CURRENT_PHASE = 5 and PHASE_5_COMPLETE = true → output:
"DriftSystem universe is fully built."
