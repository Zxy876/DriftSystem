# 《MissionControlLive TRNG 原型与 Drift System 行为内核对照说明》

## 1. Drift System 当前行为模型概述

Drift System 当前可抽象为“运行时推进 + 持久化状态”并行协作的双系统：

- `StoryEngine`：负责单次输入的行为推进、分支计算、运行时状态更新与输出生成。
- `StoryState`（或 `StoryStateManager/Repository`）：负责阶段性状态持久化、恢复、跨会话一致性。

其主流程可表达为：

`Input -> AI -> Transition -> Runtime State -> Output`

- `Input`：玩家输入、系统事件、上下文变量。
- `AI`：策略/文本决策层（含超时、失败降级策略）。
- `Transition`：把意图映射为剧情推进动作（如 `advance()` 与 beat 激活逻辑）。
- `Runtime State`：更新运行时树状态与记忆标记。
- `Output`：产出下一步叙事文本、动作建议或系统反馈。

关键语义：

- `tree_state`：叙事树当前位置及分支条件的运行时表示。
- `beat_state`：节拍（beat）级推进状态，描述当前节拍是否激活、完成、待推进。
- `fallback`：AI 不可用/超时/不确定时的降级通道，用于保证系统可继续推进。

---

## 2. MissionControlLive TRNG 架构概述

MissionControlLive 中的 TRNG 原型是一个“显式事务化叙事引擎”，核心由四层组成：

- `GraphLayer`
  - 存储已提交的 `StoryNode` 序列。
  - 仅在提交阶段追加，作为可审计的行为轨迹。

- `InternalState`
  - 存储最小内核态（如 `phase`、`silenceCount`、`tension`、`memoryFlags`、`lastNodeID`）。
  - 通过 `StatePatch` 演进，而不是任意字段散写。

- `Transaction`
  - 封装一次推进事务：`rootFromNode`、`nodes`、`draftState`、`phaseChanged`、`status`。
  - 明确区分构建态（draft）与提交态（committed）。

- `apply(event:)`
  - 统一入口，串行处理全部外部事件。
  - 禁止多入口绕过，避免状态竞态。

两阶段提交机制：

1. **Build Phase**：根据事件构建节点链 + 演进 `draftState` + 做阈值检查与不变量校验。
2. **Commit Phase**：一次性提交 `GraphLayer` 与 `InternalState`，失败则整体回滚。

关键语义：

- `phase`：叙事阶段（`intro/challenge/escalation/crisis/resolution`）。
- `silence`：超时/失联/无有效推进的计数信号，用于触发相变与风险上升。

---

## 3. 一一对应关系（Drift ↔ TRNG）

| Drift System 概念 | TRNG 原型概念 | 对照说明 |
|---|---|---|
| `advance()` | `apply(event:)` | 二者都是“单步推进入口”；TRNG 把入口显式收敛到单函数并串行化。 |
| `tree_state` | `InternalState + GraphLayer` | Drift 的树态在 TRNG 中拆为“内核态 + 可审计节点链”，提升可观察性与一致性。 |
| `fallback` | `silence` 节点与计数 | Drift 的降级语义在 TRNG 中被结构化为可计数事件，不再是隐式旁路。 |
| beat/phase 推进 | `phase` 变更逻辑 | 二者都描述剧情阶段推进；TRNG 增加“单事务内最多一次相变”约束。 |
| 分步写入风险 | Commit 边界（原子提交） | Drift 可能出现逻辑推进与状态落盘分离；TRNG 用提交边界保证一致更新或整体回滚。 |

---

## 4. 为什么用 MissionControlLive 作为实验壳

从系统架构实验角度，MissionControlLive 适合做 TRNG 原型验证，原因是：

- **可视化强**：事件、阶段、内核态可以即时映射为可观察信号，便于验证状态机是否按预期收敛。
- **事件密度高**：周期 tick、指令输入、异常路径并存，能快速覆盖正常/异常/超时场景。
- **无外部 AI API 强依赖**：可在本地稳定复现事务语义与不变量，不受外部服务波动干扰。
- **可快速验证 invariants**：链完整性、提交对齐、相变约束、silence 规则都能在短周期内反复验证。

---

## 5. 这个原型如何反向约束 Drift

TRNG 原型不是替代 Drift，而是给 Drift 提供“可执行约束模板”：

- **强制原子性**
  - 把“状态推进 + 轨迹记录 + 核心态更新”收敛到单提交边界。

- **强制单事务推进**
  - 所有外部输入统一进入单入口，避免多函数侧写导致竞态与时序漂移。

- **强制 silence 节点生成**
  - 把 fallback/timeout 类事件显式化、结构化、可审计，而非隐式吞噬。

- **限制 phase 多次跳变**
  - 单事务内最多一次相变，避免复杂事件引发“多阶段跳跃”导致语义不稳定。

---

## 6. 未来迁移路径

建议按“后端内核先行、AI 层后接”的路线迁移：

1. 将 TRNG 的事务边界与不变量规则抽取为 Drift 后端通用推进模块。
2. 在 Drift 中以事务入口替换现有 `story_engine.advance` 的分散式推进路径。
3. 保留 AI 决策层（模型推理与策略生成），但把 AI 输出统一变为事务输入事件。
4. 将 fallback 语义标准化为 silence 事件族，统一进入同一状态机。
5. 用阶段化迁移方式先保证行为一致性，再逐步优化性能与可观测性。

最终目标是：

- AI 仍负责“决策建议”，
- 事务内核负责“可验证推进”，
- 持久化层负责“跨会话一致性”，

从而形成可审计、可回滚、可演进的行为内核。