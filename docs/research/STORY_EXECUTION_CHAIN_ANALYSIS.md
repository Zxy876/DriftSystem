# Story 执行链路分析报告

> **扫描时间**：2026-02-26  
> **扫描模式**：RESEARCH（只读，无代码修改）  
> **覆盖范围**：`backend/app/core/story/`、`backend/app/core/ideal_city/`、`backend/app/core/ai/`、`common/protocols/`、`backend/app/api/`、`backend/app/routers/`

---

## === STORY 执行链路图 ===

### A. StoryEngine 主线推进链（Drift Story 关卡剧情）

```
HTTP POST /story/advance/{player_id}
  └─> story_api.api_story_advance()
        └─> story_engine.advance(player_id, world_state, action)         [story_engine.py:1601]
              ├─> _ensure_player(player_id)                              [memory dict 初始化]
              ├─> _ensure_free_mode_level(player_id)
              ├─> _inject_level_prompt_if_needed(player_id)
              ├─> _process_beat_progress(player_id, world_state, action)
              ├─> [personal mode]
              │     └─> deepseek_decide(ai_input, messages)              [deepseek_agent.py:463]
              │           ├─> _bypass_reason() → 若 circuit open → 返回静默节点
              │           ├─> 节流检查 MIN_INTERVAL=0.6s
              │           ├─> _LRU.get(cache_key) → 缓存命中直接返回
              │           ├─> [无 API KEY] → 返回本地占位节点
              │           └─> _call_deepseek_api(payload, timeout)       [dispatcher线程队列]
              │                 └─> _call_deepseek_api_sync()            [requests.post, timeout=(6s,12s)]
              │                       ├─> 成功 → 返回 parsed JSON
              │                       ├─> Timeout → 不重试(默认) → raise → advance() 捕获
              │                       └─> 其他错误 → retry(MAX_RETRIES=2) → raise
              ├─> [shared mode] → 直接返回静态节点（不调用 AI）
              ├─> 更新 players[player_id].messages / nodes               [内存]
              ├─> quest_runtime.check_completion()
              ├─> _compose_emotional_patch(player_id)
              └─> 返回 (option, node, patch)                             [不持久化 players 状态]

HTTP POST /story/load/{player_id}/{level_id}
  └─> story_engine.load_level_for_player(player_id, level_id)           [story_engine.py:1201]
        ├─> load_level(level_id)                                         [从 JSON 文件读关卡]
        ├─> players[player_id] 更新 level/messages/nodes/tree_state      [内存]
        ├─> _build_stage_patch(level)                                    [构建世界补丁]
        ├─> self._repository.save() ← 不调用                            [内存，不持久化]
        └─> 返回 bootstrap_patch
```

### B. IdealCity 叙事状态链（理想之城 StoryState）

```
HTTP POST /ideal_city/... (ideal_city_api.py)
  └─> StoryStateManager.process(player_id, scenario_id, ...)             [story_state_manager.py:113]
        ├─> StoryStateRepository.load(player_id, scenario_id)            [读 JSON 文件]
        │     └─> {root_dir}/{player_id}/{scenario_id}.json
        ├─> StoryStateAgent.infer(StoryStateAgentContext)                [story_state_agent.py:28]
        │     └─> NarrativeEngineFactory.create(ACTIVE_NARRATIVE_MODE)  [当前=REUNION]
        │           └─> ReunionNarrativeEngine.infer() / IdealCityNarrativeEngine.infer()
        │                 └─> call_deepseek(...)                         [deepseek_agent.py:559]
        │                       ├─> _bypass_reason() → 若 circuit open → 返回 bypassed=True
        │                       ├─> [无 API KEY] → 返回 parsed=None
        │                       └─> _call_deepseek_api(payload, 6s/6s)  [AI_CONNECT/READ_TIMEOUT]
        │                             └─> _call_deepseek_api_sync()
        ├─> _merge(existing, spec, narrative, player_pose, patch)        [内存合并]
        ├─> _evaluate(...)                                               [计算 coverage/score]
        └─> StoryStateRepository.save(merged_state)                     [写 JSON 文件] ✅
```

---

## === STATE 存储模型 ===

### 系统 1：StoryEngine.players（关卡剧情状态）

