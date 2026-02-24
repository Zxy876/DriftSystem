# AI Production Stability Audit

## 范围与结论

本审计覆盖当前生产运行路径中的 LLM 相关调用点、超时/重试/缓存/限流/熔断策略，以及对 `scene/realize`、`world/story/start`、`world/story/advance`、Shared 模式的影响。

结论（当前改造后）：
- 已实现统一调用防护：`timeout <= 20s`、`retry <= 2`、`max_tokens` 强制上限。
- 已实现主备模型：`PRIMARY_MODEL` + `FALLBACK_MODEL`，主模型失败/超时/限流时自动切到备模型。
- 已实现运行指标接口：`GET /ai/quota-status`。
- 已实现 `story_prebuffer`：Personal 模式进入时预生成 3 个 beat，推进优先消费缓存。
- 已实现 fail-open：`DRIFT_AI_FAIL_OPEN=true` 时，LLM 故障不阻断剧情与执行链。
- 已保证 `scene/realize` 不实时依赖 LLM；Shared 模式不触发 story LLM 推进调用。

---

## 1) LLM 调用点清单

| 调用点 | 类型 | 入口 | scene/realize 阶段 | world/story/start 阶段 | world/story/advance 阶段 | Shared 模式调用 |
|---|---|---|---|---|---|---|
| `StoryEngine.prebuffer_story_beats` | workflow | `POST /world/story/start`、`POST /world/story/enter` | 否 | 是（Personal） | 否 | 否 |
| `StoryEngine.advance -> deepseek_decide` | story 推进 | `POST /world/apply`、`POST /story/advance/{player_id}` | 否 | 间接（start后推进） | 是 | 否（已静态降级） |
| `story_api.api_story_inject -> call_deepseek` | endpoint/service | `POST /story/inject` | 否 | 否 | 否 | 不依赖模式 |
| `ideal_city.spec_normalizer -> call_deepseek` | service/workflow | `ideal_city` 相关 API 流程 | 否 | 否 | 否 | 不依赖模式 |
| `ideal_city.story_state_agent -> call_deepseek` | service/workflow | `ideal_city` 相关 API 流程 | 否 | 否 | 否 | 不依赖模式 |
| `ideal_city.build_plan_agent -> call_deepseek` | service/workflow | `ideal_city` 相关 API 流程 | 否 | 否 | 否 | 不依赖模式 |
| `ideal_city.guidance_agent -> call_deepseek` | service/workflow | `ideal_city` 相关 API 流程 | 否 | 否 | 否 | 不依赖模式 |
| `ideal_city.world_narrator -> call_deepseek` | service/workflow | `ideal_city` 相关 API 流程 | 否 | 否 | 否 | 不依赖模式 |
| `ideal_city.adjudication_explainer -> call_deepseek` | service/workflow | `ideal_city` 相关 API 流程 | 否 | 否 | 否 | 不依赖模式 |
| `EmbeddingModel(OpenAI)` | service | 语义检索/索引流程 | 否 | 否 | 否 | 不依赖模式 |

补充：
- `scene/realize` 仅资源校验 + dry_run/execute + RCON 执行，不触发 LLM。
- `world/story/start` 现在仅触发 prebuffer（Personal），用于后续推进容灾。

---

## 2) 各调用点风险分析（生产配置）

统一核心（`app/core/ai/deepseek_agent.py`）：
- 模型：`PRIMARY_MODEL`（主）/`FALLBACK_MODEL`（备）
- `max_tokens`：强制默认 `AI_MAX_TOKENS`（默认 800，且受 cap 限制）
- timeout：`CONNECT_TIMEOUT <= 20s`，`READ_TIMEOUT <= 20s`
- retry：`MAX_RETRIES <= 2`
- fallback：支持（主模型失败自动切备模型）
- 缓存：支持（LRU）
- circuit breaker：支持（失败阈值 + 熔断时间）
- rate limit：支持（token bucket + queue）

按调用点：

1. Story prebuffer / advance（deepseek_decide）
- 模型：主备模型
- max_tokens：强制
- timeout/retry：强制上限
- fallback：有（静态叙事 + 备模型）
- 缓存：有（按 context + messages）
- circuit breaker：有
- rate limit：有
- 风险：LLM波动导致叙事质量下降（不会阻断主流程）

