# backend/app/core/ai/deepseek_agent.py
from __future__ import annotations

import os
import json
import time
import random
import hashlib
import threading
from collections import OrderedDict
from concurrent.futures import Future, TimeoutError
from queue import Full, Queue
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY", "")
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
MODEL = os.getenv("OPENAI_MODEL", "deepseek-chat")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}" if API_KEY else "",
    "Content-Type": "application/json",
}

CONNECT_TIMEOUT = float(os.getenv("DEEPSEEK_CONNECT_TIMEOUT", "6"))
READ_TIMEOUT = float(os.getenv("DEEPSEEK_READ_TIMEOUT", "12"))
MAX_RETRIES = int(os.getenv("DEEPSEEK_MAX_RETRIES", "2"))
RETRY_BACKOFF = float(os.getenv("DEEPSEEK_RETRY_BACKOFF", "1.5"))

print(
    "[AI INFO] LLM config:",
    {
        "base_url": BASE_URL,
        "model": MODEL,
        "connect_timeout": CONNECT_TIMEOUT,
        "read_timeout": READ_TIMEOUT,
        "max_retries": MAX_RETRIES,
        "retry_backoff": RETRY_BACKOFF,
    },
    flush=True,
)

AI_RETRY_ON_TIMEOUT = os.getenv("IDEAL_CITY_AI_RETRY_ON_TIMEOUT", "0").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
AI_TIMEOUT_DEADLINE = float(os.getenv("IDEAL_CITY_AI_TIMEOUT_DEADLINE", "12"))

AI_DISABLED = os.getenv("IDEAL_CITY_AI_DISABLE", "").lower() in {"1", "true", "yes", "on"}
AI_FAILURE_THRESHOLD = max(1, int(os.getenv("IDEAL_CITY_AI_FAILURE_THRESHOLD", "1")))
AI_CIRCUIT_SECONDS = float(os.getenv("IDEAL_CITY_AI_CIRCUIT_SECONDS", "120"))

_lock = threading.Lock()
_LAST_CALL_TS: Dict[str, float] = {}
MAX_CACHE_SIZE = int(os.getenv("DEEPSEEK_CACHE_SIZE", str(128)))
CACHE_LOG_INTERVAL = max(0, int(os.getenv("DEEPSEEK_CACHE_LOG_INTERVAL", "50")))

AI_RATE_PER_SEC = float(os.getenv("IDEAL_CITY_AI_RATE_PER_SEC", "1.5"))
AI_RATE_BURST = max(1.0, float(os.getenv("IDEAL_CITY_AI_RATE_BURST", "3")))
AI_QUEUE_MAXSIZE = int(os.getenv("IDEAL_CITY_AI_QUEUE_MAXSIZE", "32"))
AI_QUEUE_ENQUEUE_TIMEOUT = float(os.getenv("IDEAL_CITY_AI_QUEUE_ENQUEUE_TIMEOUT", "0.15"))
AI_QUEUE_RESULT_TIMEOUT = float(os.getenv("IDEAL_CITY_AI_QUEUE_RESULT_TIMEOUT", "45"))
AI_MAX_BACKOFF = float(os.getenv("IDEAL_CITY_AI_MAX_BACKOFF", "12"))

_circuit_lock = threading.Lock()
_failure_state: Dict[str, float | int] = {"count": 0, "open_until": 0.0}

# ⭐ 最重要：缩短冷却时间
MIN_INTERVAL = 0.6

SYSTEM_PROMPT = """
你的身份是《创造之城（The City of Invention）》世界线的“造物记录官（Story + World God）”。
只能输出 JSON，不允许任何解释文字。

世界观要点：
- 灵感来自文艺复兴早期，社会鼓励用创造回应真实问题。
- 玩家被期待理解并缓解城市、人-自然、资源秩序等矛盾，而非追求效率或力量。
- 自然语言是设计笔记与推理过程，需不断审视假设、限制、风险与长效影响。
- 世界只接受真正回应问题的创造，并会记录带来的结构或态度变化。

生成要求：
- node {title,text}
- world_patch {mc:{...}, variables:{...}}
- 语气需体现“创造之城”对负责任发明的尊重与追问。
- 若题面或玩家输入缺少上下文，要主动提醒或提出问题引导补充。
- 避免把玩家传送进方块内部，避免窒息或掉入虚空。
- 若出现 NPC/人物/动物 → 必须 spawn
"""

