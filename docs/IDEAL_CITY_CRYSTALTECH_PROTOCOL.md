# Ideal City × CrystalTech Dual-Architecture Protocol

> **Document Type**: Cross-project protocol (not an implementation guide)  \
> **Scope**: Defines responsibilities and interactions between the Ideal City Plugin (logic layer) and the CrystalTech Forge mod (manifestation layer). Each project retains its own copy and implements only the responsibilities assigned herein.

---

## 0. Purpose

- Keep **research, judgment, and civic alignment** inside the Ideal City plugin.  
- Keep **materialisation, stage capabilities, and technical assets** inside the CrystalTech Forge mod.  
- Link both layers via auditable **Manifestation Intent** objects.  
- Prevent regression into direct chat, skill triggers, or automated pipelines.

---

## 1. Architecture Overview

```
┌────────────────────────┐
│   Ideal City Plugin    │  <-- Research / Judgment
└─────────▲──────────────┘
          │  Manifestation Intent (protocol payload)
┌─────────┴──────────────┐
│   CrystalTech Forge    │  --> Material / Stage Ops
└────────────────────────┘
```

**Non-negotiable principles**
1. Plugin is unaware of Forge internals.  
2. Forge is unaware of Plugin adjudication logic.  
3. Shared surface = protocol objects only.  
4. No direct API calls across sides. Forge never advances story; Plugin never spawns blocks.

---

## 2. Ideal City Plugin Responsibilities

### 2.1 Role in-world
- Represent the city’s archive & judgment system.  
- Accept player narrative submissions.  
- Shape submissions into **research-state proposals** and evaluate coverage.  
- Produce verdicts: `INCOMPLETE` (research), `ACCEPT` (eligible for manifestation).  
- Maintain required sections, coverage snapshots, research uncertainty.  
- Decide if manifestation is permitted and the **maximum stage** allowed.

### 2.2 Hard No (never do)
- Define Forge stage numerical details.  
- Emit item/block IDs, recipes, or machines.  
- Progress stage capability counters.  
- Simulate technical details.  
- Output operational commands. Only declare intent.

---

## 3. Manifestation Intent Protocol Object

### 3.1 Concept
The **only** outbound message from Plugin to Forge.  
Represents: *“Given current civic understanding, the city authorises a specific crystallisation stage.”*

### 3.2 Schema (v0)
```json
{
  "intent_id": "CRYSTAL_TECH_STAGE_UNLOCK",
  "schema_version": "0.1.0",
  "scenario_id": "default",
   "scenario_version": "2026.01",
  "allowed_stage": 1,
  "confidence_level": "research_validated",
  "constraints": ["no_stage_skip", "low_energy_only", "non_industrial"],
  "context_notes": [
    "紫水晶被认定为可进行基础材料化探索",
    "当前研究尚不支持工业化或自动化"
  ],
  "issued_at": "2026-01-09T12:34:56Z",
  "expires_at": "2026-01-10T12:34:56Z",
  "signature": "ideal-city::<uuid>"
}
```

### 3.3 Emission Conditions
- Verdict == `ACCEPT`.  
- All required sections covered.  
- No blocking research uncertainty.  
- Scenario policy authorises the requested stage.  
- Intent persisted to audit log before transmission.
   - (Optional) If scenario versions are introduced, include `scenario_version` aligned with scenario metadata.

### 3.4 Transport Envelope
- **Medium**: atomic JSON files in `protocol/city-intents/pending/`.  
- 文件整体为信封结构：
   ```json
   {
      "player_id": "<online-player-uuid>",
      "intent": { ...ManifestationIntent fields... }
   }
   ```
- `player_id` 必须指向待授权的在线玩家 UUID；如暂不可用，可临时使用占位 UUID，Forge 会在校验时提示但不中断流程。  
- `intent` 字段包含 `ManifestationIntent` 序列化结果，追加信息放入 `intent.metadata.*`。  
- Plugin writes/publishes; Forge claims by moving files to `processing/` or `processed/`.  
- Status transitions (`pending` → `processing` → `processed/failed`) are Forge-managed; Plugin never mutates files after publish.

---

## 4. CrystalTech Forge Responsibilities

### 4.1 Role in-world
- Operate the material/technical manifestation layer.  
- Poll & parse `city-intents/pending/` for `ManifestationIntent` payloads.  
- Validate `intent_id`, schema version, signature.  
- Confirm `allowed_stage == current_stage + 1` and scenario permits stage.  
- Execute stage unlock: recipes, machines, energy rules.  
- Broadcast `StageChangedEvent(stage=X, source="protocol")` to world.

