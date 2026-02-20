# SCIENCELINE DIFF REPORT

> 工程评估报告：`scienceline` 分支 vs `main` 分支

---

## 1️⃣ 结构层变化

### 新增了哪些模块？

**后端（Python）**

| 新模块路径 | 职责 |
|---|---|
| `backend/app/core/ideal_city/` | 理想之城完整域模块（20+ 文件）：DeviceSpec 语义容器、裁决合约、建造规划代理、故事状态管理、世界叙事者、社会反馈写入器、管线注册表等 |
| `backend/app/core/creation/` | 对话驱动创作规划模块：资源快照（`resource_snapshot`）、快照构建器（`snapshot_builder`）、补丁模板变换器（`transformer`）、验证器（`validation`） |
| `backend/app/core/minecraft/` | Minecraft 服务器适配：轻量级 RCON 客户端（`rcon_client`），无第三方依赖 |
| `backend/app/core/mods/` | 模组运行时加载器：发现并管理 `mods/` 目录下的零模组清单（`manifest`、`manager`） |
| `backend/app/core/world/command_safety.py` | 世界补丁命令安全分析，白名单前缀 + 注入词过滤 |
| `backend/app/core/world/patch_executor.py` | Phase 3 干跑（dry-run）工作流：校验 + 生成可执行模板列表 |
| `backend/app/core/world/patch_transaction.py` | 原子性补丁事务日志（append-only JSONL），支持撤销（undo）记录 |
| `backend/app/core/world/plan_executor.py` | 干跑校验后自动世界执行协调器，持有 `CommandRunner` 协议抽象（RCON 可替换） |
| `backend/app/core/world/resource_sanitizer.py` | Minecraft 资源标识符（ResourceLocation）清洗工具，正则驱动 |
| `backend/app/core/story/exhibit_instance_builder.py` | 展览实例构建器 |
| `backend/app/core/story/exhibit_instance_repository.py` | 展览实例存储库 |
| `backend/app/core/story/exhibit_registry.py` | 展览注册表（默认实例） |
| `backend/app/services/creation_workflow.py` | 创作工作流服务层：粘合 RCON、PatchExecutor、PlanExecutor |
| `backend/app/instrumentation/cityphone_metrics.py` | CityPhone 指标采集（Prometheus 可选，降级为本地计数器） |
| `backend/app/ml/embedding_model.py` | 嵌入向量模型适配 |
| `backend/app/api/ideal_city_api.py` | 理想之城 REST API 路由 |
| `backend/app/api/intent_api.py` | 意图解析 REST API 路由 |

**Minecraft 插件（Java）**

| 新包路径 | 职责 |
|---|---|
| `system/mc_plugin/src/.../cityphone/` | CityPhone 完整功能包（8 个文件）：命令、UI、监听器、快照、本地化、叙事面板 |
| `system/mc_plugin/src/.../atmosphere/` | 社会氛围系统：`SocialAtmosphereManager` + `SocialAtmosphereListener` |
| `system/mc_plugin/src/.../commands/IdealCityCommand.java` | 理想之城入口命令 |
| `system/mc_plugin/src/.../commands/custom/CmdPlanJump.java` | 建造规划跳转命令 |

**根目录新增**

- `city-intents/`：城市意图数据目录
- `data/`：后端数据根目录
- `mc_plugin/`：独立的插件构建目录
- `scripts/`：运维脚本集合
- `tools/auto_build.py`、`tools/sync_mods.py`：自动化构建与模组同步工具
- `MIGRATION_IDEAL_CITY.md`：理想之城迁移占位记录

---

### 删除了哪些模块？

- `ABOUT.md`（项目介绍文档，已无维护价值）
- `.claude/settings.local.json`（本地 Claude 配置，不应纳入版本控制）
- `backend/.env`（包含敏感配置，被替换为 `backend/.env.example`）

---

### 拆分了哪些模块？

- **意图路由（Intent Routing）**：原来的 `parse_intent` 函数承担所有意图解析职责；scienceline 将其拆分为：
  - `_looks_like_ideal_city_request()`（独立判断理想之城意图）
  - `_looks_like_block_request()`（独立判断方块操作意图）
  - 新增 `IDEAL_CITY_SUBMIT` 意图类型，由 `ideal_city` 管线独立处理

- **世界补丁执行（World Patch Execution）**：原来的 `WorldPatchExecutor`（Java 端）是单体类；scienceline 将其在 Python 侧拆分为三层：
  - `command_safety.py`（校验层）
  - `patch_executor.py`（干跑层）
  - `plan_executor.py`（执行层）

---

### 是否引入 core / adapter / service 分层？

**是**。scienceline 引入了明确的分层结构：

- **core 层**：`backend/app/core/ideal_city/`、`backend/app/core/creation/`、`backend/app/core/minecraft/`（纯业务逻辑，无框架依赖）
- **adapter 层**：`RconClient`（`backend/app/core/minecraft/rcon_client.py`）作为 Minecraft 服务器适配器；`RconCommandRunner`（`backend/app/services/creation_workflow.py`）实现 `CommandRunner` 协议
- **service 层**：`backend/app/services/creation_workflow.py` 粘合 RCON、PatchExecutor、PlanExecutor，供 API 层调用
- **instrumentation 层**：`backend/app/instrumentation/` 独立于业务逻辑采集指标

---

