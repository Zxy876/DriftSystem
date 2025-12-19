[![zread](https://img.shields.io/badge/Ask_Zread-_.svg?style=flat&color=00b0aa&labelColor=000000&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTQuOTYxNTYgMS42MDAxSDIuMjQxNTZDMS44ODgxIDEuNjAwMSAxLjYwMTU2IDEuODg2NjQgMS42MDE1NiAyLjI0MDFWNC45NjAxQzEuNjAxNTYgNS4zMTM1NiAxLjg4ODEgNS42MDAxIDIuMjQxNTYgNS42MDAxSDQuOTYxNTZDNS4zMTUwMiA1LjYwMDEgNS42MDE1NiA1LjMxMzU2IDUuNjAxNTYgNC45NjAxVjIuMjQwMUM1LjYwMTU2IDEuODg2NjQgNS4zMTUwMiAxLjYwMDEgNC45NjE1NiAxLjYwMDFaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00Ljk2MTU2IDEwLjM5OTlIMi4yNDE1NkMxLjg4ODEgMTAuMzk5OSAxLjYwMTU2IDEwLjY4NjQgMS42MDE1NiAxMS4wMzk5VjEzLjc1OTlDMS42MDE1NiAxNC4xMTM0IDEuODg4MSAxNC4zOTk5IDIuMjQxNTYgMTQuMzk5OUg0Ljk2MTU2QzUuMzE1MDIgMTQuMzk5OSA1LjYwMTU2IDE0LjExMzQgNS42MDE1NiAxMy43NTk5VjExLjAzOTlDNS42MDE1NiAxMC42ODY0IDUuMzE1MDIgMTAuMzk5OSA0Ljk2MTU2IDEwLjM5OTlaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik0xMy43NTg0IDEuNjAwMUgxMS4wMzg0QzEwLjY4NSAxLjYwMDEgMTAuMzk4NCAxLjg4NjY0IDEwLjM5ODQgMi4yNDAxVjQuOTYwMUMxMC4zOTg0IDUuMzEzNTYgMTAuNjg1IDUuNjAwMSAxMS4wMzg0IDUuNjAwMUgxMy43NTg0QzE0LjExMTkgNS42MDAxIDE0LjM5ODQgNS4zMTM1NiAxNC4zOTg0IDQuOTYwMVYyLjI0MDFDMTQuMzk4NCAxLjg4NjY0IDE0LjExMTkgMS42MDAxIDEzLjc1ODQgMS42MDAxWiIgZmlsbD0iI2ZmZiIvPgo8cGF0aCBkPSJNNCAxMkwxMiA0TDQgMTJaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00IDEyTDEyIDQiIHN0cm9rZT0iI2ZmZiIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIvPgo8L3N2Zz4K&logoColor=ffffff)](https://zread.ai/Zxy876/DriftSystem)
# DriftSystem · 心悦宇宙
> Fully natural-language-driven AI adventure system for Minecraft

## Overview
DriftSystem (心悦宇宙) 将 Minecraft 服务器与 AI 故事引擎融合，玩家只需自然语言即可驱动剧情、改造世界、创建关卡并推进多人协同冒险。Java 插件负责即时反馈与世界渲染，Python FastAPI 后端提供意图识别、剧情编排、DSL 注入和教程/任务逻辑。

## Core Highlights
- 多意图自然语言管线：`IntentRouter2` + `IntentDispatcher2` 实现聊天驱动的一发多命令解析。
- Heart Levels 剧情引擎：内置 30+ 章节，支持剧情分支、推荐、故事创作与小地图导航。
- 世界/镜头系统：`SceneAwareWorldPatchExecutor`、HUD、CinematicController 与 NPC 管理器联动完成动态渲染。
- 教学与创作体验：TutorialManager 保护新手流程，StoryCreativeManager 支持玩家即兴 DSL 注入。
- FastAPI 后端：结构化 API 覆盖意图、世界、剧情、NPC、教程、提示、树形 DSL、MiniMap PNG。

## Architecture
```
              ┌──────────────┐
              │ Minecraft    │
              │ Paper 1.20.x │
              └──────┬───────┘
                     │ Bukkit API
        ┌────────────▼────────────┐
        │ DriftSystem Plugin      │
        │ Java 17 + Maven         │
        │ - 聊天监听 + 意图路由   │
        │ - 世界/剧情/教程引擎    │
        │ - HUD + Cinematic + NPC │
        └────────────┬────────────┘
                     │ HTTP/JSON
        ┌────────────▼────────────┐
        │ FastAPI Backend         │
        │ Python 3.10+            │
        │ - AI Intent / Story DSL │
        │ - Heart Levels 数据      │
        │ - 世界/地图 REST 接口    │
        └─────────────────────────┘
```

## Repository Layout
```
backend/               FastAPI 服务、核心剧情/世界引擎与数据集
system/mc_plugin/      Minecraft 插件源码、构建脚本、插件元数据
docs/                  系统设计、剧情、关卡 DSL 说明
phases/                Heart Universe 项目阶段规划
tools/, scripts        构建、修复、部署自动化脚本
server/, backend/server 内置 Paper 服务器与占位资源（忽略产物）
```

## Quick Start
1. 安装 Python 3.10+, Java 17+, Maven 3.6+, Paper 1.20.x。
2. 在项目根执行：
   ```bash
   ./start_all.sh
   ```
   脚本会创建 venv、安装后端依赖、启动 FastAPI、编译插件并复制到嵌入式服务器。
3. 进入 `backend/server` 启动 Paper：
   ```bash
   java -Xmx4G -Xms2G -jar paper-*.jar
   ```
4. 游戏内执行 `/drift status` 检查联通，然后直接用自然语言对话。

## Manual Workflow
**后端**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**插件**
```bash
cd system/mc_plugin
mvn clean package
```
生成的 `target/DriftSystem-*.jar` 复制到服务器 `plugins/` 目录。

**服务器配置**
编辑 `backend/server/plugins/DriftSystem/config.yml`：
```yaml
backend_url: "http://127.0.0.1:8000"
system:
  debug: false
story:
  start_level: "level_01"
world:
  allow_world_modification: true
```

## Configuration & Secrets
- `backend/.env` (不随仓库提交)：`DEEPSEEK_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`。
- Paper 服务器属性：`backend/server/server.properties`、`eula.txt` 等按需自定。
- 插件调试：`debug.task_token` 允许 `/taskdebug` 命令访问受限接口。

## Development & Testing
- 运行后端测试：`cd backend && pytest` 或 `./test_all.sh`。
- 构建插件：`cd system/mc_plugin && mvn package`，可配合 `./build.sh` 快捷脚本。
- 集成脚本：`test_all.sh`, `test_integration.sh`, `test_story.sh`, `test_tutorial.sh` 等覆盖剧情、任务、自愈流程。
- 自检：`drift_backend_selftest.py` / `backend/drift_backend_selftest.py` 提供快速回归。

## Content & Docs
- Heart Levels 内容位于 `backend/data/heart_levels/` 与 `backend/data/flagship_levels/`。
- DSL、剧情、情绪系统等详见 `docs/*.md`、`NPC_BEHAVIORS_TESTING.md`、`TUTORIAL_SYSTEM.md`。
- `phases/` 保存项目路线图与阶段性叙事设计。

## Minecraft Commands
- `/drift status|sync|debug`：核心状态与同步。
- `/storycreative`, `/recommend`, `/questlog`：HUD、推荐与创作入口。
- `/taskdebug <token>`：意图任务调试命令（需要配置令牌）。
- 自定义命令 `tp2`, `time2`, `sayc`, `npc`, `cinematic` 等对应世界调度与 NPC 管理。

## Tooling & Automation
- `start_all.sh`：一键构建启动。
- `build_plugin.sh`, `build_and_deploy_plugin.sh`, `make_plugin.sh`：部署流水线。
- `fix_*.sh` 与 `tools/`：自动修复/结构化脚本，辅助调试或迁移。

## Troubleshooting
- 后端连通：`curl http://127.0.0.1:8000/`，日志位于 `backend/backend.log`。
- 插件配置：确保 `config.yml` backend_url 与实际端口一致。
- 世界无响应：启用 `system.debug: true`，关注服务器控制台与 `/taskdebug` 输出。
- 清理教程状态：`/reload` 前执行 `TutorialManager.cleanupPlayer`，或重启服务器重置。

## Contributing
欢迎通过 Issue、Pull Request、剧情内容或 DSL 样例参与。提交前请跑通后端测试并确认 `system/mc_plugin/target/`、`backend/venv/` 等产物未纳入版本控制。

## License
本项目以 [MIT License](./LICENSE) 授权发布，可自由使用、修改与分发。详见仓库中的 `LICENSE` 文件。

**让剧情在Minecraft中自然生长** 🌱

**体验完全由对话驱动的冒险之旅** 🚀
