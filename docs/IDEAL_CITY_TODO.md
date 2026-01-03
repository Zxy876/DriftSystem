# Ideal City Execution TODOs

EXECUTION_MODE: CONTINUOUS
EXECUTION_SCOPE: CURRENT_INTEGER_TODO
IMPLEMENTATION_ALLOWED: true

CURRENT_ROUND: 2 (COMPLETED)
LAST_COMPLETED_TODO: TODO[CEC-PACKAGE-01]
CURRENT_INTEGER_TODO: TODO 3 (PENDING DEFINITION)

对齐依据：
- 《理想之城 · 愿景 → 工程语言转换文档（冻结版）》
- 《Copilot 执行清单（不可越界点）》

- [x] TODO[CEC-STRUCTURE-01] 阶段: 概念补齐 — 记录 DeviceSpec 所需的语义字段
- [x] TODO[CEC-STRUCTURE-02] 阶段: 接口占位 — 描述 DeviceSpec → 裁决层边界
- [x] TODO[CEC-GOVERNANCE-01] 阶段: 概念补齐 — 明确 DeviceSpec 不得绕过裁决
- [x] TODO[CEC-STRUCTURE-03] 阶段: 接口占位 — 勾勒裁决输出载体

- [x] TODO[CEC-AUTHORITY-01] 阶段: 概念补齐 — 裁决逻辑必须留在世界主权
- [x] TODO[CEC-RISK-01] 阶段: 风险标记 — 禁止任务事件匹配替代裁决
- [x] TODO[CEC-STRUCTURE-04] 阶段: 接口占位 — 裁决 → 执行层授权通道
- [x] TODO[CEC-SEPARATION-01] 阶段: 概念补齐 — 裁决 / 表现层隔离
- [x] TODO[CEC-COMPAT-01] 阶段: 风险标记 — 零模组依赖约束
- [x] TODO[CEC-PACKAGE-01] 阶段: 接口占位 — 文档与模块交叉引用

## Ideal City TODO Workflow Rules (Always-On)

### Rule 1 — Source of Truth
- The only executable source is this TODO list.

### Rule 2 — Integer vs Decimal TODOs
- Integer TODOs gate phases.
- Copilot must not advance integers unless rules allow it.

### Rule 3 — Round-Based Execution
- One integer TODO per round.

### Rule 4 — Search-Driven Execution
- Only search TODOs within CURRENT_INTEGER_TODO.

### Rule 5 — Output Constraints (Stage-Aware)
- 阶段: 概念补齐 / 接口占位 / 风险标记
  - 文档 / 注释 / schema 占位
  - 不写运行逻辑

#### Rule 5.a — Execution Window Override
If EXECUTION_MODE is CONTINUOUS and IMPLEMENTATION_ALLOWED is true:
- 阶段标签不阻断最小可运行实现
- 可在 EXECUTION_SCOPE 内顺序实现
- 实现必须最小、局部
- 当 EXECUTION_SCOPE 内无剩余 [ ] TODO 时必须停止

### Rule 6 — State Feedback (Self-Updating)
- 完成后将 [ ] → [x]
- 若 CURRENT_INTEGER_TODO 下无剩余 [ ] TODO：
  - 更新 CURRENT_ROUND
  - 更新 LAST_COMPLETED_TODO
  - 推进 CURRENT_INTEGER_TODO

### Rule 7 — Human Gate
- 仅当：
  - 新增 Integer TODO
  - 修改规则
  - 变更阶段语义