# CrystalTech → Plugin 交付包（2026-01-10）

- **生成时间**：2026-01-10
- **Forge 分支/提交**：`main @ 2d89f434267da619fd3826033515e182b8407b54`
- **联调脚本**：`backend/scripts/check_protocol_end_to_end.py`

## 压缩包内容
```
protocol/technology-status.json       # 最新一次写回快照（含 stage/energy/risks/events/updated_at）
cityphone/social-feed/events.jsonl    # 最近一次阶段晋升事件样本
cityphone/social-feed/metrics.json    # trust_index 指标快照
logs/protocol_e2e_run_20260110.log    # 端到端脚本运行输出（含 intent id & 时间戳）
docs/data_source_mapping.md           # 字段来源、刷新频率、单位说明
src/forge_writer_hooks.diff           # Forge 调用 TechnologyStatusWriter / SocialFeedWriter 的关键挂点
README.md                             # 生成说明与复现步骤
```

> 注：当前样本来自本地模拟器（`scripts/simulate_protocol_worker.py`），尚未覆盖连续 24 小时真实数据。待能源与风险数据源接入后，会补充产线采集的长周期档案。

## 复现步骤
1. 清理测试输出：
   ```bash
   rm -rf run/protocol_e2e && mkdir -p run/protocol_e2e
   ```
2. 启动端到端脚本并等待其在 `run/protocol_e2e/city-intents/pending/` 写入示例意图：
   ```bash
   CRYSTALTECH_PROTOCOL_ROOT="$PWD/run/protocol_e2e" \
   PYTHONPATH=backend python3 -m scripts.check_protocol_end_to_end \
     --protocol-root "$PWD/run/protocol_e2e" \
     --auto-drop-intent --expected-stage 1 --timeout 180 --poll-interval 1
   ```
3. 另启一终端执行模拟处理：
   ```bash
   PYTHONPATH=backend python3 scripts/simulate_protocol_worker.py \
     run/protocol_e2e --timeout 60 --poll-interval 0.5
   ```
4. 脚本完成后，可在 `run/protocol_e2e/cityphone/` 获取与压缩包一致的 Artefact；日志输出见 `logs/protocol_e2e_run_20260110.log`。

如需压缩：
```bash
tar -cvzf crystaltech_protocol_bundle_20260110.tar.gz -C handoff plugin_bundle_20260110
```
