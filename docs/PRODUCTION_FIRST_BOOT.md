# PRODUCTION_FIRST_BOOT

## 首次生产启动顺序（固定）

1. 部署 Railway
2. 部署 VPS
3. 启动 MC
4. 验证 readiness
5. 单人进入 personal
6. 执行 dry_run
7. 执行 execute
8. 查看 transactions.log
9. 退出 personal
10. 三人进服

## 0) Railway 部署

- 在 Railway 绑定仓库并使用 `backend/Procfile` 启动。
- 必须配置环境变量，参考 [RAILWAY_ENVIRONMENT.md](RAILWAY_ENVIRONMENT.md)。

```bash
# 方式 A：在仓库根目录执行
cd /Users/zxydediannao/DRIFT_SCIENCELINE
railway up backend --path-as-root -d

# 方式 B：在 backend 目录执行
cd /Users/zxydediannao/DRIFT_SCIENCELINE/backend
railway up . --path-as-root -d
```

注意：如果你已经在 `backend/` 目录，不要再执行 `railway up backend --path-as-root -d`，否则会上传到错误路径（常见现象：Railpack 只看到 `./`，无法检测 Python 项目）。

## 1) VPS 部署（Ubuntu 22.04）

```bash
sudo bash deploy/setup_mc_server.sh
sudo cp deploy/minecraft.service /etc/systemd/system/minecraft.service
sudo systemctl daemon-reload
sudo systemctl enable minecraft
sudo systemctl start minecraft
```

## 2) readiness 检查

```bash
curl https://<railway-domain>/scene/execute-readiness
```

必须包含字段：

- allow_execute_flag
- rcon_available
- executor_ready
- mode
- can_execute
- reason

目标：`can_execute=true`。

## 3) 单人 personal dry_run

```bash
curl -X POST "https://<railway-domain>/world/story/start" \
  -H "Content-Type: application/json" \
  -d '{"player_id":"player_001","level_id":"flagship_tutorial"}'

curl -X POST "https://<railway-domain>/scene/realize" \
  -H "Content-Type: application/json" \
  -d '{
    "scene_id":"prod_dry_001",
    "player_id":"player_001",
    "mode":"personal",
    "domain":"P1",
    "execution_mode":"dry_run",
    "anchor":{"x":1000,"y":64,"z":0},
    "assets":[{"resource_id":"drift:path_axis_1x1x15","anchor":{"x":1000,"y":64,"z":0}}]
  }'
```

## 4) 单人 personal execute

```bash
curl -X POST "https://<railway-domain>/scene/realize" \
  -H "Content-Type: application/json" \
  -d '{
    "scene_id":"prod_exec_001",
    "player_id":"player_001",
    "mode":"personal",
    "domain":"P1",
    "execute":true,
    "anchor":{"x":1000,"y":64,"z":0},
    "assets":[{"resource_id":"drift:path_axis_1x1x15","anchor":{"x":1000,"y":64,"z":0}}]
  }'
```

## 5) 查看日志

- 后端事务日志：`backend/data/patch_logs/transactions.log`
- 验证 `patch_id` 存在 `validated` / `pending` 记录。

## 6) 退出 personal 与三人进服

```bash
curl -X POST "https://<railway-domain>/world/story/end" \
  -H "Content-Type: application/json" \
  -d '{"player_id":"player_001","level_id":"flagship_tutorial"}'
```

然后三人通过 HCMCL 连接：`<VPS公网IP>:25565`。

## 约束（写死）

- 首次 execute 必须 personal-only。
- Shared 下禁止 execute。
