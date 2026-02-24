 
DriftSystem v1.18

Engineering Specification & Implementation Canon

Semantic Creation Expansion (Understanding-Only Stage)

状态：Draft → Review
前置版本：v1.17 — Deterministic Creation Core（已冻结）
版本类型：能力扩展（理解层）
执行权状态：零新增

仓库落地范围（当前 scienceline 分支）：
	• backend/ → FastAPI 后端，承载 CreationWorkflow、ResourceCatalog 与语义层落地代码
	• mc_plugin/ → Paper 插件入口，监听玩家聊天并调用 backend API（CreationChatListener、BackendClient）
	• resourcepack/ 与 mods/ → ResourceSnapshotBuilder 的扫描输入源，产出 resource_catalog.json
	• scripts/、test_*.py → 集中存放工程自测脚本与 PyTest 套件，所有验收以这些文件为准

⸻

0. 本文档的地位（冻结声明）

本文档是 v1.18 唯一的工程落地依据。
	•	所有代码实现
	•	所有测试设计
	•	所有模块边界判断
	•	所有“是否能做 / 是否不做”的争议

均以本文档为最终裁决来源。

⸻

1. v1.18 一句话工程定义（冻结）

v1.18 的目标不是扩展系统能做什么，
而是让玩家在不理解 Minecraft 官名与系统规则的前提下，
依然能 稳定、可治理地 使用 v1.17 已存在的造物能力。

工程表达：

v1.18 只降低使用门槛，不增加系统权力。

⸻

2. 强冻结边界（Hard Constraints）

2.1 允许（Allowed）

v1.18 允许且仅允许以下能力：
	•	Transformer / ML 参与 语义理解
	•	构建资源的 语义索引（embedding / similarity）
	•	一个资源对应 多个自然语言别名
	•	歧义澄清流程（clarification）
	•	有限、确定性的软空间描述
	•	在我面前
	•	在脚下
	•	在正前方一格
	•	在这面墙上（可唯一解析时）

⸻

2.2 明确禁止（Forbidden）

v1.18 明确禁止以下行为（无例外）：
	•	❌ ML 直接决定执行
	•	❌ ML 写入世界
	•	❌ 绕过 ResourceCatalog
	•	❌ 修改或推断 execution_tier
	•	❌ 自动生成大型结构 / 蓝图
	•	❌ mineflayer / Bot 执行
	•	❌ 强化学习控制世界或 NPC
	•	❌ 模糊空间推理（多解不澄清）

⸻

2.3 冻结原则（Core Law）

ML 只能提议，不得执行。
执行权永远属于确定性系统。

这是 v1.18 不可违背的系统法则。

⸻

3. 系统架构位置（精确定义）

3.1 v1.17 管线（回顾）

玩家输入
 → 意图解析（是否为造物）
 → CreationWorkflow
 → ResourceCatalog
 → execution_tier
 → WorldExecutor


⸻

3.2 v1.18 管线（冻结）

玩家输入
 → 意图解析（是否为造物）        ← ML 不介入
 → 语义理解层（ML 候选提议）     ← 新增，仅只读
 → CreationWorkflow
 → ResourceCatalog
 → execution_tier
 → WorldExecutor

明确说明：
	•	ML 不参与“是否是造物请求”的判定
	•	ML 只参与“造物请求中资源的语义指向”

工程落地映射（仓库模块对照）