def _make_cache_key(context, messages_tail):
    key_payload = {"context": context, "messages_tail": messages_tail[-8:]}
    s = json.dumps(key_payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(s.encode()).hexdigest()


def _make_generic_cache_key(
    context: Optional[Dict[str, Any]],
    messages: List[Dict[str, str]],
    *,
    temperature: float,
    response_format: Optional[Dict[str, Any]],
) -> str:
    key_payload = {
        "context": context,
        "messages_tail": messages[-8:],
        "temperature": round(float(temperature), 3),
        "response_format": response_format,
    }
    s = json.dumps(key_payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(s.encode()).hexdigest()

class _LRUCache:
    def __init__(self, maxsize: int) -> None:
        self._data: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        self._lock = threading.Lock()
        self.maxsize = maxsize
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                self.hits += 1
                return self._data[key]
            self.misses += 1
            return None

    def put(self, key: str, value: Dict[str, Any]) -> None:
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = value
            if len(self._data) > self.maxsize:
                self._data.popitem(last=False)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "size": len(self._data),
                "hits": self.hits,
                "misses": self.misses,
                "maxsize": self.maxsize,
            }


class _TokenBucket:
    def __init__(self, rate_per_sec: float, burst: float) -> None:
        self.rate = max(0.1, rate_per_sec)
        self.capacity = max(self.rate, burst)
        self.tokens = self.capacity
        self.updated = time.monotonic()
        self._lock = threading.Lock()

    def _refill_locked(self, now: float) -> None:
        elapsed = max(0.0, now - self.updated)
        if elapsed <= 0:
            return
        refill = elapsed * self.rate
        if refill > 0:
            self.tokens = min(self.capacity, self.tokens + refill)
            self.updated = now

    def consume(self, tokens: float = 1.0) -> bool:
        now = time.monotonic()
        with self._lock:
            self._refill_locked(now)
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def wait_time(self, tokens: float = 1.0) -> float:
        with self._lock:
            now = time.monotonic()
            self._refill_locked(now)
            if self.tokens >= tokens:
                return 0.0
            needed = tokens - self.tokens
            return needed / self.rate


class _DeepseekTask:
    __slots__ = ("future", "payload", "connect_timeout", "read_timeout")

    def __init__(self, future: Future, payload: Dict[str, Any], connect_timeout: float, read_timeout: float) -> None:
        self.future = future
        self.payload = payload
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout


class _DeepseekDispatcher:
    def __init__(self, bucket: _TokenBucket) -> None:
        self.bucket = bucket
        self.queue: Queue[_DeepseekTask] = Queue(maxsize=AI_QUEUE_MAXSIZE)
        self._workers: List[threading.Thread] = []
        self._stop_event = threading.Event()
        workers = max(1, int(os.getenv("IDEAL_CITY_AI_QUEUE_WORKERS", "1")))
        for idx in range(workers):
            worker = threading.Thread(target=self._worker, name=f"deepseek-dispatcher-{idx}", daemon=True)
            worker.start()
            self._workers.append(worker)

    def submit(self, payload: Dict[str, Any], connect_timeout: float, read_timeout: float) -> Dict[str, Any]:
        future: Future = Future()
        task = _DeepseekTask(future, payload, connect_timeout, read_timeout)
        try:
            self.queue.put(task, timeout=AI_QUEUE_ENQUEUE_TIMEOUT)
        except Full:
            raise RuntimeError("deepseek_queue_full")
        try:
            return future.result(timeout=AI_QUEUE_RESULT_TIMEOUT)
        except TimeoutError as exc:
            raise RuntimeError("deepseek_queue_wait_timeout") from exc

    def _worker(self) -> None:
        while not self._stop_event.is_set():
            task = self.queue.get()
            if task is None:
                self.queue.task_done()
                return
            try:
                self._dispatch_task(task)
            finally:
                self.queue.task_done()

    def _dispatch_task(self, task: _DeepseekTask) -> None:
        waited = 0.0
        while not self.bucket.consume():
            sleep_for = min(self.bucket.wait_time(), 0.5)
            waited += sleep_for
            if waited > AI_QUEUE_RESULT_TIMEOUT:
                task.future.set_exception(RuntimeError("deepseek_rate_wait_timeout"))
                return
            time.sleep(max(0.01, sleep_for))
        try:
            result = _call_deepseek_api_sync(task.payload, task.connect_timeout, task.read_timeout)
            task.future.set_result(result)
        except Exception as exc:  # noqa: BLE001
            task.future.set_exception(exc)


_LRU = _LRUCache(MAX_CACHE_SIZE)
_REQUEST_BUCKET = _TokenBucket(AI_RATE_PER_SEC, AI_RATE_BURST)
_DISPATCHER = _DeepseekDispatcher(_REQUEST_BUCKET)


def _maybe_log_cache(event: str) -> None:
    if CACHE_LOG_INTERVAL <= 0:
        return
    stats = _LRU.stats()
    total = stats["hits"] + stats["misses"]
    if total and (total % CACHE_LOG_INTERVAL == 0):
        print(
            f"[AI INFO] DeepSeek cache {event}: hits={stats['hits']} misses={stats['misses']} size={stats['size']}/{stats['maxsize']}"
        )


def _circuit_status(now: Optional[float] = None) -> Tuple[bool, Optional[str]]:
    if AI_DISABLED:
        return True, "ai_disabled"
    current = now or time.time()
    with _circuit_lock:
        open_until = float(_failure_state.get("open_until", 0.0))
        if current < open_until:
            return True, "circuit_open"
    return False, None


def _record_success() -> None:
    with _circuit_lock:
        _failure_state["count"] = 0
        _failure_state["open_until"] = 0.0


def _record_failure(now: Optional[float] = None) -> None:
    current = now or time.time()
    with _circuit_lock:
        count = int(_failure_state.get("count", 0)) + 1
        if count >= AI_FAILURE_THRESHOLD:
            open_until = current + AI_CIRCUIT_SECONDS
            _failure_state["open_until"] = open_until
            _failure_state["count"] = 0
            print(
                f"[AI WARN] DeepSeek circuit open for {AI_CIRCUIT_SECONDS:.0f}s after repeated failures."
            )
        else:
            _failure_state["count"] = count


def _bypass_reason() -> Optional[str]:
    opened, reason = _circuit_status()
    if opened:
        return reason or "circuit_open"
    return None


def _call_deepseek_api_sync(
    payload: Dict[str, Any],
    connect_timeout: float = CONNECT_TIMEOUT,
    read_timeout: float = READ_TIMEOUT,
) -> Dict[str, Any]:
    last_error: Exception | None = None
    failure_recorded = False
    start_time = time.monotonic()
    effective_connect_timeout = connect_timeout
    effective_read_timeout = read_timeout
    if AI_TIMEOUT_DEADLINE > 0:
        # Keep per-request timeouts bounded by the overall deadline so we fail fast.
        effective_connect_timeout = min(connect_timeout, max(1.0, AI_TIMEOUT_DEADLINE * 0.5))
        effective_read_timeout = min(read_timeout, max(2.0, AI_TIMEOUT_DEADLINE))

    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.post(
                f"{BASE_URL}/chat/completions",
                headers=HEADERS,
                json=payload,
                timeout=(effective_connect_timeout, effective_read_timeout),
            )
            resp.raise_for_status()
            body = resp.json()
            content = body["choices"][0]["message"]["content"]
            result = json.loads(content)
            _record_success()
            return result
        except requests.Timeout as exc:
            last_error = exc
            print(f"[AI WARN] DeepSeek timeout attempt {attempt + 1}: {exc}")
            if not AI_RETRY_ON_TIMEOUT:
                _record_failure()
                failure_recorded = True
                break
        except requests.RequestException as exc:
            last_error = exc
            status = getattr(exc.response, "status_code", "?")
            print(
                f"[AI WARN] DeepSeek HTTP error attempt {attempt + 1}"
                f" (status={status}): {exc}"
            )
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            print(f"[AI WARN] DeepSeek parse error attempt {attempt + 1}: {exc}")

        if attempt < MAX_RETRIES:
            base_delay = RETRY_BACKOFF * (2**attempt)
            capped_delay = min(AI_MAX_BACKOFF, base_delay)
            jitter = random.uniform(0, capped_delay * 0.25)
            sleep_seconds = capped_delay + jitter
            time.sleep(max(0.05, sleep_seconds))

        if AI_TIMEOUT_DEADLINE > 0:
            elapsed = time.monotonic() - start_time
            if elapsed >= AI_TIMEOUT_DEADLINE:
                print(
                    f"[AI WARN] DeepSeek aborting after {elapsed:.1f}s without success (deadline {AI_TIMEOUT_DEADLINE}s)."
                )
                break

    if last_error:
        print("[AI ERROR] DeepSeek failed after retries:", last_error)
        if not failure_recorded:
            _record_failure()
        raise last_error
    raise RuntimeError("DeepSeek request failed without specific error")


def _call_deepseek_api(
    payload: Dict[str, Any],
    connect_timeout: float = CONNECT_TIMEOUT,
    read_timeout: float = READ_TIMEOUT,
) -> Dict[str, Any]:
    return _DISPATCHER.submit(payload, connect_timeout, read_timeout)


def deepseek_decide(context, messages_history):

    player_id = str(context.get("player_id") or "global")

    reason = _bypass_reason()
    if reason:
        print(f"[AI INFO] DeepSeek bypassed ({reason}); returning static response.")
        return {
            "option": None,
            "node": {
                "title": "创造之城 · 静默",
                "text": "AI 服务暂时不可用，档案馆会继续记录手动进度。",
            },
            "world_patch": {"variables": {}, "mc": {}},
        }

    # ⭐ 节流：改成 0.6 秒
    now = time.time()
    last = _LAST_CALL_TS.get(player_id, 0.0)
    if (now - last) < MIN_INTERVAL:
        return {
            "option": None,
            "node": {
                "title": "创造之城 · 静默帧",
                "text": "夜风掠过观察塔，灵感尚在酝酿。"
            },
            "world_patch": {"variables": {}, "mc": {}}
        }

    # ⭐ 缓存命中
    key = _make_cache_key(context, messages_history)
    cached = _LRU.get(key)
    if cached:
        _LAST_CALL_TS[player_id] = now
        _maybe_log_cache("hit")
        return cached

    # ⭐ 无 API KEY → 本地占位剧情
    if not API_KEY:
        return {
            "option": None,
            "node": {
                "title": "创造之城 · 本地风声",
                "text": "（未配置 AI 密钥，使用占位剧情）"
            },
            "world_patch": {"variables": {}, "mc": {}}
        }

    # ⭐ 真正请求 DeepSeek
    user_prompt = f"""
    根据玩家输入与历史剧情生成下一步剧情。
    只输出 JSON：
    {{
      "option": ...,
      "node": {{ "title": "...", "text": "..." }},
      "world_patch": {{
         "variables": {{}},
         "mc": {{}}
      }}
    }}
    context = {json.dumps(context, ensure_ascii=False)}
    """

    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    msgs += messages_history[-12:]
    msgs.append({"role": "user", "content": user_prompt})

    payload = {
        "model": MODEL,
        "messages": msgs,
        "temperature": 0.8,
        "response_format": {"type": "json_object"},
    }

    try:
        parsed = _call_deepseek_api(payload, CONNECT_TIMEOUT, READ_TIMEOUT)
        _LRU.put(key, parsed)
        _maybe_log_cache("fill")
        _LAST_CALL_TS[player_id] = time.time()
        return parsed

    except Exception as e:
        print("[AI ERROR]", e)
        _LAST_CALL_TS[player_id] = time.time()
        return {
            "option": None,
            "node": {"title": "创造之城 · 静默", "text": "AI 一时沉默，但工坊的灯火仍在跳跃。"},
            "world_patch": {"variables": {}, "mc": {"tell": "AI 出错，使用安全剧情"}},
        }


def call_deepseek(
    context: Optional[Dict[str, Any]],
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    response_format: Optional[Dict[str, Any]] = None,
    *,
    connect_timeout: Optional[float] = None,
    read_timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """Generic DeepSeek API wrapper used by story/world tools."""

    reason = _bypass_reason()
    if reason:
        return {
            "response": json.dumps(
                {
                    "error": reason,
                    "context": context or {},
                    "fallback": True,
                },
                ensure_ascii=False,
            ),
            "parsed": None,
            "bypassed": True,
        }

    if not API_KEY:
        return {
            "response": json.dumps(
                {"error": "missing_api_key", "context": context or {}},
                ensure_ascii=False,
            )
        }

    payload_messages: List[Dict[str, str]] = []
    if context:
        ctx_json = json.dumps(context, ensure_ascii=False)
        payload_messages.append({"role": "system", "content": f"上下文:\n{ctx_json}"})
    payload_messages.extend(messages)

    payload = {
        "model": MODEL,
        "messages": payload_messages,
        "temperature": temperature,
    }
    if response_format is not None:
        payload["response_format"] = response_format
    else:
        payload["response_format"] = {"type": "json_object"}

    timeout_connect = CONNECT_TIMEOUT if connect_timeout is None else connect_timeout
    timeout_read = READ_TIMEOUT if read_timeout is None else read_timeout

    disable_cache = bool((context or {}).get("ai_disable_cache"))
    for msg in messages:
        if getattr(msg, "get", None) and msg.get("no_cache"):
            disable_cache = True
            break

    cache_key = None
    if not disable_cache:
        cache_key = _make_generic_cache_key(context, payload_messages, temperature=temperature, response_format=payload.get("response_format"))
        cached = _LRU.get(cache_key)
        if cached is not None:
            _maybe_log_cache("hit")
            return cached

    try:
        parsed = _call_deepseek_api(payload, timeout_connect, timeout_read)
        if isinstance(parsed, (dict, list)):
            response_text = json.dumps(parsed, ensure_ascii=False)
        else:
            response_text = str(parsed)
        result = {"response": response_text, "parsed": parsed}
        if cache_key:
            _LRU.put(cache_key, result)
            _maybe_log_cache("fill")
        return result
    except Exception as exc:
        print("[AI ERROR] call_deepseek failed:", exc)
        return {
            "response": json.dumps(
                {"error": str(exc), "context": context or {}}, ensure_ascii=False
            )
        }