## Step1 审计证据 (自动生成)

下面是为 Step1（`apply()` 事务壳）变更所收集的原始 git 输出与片段，证明变更范围与可逆性（未修改 `advance()` 实现）。

**分支**:

```
feature/trng-phase1
```

**最近提交（top 5）**:

```
e345dc6e3316f313cbf13f7210130eb1be2c37e0 (HEAD -> feature/trng-phase1) docs(trng): add PR draft for Step1
8c0d3af414564a42ef1b9db285bac3fa69dea65a feat(trng): step1 apply shell (reentrancy + snapshot)
749ad121667e4f5326b027d976acd726d6194116 (origin/scienceline, scienceline) docs(trng): refine Implementation Plan for single-dev (2A/2B, last_node_id, minimal invariants)
e55ca525a764183aca616f09c17ce8e38047f6ba (tag: trng-phase1-doc-freeze) docs(trng): freeze Phase1 MAPPING/SPEC/VERIFY (anchors verified)
bbb0bded17ee198daa3947e0d3b7b6d40598d05a docs: add MissionControlLive TRNG vs Drift mapping
```

**HEAD~2..HEAD 修改的文件清单**:

```
backend/app/api/world_api.py
backend/app/core/story/story_engine.py
docs/TRNG_PHASE1_EXECUTION_BASIS/PHASE1_MC_CAUSAL_MODEL.md
docs/TRNG_PHASE1_EXECUTION_BASIS/PR_DRAFT_STEP1.md
docs/TRNG_PHASE1_EXECUTION_BASIS/PR_TEMPLATE_STEP1.md
docs/TRNG_PHASE1_EXECUTION_BASIS/README.md
scripts/step1_verify.py
```

---

### backend/app/core/story/story_engine.py 的变更（节选 diff）

```
*** diff (片段) ***
 @@
 +import uuid
 +import json
 +import hashlib
 @@
  -                "memory_flags": set(),
  +                "memory_flags": set(),
  +                "is_applying": False,
 @@
  +    def apply(self, player_id: str, world_state: Dict[str, Any], action: Dict[str, Any]):
  +        """Phase1 apply shell: per-player reentrancy guard + snapshot_before digest + delegate to existing advance().
  +        Behavior: if another apply is active for the same player, reject with busy response.
  +        This method MUST NOT modify `advance()` implementation.
  +        Returns the same tuple as `advance`: (option, node, patch)
  +        """
  +        self._ensure_player(player_id)
  +        p = self.players[player_id]
  +
  +        # Reentrancy guard (reject strategy)
  +        if p.get("is_applying"):
  +            logger.info("apply_rejected_busy", extra={"player_id": player_id})
  +            return None, None, {"mc": {"tell": "Busy: apply already in progress"}}
  +
  +        # Mark as applying
  +        p["is_applying"] = True
  +        try:
  +            # Create minimal snapshot_before
  +            snapshot = {
  +                "player_id": player_id,
  +                "last_node_id": (p.get("nodes")[-1].get("id") if p.get("nodes") else None),
  +                "timestamp": time.time(),
  +                "event_id": str(uuid.uuid4()),
  +            }
  +
  +            # Compute digest
  +            try:
  +                snapshot_json = json.dumps(snapshot, sort_keys=True, default=str)
  +                digest = hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest()
  +            except Exception:
  +                digest = str(uuid.uuid4())
  +
  +            # Audit log (structured)
  +            logger.info("apply_snapshot", extra={"player_id": player_id, "snapshot": snapshot, "snapshot_digest": digest})
  +            # Delegate to existing advance() — do not change advance internals
  +            result = self.advance(player_id, world_state, action)
  +
  +            try:
  +                option, node, patch = result
  +            except Exception:
  +                raise
  +
  +            tx_record = {"tx_id": snapshot["event_id"], "player_id": player_id, "snapshot_digest": digest}
  +            logger.info("apply_committed", extra={"player_id": player_id, "tx": tx_record})
  +            return option, node, patch
  +        finally:
  +            p["is_applying"] = False
```

（注：上面为仓库 diff 中的新增部分；`advance()` 方法体在同一次提交中未被修改。）

---

### backend/app/api/world_api.py 的变更（节选 diff）

```
*** diff (片段) ***
 +# Feature flag for Phase1 TRNG apply shell
 +ENABLE_TRNG_CORE_PHASE1 = os.environ.get("ENABLE_TRNG_CORE_PHASE1", "false").strip().lower() in {"1", "true", "on", "yes"}
 @@
  -        option, node, patch = story_engine.advance(player_id, new_state, act)
  +        # Phase1: optionally route through story_engine.apply() which wraps advance()
  +        if ENABLE_TRNG_CORE_PHASE1:
  +            option, node, patch = story_engine.apply(player_id, new_state, act)
  +        else:
  +            option, node, patch = story_engine.advance(player_id, new_state, act)
```

默认行为：`ENABLE_TRNG_CORE_PHASE1` 环境变量未设置或为 false，则走 `advance()` 路径（对回滚/可逆性友好）。

---

### scripts/step1_verify.py（新增文件，节选）

```
（文件新增，包含下列测试）
- V1: apply vs advance 等价性（fresh player）
- Reentrancy: 当 `is_applying=True` 时，`apply()` 返回 busy 模式的补丁
- Snapshot: `apply()` 会记录 `apply_snapshot` 日志
```

完整文件已添加至 `scripts/step1_verify.py`，用于本地最小验证（不作为 CI 强制）。

---

### `advance()` 位置（证据）

```
backend/app/core/story/story_engine.py:1660:    def advance(
```

如上所示，`advance()` 位于文件中（行号会随仓库状态变化），在 Step1 的提交范围内未被修改（diff 仅包含新增 `apply()`、若干 import 与 player state 字段）。

---

结论：

- 已在 `backend/app/core/story/story_engine.py` 中添加 `apply()` 事务壳，实现了单玩家重入保护、快照摘要记录，并在结束时委派回现有的 `advance()`。 
- `backend/app/api/world_api.py` 增加了基于环境变量的特性开关 `ENABLE_TRNG_CORE_PHASE1`，默认关闭，保证回滚与可逆性。
- 变更已提交到本地分支 `feature/trng-phase1`（详见上方提交记录）。

如需我把该分支推送到远程并打开 PR（或将此证据文件合并到文档分支），请回复确认。
