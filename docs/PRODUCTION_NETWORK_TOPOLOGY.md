# PRODUCTION_NETWORK_TOPOLOGY

## 固定网络结构

- HCMCL → VPS:25565
- Railway → VPS:25575 (RCON)

## 角色边界（写死）

- Minecraft 不在 Railway 上运行。
- Railway 只负责 API + RCON 控制。

## 流量说明

1. 玩家（HCMCL）只连接 VPS 的 Minecraft 游戏端口 `25565`。
2. 后端（Railway）只连接 VPS 的 RCON 端口 `25575`。
3. Scene Realization 执行链在 Railway 后端内完成，最终通过 RCON 下发命令到 VPS。