| 属性 | 说明 |
|------|------|
| 定义位置 | `backend/app/core/story/story_engine.py` → `StoryEngine.__init__()` |
| 数据结构 | `Dict[str, Dict[str, Any]]`（Python 嵌套字典，每个 player_id 对应一个 dict） |
| 存储方式 | **纯内存变量** |
| 声明方式 | 模块级单例 `story_engine = StoryEngine()`（文件末尾 line 2448） |
| 生命周期持有者 | `StoryEngine` 实例；进程终止即丢失 |
| 持久化 | ❌ 无，player 状态不写入任何文件或数据库 |

每个玩家的 dict 包含：`level`, `messages`, `nodes`, `tree_state`, `ended`, `runtime_mode`, `last_time`, `last_say_time`, `memory_flags`, `emotional_profile`, `current_exhibit`, `scenario_id`, `beat_state`, `pending_nodes`, `pending_patches`, `story_prebuffer`, `exit_profile`, `autofix_hints` 等。

### 系统 2：IdealCity StoryState（理想之城叙事状态）

| 属性 | 说明 |
|------|------|
| 定义位置 | `backend/app/core/ideal_city/story_state.py` → `class StoryState(BaseModel)` |
| 数据结构 | **Pydantic BaseModel 类**（强类型，含 player_id, scenario_id, goals, logic_outline, resources, milestones 等字段） |
| 存储方式 | **本地 JSON 文件**，路径为 `{root_dir}/{player_id}/{scenario_id}.json` |
| 包装格式 | `StoryStateEnvelope { state: StoryState, frozen_at: datetime }` |
| 存储模块 | `StoryStateRepository`（`story_state_repository.py`）；写入时持有 `threading.Lock()` |
| 生命周期持有者 | `StoryStateManager`（`story_state_manager.py`）；依赖 `StoryStateRepository` |
| 持久化 | ✅ 每次 `process()` / `sync_execution_feedback()` / `apply_pose_update()` 后均调用 `save()` |

### 系统 3：共享协议对象

| 属性 | 说明 |
|------|------|
| 定义位置 | `common/protocols/story_state.py` |
| 数据结构 | `TypedDict`（`StoryStatePatchPayload`）+ 工具函数 `coerce_story_state_patch()` |
| 用途 | 跨模块规范化 patch payload 的数据契约；不直接存储 |

---

## === TIMEOUT 处理流程 ===

### deepseek_decide()（StoryEngine.advance 路径）

```
请求 → _call_deepseek_api_sync()
         ├─ requests.Timeout 触发
         │    ├─ AI_RETRY_ON_TIMEOUT=False（默认）→ 立即 break（不重试）
         │    ├─ _record_failure() → 可能触发 circuit breaker（AI_FAILURE_THRESHOLD 次后）
         │    └─ raise requests.Timeout
         │
         └─ advance() 的 except Exception 捕获
              ├─ DRIFT_AI_FAIL_OPEN=true（默认）→ 返回静态 fallback 节点
              │    {option:None, node:{title:"创造之城·降级叙事", text:"..."}, world_patch:{}}
              └─ players[player_id] 中仅追加了 user 消息，AI 节点和 tree_state 未写入
```

### call_deepseek()（IdealCity 叙事引擎路径）

```
AI_CONNECT_TIMEOUT = 6.0s（IDEAL_CITY_AI_CONNECT_TIMEOUT env）
AI_READ_TIMEOUT    = 6.0s（IDEAL_CITY_AI_READ_TIMEOUT env）
overall deadline   = 12.0s（IDEAL_CITY_AI_TIMEOUT_DEADLINE env）

请求 → _call_deepseek_api_sync()
         ├─ Timeout → raise → call_deepseek() except 捕获
         │    ├─ DRIFT_AI_FAIL_OPEN=true → 返回 {parsed:None, response:"error..."}
         │    └─ 引擎收到 parsed=None → 返回空 StoryStatePatch（部分含 fallback_used=True）
         │
         └─ StoryStateManager.process() 继续执行 _merge() + _evaluate() + save()
              → state 被保存（含空 patch 合并结果）
```

---

## === Fallback 流程 ===

### Fallback 触发条件

| 条件 | 路径 | 触发机制 |
|------|------|----------|
| 无 API KEY | `deepseek_decide()` | 返回"本地风声"占位节点（option=None） |
| 无 API KEY | `call_deepseek()` | 返回 `{parsed:None}` |
| Circuit breaker 开路 | 两条路径均覆盖 | 返回 bypassed/静默节点 |
| AI 服务超时 | `_call_deepseek_api_sync()` | 抛出异常，由调用方捕获 |
| AI 返回非 JSON | `_call_deepseek_api_sync()` | `json.JSONDecodeError` → retry → 最终 raise |
| 请求速率限制 | `_DeepseekDispatcher.submit()` | queue 满 → `RuntimeError("deepseek_queue_full")` |