## 2️⃣ 状态管理变化

### 是否减少全局状态？

**部分减少**。scienceline 在以下维度减少了全局状态：

- `StoryStateManager`（`backend/app/core/ideal_city/story_state_manager.py`）将理想之城的叙事状态从 `StoryEngine` 的 `players` 字典中独立出来，改用专属的 `StoryStateRepository` 管理，避免所有状态混存于同一个全局 dict。
- `ExhibitInstanceRepository` 独立管理展览实例，不再耦合进 `StoryEngine` 的核心状态字典。
- `PatchTransactionLog` 以 JSONL 文件持久化补丁事务，将一次性内存状态落盘，减少运行时全局内存占用。

---

### 是否重构了 state 结构？

**是**。`StoryEngine` 的玩家状态 dict（`self.players`）在 scienceline 中扩展了新字段，结构化程度提升：

```python
# scienceline 新增字段
{
    "current_exhibit": None,        # 当前展览定位
    "scenario_id": None,            # 档案ID
    "_exhibit_instance_session": {  # 展览实例会话（仅内部使用）
        "applied": {},
        "captured": set(),
    }
}
```

`get_public_state()` 也相应新增 `current_exhibit` 字段输出，让外部查询可以获得完整的上下文。

---

### 是否解决了某个状态不一致问题？

**是**。`_bind_exhibit_to_player()` 方法在关卡加载时主动将展览上下文绑定到玩家状态，确保 `current_exhibit` 与当前关卡始终一致，解决了 main 分支中展览上下文未纳入玩家状态、导致 AI 提示词缺失展览信息的不一致问题。

---

## 3️⃣ 算法或复杂度变化

### 是否替换数据结构？

- **补丁事务**：从纯内存 dict 替换为 append-only JSONL 文件（`PatchTransactionLog`），牺牲少量写入速度换取持久性与可审计性。
- **展览注册表**：引入 `exhibit_registry.py`，使用静态注册表替代动态全局查找。

---

### 是否降低某段逻辑复杂度？

**是**。`intent_engine.py` 中：

- main 分支：`parse_intent` 函数内部直接内联所有判断逻辑，分支过多。
- scienceline：将 `_looks_like_ideal_city_request()` 和 `_looks_like_block_request()` 提取为独立函数，降低单函数复杂度，提升可测试性。

`world_api.py` 中新增 `_summarize_commands()` 辅助函数，将命令列表转换为结构化摘要，替代原本内联的字符串拼接逻辑。

---

### 是否增加缓存/索引？

- `backend/data/transformer/semantic_index.json`（scienceline 新增）：为资源目录建立语义索引，供创作规划变换器快速查找资源。
- `backend/data/transformer/resource_catalog.seed.json`（scienceline 新增）：资源目录种子文件，作为 `ResourceCatalog` 的初始数据。

---

## 4️⃣ 删除了什么？

> **这一条最重要**

### 删除了哪些重复逻辑？

- **重复的意图分支判断**：main 分支中 `world_api.py` 和 `intent_engine.py` 内部各自内联判断"是否为方块操作"；scienceline 将其统一提取为 `_looks_like_block_request()`，一处定义，多处复用。

- **重复的 AI 提示词注入**：main 分支中 `story_loader.py` 的 `build_level_prompt()` 函数对 NPC、文本等上下文逐一手动拼接；scienceline 提取了 `structured_guidance`（CityPhone 结构化摘要指引）和 `exhibit_block`（展览定位块）作为独立构建块，消除了散布在 prompt 末尾的重复格式约定。

---

### 删除了哪些临时方案？

- `backend/.env`（内含明文密钥）被删除，替换为 `backend/.env.example`（仅保留占位变量名），终结了"先提交密钥后处理"的临时方案。

- `ABOUT.md` 删除，其内容已被 `README.md` 和 `SUMMARY.md` 覆盖，消除了冗余文档的维护负担。

- `.claude/settings.local.json` 删除，移出了本地 AI 辅助配置对代码库的污染。

---

### 删除了哪些"概念型代码"？

- main 分支 `backend/app/core/world/trigger.py`、`backend/app/core/world/patch_optimizer.py` 等文件中存在大量"声明了接口但未接入实际执行链"的占位概念代码；scienceline 通过引入 `patch_executor.py` → `plan_executor.py` → `RconCommandRunner` 的完整链路，将这些概念落地为可运行的执行流，不再需要单独维护"仅用于说明架构意图"的骨架代码。

- `execution_boundary.py` 的注释中明确标注："Nothing here triggers Minecraft actions directly；it only prepares structured payloads"——scienceline 用精确的边界声明取代了 main 分支中模糊的职责注释，消除了"概念型注释型代码"。

---

## 5️⃣ 你认为的核心改进

一句话：

> **scienceline 解决了 main 分支"世界操作无执行链、理想之城无独立域边界"的结构问题**——通过引入 `ideal_city` 完整域模块、`creation` 规划层、`service` 粘合层，以及 `command_safety → patch_executor → plan_executor → RconClient` 的四级安全执行链，将 main 分支中散落在 story_engine 和 world_api 内的混合职责拆解为边界清晰、可独立测试的模块，同时保持零模组可运行的核心约束。

---

*报告生成基于 `main`（commit `009d829`）与 `scienceline`（commit `8d3c92b`）的 git diff 分析。*
