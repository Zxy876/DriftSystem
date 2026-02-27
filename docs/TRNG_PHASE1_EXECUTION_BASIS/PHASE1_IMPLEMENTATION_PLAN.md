## TRNG Phase1 Implementation Plan (Step0 ~ Step4)

目标：按用户指定的四步序列将 `story_engine.advance` 逐步迁移到事务壳（Transaction）+ 分阶段写入模型，降低一次性重构风险。

注意：此文档只描述实现计划、回滚与验证策略；不包含代码变更。

### Step0 — 准备与特性开关
- 改哪些文件：
  - 添加配置/特性开关位置（示意文档/配置），例如 `backend/config.py` 或环境变量文档（仅文档描述）。
- 不改哪些文件：
  - `story_engine.py`、`story_graph.py`、API 层代码（暂不改）。
- 回滚策略：
  - 若后续步骤失败，仅撤回配置开关（禁用新逻辑），系统回退到原 advance 行为。
- 验证方式：
  - 在本地/测试环境启动服务，确保在开关为 `off` 时系统行为与基线一致（运行现有 acceptance tests）。
- 风险等级：低。

### Step1 — 插入事务壳（不改内部逻辑）
- 改哪些文件：
  - 新建 `Transaction` 类文件（示意文档/类型定义），在 `story_engine.py` 中新增 `apply(event)` 接口作为入口代理，内部仍调用现有 `advance()`。
- 不改哪些文件：
  - `advance()` 的实现逻辑、`story_graph.py`、持久层代码（暂不改）。
- 回滚策略：
  - 仅删除/禁用 `apply(event)` 入口并恢复 API 调用到 `advance()`。由于未改逻辑，风险低。
- 验证方式：
  - 在启用开关下，通过单元测试和集成测试确认 `apply(event)` 与直接调用 `advance()` 行为一致（响应、状态变更、日志）。
  - 监控日志中是否出现异常/性能回归。
- 风险等级：低→中（接口新增，注意并发入口）。

### Step2 — 将写语义分步迁移（单兵安全）
说明：按单兵可执行节奏，把“写语义迁移”拆为两小步，避免一次性破坏多个子系统。

#### Step2A — 仅缓冲 `nodes`
- 改哪些文件：
  - `story_engine.py`：仅将 `p["nodes"].append(...)` 改为 `tx.nodes.append(...)`（build 阶段缓冲 nodes）；不触及其他字段。
- 不改哪些文件：
  - `pending_patches`、`emotional_profile`、`quest_runtime`、`minimap`、`event_manager` 等保持原地写入。
- 回滚策略：
  - 可在 feature 分支中回退或通过特性开关回到原行为；为安全，可先在 canary 玩家/测试分组启用。
- 验证方式：
  - 单元测试：确认在 build 期间 `self.players` 的 `nodes` 未被修改（节点仅在 `tx.nodes`），读接口在 commit 前不可见。
  - 集成/并发测试：模拟并发请求，验证看不到 tx 缓冲的中间节点。
- 风险等级：高→可控（仅影响 graph 对齐点）。

#### Step2B — 缓冲 `pending_patches`（及其 emit）
- 改哪些文件：
  - `story_engine.py`：在 build 阶段把 `p["pending_patches"]` 的写改为写入 `tx.pending_patches`，并在 commit 时合并/emit 到 `p`。
- 不改哪些文件：
  - 其它 runtime 字段仍保留原地写入（除非后续明确拆分）。
- 回滚策略：
  - 分支回退或通过开关禁用 tx 路径；先在少量玩家启用并观察 pending_patches 的最终语义。
- 验证方式：
  - 单元测试：确认 commit 前 `p["pending_patches"]` 未被外部观察到，commit 后行为与原语义一致。
  - 集成测试：检查 patches 被正确 emit 且顺序保持不变。
- 风险等级：中→高（涉及事件发射与副作用）。

### Step3 — 逐步抽出 `committed_state.last_node_id`（最小对齐单元）
说明：不要一次性抽出整个 `committed_state`，先只抽取 `last_node_id`，以建立 graph 层与 commit 对齐的最小可验证事务变量。

- 改哪些文件：
  - `story_engine.py`：引入 `committed_state.last_node_id` 的读写抽象；在 commit 阶段仅更新 `last_node_id`；保留其他字段在 `self.players`。
- 不改哪些文件：
  - 不改 `silence`/`tension`/`phase` 等复杂 domain 字段；不动持久层写入方式（除非后续需要）。
- 回滚策略：
  - 回退到原先直接替换 `self.players` 的方式；先在 canary 环境验证并比对差异日志。
- 验证方式：
  - 单元与集成测试：验证 commit 顺序保证 graph.appendCommitted(tx.nodes) 与 `committed_state.last_node_id` 的对齐。
  - 在 staging 上运行历史回放/一致性检查工具以确认无丢失/重叠节点。
- 风险等级：中（但比抽出全部 committed_state 大幅降低风险）。

### Step4 — 最小化 invariant 集合并實现 abort 路径（Step4A）
说明：不要一次性加全量断言；先实现最关键的 3 条 invariant，减少调试噪音。

#### Step4A — minimal invariants
- 改哪些文件：
  - 在 `Transaction` 中实现 `verifyBuildInvariants()` / `verifyCommitInvariants()`，但初期仅包含三条断言：
    1. `tx.nodes` 非空（若业务期望有节点时）
    2. 节点链连通（每个 node.from 指向前一个 node.id 或 root）
    3. `tx.rootFromNode` 或 root 与 `committed_state.last_node_id` 对齐（root 检查）
- 不改哪些文件：
  - 其余非关键 invariant 暂缓（移至 Phase1.5）。
- 回滚策略：
  - 如果这些断言触发，切回特性开关或在 PR 中临时放宽断言以辅助故障排查，并在 bugfix 分支中修复根因。
- 验证方式：
  - property tests 与边界 case 测试，确保 abort 行为不会留下半提交状态。
  - 在 staging canary 中验证低频异常触发并评估 false-positive。
- 风险等级：中→低（因断言集受限而更易定位问题）。

---

## 回滚与分支策略（总体）
- 所有代码变更按小步提交到 feature 分支 `feature/trng-phase1`，每个子步骤在独立 PR/merge request 中审核与合并。
- 每个 PR 必须包含：单元测试、集成测试、回退脚本（若涉及 DB 变更）、变更说明与启用开关。

## 验证矩阵（简要）
- 单元测试：覆盖 Transaction 构造、build/commit/abort 行为。
- 集成测试：在 staging 上运行 `PHASE1` 开关打开与关闭两套流量，对比结果一致性。
- 回归测试：现有 acceptance tests 必须在开关关闭时 100% 通过。

## 风险总览
- 最大风险：Step2（写语义被改动导致并发/一致性缺陷）。
- 缓解：小步提交、影子写、开关控制、丰富测试覆盖、逐步扩大启用范围（canary）。

## 交付物（每步）
- Step0：配置/环境说明、切换开关文档。
- Step1：`apply()` 接口与 Transaction 定义（API 文档）、一致性回归测试。
- Step2：`tx` 缓冲结构实现、单元与集成测试、canary 部署说明。
- Step3：`committed_state` 子集模型与迁移/兼容说明、staging 验证报告。
- Step4：invariant 列表、abort/回滚实现、property tests 与监控面板设置。

---

备注：此计划遵循“先边界再迁移、先小步再放大”的原则；不包含任何代码改动，供团队评审与批准后切分为 PR。
