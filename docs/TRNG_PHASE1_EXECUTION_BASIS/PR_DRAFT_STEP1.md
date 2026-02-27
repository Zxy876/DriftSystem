# PR Draft: Step1 — 插入事务壳（apply shell + reentrancy + snapshot）

Branch: `feature/trng-phase1`

## 对应 Implementation Plan
引用: docs/TRNG_PHASE1_EXECUTION_BASIS/PHASE1_IMPLEMENTATION_PLAN.md — Step1

## 修改文件
- backend/app/core/story/story_engine.py  (新增 `apply()` shell, `_apply_locks`, abort audit, 规范化审计字段)
- backend/app/api/world_api.py  (在 `/world/apply` 路由中按请求评估 feature flag)
- scripts/step1_verify.py  (本地最小化验证脚本：V1/Reentrancy/Snapshot + 并发/异常审计测试)
- docs/TRNG_PHASE1_EXECUTION_BASIS/PHASE1_MC_CAUSAL_MODEL.md (文档补充)
- docs/TRNG_PHASE1_EXECUTION_BASIS/README.md (SSoT 与禁止修改列表补充)
- docs/TRNG_PHASE1_EXECUTION_BASIS/PR_TEMPLATE_STEP1.md (VERIFY 部分调整)

## 不修改文件
- `backend/app/core/story/story_engine.py` 的 `advance()` 函数主体逻辑未改动（严格禁止修改）
- `backend/app/core/story/story_graph.py`, `backend/app/core/ideal_city/*`, `quest_runtime`, `minimap`, `event_manager` 等均未改动

## Feature Flag 行为
- Flag: `ENABLE_TRNG_CORE_PHASE1`（环境变量，默认 `false`）
- OFF: 当前行为不变，API 调用走 `story_engine.advance()`（原路径）
- ON: `/world/apply` 会调用 `story_engine.apply()`（新壳），该方法执行 per-player 重入拒绝、snapshot_before 记录并 delegate 到 `advance()`；最终输出与直接调用 `advance()` 等价

## Step1b（本次补强）说明

为了在真实多 worker / 多线程部署下保证 Step1 的可审计性与正确性，本次补强（Step1b）做了以下硬化（仍属于 Step1 范围）：

- 使用 `threading.Lock` 的 per-player 非阻塞锁（`_apply_locks`）替代单纯的布尔标记，避免并发竞态。
- 在 `apply()` 内对 `advance()` 的异常路径增加 `apply_aborted` 审计日志，包含 `tx_id`、`snapshot_digest` 与 `error` 字段，之后重新抛出异常。
- 规范化审计字段：`tx_id`、`player_id`、`root_from_node`、`timestamp`、`action_type`，并使用 `snapshot_digest` 作为摘要索引。
- 将 feature flag 的求值从模块导入时固定改为按请求求值（`is_trng_phase1_enabled()`），便于运行时切换与测试注入。
- Busy 响应增加可机读的 `meta` 字段：`{"meta": {"status": "busy", "code": "APPLY_REENTRANT"}}`，客户端/测试端可据此判定重入拒绝。

这些改动遵守严格规则：未改动 `advance()` 逻辑，仅变更 `apply()` 壳层、API 的 flag 求值与验证脚本。

## VERIFY 覆盖（如何运行)
- V1: 等价性
  - 运行 `python3 scripts/step1_verify.py`（会在本地运行 V1/Reentrancy/Snapshot/Concurrency/Abort 五项测试）
  - V1: 确认 `advance()` 与 `apply()` 在相同初始 snapshot 下返回相同输出
- Reentrancy test
  - 在 `scripts/step1_verify.py` 中验证当 `is_applying=True` 时第二次 `apply()` 被拒绝且返回 `meta.status=busy`
- Snapshot test
  - `scripts/step1_verify.py` 会捕获日志并检查存在 `apply_snapshot` 记录（包含 `snapshot_digest` 与 `tx_id`）
- Concurrency smoke
  - 模拟两个并发 `apply()`，断言一个成功一个返回 busy
- Abort logging
  - 模拟 `advance()` 抛出异常，断言 `apply_aborted` 日志出现并包含 `error` 字段

## 不变量变化
- 无（Step1 仅插入壳并记录 snapshot，不引入新的 invariant 校验）

## 回滚方式
- revert 提交或关闭 feature flag（`ENABLE_TRNG_CORE_PHASE1=false`）即可回退到原行为

## Commit message
- `feat(trng): step1b harden apply shell (lock + abort audit + flag eval)`
