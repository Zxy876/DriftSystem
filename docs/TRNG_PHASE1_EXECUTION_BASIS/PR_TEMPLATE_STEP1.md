# Step1 - 插入事务壳（apply 壳 + reentrancy + snapshot）

## 对应 Implementation Plan
引用: docs/TRNG_PHASE1_EXECUTION_BASIS/PHASE1_IMPLEMENTATION_PLAN.md — Step1

## 修改文件
- （列出将被修改的文件路径）

## 不修改文件
- advance() 的内部实现（暂不改）
- story_graph.py / 持久层代码（不改）

## Feature Flag 行为
- ON: `ENABLE_TRNG_CORE_PHASE1` 打开后，API 入口路由经 `apply(event)` 代理到新 Transaction 壳；内部仍调用 `advance()`（无行为变更）。
- OFF: 路径回退到原始 `advance()` 直接执行行为（完全回退）。

## VERIFY 覆盖（Step1）
- V1: apply(event) 路径与 `advance()` 输出一致（单元测试与集成测试）。
- Reentrancy test: 同一 `player_id` 连续触发两次 `apply` 时，第二次应被拒绝或安全排队（并在日志中记录）。
- Snapshot test: `apply(event)` 入口必须创建 `snapshot_before`（记录 digest 或快照日志以便审计/回放）。

## 不变量变化
- 当前实现保证：
  - per-player reentrancy guard（`is_applying`）
  - 在入口处 snapshot_before 的创建
  - build 阶段的写入仅限 tx（暂不改变 advance 行为实质）

## 回滚方式
- revert commit 即可；Feature Flag 关闭后恢复原行为。
