# CityPhone 在 DriftSystem · ScienceLine 中的定位

## 1. 角色概览
- CityPhone 被定位为理想城市线的“档案终端”，玩家主动召出它以理解裁决流程、建造进度与技术态势，而不是通过它直接操作世界。
- 按 `README.md` 的说明，它负责读取档案状态、收集叙述并触发裁决；世界气氛与粒子反馈依旧由插件和世界逻辑主导，保持“行动在 Forge、理解在 CityPhone”的双轨体验。
- 这一定位保证玩家即便不打开 CityPhone 也能继续游玩，但在需要整理叙述、补全结构或回顾阶段历史时，可以随时获得档案馆视角的指导。

## 2. 全链路流程
```
玩家 → `/cityphone` 指令 / 右键道具
  │
  ▼
Paper 插件 (`com.driftmc.cityphone.*`)
  │  REST 调用 `/ideal-city/cityphone/*`
  ▼
FastAPI (`app/api/ideal_city_api.py`)
  │  调度
  ▼
`IdealCityPipeline` (`app/core/ideal_city/pipeline.py`)
  │  整合 StoryState / BuildPlan / Protocol artefact
  ▼
后端存储与协议目录
  │
  └─ `backend/data/ideal_city/story_state/…`
     `backend/data/ideal_city/build_queue/…`
     `backend/data/ideal_city/protocol/{cityphone,…}`
```

## 3. 插件侧实现（`system/mc_plugin/`）
- `CityPhoneManager`：生成带有 `cityphone_device` NBT 标记的指南针道具，负责 `/ideal-city/cityphone/state` 与 `/ideal-city/cityphone/action` 的调用，当前仅支持 `submit_narrative` 与 `push_pose` 动作。
- `CityPhoneCommand`：挂接 `/cityphone give|open|say|pose`，面向无 GUI 的快速调试。
- `CityPhoneListener` 与 `CityPhoneInventoryListener`：拦截右键与 GUI 交互，确保只有持有 CityPhone 道具时才能打开界面；模板套用相关按钮已移除。
- `CityPhoneUi`：使用库存界面呈现四大面板（阶段、资源、定位、计划）以及模板按钮；全部文案以档案馆口吻生成。
- `CityPhoneSnapshot`：解析后端返回的 JSON，统一转为插件可用的数据结构（状态标签、覆盖率、建造评分、坐标、计划信息等）。

## 4. 后端管线（`backend/app/core/ideal_city/`）
- `IdealCityPipeline.cityphone_state`：聚合 `StoryStateRepository`、`IdealCityRepository` 与执行记录，输出 `CityPhoneStatePayload`。面板内容分别映射故事结构覆盖度、资源清单与风险、坐标同步状态、建造计划及其阻塞原因，同时附带 `TechnologyStatusRepository` 读取的阶段/能源/风险快照。
- `IdealCityPipeline.handle_cityphone_action`：处理来自插件的动作。
  - `request_state`：直接返回当前快照。
  - `submit_narrative`：将叙述封装为 `DeviceSpecSubmission`，驱动裁决、生成建造计划与 Manifestation Intent，并返回最新状态。
  - `push_pose`：写入玩家坐标及位置提示。
  - （模板套用已下线，不再暴露 `apply_template` 动作。）
- `StoryStateManager`：为 CityPhone 面板提供覆盖度、阻塞项与评分，并维护模板、跟进问题、建造准备状态。
- `NarrativeIngestion`、`ManifestationIntentWriter`、`BuildScheduler` 等配套模块会在裁决通过后更新建造计划和城市意图，CityPhone 面板据此显示待办或执行进度。

| 动作 | HTTP 接口 | 作用 | 核心实现 |
|------|-----------|------|----------|
| 获取状态 | `GET /ideal-city/cityphone/state/{player}` | 返回 `CityPhoneStatePayload` | `IdealCityPipeline.cityphone_state` |
| 提交叙述 | `POST /ideal-city/cityphone/action` + `action="submit_narrative"` | 触发裁决、生成建造计划、更新 StoryState | `IdealCityPipeline.handle_cityphone_action` → `submit()` |
| 同步坐标 | 同上 + `action="push_pose"` | 写入 `StoryState.player_pose` 与地标提示 | `StoryStateManager.apply_pose_update` |
| 模板套用 | （已下线） | （功能冻结） | — |

## 5. 数据与协议来源
- StoryState：`backend/data/ideal_city/story_state/` 下维护每位玩家、每个场景的 JSON 缓存，供 CityPhone 即时读取。
- 建造计划：`backend/data/ideal_city/build_queue/` 保存排队与执行记录，`fetch_executed_plan` 结合日志为计划面板生成说明。
- 协议 artefact：若设置 `IDEAL_CITY_PROTOCOL_ROOT`，CityPhone 会读取外部 Forge/CrystalTech 写入的 `technology-status.json` 及 `cityphone/social-feed/`，默认落在 `backend/data/ideal_city/protocol/`。`TechnologyStatusRepository` 对旧键名保持兼容。
- 社会反馈：`SocialFeedbackRepository` 可基于 `cityphone/social-feed/events.jsonl` 与 `metrics.json` 生成信任指数与氛围数据，供后续扩展在 CityPhone 或气氛播发中展示。

## 6. 相关文档与测试
- 设计稿：`docs/CITYPHONE_UI_PLAN.md` 详细描述 UI 阶段、面板与交互原型。
- 快速指南：`README.md` 提供 `/cityphone` 系列命令与故障排查。（如“CityPhone 不更新”需清理 `story_state` 缓存。）
- 测试覆盖：`backend/test_ideal_city_pipeline.py` 校验 `cityphone_state` 的准备状态与研究提示；可按需扩展断言技术状态和计划同步。
- 脚本工具：`backend/scripts/check_protocol_end_to_end.py` 用于检查 `protocol/cityphone/` 目录格式是否满足前后端要求。

## 7. 运维与扩展提示
- 环境变量：根据部署需要设置 `IDEAL_CITY_DATA_ROOT` 与 `IDEAL_CITY_PROTOCOL_ROOT`，以重定向存储与协议目录；否则均落在 `backend/data/ideal_city/`。
- 插件配置：确保 `BackendClient` 指向的后端地址与 FastAPI 服务一致，避免 CityPhone 请求失败。
- 常见诊断：
  - 状态无更新 → 检查后端日志与 `/ideal-city/cityphone/state` 响应；若缓存异常，可删除对应 `story_state` 文件。
  - 计划面板缺失 → 确认 `build_queue` 中已有排队或执行记录，并在 `CityPhonePlanPanel` 的 `pending_reasons` 中查看阻塞说明。
  - 技术状态为空 → 确认协议目录下存在 `technology-status.json`，必要时使用 `TechnologyStatusWriter` 填充样例。
- 扩展建议：CityPhone 面板数据均来自 `CityPhoneStatePayload`，可在 pipeline 中新增字段并在 `CityPhoneSnapshot`、UI 渲染处消费，实现更多档案信息而不破坏现有流程。
