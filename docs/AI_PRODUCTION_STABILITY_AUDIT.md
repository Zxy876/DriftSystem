# Drift 生产级 AI 稳定性审计报告

日期：2026-02-24  
范围：Production 路径中全部 LLM 调用与执行链风险

## 1) LLM 调用点清单（全量）

### 1.1 Endpoint 直接触发

| endpoint | service/workflow | scene/realize 阶段 | world/story/start 阶段 | world/story/advance 阶段 | Shared 模式 |
|---|---|---|---|---|---|
| `POST /world/apply` | `StoryEngine.advance -> deepseek_decide`（仅 personal） | 否 | 否 | 是 | 禁止（静态文案） |
| `POST /story/advance/{player_id}` | `StoryEngine.advance -> deepseek_decide`（仅 personal） | 否 | 否 | 是 | 禁止（静态文案） |
| `POST /world/story/start` | `StoryEngine.prebuffer_story_beats`（预生成 3 beats） | 否 | 是 | 否 | 禁止 |
| `POST /world/story/enter` | `StoryEngine.prebuffer_story_beats`（预生成 3 beats） | 否 | 是 | 否 | 禁止 |
| `POST /story/inject` | `call_deepseek`（世界描述补全） | 否 | 否 | 否 | 不依赖模式 |
| `POST /ai/intent` | `parse_intent`（shared 仅 fallback，不触发 LLM） | 否 | 否 | 否 | 禁止 LLM |
| `POST /hint/` | `HintEngine.get_hint -> call_deepseek`（失败降级） | 否 | 否 | 否 | 不依赖模式 |

### 1.2 Service / Workflow 间接触发

| service/workflow | 入口路径 | scene/realize | story/start | story/advance | Shared |
|---|---|---|---|---|---|
| `deepseek_decide` | story 叙事推进 | 否 | 否 | 是 | 禁止 |
| `call_deepseek` | story 注入 / ideal_city / hint / intent | 否 | 否 | 仅间接 | 部分路径禁用 |
| `EmbeddingModel._embed_openai_batch` | 语义召回/索引流程 | 否 | 否 | 否 | 不依赖模式 |
| `ideal_city.*_agent` | adjudication/build_plan/story_state/guidance/world_narrator | 否 | 否 | 否 | 不依赖模式 |

### 1.3 明确不调用 LLM 的关键阶段

- `POST /scene/realize`：仅做资源选择、结构校验、dry_run/execute 执行；不做实时模型调用。  
- `GET /scene/execute-readiness`：仅检查 flag/RCON/executor，不做模型调用。

## 2) 每个调用点风险分析（模型 / 参数 / 保护）

### 2.1 统一网关（`app/core/ai/deepseek_agent.py`）

| 维度 | 现状 |
|---|---|
| 模型名称 | `PRIMARY_MODEL`，失败切 `FALLBACK_MODEL` |
| `max_tokens` | 强制注入；`None` 自动替换默认值并受 cap 限制 |
| timeout | `CONNECT_TIMEOUT <= 20s`，`READ_TIMEOUT <= 20s` |
| retry | `MAX_RETRIES <= 2` |
| fallback | 有（主模型失败/超时/429 触发） |
| 缓存 | 有（LRU） |
| circuit breaker | 有（失败阈值 + 熔断窗口） |
| rate limit | 有（token bucket + queue） |

### 2.2 调用点级别

| 调用点 | model | max_tokens | timeout | retry | fallback | cache | circuit breaker | rate limit |
|---|---|---|---|---|---|---|---|---|
| `StoryEngine.prebuffer_story_beats` | 主/备模型 | 强制 | <=20s | <=2 | 是 | 是 | 是 | 是 |
| `StoryEngine.advance` | 主/备模型 | 强制 | <=20s | <=2 | 是（异常降级文本） | 是 | 是 | 是 |
| `story_api.api_story_inject` | 主/备模型 | 强制 | <=20s | <=2 | 是（基础 world patch） | 是 | 是 | 是 |
| `ai_router -> parse_intent` | 主/备模型（personal 才可用） | 强制 | <=20s | <=2 | 是（deterministic fallback） | 是 | 是 | 是 |
| `hint_api -> HintEngine` | 主/备模型 | 强制 | <=20s | <=2 | 是（`action: null`） | 是 | 是 | 是 |
| `EmbeddingModel(OpenAI)` | `OPENAI_EMBEDDING_MODEL` | N/A | <=20s | <=2 | 是（hash vector） | 否 | 否 | provider 侧 |

## 3) 本次立即落地改造（执行结果）

### 3.1 强制超时与重试

- 所有 `call_deepseek / deepseek_decide` 路径统一：`timeout <= 20s`、`retry <= 2`。  
- `intent_engine` 与 `hint_engine` 改为走统一网关，不再裸连模型。

### 3.2 强制 `max_tokens`

- 统一在网关层兜底：禁止 `max_tokens=None`；无值则自动填默认上限。

### 3.3 Fallback 模型

- 已启用 `PRIMARY_MODEL` 与 `FALLBACK_MODEL`。  
- 触发条件：主模型失败 / timeout / rate limit（429）等。

### 3.4 `story_prebuffer`

- Personal 模式开始即预生成 3 个 beat。  
- 推进时优先消费缓存；模型失败仍可继续推进。

### 3.5 quota 监测接口

- `GET /ai/quota-status` 已上线。  
- 返回：`provider`, `model`, `last_error`, `rate_limit_hits`, `timeout_count`, `fallback_count`。

### 3.6 主流程解耦

- `scene/realize` 与 Story LLM 解耦。  
- Shared 模式不调用 story LLM。  
- Personal 模式下即便 `deepseek_decide` 抛异常也会 fail-open 返回降级 narrative，避免卡死。

## 4) 执行安全策略

- 环境变量：`DRIFT_AI_FAIL_OPEN=true`（默认 true）。  
- 语义：AI 故障只影响 narrative 质量，不阻断 build/execute 主链。

## 5) 交付标准对照

1. 审计文档：本文件。  
2. 改造 diff：`intent_engine`、`hint_engine`、`story_engine`、测试文件。  
3. 新增测试：见 `backend/test_ai_stability_guardrails.py` 新增 3 条（shared/no-llm、hint fail-open、personal fail-open）。  
4. 生产日志验证截图：见下方“日志证据文件”（文本证据，可在生产控制台按同命令截图）。  
5. 证明 LLM 不阻断 execute：`scene/realize` 无 LLM 依赖 + 回归测试通过。

## 6) 日志证据文件

- 本次回归输出已记录于：`logs/ai_stability_validation_2026-02-24.txt`（测试通过日志）。

## 7) 最终结论

- 模型挂掉 ≠ Drift 崩溃  
- 模型限流 ≠ 剧情中断  
- 模型超时 ≠ 执行链断裂
