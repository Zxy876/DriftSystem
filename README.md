[![zread](https://img.shields.io/badge/Ask_Zread-_.svg?style=flat&color=00b0aa&labelColor=000000&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTQuOTYxNTYgMS42MDAxSDIuMjQxNTZDMS44ODgxIDEuNjAwMSAxLjYwMTU2IDEuODg2NjQgMS42MDE1NiAyLjI0MDFWNC45NjAxQzEuNjAxNTYgNS4zMTM1NiAxLjg4ODEgNS42MDAxIDIuMjQxNTYgNS42MDAxSDQuOTYxNTZDNS4zMTUwMiA1LjYwMDEgNS42MDE1NiA1LjMxMzU2IDUuNjAxNTYgNC45NjAxVjIuMjQwMUM1LjYwMTU2IDEuODg2NjQgNS4zMTUwMiAxLjYwMDEgNC45NjE1NiAxLjYwMDFaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00Ljk2MTU2IDEwLjM5OTlIMi4yNDE1NkMxLjg4ODEgMTAuMzk5OSAxLjYwMTU2IDEwLjY4NjQgMS42MDE1NiAxMS4wMzk5VjEzLjc1OTlDMS42MDE1NiAxNC4xMTM0IDEuODg4MSAxNC4zOTk5IDIuMjQxNTYgMTQuMzk5OUg0Ljk2MTU2QzUuMzE1MDIgMTQuMzk5OSA1LjYwMTU2IDE0LjExMzQgNS42MDE1NiAxMy43NTk5VjExLjAzOTlDNS42MDE1NiAxMC42ODY0IDUuMzE1MDIgMTAuMzk5OSA0Ljk2MTU2IDEwLjM5OTlaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik0xMy43NTg0IDEuNjAwMUgxMS4wMzg0QzEwLjY4NSAxLjYwMDEgMTAuMzk4NCAxLjg4NjY0IDEwLjM5ODQgMi4yNDAxVjQuOTYwMUMxMC4zOTg0IDUuMzEzNTYgMTAuNjg1IDUuNjAwMSAxMS4wMzg0IDUuNjAwMUgxMy43NTg0QzE0LjExMTkgNS42MDAxIDE0LjM5ODQgNS4zMTM1NiAxNC4zOTg0IDQuOTYwMVYyLjI0MDFDMTQuMzk4NCAxLjg4NjY0IDE0LjExMTkgMS42MDAxIDEzLjc1ODQgMS42MDAxWiIgZmlsbD0iI2ZmZiIvPgo8cGF0aCBkPSJNNCAxMkwxMiA0TDQgMTJaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00IDEyTDEyIDQiIHN0cm9rZT0iI2ZmZiIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIvPgo8L3N2Zz4K&logoColor=ffffff)](https://zread.ai/Zxy876/DriftSystem)
# DriftSystem · 心悦宇宙

最低摩擦的 AI 冒险体验：玩家进入 Minecraft 后只需自然语言对话，即可调度剧情、生成建造计划、触发社会反馈并让世界实时响应。

当前分支 **scienceline** 针对「紫水晶企划 × 双向通信」玩法做了以下整合：
- CityPhone UI 读取档案馆状态、收集叙述并在提交后自动触发裁决流程。
- Forge 侧写回的 `cityphone/social-feed` 事件映射为「城市气氛」，玩家上线即看到粒子/天气/音效反馈。
- 理想城市流水线（Ideal City Pipeline）统一承接叙述、裁决、建造、社会反馈与技术状态，维持审计可追踪性。

## 目录解剖

```
backend/                  FastAPI 后端，含 Ideal City 管线、Heart Levels 数据、社会反馈解析
system/mc_plugin/         Paper 1.20 插件源码，负责玩家交互、世界渲染、CityPhone、气氛播发
docs/                     设计稿与操作手册（CityPhone、Ideal City、Cinematic 等）
phases/, scripts/, tools/ 迭代规划、调试脚本、自动化入口
server/, backend/server   内嵌 Paper 测试服（构建产物，勿提交）
tmp_protocol_run/         临时导出的 Forge 协议样本（开发期缓存）
```

## CityPhone 文档索引

- [CityPhone 作为策展终端的愿景说明](docs/cityphone-vision.md)
- [CityPhone 策展终端工程落地方案](docs/cityphone-execution-plan.md)
- [CityPhone API Contract Snapshot (Iteration 1 Narrative Baseline)](docs/api/cityphone-contract.md)
- [展馆叙事 Markdown → JSON 生成脚本](backend/scripts/generate_exhibit_narrative.py)

## 端到端回路

1. **玩家叙述**：聊天监听器将自然语言交给 `IntentRouter2` 与 `IntentDispatcher2`，必要时写入 CityPhone。
2. **后端裁决**：`/ideal-city/cityphone/action` 接口将叙述包装成 DeviceSpec，执行语义归一化 → 审裁 → 建造计划 → 叙事播报。
3. **Forge 回写**：阶段推进后 Forge 生成 `cityphone/social-feed/events.jsonl` 与 `metrics.json`。
4. **城市气氛**：`SocialFeedbackRepository` 解析社会反馈并派生粒子/天气/音效，插件通过新接口 `/ideal-city/social-feedback/atmosphere` 拉取。
5. **上线播报**：`SocialAtmosphereListener` 在玩家加入时调用 `SocialAtmosphereManager`，展示标题、发送摘要、播放粒子与临时天气，默认 10 秒后恢复天气。

```
玩家 -> Paper Plugin -> FastAPI -> Ideal City Pipeline
   ^                  |            |
   |                  |            v
 社会气氛 <- Forge <- 数据协议 <- Build/Social Writers
```

## 快速启动

```bash
# 后端
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 插件
cd ../system/mc_plugin
mvn clean package
cp target/mc_plugin-1.0-SNAPSHOT.jar ../../server/plugins/DriftSystem.jar

# Paper 服务器（首次需接受 EULA）
cd ../../server
java -Xmx4G -Xms2G -jar paper-1.20.1.jar
```

配置 `server/plugins/DriftSystem/config.yml`，确保：

```yaml
backend_url: "http://127.0.0.1:8000"
debug:
  task_token: "<optional-token>"
```

游戏内验证：

```text
/drift status            # 检查后端连通
/cityphone give          # 获取 CityPhone 终端
/cityphone open          # 打开档案界面
聊天描述愿景/行动       # 触发 Ideal City 裁决
重新登录                # 查看城市气氛播报（粒子/天气/音效 + 摘要）
```

## 关键后端接口

- `POST /ideal-city/cityphone/action`：CityPhone 提交、姿态同步、模板操作。
- `GET  /ideal-city/cityphone/state/{player}`：UI 状态快照。
- `GET  /ideal-city/social-feedback/atmosphere`：返回社会反馈快照 + 气氛推导（新功能）。
- `POST /ideal-city/narrative/ingest`：自然语言事件自动归档为草稿或正式提案。
- `GET  /ideal-city/build-plans/executed/{plan}`：建造执行记录审计。

## 开发提示

- **测试**：`cd backend && python3 -m pytest test_social_feedback.py` 覆盖社会反馈解析；`./test_all.sh` 运行完整后端自测。
- **插件构建**：`cd system/mc_plugin && mvn -q package -DskipTests`，生成物位于 `target/mc_plugin-1.0-SNAPSHOT.jar`。
- **CityPhone 协议样本**：Forge 样本位于 `tmp_protocol_run/cityphone/social-feed/`，如需重置可运行 `rm -rf tmp_protocol_run && mkdir -p tmp_protocol_run`。
- **Secrets**：`backend/.env` 持久化 OpenAI/Deepseek 等密钥。模板见 `backend/.env.example`（已忽略版本控制）。

## 常用命令速查

| 命令                  | 用途                                   |
|-----------------------|----------------------------------------|
| `/drift status`       | 查看后端状态、场景联通                |
| `/taskdebug <token>`  | 手动触发任务调试，需要 config 令牌     |
| `/cityphone open`     | 打开档案馆 CityPhone                   |
| `/cinematic <dsl>`    | 执行镜头 DSL（配合 CityPhone mod hooks）|
| `/storycreative`      | 进入剧情创作模式                       |

## 故障排查

- **气氛缺失**：确认后端 `protocol/cityphone/social-feed/` 目录存在有效事件；可运行 `python backend/scripts/check_protocol_end_to_end.py` 检验 Forge 回路。
- **CityPhone 不更新**：检查 `backend/logs` 与 `/ideal-city/cityphone/state` 响应，必要时删除 `backend/data/ideal_city/story_state` 对应玩家缓存。
- **建造计划无效**：`backend/data/ideal_city/build_queue/executed` 内文件可追踪执行指令和缺失模组。
- **意图无响应**：服务器日志查看 `IntentDispatcher2` 输出，确保 Paper 端未丢失与后端通信。

## 许可证

项目沿用 [MIT License](./LICENSE)。代码、剧情与工具可自由复用，引用时请注明来源。

> 让剧情在 Minecraft 中自然生长，
> 让城市的每一次呼吸都回应玩家行动。