### 4.2 Hard No (never do)
- Evaluate player intent.  
- Request next stages on its own.  
- Infer story direction.  
- Bypass protocol for locked stages.  
- Modify or fabricate intents.  
- Write to Plugin data paths (read-only).

---

## 5. Stage Alignment Rules

1. **Dual trigger**: Stage advances only when both Manifestation Intent and valid in-world technical behaviour occur (e.g., recipe crafted).  
2. **No stage skipping**:  
   - Forge rejects `allowed_stage > current_stage + 1`.  
   - Plugin never issues beyond scenario-approved stage.  
3. Forge logs and ignores any intent outside allowed bounds.

---

## 6. Failure / Incomplete Handling

### Plugin side
- Verdict `INCOMPLETE`: do not emit Manifestation Intent.  
- Record `research_hint` in CityPhone state only.  
- No executable instructions.

### Forge side
- Missing intent: keep stage-locked behaviours disabled.  
- Invalid intent: log `intent_rejected` with reason; no compensation, no retries.

---

## 7. CityPhone × Manifestation Experience

- CityPhone messaging stays diegetic: "该技术路径已被城市系统认可 / 尚在研究中".  
- Never state "解锁了 Stage X".  
- Technical feedback appears through world changes (recipes, machines), not chat overlays.

---

## 8. Multi-Device Ecosystem Principle (多设备联动生态)

**Core metaphor**  
- Ideal City plugin / CityPhone acts like a *mobile terminal* (understanding, archives).  
- CrystalTech Forge acts like the *primary workstation* (world operations).  
- Players are not switching systems; they are operating a layered device ecosystem within the same world.

**Device responsibility split**  
- **Forge (Primary Surface / 主设备)**: continuous world interaction, high bandwidth, all manifestation and stage capabilities; always the place where things happen.  
- **CityPhone (Secondary Surface / 副设备)**: on-demand, never blocks world play, provides state insight, research records, adjudication context; never executes complex actions.

**Interaction rules**  
1. *No primary-window hijack*: CityPhone never auto-opens, interrupts, or becomes the main task flow; all decisive actions remain in Forge.  
2. *Operate vs. Understand*: Forge handles action, experiments, and silent constraints; CityPhone explains why the world responds, logging research/incomplete/accepted states.  
3. *No AI-chat tone*: CityPhone output uses in-world archival language, avoids second-person commands, and does not mimic dialogue.

**UX litmus test**  
- Players should feel Forge is the world, CityPhone is where the city records understanding; the world keeps running even if CityPhone stays closed, and opening it clarifies current stage rather than driving the loop.

**Long-term implication**  
- Supports future expansion into multiple technical lines, additional Forge modules, or varied CityPhone clients without rebuilding core experience.

**Design constitution**  
> 世界先发生，理解随后到来。电脑改变世界，手机解释世界。

---

## 9. Amethyst Theme Anchor (企划母题约束)

- Amethyst is the **theme anchor** that frames every proposal; it is not a mandatory material step.  
- A submission must satisfy at least one of:
   1. Address a problem triggered by amethyst activity.  
   2. Constrain risks introduced by amethyst exploration.  
   3. Expand the city’s understanding of amethyst’s cultural or social role.  
- Proposals that make no meaningful reference to amethyst remain `INCOMPLETE` with CityPhone hint: "当前企划尚未与紫水晶议题建立清晰关联，需要进一步陈述。"
- Player freedom is preserved: responses can be exhibition, governance, technical boundary-setting, or critical suspension of amethyst usage.

---

## 10. Execution Split Checklist

| Concern | Ideal City Plugin | CrystalTech Forge |
|---------|------------------|-------------------|
| Scenario policy | Own + version | Read-only |
| Research coverage | Compute & persist | None |
| Manifestation Intent | Generate + log | Consume + validate |
| Stage capability | None | Implement |
| Recipes / machines | None | Implement |
| CityPhone UI | Provide research hints | No UI |
| Persistence | Append intents, rulings | Stage state, recipe data |

---

## 11. Definition of Done

1. Plugin operates full research loop without Forge present.  
2. Forge runs stage mechanics with default locks when plugin absent.  
3. Combined system: stage advances **only** when both civic intent (Plugin) and technical behaviour (Forge) align.

---

## 12. Operational Guidance

