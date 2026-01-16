# Phase 0 · 聊天输入链路审计记录（2026-01-14）

> 目标：摸清当前“聊天 → 意图 → 裁决 → world_patch → ExhibitInstance”链路的真实运行状态，为 Phase 1+ 的改造与 Transformer 接入提供基线。

---

## 1. 当前入口与触发面
- **聊天事件入口**：`POST /ideal-city/narrative/ingest`（文件：`backend/app/api/ideal_city_api.py`）。
  - 接收 `NarrativeChatEvent`（player_id、message、scenario_id、channel 等）。
  - 直接调用 `IdealCityPipeline.ingest_narrative_event`。
- **CityPhone 只读接口**：`GET /ideal-city/cityphone/state/{player_id}` 输出档案视图，未参与创造链路。
- **CityPhone 行为接口**：`POST /ideal-city/cityphone/action` 仍存在，但本阶段视为辅助，不作为创造主入口。

---

## 2. 链路分解（核心函数与文件）
```
NarrativeChatEvent
  ↓  (app/core/ideal_city/narrative_ingestion.py)
NarrativeFieldExtractor.extract  →  NarrativeExtraction
  ↓
IdealCityPipeline.ingest_narrative_event (app/core/ideal_city/pipeline.py)
  ↳ DeviceSpecSubmission (draft or full)
  ↳ IdealCityPipeline.submit
        • detect_intent → IntentKind (refresh mods 特殊分支)
        • StoryStateManager.process → story_outcome
        • IdealCityAdjudicator.evaluate → ruling
        • GuidanceAgent.generate → guidance
        • BuildPlanAgent.generate → BuildPlan (可选)
        • ManifestationIntentWriter.write_intent → city-intents/pending
        • BuildScheduler.enqueue → build_queue/build_queue.jsonl
        • ExhibitInstanceRepository.save_instance （通过 StoryState / Exhibit 模块间接触发）
  ↓
IdealCityRepository.save → JSONL 归档（spec / ruling / notice / plan）
```

### 2.1 Narrative 提取
- 规则引擎，字段别名定义在 `FIELD_ALIASES`，覆盖中英文标签。
- 缺少 `vision` 或 `actions` 时：
  - 方案一：首段长度足够则作为草稿 (`is_draft=True`) 进入提交，返回 `status="needs_review"`。
  - 方案二：文本极短则 `status="rejected"`，无后续提交。
- 定位：`NarrativeChatIngestor.process` 仅做解析，不含世界资源理解。

### 2.2 DeviceSpec 提交
- `DeviceSpecSubmission.to_spec` 结合 `SpecNormalizer` 与 `StoryState` 生成结构化裁决输入。
- 缺乏资源 → `story_outcome.ready_for_build` 可能为 False，导致 BuildPlan 未生成。

### 2.3 Build 与 Manifestation
- `BuildPlanAgent.generate` 产出 `BuildPlan`，并保存玩家位姿（来自提交或 StoryState）。
- `BuildScheduler.enqueue` 将计划写入 `backend/data/ideal_city/build_queue/build_queue.jsonl`。
- `ManifestationIntentWriter.write_intent` 将确定性 patch/intents 丢到 `backend/data/ideal_city/protocol/city-intents/pending/`，供外部执行器消费。
- 执行结果落地：
  - 成功/失败日志写入 `backend/data/ideal_city/build_queue/{executed|failed}/<plan_id>.json`。
  - StoryState 在 `story_state/<player>/<scenario>.json` 中记录历史注记。

### 2.4 ExhibitInstance 持久化
- `ExhibitInstanceRepository`（`backend/app/core/story/exhibit_instance_repository.py`）
  - 保存目录：`backend/data/ideal_city/exhibit_instances/<scenario>/`。
  - `index.json` 维护元数据列表；CityPhone 展示逻辑读取该索引。
  - 当前写入由剧情/执行模块触发；要验证创造保留需确认此层是否被调用（待 Phase 1 进一步追踪）。

