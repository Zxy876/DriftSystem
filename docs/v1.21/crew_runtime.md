# Crew Runtime（Issue 3.3）

- 运行脚本：`node system/taskcrew/bridge.js --dry-run docs/v1.21/crew_task_example.json`
- 默认 dry-run：仅解析任务 JSON，打印动作，不连接 Mineflayer / Minecraft。
- 约束：只允许动作 setblock / clear / travel；若缺必要坐标/方块/区域将报错退出。
- TODO（需在线上环境验证）：
  - 真实 mineflayer 适配与安全沙箱。
  - 执行前后世界状态快照与回滚路径。

## 当前现状（玩家指挥）
- 目前仅支持通过 CLI 调用 `system/taskcrew/bridge.js` 执行任务，动作限定 setblock/clear/travel。
- MC 服内暂无“指挥建造团队”的指令；`plugin.yml` 列表命令不含下发建造任务能力。
- 若需玩家在聊天框指挥，后续需新增插件指令（示例 `/crew`/`/buildteam`）并接入 backend/bridge，再行实现。
