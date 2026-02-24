# DRIFT_PRODUCTION_DEPLOYMENT_EXECUTION_PLAN

## 目标

- 后端部署到 Railway
- Minecraft 部署到境外 VPS（新加坡）
- RCON 连通
- readiness 可用
- 单人 personal execute 成功
- 三人通过 HCMCL 进服
- 输出部署文档并封板

## 约束

- 禁止新增架构
- 禁止改动 V3 生产锁
- 只做部署与验证

## 第一阶段：Railway 后端部署

1. 使用 `backend/Procfile` 启动服务。
2. 配置环境变量（见 [RAILWAY_ENVIRONMENT.md](RAILWAY_ENVIRONMENT.md)）。
3. 上线后验证 `GET /scene/execute-readiness`。

## 第二阶段：VPS Minecraft 部署

1. 在 Ubuntu 22.04 执行 [deploy/setup_mc_server.sh](../deploy/setup_mc_server.sh)。
2. 安装 systemd 服务 [deploy/minecraft.service](../deploy/minecraft.service)。
3. 执行：
   - `sudo systemctl enable minecraft`
   - `sudo systemctl start minecraft`

## 第三阶段：网络结构固定

见 [PRODUCTION_NETWORK_TOPOLOGY.md](PRODUCTION_NETWORK_TOPOLOGY.md)。

## 第四阶段：首次生产验证

执行 [PRODUCTION_FIRST_BOOT.md](PRODUCTION_FIRST_BOOT.md) 中 10 步顺序。

## 第五阶段：自动化 Scene 行为（已实现）

自然语言导入路径固定为：

natural language
-> level.json
-> scene.json
-> /scene/realize

实现点：

- 导入 level 时自动写入 `scene` 区块
- 自动调用 `/scene/realize`
- 默认 `dry_run`
- 返回 `scene_status`
- 用户显式确认 execute 时才执行

禁止：natural language 直接 build。

## 第六阶段：上线前强制检查

上线前必须确认：

- readiness.can_execute == true
- RCON 连通
- personal execute 成功
- Shared 下不会触发 execute
- 三人可连 25565

## 第七阶段：交付清单

- VPS 部署脚本： [deploy/setup_mc_server.sh](../deploy/setup_mc_server.sh)
- systemd 文件： [deploy/minecraft.service](../deploy/minecraft.service)
- Railway 环境变量文档： [RAILWAY_ENVIRONMENT.md](RAILWAY_ENVIRONMENT.md)
- 首次上线 runbook： [PRODUCTION_FIRST_BOOT.md](PRODUCTION_FIRST_BOOT.md)
- 网络拓扑说明： [PRODUCTION_NETWORK_TOPOLOGY.md](PRODUCTION_NETWORK_TOPOLOGY.md)
- 自动化 scene 调用说明：本文件第五阶段 + [PRODUCTION_FIRST_BOOT.md](PRODUCTION_FIRST_BOOT.md)

完成后停止扩展。