### Fallback 对 story_state 的影响

| 路径 | Fallback 行为 | 是否改变 StoryState | 剧情图是否推进 |
|------|--------------|---------------------|----------------|
| `deepseek_decide()` 失败 | 返回 `option=None`，静态 node | ❌ players[id] 消息追加，但 tree_state / nodes 未更新 AI 节点 | ❌ option=None，无推进 |
| `IdealCity call_deepseek()` 失败 | parsed=None → 空 `StoryStatePatch` | ✅ 状态仍被 merge+save（patch 为空/minimal） | N/A（叙事状态，非剧情图） |
| `IdealCity` fallback patch | `protocol_flags: {fallback_used: True}` | ✅ 写入 protocol_state | N/A |
| Shared mode（非 personal） | 直接返回静态节点，不调用 AI | ❌ 不更新 | ❌ |

**本地安全剧情**（`deepseek_decide` 返回值举例）：
- `"创造之城 · 静默"` / `"AI 一时沉默，但工坊的灯火仍在跳跃。"`
- `"创造之城 · 降级叙事"` / `"叙事模型暂时不可用，系统已切换到安全文本继续推进。"`

---

## === 潜在风险总结 ===

### 风险 1：StoryEngine.players 无持久化 [状态丢失风险]
- `advance()` 每次只更新内存中的 `self.players[player_id]`，进程重启后所有玩家的关卡进度、对话历史（messages）、节点历史（nodes）、情绪档案（emotional_profile）、内存标志（memory_flags）全部丢失。
- 关联文件：`story_engine.py:advance()`, `story_engine.py:load_level_for_player()`

### 风险 2：多 Worker 下全局单例不共享 [状态丢失风险]
- `story_engine = StoryEngine()` 是模块级单例（`story_engine.py` line 2448）。
- Procfile：`uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`（单 worker 默认）。
- 若以 `--workers N`（N>1）启动，每个进程各自持有独立的 `story_engine.players` 字典，同一玩家在不同进程的请求会产生分裂状态；关卡进度在 worker 之间不可见。

### 风险 3：StoryStateRepository 文件锁不跨进程 [状态丢失风险]
- `StoryStateRepository.save()` 使用 `threading.Lock()`，仅防止同进程内多线程竞争。
- 多进程部署时，两个 worker 可同时读写同一玩家的 `{player_id}/{scenario_id}.json`，存在数据覆盖风险。

### 风险 4：AI 超时时 StoryEngine 状态不一致
- `advance()` 在 AI 超时后返回 fallback 节点，但 `p["messages"]` 已追加了 user 消息；AI 的 node 未写入 `p["nodes"]`，也未更新 `tree_state`。
- 若下次请求再次尝试，消息历史与节点历史将不对称。

### 风险 5：LAST_CALL_TS 全局字典线程安全 [结构不透明]
- `_LAST_CALL_TS: Dict[str, float]` 在 `deepseek_agent.py` 中无锁保护，多线程并发时可能产生竞态（但影响有限，仅用于速率限制）。

### 风险 6：ai_story_api.py 的 story_engine 访问路径 [结构不透明]
- `ai_story_api.py` 通过 `request.app.state.story_engine` 获取引擎实例，但 `main.py` 仅 `from app.core.story.story_engine import story_engine`（模块级变量），并未将其挂载到 `app.state`。
- 若 `app.state.story_engine` 未初始化，`ai_react_to_world()` 调用时会 `AttributeError`。

### 风险 7：StoryGraph 轨迹（trajectory）无持久化
- `StoryGraph.trajectory` 在内存中存储玩家关卡进入/退出历史，重启后丢失，影响 `recommend_next_levels()` 的推荐质量。

### 风险 8：deepseek_decide 节流时间戳 _LAST_CALL_TS 与 players 不隔离
- 节流是按 `player_id` 粒度控制的，但 `_LAST_CALL_TS` 是跨所有玩家共享的全局字典，多 worker 部署下各进程独立维护，节流失效。

---

*本文档为自动生成的结构扫描报告，仅整理代码事实，不包含修复方案。*
