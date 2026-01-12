# CrystalTech → CityPhone 数据源映射

> 更新时间：2026-01-10

## 阶段推进（`technology-status.stage` / social feed `stage_advance`）
- **来源组件**：`ManifestationIntentService.markStageConsumed` 在显化完成时触发。
- **采集路径**：调用 `ProtocolOutputs.socialFeedWriter().recordStageAdvance(...)` 写入 `cityphone/social-feed`, 并通过 `TechnologyStatusWriter.updateStage(...)` + `recordStageManifest(...)` 刷新 `technology-status.json`。
- **刷新频率**：按阶段事件实时写入；每次显化推进都会刷新顶层 `updated_at` 与 `recent_events`。
- **单位与含义**：`stage.current/level` 为整数阶段号；`label` 基于阶段号映射（baseline/materialization/stabilization/...）。

## 能源统计（`technology-status.energy`）
- **来源组件**：`TechnologyStatusWriter.updateEnergy(...)` 接受实时快照；若未显式填写，则由 `TechnologyStatusWriter` 根据阶段生成占位数据（`derivedForStage`)。
- **现状**：Forge 侧尚未接入真实能源网路，当前回执为阶段导出的稳定占位值（状态 `stable`，level 0-100）。
- **接入计划**：待 `CrystalEnergyNetwork` 指标完成后，从服务器 Tick 内聚合近 5 分钟平均值，调用 `updateEnergy(status, level, generation, consumption, reserve, timestamp)` 刷新；同时报送单位：`generation/consumption/reserve` 以 CrystalFlux/tick 计。

## 风险枚举（`technology-status.risks`）
- **来源组件**：预留结构 `TechnologyStatusWriter.replaceRisks(List<RiskEntry>, Instant)`。
- **现状**：暂未发现可回写的风险事件，字段为空数组。
- **接入计划**：待城市系统确认风险枚举后，在风险检测监听器中构造 `RiskEntry.of(id, label, severity, description, updatedAt)` 并调用 `replaceRisks`。

## 事件流水（`technology-status.recent_events`)）
- **来源组件**：`TechnologyStatusWriter.recordStageManifest(...)` 由阶段推进时调用，追加 `stage_manifested` 类型事件。
- **刷新频率**：每次阶段推进追加一条，保留最近 32 条；较旧事件将被裁剪。
- **备注**：事件包含 `player_id`、`player_name`、`scenario_id/version` 等上下文，方便 CityPhone 时间线复现。

## 信任指数（`cityphone/social-feed/trust_index.json` & `metrics.json`）
- **来源组件**：`SocialFeedWriter` 维护内存态 `trustIndex`，每次阶段推进以 `+0.05` 调整，并写入 `trust_index.json`。
- **现状**：使用默认初始值 0.5。若未来需要更复杂曲线，可在阶段推进监听中传入自定义增量。
- **接入计划**：与城市系统确认后，可在 `SocialFeedWriter` 扩展接口以接受外部评分。

## 数据落盘路径
- `technology-status.json`：`run/cityphone/technology-status.json`
- `social-feed`
  - 离散事件：`run/cityphone/social-feed/*.json`
  - 指标快照：`run/cityphone/social-feed/trust_index.json`
  - 归档（压缩包中提供）：`cityphone/social-feed/events.jsonl`、`metrics.json`

## 刷新触发概览
| 触发行为 | 写入 artefact | 说明 |
| --- | --- | --- |
| Manifestation Intent 显化成功 (`markStageConsumed`) | `social-feed` 事件、`technology-status`、`recent_events`、`trust_index` | 当前唯一触发点，含阶段信息与占位能源。 |
| Energey 传感器（待接入） | `technology-status.energy` | 计划在 Tick 汇总后调用 `updateEnergy`。 |
| 风险分析（待接入） | `technology-status.risks` | 完成风险监控后批量替换。 |

> 若需要扩展字段或新增事件类型，请提前告知，我们同步更新写入逻辑与文档。
