# 理想城 × 水晶科技 联调检查清单

此表用于 Forge 团队在不依赖 Plugin 运行的情况下，自检 Manifestation Intent 联调是否通过。

## 预备条件
- 已获得目录结构：`city-intents/pending|processing|processed|failed/`
- 拥有示例文件：`city-intents/pending/example-stage-1.json`（包含 `player_id` + `intent` 信封结构）
- 如需自动生成，可运行 `scripts/drop_intent_example.py`

## 验收步骤
- [ ] 将示例 intent 信封放入 `city-intents/pending/`
- [ ] Forge 日志打印 “Intent received” 或等效提示
- [ ] JSON schema 校验通过（字段名、类型、时间戳）
- [ ] 意图文件被移动至 `city-intents/processing/`
- [ ] 合法玩家行为触发阶段推进（Stage advance）
- [ ] 意图文件在完成后移入 `city-intents/processed/`
- [ ] 当目录为空时，Stage 不发生推进
- [ ] 过期意图被拒绝并移入 `city-intents/failed/`，同时输出拒绝原因

## Plugin 行为声明
- Plugin 仅在裁决 `ACCEPT` 且 ready_for_build 时写入 `pending/`；`INCOMPLETE` 或草稿状态不会生成意图。

## 常见问题提醒
- 若需要自定义 intent，请保持信封结构和 `player_id`、`intent.allowed_stage`、`intent.issued_at`、`intent.expires_at` 等字段完整，并使用 ISO-8601 UTC 时间。
- Forge 可根据自身流程将文件移动到 `processing/` 或 `failed/`，Plugin 不会回写这些目录。

## 产线对接交付物（Forge → Plugin）
- `technology-status.json` 样例：包含最新 stage、energy、risks、events、updated_at 字段，便于我们对照解析。
- 社会反馈稿件：`cityphone/social-feed/events.jsonl` 与 `metrics.json` 实际输出，至少覆盖一次阶段晋升事件。
- 数据源说明文档：列出阶段推进触发点、能耗统计接口、风险事件定义、信任指数计算方式。
- Writer 接入代码：调用 `TechnologyStatusWriter`、`SocialFeedWriter` 的关键片段或 Pull Request 链接。
- 联调日志：`/crystalintent` 本地运行记录、端到端脚本输出（含 intent id / timestamp），用于验收归档。
- 端到端自测：使用插件仓库脚本 `PYTHONPATH=backend python3 -m scripts.check_protocol_end_to_end --protocol-root <bundle_dir>` 验证样本可被解析并生成 CityPhone 快照。

```
-> 2026-01-10 已收到 `plugin_bundle_20260110/`，样本通过 `scripts.check_protocol_end_to_end` 自测；待 Forge 接入真实能源与风险数据后，可在同目录持续追加样本并复跑脚本。
```