---

## 3. 数据与存储现状
| 存储内容 | 路径 | 写入方式 |
| --- | --- | --- |
| DeviceSpec 历史 | `backend/data/ideal_city/device_specs.jsonl` | `IdealCityRepository.save` append |
| 裁决记录 | `backend/data/ideal_city/adjudication_rulings.jsonl` | 同上 |
| 执行通知 | `backend/data/ideal_city/execution_notices.jsonl` | 同上 |
| BuildPlan 队列 | `backend/data/ideal_city/build_queue/build_queue.jsonl` | `BuildScheduler.enqueue` |
| BuildPlan 执行日志 | `backend/data/ideal_city/build_queue/executed/*.json` | 外部执行器回填 |
| Manifestation intents | `backend/data/ideal_city/protocol/city-intents/pending/*.json` | `ManifestationIntentWriter` |
| Exhibit 实例 | `backend/data/ideal_city/exhibit_instances/<scenario>/*.json` | `ExhibitInstanceRepository.save_instance` |
| StoryState 档案 | `backend/data/ideal_city/story_state/<player>/<scenario>.json` | `StoryStateRepository.save` |

---

## 4. 日志与监控
- **Backend 运行日志**：`DRIFT_SCIENCELINE/logs/latest.log`、`backend/backend.log`（需确认启动脚本写入策略）。
- **CityPhone Metrics**：`app/instrumentation/cityphone_metrics.py` 提供 Prometheus Counter（或本地计数器）。当前未集成到聊天链路，仅收敛 State/Action 请求量。
- **调试建议**：Phase 1 前可增加 `NarrativeIngestionResponse` 的入库日志（目前仅通过 API 返回，不自动写文件）。

---

## 5. 现状痛点（Phase 0 观察）
1. **世界资源理解缺失**：Narrative 提取仅做文本解析，无法校验资源是否存在，导致 `story_outcome.ready_for_build` 容易失败。
2. **BuildPlan → ExhibitInstance 映射不透明**：目前依赖 StoryState/执行器侧逻辑，没有显式追踪“某个 plan 产出哪些 Exhibit”。后续需要在 Manifestation 或执行回调处挂钩。
3. **错误追踪分散**：Build 失败记录在 `build_queue/failed`，但 Narrative API 返回仅提示“needs_review”；玩家侧缺乏直接反馈。
4. **缺少回归脚本**：尚未发现自动脚本验证“聊天 → 执行 → 持久化”；现有测试（例如 `backend/test_ideal_city_pipeline.py`）主要覆盖 Spec 流程。
5. **CityPhone 依赖残留**：虽然愿景强调 CityPhone 只读，StoryState 仍将提示写入其视图，需要确认这些提示不会阻断聊天链路。

---

## 6. 建议的下一步采样 / 校验
- **实机复现路径**：
  1. 启动 `backend/start_backend.sh` 与 MC 侧执行器。
  2. 通过聊天发送“包含资源标签”的创造请求，捕获 `backend/data/ideal_city` 目录变化。
  3. 记录响应中的 `plan_id`，确认对应文件写入 `build_queue/executed`，并在世界中确认 patch 生效。
  4. 检查 `exhibit_instances/index.json` 是否新增条目。
- **脚本化日志**：添加临时脚本 `scripts/phase0_dump_queue.py`（待建）以可视化队列状态，辅助 Phase 1 调试。
- **数据健康检查**：对历史 JSONL 进行一次格式校验，避免旧数据阻塞新版解析。

---

## 7. Phase 1 准备事项
- 产出 Narratives → Intent 标注集（≥100 条），以便后续 Transformer 校验用。
- 设计 `creation_plan` Schema 草稿，明确输入（意图结构）与输出（world_patch/ExhibitInstance）字段，便于将来对接。
- 对 `ManifestationIntent` 与外部执行器的契约进行一次协议确认，确保我们接管资源组合时不破坏现有执行链。

---

*记录人：GPT-5-Codex · 2026-01-14*