2. story/inject（call_deepseek）
- 模型：主备模型
- max_tokens：强制
- timeout/retry：强制上限
- fallback：有（错误时回退基础 world patch）
- 缓存：有
- circuit breaker：有
- rate limit：有
- 风险：内容质量波动，不影响执行链

3. ideal_city 全链路（call_deepseek）
- 模型：主备模型
- max_tokens：强制
- timeout/retry：强制上限
- fallback：有（各 agent 内部 deterministic fallback）
- 缓存：有（agent 级 + deepseek LRU）
- circuit breaker：有
- rate limit：有
- 风险：策略文本/建议可能降级，但不影响构建执行主链

4. EmbeddingModel(OpenAI)
- 模型：`OPENAI_EMBEDDING_MODEL`
- max_tokens：N/A（embedding 接口）
- timeout：`OPENAI_TIMEOUT` 被限制到 <=20
- retry：`max_retries=2`
- fallback：有（哈希向量 fallback）
- 缓存：无显式 embedding 缓存（索引层有）
- circuit breaker：无
- rate limit：依赖 provider
- 风险：语义召回质量下降，不影响 execute 主链

---

## 3) 本次落地改造

### 3.1 强制超时/重试
- Deepseek/OpenAI-compatible 调用统一限制：
  - `CONNECT_TIMEOUT <= 20`
  - `READ_TIMEOUT <= 20`
  - `MAX_RETRIES <= 2`
- Embedding OpenAI 调用：
  - `OPENAI_TIMEOUT` 限制到 <=20
  - `max_retries=2`

### 3.2 强制 max_tokens
- 所有 `call_deepseek/deepseek_decide` 请求统一注入 `max_tokens`。
- 防止出现 `max_tokens=None`。

### 3.3 主备模型 fallback
- 新增环境变量：
  - `PRIMARY_MODEL`
  - `FALLBACK_MODEL`
- 主模型失败/超时/限流时自动切备模型。

### 3.4 story_prebuffer
- Personal 模式进入（`/world/story/start`、`/world/story/enter`）时预生成 3 个 beat。
- 推进时优先消费缓存，再回填缓存。
- 模型失败时保持可推进（fail-open）。

### 3.5 quota 监测接口
- 新增：`GET /ai/quota-status`
- 返回：
  - `provider`
  - `model`
  - `last_error`
  - `rate_limit_hits`
  - `timeout_count`
  - `fallback_count`

### 3.6 解耦与主链保护
- `scene/realize` 不依赖 LLM。
- Shared 模式下 `StoryEngine.advance` 直接静态响应，不触发 LLM。
- `DRIFT_AI_FAIL_OPEN=true` 时：AI 故障不阻断 personal 玩法与 execute 链。

---

## 4) 运行验证（日志与接口）

建议线上验证步骤：
1. `GET /ai/quota-status`
2. `POST /world/story/start`（Personal）
3. `POST /story/advance/{player_id}` 或 `POST /world/apply`
4. 关闭/阻断上游模型后重复步骤 2-3，确认仍可推进（文本降级但不阻塞）
5. `POST /scene/realize`（dry_run/execute）确认不受 LLM 故障影响

日志观察点（示例）：
- fallback 切换日志
- timeout/rate-limit 计数增长
- `scene/realize` 200 + execute report 正常

---

## 5) 关键环境变量

- `DRIFT_AI_FAIL_OPEN=true`
- `PRIMARY_MODEL=...`
- `FALLBACK_MODEL=...`
- `AI_MAX_TOKENS=800`
- `AI_MAX_TOKENS_CAP=1200`
- `DEEPSEEK_CONNECT_TIMEOUT=20`（会自动 clamp）
- `DEEPSEEK_READ_TIMEOUT=20`（会自动 clamp）
- `DEEPSEEK_MAX_RETRIES=2`（会自动 clamp）

---

## 6) 结论

已满足目标：
- 模型挂掉 ≠ Drift 崩溃
- 模型限流 ≠ 剧情中断
- 模型超时 ≠ 执行链断裂

并且满足执行安全要求：
- 禁止在 `scene/realize` 阶段实时依赖 LLM（已满足）
- Shared 模式禁止模型调用（story 推进已满足）
- execute 期间不等待模型（已满足）
