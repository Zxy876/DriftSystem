
PHASE RUNNER — Autonomous AI Development Pipeline (v2.0)

Objective

让 GitHub Copilot 能够自动读取 STATE.md 和 /phases/*.md，并依序执行任意数量的阶段（Phase 0 → ∞），直到全部完成。

⸻

Core Principles
	1.	STATE.md 是唯一的世界状态来源。
	2.	PHASE_RUNNER 不硬编码阶段数量，而是依赖以下方式判断：
	•	当前阶段对应的 success flag 是否存在
	•	/phases/phase_<N>.md 文件是否存在
	3.	如下一阶段存在 → 自动进入下一阶段。

⸻

Phase Numbering Rules
	•	阶段文件必须放在：
/phases/phase_0.md
/phases/phase_1.md
…
/phases/phase_N.md
	•	STATE.md 必须包含：
	•	当前阶段编号（CURRENT_PHASE = X）
	•	每阶段成功 Flag（PHASE_X_COMPLETE = true）

⸻

Execution Rules（Copilot 必须遵守）

Rule 1 — 读取当前状态
	1.	读取 /docs/STATE.md
	2.	找到字段：

CURRENT_PHASE = X



Rule 2 — 加载对应阶段文件

加载：

/phases/phase_X.md

如果不存在该文件 → 自动结束执行并提示：No further phases.

Rule 3 — 执行前必须输出 PLAN

PLAN 必须包含：
	•	Entry Conditions（需要哪些 success flag）
	•	Expected code areas（预计改动哪些文件）
	•	Risk summary（若有）
	•	Next-phase expectation（成功后的切换方向）

Rule 4 — 校验 Entry Conditions
	•	如果 STATE.md 不满足 entry conditions：
→ 停止并告知需要补充状态。

Rule 5 — 执行 Phase
	1.	根据阶段提示词生成 pseudo-diff
	2.	将 pseudo-diff 转换成真实代码修改
	3.	展示 unified diff（忽略长文件）

Rule 6 — 更新 STATE.md

必须更新以下内容：
	•	PHASE_X_COMPLETE = true
	•	CURRENT_PHASE = X + 1
	•	更新 Next Actions / Risk / Progress

Rule 7 — 停止，等待用户输入

当阶段结束必须输出：

Phase X complete. Type 'continue' to move to next phase.

用户输入 continue 后才能继续执行下一阶段。

⸻

Termination Rule（自动扩展支持）

如果下一个阶段文件不存在：

/phases/phase_<X+1>.md not found.
All executable phases are complete.
DriftSystem universe remains extensible — add new phase_x.md to continue evolution.


⸻

Developer Instruction

开发者只需输入：

Run Phase Runner

如要继续下阶段：

continue


⸻

End

PHASE RUNNER v2.0 支持：
	•	无限阶段扩展
	•	自我推进
	•	自动修改代码
	•	自动更新 STATE.md
	•	自动停止/继续
	•	完整兼容你未来所有想扩展的能力

