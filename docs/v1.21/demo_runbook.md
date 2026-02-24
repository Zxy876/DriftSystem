# demo_features.sh 运行手册（Issue 7.1）

- 默认 `--dry-run`：不发请求，仅记录计划到 `logs/demos/<date>/demo.log`（默认 `<date>=20260121` 可通过 `DEMO_DATE` 覆盖）。
- 实际演示：`bash demo_features.sh --run`（需后台可用，BASE_URL 默认 http://127.0.0.1:8000）。
- 阶段顺序：IMPORT → SET_DRESS → REHEARSE → TAKE（对应 backend 阶段迁移）。
- 输出目录：`logs/demos/<date>/`，包含 `demo.log` 以及 curl 输出（若运行模式）。
- TODO（需人工环境验证）：
  - 确认 backend 连接无误，替换真实 player_id。
  - 可将阶段迁移与导演 token 集成到 /director 命令链路进行演示。