| 管线阶段 | 仓库模块 | 入口文件 / 函数 | 说明 |
| --- | --- | --- | --- |
| 玩家输入采集 | mc_plugin/src/main/java/com/driftmc/CreationChatListener.java | CreationChatListener#onPlayerChat | 监听玩家聊天，将文本投递至 backend `/intent/recognize` 与 `/intent/plan` |
| 意图解析（是否为造物） | backend/app/services/creation_workflow.py | `classify_message`、`CreationIntentClassifier` | 纯确定性，沿用 v1.17 流程，不引入 ML |
| 语义理解层（ML 候选提议） | backend/app/services/semantic_proposal.py、backend/app/core/resource_catalog/alias_resolver.py | `SemanticProposalService.collect_candidates`、`AliasResolver.resolve` | 新增理解层，所有候选走 ResourceCatalog 过滤 |
| CreationWorkflow 治理 | backend/app/services/creation_workflow.py | `generate_plan`、`_collect_transformer_candidates` | 负责澄清、执行权限判定，保持确定性治理逻辑 |
| ResourceCatalog 校验 | backend/app/core/resource_catalog/service.py、store.py | `ResourceService.ensure_active`、`ResourceEntry` | 统一管理资源元数据与 execution_tier |
| execution_tier → WorldExecutor | backend/app/core/world/plan_executor.py、patch_executor.py | `PlanExecutor.run_plan` | 仅在澄清通过后执行，v1.18 不改写 |
| 审计与日志 | backend/app/services/creation_workflow.py、backend/app/instrumentation/* | `_log_semantic_resolution` | 记录模型版本、来源，保证可追溯 |

⸻

4. 核心能力目标

⸻

4.1 目标 A：资源语义命中规模化（Alias at Scale）

当前问题（v1.17）
	•	大量资源只能使用 minecraft:<id>
	•	别名依赖人工硬编码
	•	容错率低
	•	新玩家体验差

⸻

v1.18 方案
为所有 ResourceCatalog.status == active 的资源构建：
	•	语义索引（embedding）
	•	多别名映射
	•	统一的语义检索接口

资源逻辑结构（示例）

{
  "resource_id": "minecraft:soul_lantern",
  "display_name": "灵魂灯笼",
  "aliases": ["灵魂灯", "幽魂灯"],
  "semantic_tags": ["灯", "照明", "灵魂"]
}


⸻

运行流程

用户输入
 → 文本向量化
 → Top-K 语义候选
 → 交由 CreationWorkflow 治理


⸻

验收标准（冻结）
	•	✅ 玩家无需输入 minecraft:id
	•	✅ ≥95% safe_auto 资源可被自然语言命中
	•	✅ 所有命中必须通过 ResourceCatalog
	•	✅ 所有歧义 必须进入澄清
	•	❌ 任何无法确定命中的请求 不得写世界

仓库落地路径（必须全部完成）
	•	数据基线：`backend/data/transformer/resource_catalog.json` 由 `ResourceSnapshotBuilder` 生成，所有别名/标签补全需通过该 builder（文件：`backend/app/core/creation/snapshot_builder.py`）。
	•	语义索引：新增 `backend/app/ml/embedding_model.py`（向外部向量服务取 embedding）、`backend/app/ml/resource_index.py`（管理 Top-K 检索，持久化在 `backend/data/transformer/semantic_index.json`）。索引生成脚本放置于 `backend/scripts/build_semantic_index.py`，执行后自动写入版本号。
	•	多别名映射：扩展 `backend/app/core/resource_catalog/alias_resolver.py`，将 builder 产出的 aliases + 语义层别名统一写回 `resource_catalog.json`，并在 `AliasResolver.refresh` 时载入。
	•	接口统一：对外仅暴露 `SemanticProposalService.collect_candidates`（已存在），新索引通过 `token_iterator` 与 `resource_resolver` 回流，禁止新增绕过 ResourceCatalog 的调用。
	•	测试覆盖：必须补充 / 更新 `backend/test_semantic_proposal_service.py`、`backend/test_creation_workflow_clarification.py`、`backend/test_resource_catalog.py`，确保多别名、模糊匹配、澄清路径全覆盖。
	•	数据质量守护：在 `backend/tests/fixtures` 内新增资源覆盖率快照（例如 `semantic_alias_coverage.yaml`），配合 `pytest` 校验 ≥95% safe_auto 命中率。

⸻

4.2 目标 B：Transformer = 提议层（Proposal Layer）

Transformer 输出（冻结 Schema）

{
  "intent": "CREATE_BLOCK",
  "candidates": [
    {
      "resource_id": "minecraft:soul_lantern",
      "confidence": 0.82
    }
  ],
  "origin": "transformer_v1_18"
}


⸻

Transformer 被禁止
	•	❌ 生成命令
	•	❌ 决定执行
	•	❌ 修改权限
	•	❌ 跳过澄清
	•	❌ 接触 WorldExecutor

⸻

技术约束
	•	固定 JSON Schema
	•	无执行接口
	•	Feature Flag 可随时关闭
	•	仅通过 SemanticProposalService 接入

仓库落地路径（必须全部完成）
	•	服务封装：`backend/app/services/semantic_proposal.py` 负责 Transformer 候选聚合，新增 ML 通道需在此文件注册 feature gate 与 source label，不允许在其它模块直接实例化 `CreationTransformer`。
	•	配置管理：新增 `.env` 键 `TRANSFORMER_PROPOSAL_ENABLED`、`SEMANTIC_VECTOR_ENABLED` 默认关闭，现有 `creation_workflow._is_feature_enabled` 负责读取；Feature Flag 统一写入 `backend/README_NEW.md` 的配置段。
	•	模型快照：Transformer 资源快照仍由 `backend/data/transformer/resource_catalog.json` 提供，新增字段 `origin`、`generated_at` 需在 `ResourceSnapshotBuilder` 写入，并在 `SemanticProposalService.model_version` 回传。
	•	调用标注：所有调用 `SemanticProposalService.collect_candidates` 的地方（当前仅 `creation_workflow._collect_transformer_candidates`）必须添加第 7.3 节规定的 ML 角色声明注释，提交前运行 `pytest backend/test_semantic_proposal_service.py -k proposal_annotation` 校验。
	•	遥测：在 `_log_semantic_resolution` 中记录 `origin`、`confidence`、`token`，并通过 `backend/app/instrumentation/cityphone_metrics.py` 暴露 `semantic_proposal_total` 指标，方便线上观测。
	•	回滚预案：`backend/app/services/creation_workflow.py` 必须保留 `_collect_transformer_candidates` → `_propose_generic_clarification_candidates` 的 fallback，Feature Flag 关闭后自动退回 v1.17 行为。

⸻

4.3 目标 C：确定性软空间建造

支持语义
	•	在我面前
	•	在脚下
	•	在正前方一格
	•	在这面墙上（唯一解析）

规则（冻结）
	•	必须唯一解析
	•	多解 → 澄清
	•	澄清前 零写入

仓库落地路径（必须全部完成）
	•	解析入口：沿用 `backend/app/services/creation_workflow.py` 中的 `_detect_soft_placement_directives`、`_compute_soft_placement_coordinates`，必要时扩展 `_SOFT_PLACEMENT_PATTERNS`，禁止在其它模块重复实现。
	•	玩家上下文：`IntentExecuteRequest.player_context`（位于 `backend/app/api/intent_api.py`）需填充位置、朝向，由 mc_plugin 的 `BackendClient.postJsonAsync` 上传；插件侧新增位置采集逻辑，放在 `mc_plugin/src/main/java/com/driftmc/CreationChatListener.java`。
	•	歧义处理：保持 `_extract_soft_placement_plan` 抛出 `ClarificationRequired(reason="ambiguous_location")`，并在 `backend/test_creation_workflow_soft_placement.py` 覆盖“缺少上下文”与“多命中”场景。
	•	世界写入：软空间生成的坐标写入 `CreationPlanStep.position` 与 `CreationPatchTemplate.world_patch.metadata.coordinates`，由 `backend/app/core/world/plan_executor.py` 执行；执行前必须在 `WorldChangeLog` 记录来源标签 `soft_placement:<kind>`。
	•	Feature Flag：`SOFT_PLACEMENT_ENABLED` 控制软空间能力，默认关闭；在 `backend/start_backend.sh` 与 `README_NEW.md` 样例中标注开启方式。
	•	安全校验：扩展 `backend/test_creation_workflow_coordinates.py`，验证软空间坐标与玩家方向匹配；`test_world_change_guard.py` 补充对 `soft_placement` 来源的守卫。

⸻

5. ML 模块工程划分（职责级，不是实现清单）

⚠️ 本节定义 逻辑职责，不要求 v1.18 全部自研实现。

backend/app/ml/
	__init__.py                # 模块导出，供 SemanticProposalService 引用
	embedding_model.py         # 文本向量化（外部服务 / 向量数据库 SDK 包装）
	resource_index.py          # 语义索引 / Top-K（统一加载、缓存、失效机制）
	semantic_resolver.py       # 候选生成（聚合 alias + embedding 结果）
	confidence_calibrator.py   # 置信度调节（可根据实验配置进行线性校准）
	feature_flag.py            # 语义层启停（封装环境变量读取 + 缓存）

脚本与数据：
backend/scripts/build_semantic_index.py   # 扫描 ResourceCatalog、生成 embedding 与索引
backend/data/transformer/semantic_index.json  # 索引持久化文件（git 管理，随版本更新）

说明：
	•	允许使用第三方模型 / API
	•	不要求训练代码
	•	不引入 loss / backprop / RL

⸻

6. 治理不变量（不可破坏）
	•	所有世界写入 → CreationWorkflow
	•	ResourceCatalog 是唯一授权源
	•	execution_tier 决定执行能力
	•	WorldChangeLog 记录全部写入
	•	语义层可随时关闭并回退 v1.17

⸻

7. v1.18 工程注释范式（中文 · 强制执行）

本节不是“建议”，而是 工程规范的一部分。
所有 v1.18 相关代码 必须遵守，否则视为实现不合格。

目标只有一个：

任何代码，只要是 v1.18 的，我（项目所有者）能一眼看懂：
	•	你在干什么
	•	你为什么这么干
	•	你明确没在干什么

⸻

7.1 文件级注释规范（必须）

每一个 v1.18 新增或修改的文件，文件顶部必须有中文说明。

标准模板（必须原样包含语义）

"""
【v1.18 语义层模块】

模块用途：
- 本文件用于：<一句话说明做什么>

工程边界：
- 仅参与【语义理解 / 候选提议】
- ❌ 不具备执行权限
- ❌ 不得写入世界
- ❌ 不得修改 execution_tier

版本说明：
- 引入于 DriftSystem v1.18
- 属于“理解层”，不属于“执行层”
"""

❌ 禁止写法
	•	只写英文
	•	只写“helper / utils / service”
	•	没写“不做什么”

⸻

7.2 函数级注释规范（必须回答 3 个问题）

每一个对语义、ML、澄清、规划有影响的函数，必须用中文回答以下三点：

标准模板

def resolve_semantic_candidates(text: str) -> list[Candidate]:
    """
    【为什么存在】
    - 这个函数存在的原因是什么
    - 它解决的是“哪一步”的问题

    【它具体做什么】
    - 输入是什么
    - 输出是什么
    - 结果会被谁使用

    【它明确不做什么】
    - 它不会做哪些事情（尤其是执行相关）
    """

示例（正确）

def generate_semantic_proposals(message: str) -> list[SemanticCandidate]:
    """
    【为什么存在】
    - 将玩家的自然语言输入转化为“可能的资源候选”
    - 用于降低玩家对官名与 Catalog 的理解门槛

    【它具体做什么】
    - 输入：玩家的原始自然语言文本
    - 输出：Top-K 资源候选（仅提议，不裁决）
    - 输出结果将交由 CreationWorkflow 进行治理与裁决

    【它明确不做什么】
    - 不决定是否执行
    - 不校验 execution_tier
    - 不写入世界
    """


⸻

7.3 ML / Transformer 调用强制标注规范

凡是涉及 ML / Transformer / embedding 的地方，必须显式标注其“权力边界”。

强制标注字段（必须全部出现）

# 【ML 角色声明】
# ML_ROLE: 仅用于语义提议（proposal_only）
# EXECUTION_AUTHORITY: 无
# GOVERNANCE_OWNER: CreationWorkflow

示例

# 【ML 角色声明】
# ML_ROLE: 仅用于语义提议（proposal_only）
# EXECUTION_AUTHORITY: 无
# GOVERNANCE_OWNER: CreationWorkflow

candidates = semantic_proposal_service.propose(message)

目的：
	•	防止未来任何人“顺手让 ML 执行”
	•	防止你将来回看代码时产生歧义

⸻

7.4 危险 / 不应被玩家触达的分支注释规范

任何理论上不应该被玩家触达的分支，必须明确写清楚。

标准模板（必须包含关键词）

# 【内部安全分支｜v1.18】
# INTERNAL_UNREACHABLE
# 说明：
# - 该分支不应被任何玩家路径触发
# - 若触发，说明语义或治理管线存在严重错误
# - 该分支不承担兜底职责，不向玩家暴露

示例

# 【内部安全分支｜v1.18】
# INTERNAL_UNREACHABLE
# 说明：
# - 该分支仅用于内部监控与告警
# - 不作为任何形式的 fallback 或自动修复
_log_internal_fallback(event)


⸻

7.5 澄清（Clarification）相关代码注释规范

凡是抛出 ClarificationRequired / 返回澄清 payload 的地方，必须说明“为什么不能执行”。

"""
【澄清触发原因说明】
- 当前输入无法唯一映射到可执行资源
- 为避免误写世界，系统选择进入澄清流程
"""

禁止：
	•	“暂时不知道”
	•	“模型不确定”
	•	“fallback”

必须是治理原因，而不是模型原因。

⸻

7.6 测试文件注释规范（你现在最需要的）

每一个 v1.18 测试文件，文件头必须写：

"""
【v1.18 语义层测试】

测试目的：
- 验证治理不变量是否被破坏
- 验证澄清是否正确触发

注意：
- 本测试不验证具体 Minecraft 官名
- 本测试不作为资源正确性的依据
"""

若是示例测试（example）

@pytest.mark.example
"""
【示例测试】
- 仅用于演示完整链路
- 不参与 v1.18 冻结验收
"""


⸻

7.7 本注释范式的冻结声明

自 v1.18 起，
“我能否看懂这段代码”
是代码是否可接受的工程标准之一。

任何不符合本注释规范的实现：
	•	即使功能正确
	•	即使测试通过

也必须重写。

7.8 注释规范执行机制（必须落实）

	•	静态校验脚本：新增 `backend/tools/validate_v118_comments.py`，解析 Python / Java 文件头与函数 docstring，检查是否包含 7.1 ~ 7.6 规定字段；脚本以退出码约束 CI。
	•	PyTest 钩子：在 `backend/conftest.py` 中注册自定义标记 `@pytest.mark.v118_semantic`，并在 `tests/test_v118_comment_contract.py` 中抽样验证关键模块（`creation_workflow.py`、`semantic_proposal.py`、`alias_resolver.py`）。
	•	CI 集成：`backend/test_all.sh` 新增步骤调用 `python tools/validate_v118_comments.py`；GitHub Actions / 本地 pre-commit 均需执行。
	•	知识库：在 `README_NEW.md` 的“工程规范”章节加入链接，指向本节，提醒贡献者按模板撰写。

 

8. 退出 / 冻结标准（全部满足）
	•	✅ 自然语言稳定命中资源
	•	✅ 无需官名
	•	✅ ML 不执行
	•	✅ 歧义强制澄清
	•	✅ 澄清前零写入
	•	✅ 可回滚
	•	✅ Feature Flag 生效
	•	✅ 冻结测试通过（非 example）

验收流水线（必须全部通过）
	•	后端单测：`pytest backend/test_semantic_proposal_service.py backend/test_creation_workflow_clarification.py backend/test_creation_workflow_soft_placement.py backend/test_world_change_guard.py`
	•	集成脚本：`cd backend && ./test_all.sh`（新增语义层章节，验证 Feature Flag 与澄清链路）
	•	插件联调：启动 `mc_plugin` + `backend/app`，使用 `scripts/demo_features.sh` 执行“在我面前放一个灵魂灯”并记录 `backend/logs/semantic_resolution.log`
	•	回滚演练：关闭 `SEMANTIC_LAYER_ENABLED`，确认 `SemanticProposalService` 不再被调用，日志仅出现 alias/hard 路径

⸻

9. 本版本明确不做（再次冻结）
	•	自动造房
	•	蓝图系统
	•	AI 主导建造
	•	NPC / RL
	•	电影系统

⸻

10. 成功定义（体验级）

玩家说：

在我面前放一个灵魂灯

系统做到：
	•	正确
	•	可解释
	•	可审计
	•	可回滚
	•	可治理

⸻

11. v1.18 的哲学

v1.18 不是更强的 AI
而是更低门槛的系统

ML 扩展理解
系统保持权力

⸻

12. 长期兼容声明

未来版本可以引入：
	•	NPC 智能
	•	多轮规划
	•	强化学习

但：

v1.18 永远是最后一个“ML 无执行权”的版本。

 