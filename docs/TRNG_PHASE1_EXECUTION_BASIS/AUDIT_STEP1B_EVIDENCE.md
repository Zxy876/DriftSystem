# Step1b 审计证据（完整片段）

说明：下列片段展示了 `apply()` 的完整控制流（非阻塞 per-player lock -> snapshot -> 委派 -> commit/abort 审计 -> finally 释放锁），并列出 `world_api` 的按请求 flag 求值以及 `scripts/step1_verify.py` 的入口片段。文件路径与近似行号已标注，便于审查。

---

**文件**: backend/app/core/story/story_engine.py (approx [L600-L740])

--- 片段开始 ---

```python
    def apply(self, player_id: str, world_state: Dict[str, Any], action: Dict[str, Any]):
        """Phase1 apply shell (Step1b hardened):

        - Non-blocking per-player lock to avoid races across threads/workers
        - Normalized audit schema for snapshot/commit/abort
        - Delegate to existing advance() without changing its body

        Returns the same tuple as `advance`: (option, node, patch)
        """
        self._ensure_player(player_id)
        p = self.players[player_id]

        # Obtain or create per-player lock
        lock = self._apply_locks.setdefault(player_id, threading.Lock())

        acquired = lock.acquire(blocking=False)
        if not acquired:
            logger.info("apply_rejected_busy", extra={"player_id": player_id})
            busy_patch = {
                "mc": {"tell": "Busy: apply already in progress"},
                "meta": {"status": "busy", "code": "APPLY_REENTRANT"},
            }
            return None, None, busy_patch

        # We hold the lock; optional debug flag
        p["is_applying"] = True
        tx_id = str(uuid.uuid4())
        try:
            # Build resilient root_from_node helper
            root_from_node = None
            try:
                nodes = p.get("nodes")
                if isinstance(nodes, (list, tuple)) and nodes:
                    last = nodes[-1]
                    if isinstance(last, dict):
                        root_from_node = last.get("id")
                    else:
                        root_from_node = getattr(last, "id", None)
            except Exception:
                root_from_node = None

            # Determine action_type
            action_type = None
            if isinstance(action, dict):
                action_type = action.get("type")
                if not action_type and action.get("say"):
                    action_type = "say"

            snapshot = {
                "tx_id": tx_id,
                "player_id": player_id,
                "root_from_node": root_from_node,
                "timestamp": time.time(),
                "action_type": action_type,
            }

            # Compute digest from compact snapshot
            try:
                snapshot_json = json.dumps(snapshot, sort_keys=True, default=str)
                snapshot_digest = hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest()
            except Exception:
                snapshot_digest = str(uuid.uuid4())

            # Audit: snapshot (stable schema)
            logger.info("apply_snapshot", extra={
                "tx_id": snapshot["tx_id"],
                "player_id": player_id,
                "root_from_node": root_from_node,
                "snapshot_digest": snapshot_digest,
            })

            # Delegate to existing advance(); capture exceptions to emit abort audit
            try:
                result = self.advance(player_id, world_state, action)
            except Exception as exc:
                # Abort audit with normalized error info, then re-raise
                error_info = {"type": exc.__class__.__name__, "message": str(exc)}
                logger.exception("apply_aborted", extra={
                    "tx_id": snapshot["tx_id"],
                    "player_id": player_id,
                    "snapshot_digest": snapshot_digest,
                    "error": error_info,
                })
                raise

            # On success, emit committed audit
            try:
                option, node, patch = result
            except Exception:
                # If result unpacking fails, treat as error (re-raise)
                raise

            logger.info("apply_committed", extra={
                "tx_id": snapshot["tx_id"],
                "player_id": player_id,
                "snapshot_digest": snapshot_digest,
            })

            return option, node, patch
        finally:
            p["is_applying"] = False
            try:
                if acquired:
                    lock.release()
            except Exception:
                logger.exception("apply_lock_release_failed", extra={"player_id": player_id})
```

--- 片段结束 ---

**文件**: backend/app/api/world_api.py (approx [L110-L126] for flag, [L536-L546] for usage)

```python
def is_trng_phase1_enabled() -> bool:
    """Evaluate feature flag per-request. Default false."""
    return os.environ.get("ENABLE_TRNG_CORE_PHASE1", "false").strip().lower() in {"1", "true", "on", "yes"}

# ...
if is_trng_phase1_enabled():
    option, node, patch = story_engine.apply(player_id, new_state, act)
else:
    option, node, patch = story_engine.advance(player_id, new_state, act)
```

**文件**: scripts/step1_verify.py (entrypoint)

```python
if __name__ == "__main__":
    test_v1_equivalence()
    test_reentrancy()
    test_snapshot_logging()
    test_concurrency_smoke()
    test_abort_logging()
    print("All Step1 verifications passed.")
```

---

证据：`advance()` 未被修改（示例命令与说明）

在仓库根运行下列命令可以展示 `advance()` 在本次变更区间没有变动（只截取 `def advance` 段以便审阅）：

```bash
# 在 repo 根执行：
# 比较最近一次提交与其父提交（根据你的提交历史可能需要调整 base..head）
git diff HEAD~1..HEAD -- backend/app/core/story/story_engine.py | sed -n '/def advance/,/def /p'
```

- 期望输出：无差异（即没有以 `-` 或 `+` 开头的行包含 `def advance` 的实现），表示 `advance()` 实现未改动。

---

请确认我可以把这些变更归档到一个 PR（草稿）并在 PR 描述中包含上面证据与 README 链接；按你的指示我将先不推送，等你确认再推送并打开 Draft PR。若需我现在把本地的 `git diff ...` 输出直接嵌入此文件，请回复，我会追加具体命令输出片段（只贴少量行以便审阅）。
