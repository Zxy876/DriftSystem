# DRIFT_FIRST_REAL_EXECUTE_RUNBOOK

本手册用于首次真实 execute 上线。**首次真实 execute 必须 personal-only，Shared 禁止执行**。

---

## 1️⃣ 环境检查

上线前逐项确认：

1. 服务器 IP
  - 记录 MC 服务器 IP（示例：`127.0.0.1` 或实际公网/内网地址）。
2. MC 版本
  - 记录当前服务端版本（与插件版本匹配）。
3. RCON 是否开启
  - `server.properties` 中 `enable-rcon=true`。
4. 端口是否开放
  - `server.properties` 中 `rcon.port` 与网络安全组/防火墙一致放通。
5. 后端部署位置
  - 明确后端进程所在机器、启动方式、日志路径。

附：后端常用环境变量

- `MINECRAFT_RCON_HOST`
- `MINECRAFT_RCON_PORT`
- `MINECRAFT_RCON_PASSWORD`
- `DRIFT_SCENE_REALIZATION_ONLY=1`
- `DRIFT_SCENE_REALIZE_ALLOW_EXECUTE`（首次默认 `0`）

---

## 2️⃣ readiness 验证步骤

执行：

```bash
curl -s "http://127.0.0.1:8000/scene/execute-readiness?player_id=player_001"
```

必须看到（至少这四项均为 true）：

```json
{
  "allow_execute_flag": true,
  "rcon_available": true,
  "executor_ready": true,
  "can_execute": true
}
```

如果 `can_execute=false`，排查顺序写死：

1. `allow_execute_flag=false`
  - 设置 `DRIFT_SCENE_REALIZE_ALLOW_EXECUTE=1`
  - 重启后端后重查 readiness。
2. `rcon_available=false`
  - 检查 MC 端 `enable-rcon`、`rcon.port`、`rcon.password`
  - 检查端口放通与主机可达性
  - 重启 MC 后重查 readiness。
3. `executor_ready=false`
  - 检查后端 RCON 连接配置是否与 MC 一致
  - 检查后端日志中的 RCON handshake 错误
  - 重启后端后重查 readiness。

---

## 3️⃣ 首次真实执行流程（personal-only）

**以下顺序必须严格执行，不允许调整：**

1. 三人进入 Shared。
2. 仅 Player1 进入 Personal。
3. 仅 Player1 执行 `/scene/realize`（`execute=true`）。
4. 验证 patch log。
5. 验证世界生成。
6. Player1 退出 Personal。
7. 三人集合。

请求样例（Player1，personal-only）：

```json
{
  "scene_id": "first_exec_live_01",
  "player_id": "player_001",
  "mode": "personal",
  "domain": "P1",
  "execute": true,
  "anchor": {"x": 1000, "y": 64, "z": 0},
  "assets": [
   {"resource_id": "drift:path_axis_1x1x15", "anchor": {"x": 1000, "y": 64, "z": 0}}
  ]
}
```

强约束：

- 首次真实 execute 仅允许 `mode=personal`。
- Shared 模式禁止 execute。

---

## 4️⃣ 回滚与风险处理

若发生异常（`blocked`、执行失败、世界异常），立即执行：

1. 关闭环境变量
  - `DRIFT_SCENE_REALIZE_ALLOW_EXECUTE=0`
2. 重启后端
3. 重启 MC
4. 清理 Personal 域
  - 清理本次 execute 影响区域，仅限对应 `P{n}` 域
5. 不允许 Shared 执行
  - 保持 shared 禁 execute，回到 dry-run 验证

回滚后必须复检：

- `GET /scene/execute-readiness`
- `can_execute` 应为 `false`（直到再次批准开启）

