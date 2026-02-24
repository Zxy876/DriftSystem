# Ideal City Prompt Protocol v2

## 目标
将叙事提示词从“实现细节”升级为“协议契约”，并与当前架构保持一致：

- 叙事层物理隔离：Ideal City 与 Reunion 各自独立引擎。
- 执行层共享：`/world/apply`、`/scene/realize`、`/scene/execute-readiness` 不分叉。
- 状态可审计：同一回合的输入、判定、追问、推进结果都可追踪。

本协议只约束 **Prompt 与状态机交互**，不引入新能力面。

## 适用范围
- `ACTIVE_NARRATIVE_MODE=IDEAL_CITY`：启用本协议的完整字段与判定。
- `ACTIVE_NARRATIVE_MODE=REUNION`：仅复用执行层，不复用 Ideal City 的协议字段。
- `EXPERIMENTAL/CINEMATIC`：必须通过 `narrative.factory` 注册后才可生效。

## 不可违背的约束（MUST）
1. 任何“完成度”判断必须来自场景协议字段，不得写死在 Python 条件分支里。
2. 缺失字段必须通过追问向玩家索取，不得自动补全默认答案。
3. 引擎输出失败时必须 fail-open 到可继续叙事的降级文本，不得阻断回合推进。
4. 协议版本必须显式记录（`prompt_version`），便于灰度和回放对比。
5. 日志必须包含 `narrative_mode` 与关键判定结果（覆盖率、缺失字段、是否推进）。

## 协议对象

### 1) Scenario Protocol
每个场景必须声明：

- `scenario_id`
- `protocol_version`
- `required_sections`（唯一真值来源）
- `acceptance_rules`（可选，规则化判定）
- `hint_policy`（追问粒度与语气约束）

### 2) Turn Input
每回合输入最少包含：

- `player_input`
- `story_state_snapshot`
- `missing_sections`
- `narrative_mode`

### 3) Turn Output
每回合输出最少包含：

- `coverage`（已覆盖字段集合）
- `missing_sections`（仍缺失字段集合）
- `next_question`（仅一个主问题）
- `advance_allowed`（是否可推进剧情）
- `prompt_version`

## 判定流程（Ideal City）
1. 读取场景 `required_sections`。
2. 从玩家输入中抽取结构化覆盖项。
3. 计算 `coverage` 与 `missing_sections`。
4. 若有缺失：生成单问题追问并保持当前剧情阶段。
5. 若无缺失：允许推进，并将结果写入 `story_state`。

> 说明：`protocol_state` 仅服务 Ideal City 判定；Reunion 引擎不依赖该对象。

## Prompt 模板要求
Ideal City 提示词必须固定包含以下块：

1. `ROLE`：当前叙事身份与边界。
2. `GOAL`：本回合唯一目标（补齐协议字段或允许推进）。
3. `REQUIRED_SECTIONS`：来自场景，不得改写。
4. `CURRENT_COVERAGE`：已覆盖字段。
5. `MISSING_SECTIONS`：待补字段。
6. `OUTPUT_SCHEMA`：强制输出字段（见 Turn Output）。

## 失败与降级策略
- LLM 调用异常：返回安全降级文本 + 保留 `missing_sections`，回合继续。
- 配额/超时抖动：沿用统一 AI 护栏（timeout/retry/fallback/max_tokens）。
- 非法输出：丢弃无效字段，进入“最小可解释”追问路径。

## 验证清单

### 自动化
- `backend/test_narrative_factory_modes.py`
- `backend/test_story_state_agent_reunion.py`
- `backend/test_world_mode_lock.py`
- `backend/test_ideal_city_pipeline.py`

### 线上探针（最小）
1. `narrative_mode=IDEAL_CITY`：缺 1 个字段时必须返回单问题追问。
2. 补齐后：`advance_allowed=True` 且进入下一阶段。
3. 切换 `narrative_mode=REUNION`：应走 Reunion 引擎，不读取 Ideal City 的 `protocol_state`。

## 迁移与发布建议
- 先灰度场景：从单场景开始启用 `required_sections` 严格判定。
- 保留回滚位：按 `prompt_version` 做快速回退。
- 发布后观察：关注 `missing_sections` 长尾分布与推进率变化。

## 一句话标准
“是否推进剧情”只由场景协议满足度决定，不由硬编码默认值决定。