1. **Data Path Agreement**  
   - Shared folder `protocol/city-intents/`.  
   - Plugin publishes atomic JSON payloads to `city-intents/pending/`.  
   - Plugin maintains append-only audit at `city-intents/intent_audit.jsonl`.  
   - Forge writes `manifestation_events.jsonl` (readable by Plugin for telemetry).  
   - Paths configured via environment variables `IDEAL_CITY_PROTOCOL_ROOT`, `CRYSTALTECH_PROTOCOL_ROOT`.

2. **Versioning**  
   - `schema_version` increments on breaking changes.  
   - Both sides maintain changelog.  
   - Old versions remain readable until decommissioned with mutual agreement.

3. **Audit & Recovery**  
   - Plugin keeps signed archive of emitted intents.  
   - Forge records timestamp, stage delta, player context.  
   - On consumption, if `now > expires_at`, Forge logs `intent_expired` and ignores the entry.  
   - On crash, Forge replays intents marked `pending` or `claimed` but not `settled`.
   - Repository 的 `list_intents()` 仅用于运维可视化或回溯，不参与裁决或推进逻辑。

4. **Testing Routines**  
   - Plugin: unit tests ensuring intents produced only under valid coverage.  
   - Forge: integration tests verifying stage unlock triggered by queue plus in-game action.  
   - Joint smoke test: emit synthetic intent, perform matching recipe, verify event broadcast.

5. **Security Boundaries**  
   - No direct RPC; file-based or message bus with ACL.  
   - Intent signatures signed with Plugin-owned key; Forge verifies.  
   - Forge never caches player-submitted text beyond logging requirements.

### 12.1 Manifestation Intent File Delivery (Forge → Plugin)

**Directory structure**

```
city-intents/
├─ pending/        # new intents pending Forge consumption
├─ processing/     # optional acknowledgement workspace
├─ processed/      # Forge-confirmed completions
└─ failed/         # validation errors / unreadable files
```

**Write rules**
- UTF-8 JSON; filename suggestion: `<intent_id>.json` (intent ids must be globally unique).
- Atomic publish: write temp file → flush/fsync → atomic rename into `pending/`. Files in `pending/` are assumed complete.

**Minimum JSON schema**
```json
{
   "intent_id": "string",
   "scenario_id": "string",
   "allowed_stage": <number>,
   "issued_at": "ISO-8601 timestamp"
}
```
Optional keys: `scenario_version`, `expires_at`, `notes` (array of strings). Unrecognised fields are ignored.

**Metadata & failures**
- Optional sidecar `<intent_id>.meta` (e.g. generator, run id, signature status).
- On validation failure move JSON to `failed/<intent_id>.json` and emit human-readable `failed/<intent_id>.reason`.
- 提供的示例：`city-intents/pending/example-stage-1.json` 使用占位 `player_id`（`00000000-0000-0000-0000-000000000000`），Forge 可在获取真实在线玩家 UUID 后替换。  
- 若需自动生成，运行 `scripts/drop_intent_example.py` 会以原子方式写入新的示例意图；可通过 `--player-id` 指定授权玩家。

**Lifecycle expectations**
- Document retention policy for `processing/` and `processed/` (retention time, max files, crash recovery).
- Forge treats `pending/` as the sole ingress and will not clean plugin directories.

**Retry & rate limits**
- Define retry policies for IO/network/auth errors, including cadence and cap.
- Document concurrency limits to avoid flooding `pending/` and describe per-player/scenario throttles if any.

**Self-test artefact**
- Provide either an automated script or manual checklist that produces a sample intent, writes to `pending/`, and states the expected Forge logs/stage change.

**Authority boundaries**
- Plugin writes only under `pending/`; it does not mutate Forge-managed paths.
- Forge reads/moves intent files; it does not write into plugin-owned data.

**Definition of Done**
1. Plugin reliably writes valid intents into `pending/`.  
2. Forge consumes without manual intervention and advances stage when appropriate.  
3. Partial files never appear in `pending/`.  
4. Failures are archived with human-readable reasons.  
5. Directory usage stays bounded during long-running operation.

---

## 13. Change Management

- Protocol modifications must be documented via RFC referencing this file.  
- Both projects sign off before altering schema or transport.  
- Emergency hotfixes limited to log-level or transport reliability; no stage logic bypass.

---

## 14. Implementation Ownership Snapshot

- **Ideal City Plugin (我们负责)**  
   - Manifestation Intent 数据模型与目录写入流程（`city-intents/pending/` + `intent_audit.jsonl`）。  
   - `ACCEPT` 裁决 → intent 生成；`INCOMPLETE` → 研究态记录。  
   - 审计与签名机制、CityPhone 展示管线。
