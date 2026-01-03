# Ideal City Migration Placeholder Record

对齐依据：
- 《理想之城 · 愿景 → 工程语言转换文档（冻结版）》
- 《Copilot 执行清单（不可越界点）》

## 新增占位抽象
- `backend/app/core/ideal_city/device_spec.py`：建立 DeviceSpec 语义容器占位，仅记录职责与禁区。
- `backend/app/core/ideal_city/adjudication_contract.py`：定义世界裁决接口边界，占位接受/部分/拒绝语义。
- `backend/app/core/ideal_city/execution_boundary.py`：声明执行层与裁决输出的责任分割。
- `backend/app/core/ideal_city/__init__.py`：聚合理想之城抽象占位，避免导入副作用。
- `docs/IDEAL_CITY_TODO.md`：集中管理理想之城执行清单对应的语义 TODO。

## 暂不触碰的现有系统
- 既有任务运行时与世界补丁执行循环保持原状，确保 Drift 核心事件→响应范式不被破坏。
- 情绪天气、记忆标记、推荐引擎保持现行策略，仅待后续语义映射。
- 插件侧事件采集与节流逻辑不做调整，防止越界触及表现层实现。

## 明确禁止的风险
- 禁止以自然语言直接驱动世界补丁或命令，必须先经过世界裁决层。
- 禁止引入算法题评测或 OJ 逻辑作为 DeviceSpec 的裁决依据。
- 禁止依赖科技模组作为核心裁决或执行前提，保持零模组可运行。
- 禁止将裁决权下放至表现层或插件逻辑，确保世界主权留在后台。

## Semantic Guardrails Confirmation
- `backend/app/core/ideal_city/device_spec.py` 显式标注为非任务、非剧情节点、非世界补丁发起者，专守 DeviceSpec 一等对象语义。
- `backend/app/core/ideal_city/adjudication_contract.py` 明确自身是非裁决执行者（只定义边界），非插件入口，非算法评测器。
- `backend/app/core/ideal_city/execution_boundary.py` 指定为非 mod 接口、非命令调度器、非渲染逻辑承载者，限制自身为裁决结果传递描述层。
- Legacy Drift 概念（任务会话、剧情节点、世界补丁生成器、Kunming Lake / Xinyue 专属 schema）被标注为不得复用到理想之城抽象中。
