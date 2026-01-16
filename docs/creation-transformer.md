# Resource-Behavior Transformer 笔记（Phase 2 Kickoff）

> 版本：2026-01-14 · 维护者：Drift System 工程团队

---

## 1. 模块概览
- 位置：`backend/app/core/creation/`。
- 组成：
  - `ResourceCatalog` / `ResourceSnapshot`：加载可建造资源列表。
  - `ResourceSnapshotBuilder`：扫描仓库 artefacts 生成资源快照。
  - `CreationTransformer`：依据 Phase 1 `slots` 推导 `creation_plan`。
- 输出：
  - 计划摘要（动作、材料、置信度）。
  - 已匹配 / 未匹配材料列表与告警备注。
  - 资源快照版本戳，支持调试与缓存控制。

## 2. 数据来源
- 动态快照：`ResourceSnapshotBuilder` 扫描 `mods/` 与 `resourcepack/assets/`，写入 `backend/data/transformer/resource_catalog.json`。
  - 字段：`resource_id`, `label`, `aliases`, `tags`, `available`, `commands`。
  - 同步收集 `mod.json` 中的建造指令（`setblock`/`fill` 等）作为命令模板。
- 种子文件：`backend/data/transformer/resource_catalog.seed.json` 保留 drift 系列等人工维护条目。
- 未来扩展：引入世界存档/服务器导出的物资快照，实现增量更新。

## 3. API 接入
- 新增接口：`POST /intent/plan`
  - 请求：`{"message": "..."}`（沿用 Phase 1 请求体）。
  - 响应：`summary`, `materials`, `steps`, `notes`, `unresolved_tokens`, `snapshot_generated_at`。
- Ideal City 管线：`intent_analysis.creation_plan` 同步返回完整计划，供后续阶段消费。

## 4. Patch 步骤与模板草案
- `CreationPlan.steps`
  - 针对每个已匹配材料生成 `step-{n}`，附带命令模板与 `required_resource`。
  - `step_type` V1：`block_placement` / `mod_function` / `entity_spawn` / `manual_review` / `custom_command`。
  - 未匹配材料或未知类型统一落到 `manual_review`，并强制 `status=draft|needs_review`。
- `CreationPlan.patch_templates`
  - 为每个步骤输出 `world_patch` 草稿（含 `mc.commands`、标签、占位符），并运行 `validate_patch_template()`。
  - 模板包含 `validation` 字段，集中记录 `errors` / `warnings` / `execution_tier` / `missing_fields` / `unsafe_placeholders`。
  - 命令统一经过 `command_safety.analyze_commands` 白名单校验；不合规直接阻断。
- `CreationPlan` 级别输出 `execution_tier`、`unsafe_steps`、`safety_assessment`，供 Patch Executor 判定是否自动执行。
- API `/intent/plan` 与 Ideal City 均返回上述结构，为 Phase 3 world_patch 接入做准备。

## 5. 测试与验证
- 单测：`backend/test_creation_plan_transformer.py`
  - 校验材料匹配、未匹配提示、非创造降级路径。
  - 断言 `steps` 含 resolved/needs_review 状态与资源关联。
- 集成测试：复用 Phase 1 pytest 套件，验证 `intent_analysis` 结构回传。

## 6. 后续 TODO
1. 将动态快照纳入 CI 定时任务，覆盖服务器世界状态导出。
2. 引入坐标/布局推断，生成 `creation_plan.steps[*].commands` 的多步变体。
3. 与 world_patch 执行器联调，建立步骤到命令流水线的映射表。
4. 记录 Transformer 置信度与步骤执行成功率，纳入 Phase 4 指标监控。

---

*任何更新需同步本笔记与 `docs/chat-input-phase-status.md`。*