- **CrystalTech Forge（对方执行）**  
   - Intent 文件消费与校验逻辑。  
   - Stage Capability 推进、配方与机器解锁。  
   - `StageChangedEvent` 广播与世界反馈。

---

## 15. One-line Principle

**World understanding precedes technological manifestation.**

---

## 16. Purple Amethyst Two-way Play Patterns （紫水晶双向通信玩法）

### 16.1 技术进化 × 社会反馈（Play 1）
- Forge 侧记录节点：机器建造、能源扩容、阶段晋升、事故与超载。
- Plugin/CityPhone 侧每个结算周期生成四类社会反应稿件：`praise`（赞扬）、`concern`（担忧）、`controversy`（争议）、`regulation_proposal`（管制提案）。
- CityPhone 以“城市新闻 / 档案馆”形式发布，允许玩家点赞或发起留言，形成“社会回应”而非系统评分。
- 社会反应计入城市指标（Trust/Confidence），触发后续事件或政策讨论。

### 16.2 研究驱动的新题面（Play 2）
- 市民来信或事件（CityPhone Inbox）可携带主题标签，例如“amethyst_dust_health”。
- Plugin 根据标签生成新的 scenario 草案，例如「紫水晶粉尘的社会影响评估」，并动态调整 `required_sections`（新增 `health_impact`、`mitigation_plan` 等字段）。
- Forge 接收对应的 `scenario_activation` 信号，解锁调查型任务（采样、净化装置、记录仪部署），并返回测量结果用于 Plugin 评估。
- CityPhone 将研究进展与缓解方案作为阶段性交互任务向玩家呈现。

### 16.3 多结局社会记忆（Play 3）
- Plugin 维护三条长期叙事计分：`industrial_priority`、`community_priority`、`conservative_path`。
- Forge 报告关键行为（高耗能设施上线、社区福利项目、停滞/封存决策），驱动计分变化。
- CityPhone 在季度/年度生成“城市脉搏”与“年度总结”，并归档于社会记忆库；结局可呈现为冷漠工业线、稳健社区线、保守守成线等不同社会叙事。
- 归档结果反向影响后续阶段阈值或解锁特殊剧情（如社会示威、政府干预、科研突破）。

### 16.4 互动与情绪曲线
- Forge → Plugin：推送“技术通告”“行动报告”“辟谣稿”，供 CityPhone 侧发布。
- Plugin → Forge：发起公投、筹款或应急行动指令，对应世界内的 NPC 示威、资源分配、自发维修。
- 引入 `trust_index` 与 `stress_index` 双曲线；来自社会反应、事件报告、Forge 行动，超过阈值时触发特殊事件。


## 17. Forge 同步开发交付物（CrystalTech Delivery Checklist）

### 17.1 协议层实现
- Intent 消费服务：轮询 `city-intents/pending/`，验证签名、模式版本、阶段递增规则。
- 社会反馈回写：在 `cityphone/social-feed/` 下生成 `event` 文件（四类稿件 + 信任指数变动），Plugin 负责展示与归档。
- 反向状态信封：新增 `technology-status` JSON（含 stage、energy、风险、事件），供 CityPhone 呈现。

#### 17.1.a 社会反馈回写格式（Forge → Plugin）
- 目录：`protocol/cityphone/social-feed/`
- `events.jsonl`：每行单条稿件，字段 `entry_id`、`category`(`praise|concern|controversy|regulation_proposal`)、`title`、`body`（或 `summary`）、`issued_at`（ISO-8601）、可选 `stage`、`trust_delta`、`stress_delta`、`tags`（字符串或数组）。
- `metrics.json`：汇总指标 `{ "trust_index": float, "stress_index": float, "updated_at": ISO-8601 }`；若缺失 `updated_at`，Plugin 将以最新稿件时间回填。
- Plugin 已提供容错读取：忽略非法 JSON、字段缺失时默认值为 0 / 空列表。

#### 17.1.b 技术状态信封（Forge → Plugin）
- 文件：`protocol/technology-status.json`
- 字段规范：
   - `stage`：对象 `{ "label": str, "level": int, "progress": 0-1 }`，也可直接提供字符串/数字（Plugin 自动归一）。
   - `energy`：对象 `{ "generation": float, "consumption": float, "capacity": float, "buffer|storage|reserve": float }`。
   - `risks`：数组 `{ "risk_id": str, "level|severity": str, "summary|description|note": str }`。
   - `recent_events|events|event_log`：数组 `{ "event_id|id": str, "category|type": str, "description|summary|note": str, "occurred_at|timestamp": ISO-8601, "impact|effect": str }`。
   - `updated_at`：ISO-8601 字符串；缺省时 Plugin 以最近事件时间补齐。
