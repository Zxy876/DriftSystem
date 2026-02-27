# PR Draft: Step1 — 插入事务壳（apply shell + reentrancy + snapshot）

Branch: `feature/trng-phase1`

## 对应 Implementation Plan
引用: docs/TRNG_PHASE1_EXECUTION_BASIS/PHASE1_IMPLEMENTATION_PLAN.md — Step1

## 修改文件
- backend/app/core/story/story_engine.py  (新增 `apply()` shell, `is_applying` flag, snapshot logging)
- backend/app/api/world_api.py  (在 `/world/apply` 路由中根据 feature flag 调用 `story_engine.apply`)
- scripts/step1_verify.py  (本地最小化验证脚本：V1/Reentrancy/Snapshot)
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

## VERIFY 覆盖（如何运行）
- V1: 等价性
  - 运行 `python3 scripts/step1_verify.py`（会在本地运行 V1/Reentrancy/Snapshot 三项测试）
  - V1: 确认 `advance()` 与 `apply()` 在相同初始 snapshot 下返回相同输出
- Reentrancy test
  - 在 `scripts/step1_verify.py` 中验证当 `is_applying=True` 时第二次 `apply()` 被拒绝
- Snapshot test
  - `scripts/step1_verify.py` 会捕获日志并检查存在 `apply_snapshot` 记录（包含 snapshot_digest 与 tx_id）

## 不变量变化
- 无（Step1 仅插入壳并记录 snapshot，不引入新的 invariant 校验）

## 回滚方式
- revert 提交或关闭 feature flag（`ENABLE_TRNG_CORE_PHASE1=false`）即可回退到原行为

## Commit message
- `feat(trng): step1 apply shell (reentrancy + snapshot)`
