
⸻

PHASE RUNNER — Autonomous AI Development Pipeline (v2.3)

Objective
---------
让 GitHub Copilot 能够自动读取 STATE.md 与 /phases/ 下的阶段文件，
并依序执行 Phase_0 → Phase_1 → … → Phase_N，
直到所有阶段完成，且每个阶段都通过自校验（Outcome Verification）。

v2.3 主要能力：
 - 自动生成缺失的 `## Verification` 区块
 - 自动执行四级验证流程（文件 → 后端 → 触发器 → 状态机）
 - 验证失败则自动阻断，防止错误进入下一阶段

------------------------------------------------------------------------

Core Principles
---------------
1. STATE.md 是唯一且绝对的世界状态（SSoT）
2. Phase Runner 不硬编码阶段数量，完全依赖：
   - CURRENT_PHASE
   - /phases/ 下的对应文件是否存在
3. 下一阶段存在 → 自动执行
4. 缺少 Verification → 自动补全
5. 验证不通过 → 禁止推进阶段

------------------------------------------------------------------------

Phase Numbering Rules
---------------------
阶段文件必须如下格式：

  /phases/phase_0.md
  /phases/phase_1.md
  …
  /phases/phase_N.md

STATE.md 必须包含：

  CURRENT_PHASE = X
  PHASE_X_COMPLETE = true

------------------------------------------------------------------------

Execution Rules（Copilot MUST follow）
-------------------------------------

Rule 1 — 读取当前状态
---------------------
Copilot 必须执行：
  1. 打开 /docs/STATE.md
  2. 解析字段： CURRENT_PHASE = X

Rule 2 — 加载对应阶段文件
--------------------------
加载路径：

  /phases/phase_X.md

若不存在 → 输出：

  /phases/phase_X.md not found.
  All executable phases are complete.
  DriftSystem evolution awaits new phase definitions.

并停止。

------------------------------------------------------------------------

⭐ Rule 3 — 自动检查并补全 Verification（v2.3 NEW）
----------------------------------------------------
若 phase_X.md 中缺少：

  ## Verification

Copilot 必须：

1. 自动生成如下模板：

    ## Verification
    - Validate required triggers fire as expected.
    - Validate tasks progress upon corresponding rule_event.
    - Validate StoryEngine handles events without error.
    - Validate TaskRuntime milestone completion.
    - Validate StoryGraph progression if applicable.

2. 将此区块 **自动追加写入 phase_X.md 末尾**
3. 展示 diff
4. 继续流程

（不得跳过）

------------------------------------------------------------------------

Rule 4 — 输出 PLAN（强制）
-------------------------
PLAN 必须包含：

  • Entry Conditions  
  • Expected Code Areas  
  • Risk Summary  
  • Next-phase Expectation  

缺少 PLAN → 禁止继续。

------------------------------------------------------------------------

Rule 5 — 校验 Entry Conditions
------------------------------
若 STATE.md 不满足 Entry Conditions：

输出：

  Entry conditions not met. Please update STATE.md manually.

停止执行。

------------------------------------------------------------------------

Rule 6 — 执行阶段（核心步骤）
------------------------------
依序执行：

  1. 生成 pseudo-diff  
  2. 生成 unified diff  
  3. 显示 diff  
  4. 自动应用 patch 到仓库  

不得跳过。

------------------------------------------------------------------------

⭐ Rule 7 — 执行 Outcome Verification（四级验证 / v2.3）
--------------------------------------------------------

阶段执行后，Copilot 必须自动执行四层验证：

LEVEL 1 — File/Schema Validation
--------------------------------
验证：

  ✔ 修改的文件存在  
  ✔ JSON schema 字段合法  
  ✔ rule_event/memory_set/conditions 格式正确  
  ✔ level_id 已 canonicalized  

LEVEL 2 — Backend Functional Validation
---------------------------------------
执行：

from app.core.story.story_engine import StoryEngine
engine = StoryEngine()
engine.load_level_for_player(“tester”, “”)
engine.handle_rule_event(“tester”, {“rule_event”: “<expected_event>”})

验证：

  ✔ 无异常  
  ✔ TaskRuntime 正常推进  

LEVEL 3 — Mock Plugin Event Verification
----------------------------------------
模拟：

  • NPC right-click  
  • checkpoint 进入  
  • chat / interact  

即触发：

  POST /world/story/rule-event  
  POST /story/load  
  POST /world/apply  

验证返回值 200 且结构完整。

LEVEL 4 — State Machine Validation
----------------------------------
验证：

  ✔ active tasks 正确  
  ✔ milestones 正常完成  
  ✔ rule_event 可以匹配任务  
  ✔ StoryGraph 可以推荐后续关卡（若相关）

如果任何一项失败 → 输出：

Phase X verification failed.

Unmet verification:
	•	<列表>

Please revise implementation or request auto-fix.

并停止推进下一阶段。

------------------------------------------------------------------------

Rule 8 — 更新 STATE.md（只有验证通过时）
----------------------------------------
Copilot 必须写入：

  PHASE_X_COMPLETE = true
  CURRENT_PHASE = X + 1

并更新 STATE.md 的：

  • Progress  
  • Next Actions  
  • Risks  
  • Notes  

并展示 diff。

------------------------------------------------------------------------

Rule 9 — Stop & Wait
---------------------
阶段成功时输出：

  Phase X complete.
  Type 'continue' to run the next phase.

然后停止，等待开发者输入：

  continue

------------------------------------------------------------------------

Rule 10 — Continue 语义
-----------------------
用户输入 continue 时，Copilot MUST：

  • 再次读取 STATE.md  
  • 使用新的 CURRENT_PHASE  
  • 从 Rule 1 重新开始 Phase Runner  

------------------------------------------------------------------------

Termination Rule
----------------
若 /phases/phase_(X+1).md 不存在：

/phases/phase_(X+1).md not found.
All executable phases are complete.
DriftSystem evolution awaits new phase definitions.

并停止。

------------------------------------------------------------------------

Developer Instructions
----------------------
开始自动执行：

  Run Phase Runner

执行下一阶段：

  continue

新增阶段：

  创建 /phases/phase_<N>.md 即可。

------------------------------------------------------------------------

END OF PHASE RUNNER v2.3