- Plugin 现已将快照注入 CityPhone 状态 `technology_status` 节点，前端可直接展示阶段、能源、风险与最近事件。

#### 17.1.c Writer 接入参考（Forge → Plugin）
- `app/core/ideal_city/technology_status_writer.py` 暴露 `TechnologyStatusWriter`：
   - `update_stage(StageSnapshot, updated_at)`、`update_energy(EnergySnapshot)`、`record_risk(RiskEvent)`、`record_event(TechnologyEvent)`、`set_updated_at(...)` 等方法，所有调用默认执行原子写入，确保 `technology-status.json` 始终一致。
   - 适用于 ManifestationIntentService、StageProgressListener 等生命周期钩子：每次阶段推进、能源刷新或风险变更时调用对应方法，并在调用链结束时（若重度批量更新）执行 `commit()`。
- `app/core/ideal_city/social_feed_writer.py` 提供 `SocialFeedWriter`：
   - `append_event(...)` 自动维护 `events.jsonl`，默认按 `entry_id` 去重；`set_metrics(...)` 可同步 `trust_index`/`stress_index` 与时间戳。
   - 建议在阶段推进、风险通报、科研突破等事件里调用，确保 CityPhone 新闻流及时更新。
- Writer 辅助类型：`StageSnapshot`、`EnergySnapshot`、`TechnologyEvent`、`RiskEvent` 均位于同一模块，可直接实例化；所有时间字段使用 UTC `datetime`。
- 数据源映射待 Forge 确认：
   - 阶段推进触发点 → `update_stage`
   - 能耗统计/曲线 → `update_energy`
   - 风险状态列表 → `record_risk`
   - 事件广播（包括阶段晋升、事故、维护）→ `record_event`
   - 社会稿件与指标 → `SocialFeedWriter.append_event` / `set_metrics`
- Forge 输出 artefacts 需在每日例会前提交：
   1. `technology-status.json` 实际样例（含 stage/energy/risks/events 真实数据）。
   2. `cityphone/social-feed/events.jsonl` + `metrics.json` 最近 24 小时内容。
   3. 对应代码片段或 API 文档（ManifestationIntentService 钩子、能源统计类、风险枚举），以便双方审阅。

### 17.2 玩法功能模块
- **Stage Telemetry**：记录每次机器建造、能源扩容、事故事件，写入 `forge/events/telemetry.jsonl`。
- **Social Echo Hooks**：在阶段晋升、关键设施上线时调用 `SocialEchoAPI.broadcast(type, payload)`（由 Forge 提供），以通知 CityPhone。
- **Scenario Task Bridge**：接收 Plugin 的 `scenario_activation` 指令，生成可执行任务节点（如样本采集、装置安装）并追踪完成状态。
- **Ending Memory Vault**：根据累计指标生成 `ending_state` 记录，供 CityPhone 年度总结合成。

### 17.3 同步节奏
- 每周例行同步：
   - Forge 提交阶段进度、能源数据、关键事件。
   - Plugin 反馈社会情绪曲线、研究进展。
- 重大版本门槛：
   1. Intent 消费 & Stage 解锁打通。
   2. 社会反馈回写与 CityPhone 展示闭环。
   3. Scenario 驱动任务与回传验证。
   4. 多结局记忆档案首轮生成。

### 17.4 自测与联调要求
- Forge 自测：提供 CLI/单元测试验证阶段推进、事件记录、社会反馈生成。
- 联调脚本：
   - `scripts/forge_drop_status.py` → 写入示例技术状态。
   - `scripts/plugin_emit_research_case.py` → 触发 scenario。
   - 期望输出：CityPhone 展示社会稿件、Forge 控制台打印阶段结果。
- 验收清单：
   - Intent 文件消费成功率 100%，过期/异常均写入 `failed/`。
   - 社会反馈回写延迟 < 5s，错误重试具备指数退避。
   - Ending 归档可在单世界运行 10 in-game 日后稳定生成。

### 17.5 交付沟通接口
- 负责人映射：Plugin（我们）维持 CityPhone、裁决、归档；Forge 团队负责世界行为、事件、回写接口。
- Issue 跟踪：GitHub `CrystalTech/forge` 仓库新建 `amethyst-duplex` 标签，对应需求拆分。
- 周报模版：
   - 已完成：阶段进度、事件回写、任务桥接。
   - 阻塞项：协议问题、性能限制、数据一致性。
   - 下周计划：待实现模块或联调安排。