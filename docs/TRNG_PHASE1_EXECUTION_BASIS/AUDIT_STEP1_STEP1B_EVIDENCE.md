## Step1b 补强审计证据

下面为 Step1b 的关键变更节选，证明本次补强满足要求：

### `story_engine.apply()`（使用 per-player 非阻塞锁 + abort 审计 + 规范化字段）

```
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
        ...
        snapshot = {
            "tx_id": tx_id,
            "player_id": player_id,
            "root_from_node": root_from_node,
            "timestamp": time.time(),
            "action_type": action_type,
        }

        snapshot_digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True, default=str).encode("utf-8")).hexdigest()

        logger.info("apply_snapshot", extra={
            "tx_id": snapshot["tx_id"],
            "player_id": player_id,
            "root_from_node": root_from_node,
            "snapshot_digest": snapshot_digest,
        })

        try:
            result = self.advance(player_id, world_state, action)
        except Exception as exc:
            error_info = {"type": exc.__class__.__name__, "message": str(exc)}
            logger.exception("apply_aborted", extra={
                "tx_id": snapshot["tx_id"],
                "player_id": player_id,
                "snapshot_digest": snapshot_digest,
                "error": error_info,
            })
            raise

        logger.info("apply_committed", extra={
            "tx_id": snapshot["tx_id"],
            "player_id": player_id,
            "snapshot_digest": snapshot_digest,
        })
        return option, node, patch
    finally:
        p["is_applying"] = False
        if acquired:
            lock.release()
```

### `world_api.py` 的 flag 求值（按请求）

```
def is_trng_phase1_enabled() -> bool:
    """Evaluate feature flag per-request. Default false."""
    return os.environ.get("ENABLE_TRNG_CORE_PHASE1", "false").strip().lower() in {"1", "true", "on", "yes"}

# ...
if is_trng_phase1_enabled():
    option, node, patch = story_engine.apply(player_id, new_state, act)
else:
    option, node, patch = story_engine.advance(player_id, new_state, act)
```

### `scripts/step1_verify.py`（新增并发与 abort 测试节选）

```
def test_concurrency_smoke():
    # monkeypatch advance to be slow, start two threads calling apply
    # expect one success and one busy

def test_abort_logging():
    # monkeypatch advance to raise
    # call apply and assert apply_aborted log present
```

---

当前变更已提交到本地分支 `feature/trng-phase1`（commit: `feat(trng): step1b harden apply shell (lock + abort audit + flag eval)`）。

如需我将分支推送并在远程打开 PR（包含 Step1b 说明），请确认，我会推送并创建草拟 PR。
