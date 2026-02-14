[![zread](https://img.shields.io/badge/Ask_Zread-_.svg?style=flat&color=00b0aa&labelColor=000000&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTQuOTYxNTYgMS42MDAxSDIuMjQxNTZDMS44ODgxIDEuNjAwMSAxLjYwMTU2IDEuODg2NjQgMS42MDE1NiAyLjI0MDFWNC45NjAxQzEuNjAxNTYgNS4zMTM1NiAxLjg4ODEgNS42MDAxIDIuMjQxNTYgNS42MDAxSDQuOTYxNTZDNS4zMTUwMiA1LjYwMDEgNS42MDE1NiA1LjMxMzU2IDUuNjAxNTYgNC45NjAxVjIuMjQwMUM1LjYwMTU2IDEuODg2NjQgNS4zMTUwMiAxLjYwMDEgNC45NjE1NiAxLjYwMDFaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00Ljk2MTU2IDEwLjM5OTlIMi4yNDE1NkMxLjg4ODEgMTAuMzk5OSAxLjYwMTU2IDEwLjY4NjQgMS42MDE1NiAxMS4wMzk5VjEzLjc1OTlDMS42MDE1NiAxNC4xMTM0IDEuODg4MSAxNC4zOTk5IDIuMjQxNTYgMTQuMzk5OUg0Ljk2MTU2QzUuMzE1MDIgMTQuMzk5OSA1LjYwMTU2IDE0LjExMzQgNS42MDE1NiAxMy43NTk5VjExLjAzOTlDNS42MDE1NiAxMC42ODY0IDUuMzE1MDIgMTAuMzk5OSA0Ljk2MTU2IDEwLjM5OTlaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik0xMy43NTg0IDEuNjAwMUgxMS4wMzg0QzEwLjY4NSAxLjYwMDEgMTAuMzk4NCAxLjg4NjY0IDEwLjM5ODQgMi4yNDAxVjQuOTYwMUMxMC4zOTg0IDUuMzEzNTYgMTAuNjg1IDUuNjAwMSAxMS4wMzg0IDUuNjAwMUgxMy43NTg0QzE0LjExMTkgNS42MDAxIDE0LjM5ODQgNS4zMTM1NiAxNC4zOTg0IDQuOTYwMVYyLjI0MDFDMTQuMzk4NCAxLjg4NjY0IDE0LjExMTkgMS42MDAxIDEzLjc1ODQgMS42MDAxWiIgZmlsbD0iI2ZmZiIvPgo8cGF0aCBkPSJNNCAxMkwxMiA0TDQgMTJaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00IDEyTDEyIDQiIHN0cm9rZT0iI2ZmZiIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIvPgo8L3N2Zz4K&logoColor=ffffff)](https://zread.ai/Zxy876/DriftSystem)
[![完整文档](https://img.shields.io/badge/文档-zread.ai-00b0aa)](https://zread.ai/Zxy876/DriftSystem)

# DriftSystem · 心悦宇宙

> **用自然语言驱动世界** — 一个完全由 AI 驱动的 Minecraft 剧情系统

[![Demo Video](https://img.shields.io/badge/Watch_Demo-bilibili-pink?logo=bilibili)](https://b23.tv/UhqhkE9)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)

---

## 视频介绍

[【我做了一个「用自然语言驱动世界」的 Minecraft AI 剧情系统｜DriftSystem Demo](https://b23.tv/UhqhkE9)](https://b23.tv/UhqhkE9)

> 点击上方链接观看完整演示视频，了解 DriftSystem 的核心功能和玩法体验。

---

## 简介

DriftSystem (心悦宇宙) 将 Minecraft 服务器与 AI 故事引擎融合，玩家只需使用自然语言即可驱动剧情、改造世界、创建关卡并推进多人协同冒险。

- **Java 插件**负责即时反馈与世界渲染
- **Python FastAPI 后端**提供意图识别、剧情编排、DSL 注入和教程/任务逻辑

---

## 核心特性

### 多意图自然语言管线
- `IntentRouter2` + `IntentDispatcher2` 实现聊天驱动的一发多命令解析
- 支持对话、世界控制、关卡跳转、剧情创作等多种意图

### Heart Levels 剧情引擎
- 内置 **30+ 章节**，支持剧情分支、推荐、故事创作与小地图导航
- AI 生成式关卡系统，用自然语言即时创建新内容

### 世界/镜头系统
- `SceneAwareWorldPatchExecutor` 实现动态世界渲染
- HUD、CinematicController 与 NPC 管理器联动
- 情绪天气系统：根据剧情氛围改变天气、光照和音乐

### 教学与创作体验
- `TutorialManager` 保护新手流程，7 步引导系统
- `StoryCreativeManager` 支持玩家即兴 DSL 注入

### FastAPI 后端
- 结构化 API 覆盖意图、世界、剧情、NPC、教程、提示、树形 DSL、MiniMap PNG
- 完整的自愈与测试覆盖

---

## 系统架构

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

---

## 快速开始

### 方式一：Demo 体验包（推荐）

适合教师和快速体验用户。

1. **下载 HMCL 启动器**：https://hmcl.huangyuhui.net/
2. **安装 Minecraft 1.20.1**：在 HMCL 中安装 Minecraft Java 版 1.20.1
3. **下载 Demo 包**：解压 `DriftSystem_Demo.zip` 到桌面
4. **启动**：双击 `启动游戏.bat`，等待自动安装完成
5. **进入游戏**：保持两个黑色窗口开启，在 HMCL 中启动游戏，添加服务器 `localhost`

> 详见 [DriftSystem_Demo/README_FIRST.txt](DriftSystem_Demo/README_FIRST.txt)

### 方式二：开发者部署

```bash
# 1. 启动后端服务
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 2. 构建并部署插件
cd system/mc_plugin
./build.sh

# 3. 启动 Minecraft 服务器
cd backend/server
java -Xmx4G -Xms2G -jar paper-*.jar
```

### 一键启动脚本

```bash
./start_all.sh  # 自动构建、启动后端和服务器
```

---

## 游戏内命令

| 命令 | 功能 |
|------|------|
| `/drift status` | 查看系统状态 |
| `/drift sync` | 同步后端数据 |
| `/drift debug` | 切换调试模式 |
| `/storycreative` | 打开故事创作 HUD |
| `/recommend` | 获取关卡推荐 |
| `/questlog` | 查看任务日志 |
| `/drift tutorial start` | 开始/重新开始教学 |

---

## 项目结构

```
backend/               # FastAPI 服务、核心剧情/世界引擎与数据集
│   ├── app/          # API 路由、核心 AI 引擎、剧情系统
│   ├── data/         # Heart Levels、Flagship Levels、NPC 数据
│   └── server/       # 嵌入式 Paper 服务器配置
│
system/mc_plugin/      # Minecraft 插件源码
│   ├── src/main/java/com/driftmc/
│   │   ├── intent/   # 意图路由与分发
│   │   ├── world/    # 世界 patch 执行器
│   │   ├── story/    # 剧情引擎集成
│   │   ├── npc/      # NPC 行为系统
│   │   └── tutorial/ # 新手教学系统
│   └── pom.xml       # Maven 构建配置
│
docs/                  # 系统设计文档
│   ├── NPC_SYSTEM.md
│   ├── GEN_LEVEL_SYSTEM.md
│   ├── TUTORIAL_SYSTEM.md
│   └── ...
│
phases/                # 项目阶段规划
tools/, scripts/       # 构建、修复、部署自动化脚本
```

---

## 配置说明

### 后端环境变量 (`backend/.env`)

```env
DEEPSEEK_API_KEY=sk-xxxxx
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
```

### 插件配置 (`plugins/DriftSystem/config.yml`)

```yaml
backend_url: "http://127.0.0.1:8000"

system:
  debug: false

story:
  start_level: "level_01"

world:
  allow_world_modification: true
  allow_story_creation: true
```

---

## 开发与测试

```bash
# 后端测试
cd backend && pytest

# 构建插件
cd system/mc_plugin && mvn package

# 集成测试
./test_integration.sh
./test_tutorial.sh
```

---

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| 插件无法连接后端 | 检查 `curl http://127.0.0.1:8000/`，确认后端运行 |
| 意图识别失败 | 检查 `DEEPSEEK_API_KEY` 是否设置正确 |
| 世界 patch 不执行 | 启用 `system.debug: true` 查看日志 |
| 教程无法重置 | 执行 `/reload` 或重启服务器 |

更多问题请参考 [DEPLOYMENT.md](DEPLOYMENT.md) 和 [INTEGRATION.md](INTEGRATION.md)。

---

## 文档索引

- [SUMMARY.md](SUMMARY.md) - 完整集成总结
- [DEPLOYMENT.md](DEPLOYMENT.md) - 完整部署指南
- [INTEGRATION.md](INTEGRATION.md) - 技术集成文档
- [TUTORIAL_SYSTEM.md](TUTORIAL_SYSTEM.md) - 教学系统文档
- [NPC_BEHAVIORS_TESTING.md](NPC_BEHAVIORS_TESTING.md) - NPC 行为规范
- [GEN_LEVEL_SYSTEM.md](docs/GEN_LEVEL_SYSTEM.md) - 生成式关卡系统

更多文档请访问 [zread.ai/Zxy876/DriftSystem](https://zread.ai/Zxy876/DriftSystem)

---

## 系统要求

- **Python**: 3.10+
- **Java**: 17+
- **Maven**: 3.6+
- **Minecraft**: Paper 1.20.1
- **内存**: 4GB+ RAM
- **网络**: 稳定连接（用于 AI API）

---

## 贡献指南

欢迎通过以下方式参与：

- 提交 Issue 报告问题
- 提交 Pull Request 贡献代码
- 创作新的剧情关卡
- 分享 DSL 设计模式

---

## 许可证

本项目以 [MIT License](./LICENSE) 授权发布，可自由使用、修改与分发。

---

**[关于本项目](ABOUT.md)** · **[完整文档 @ zread](https://zread.ai/Zxy876/DriftSystem)**

**让剧情在 Minecraft 中自然生长** 🌱

**体验完全由对话驱动的冒险之旅** 🚀
