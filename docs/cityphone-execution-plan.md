# CityPhone 策展终端工程落地方案

> 适用范围：Drift System · Science Line 分支（Paper 插件 + Backend FastAPI），配套 Vision 文档《cityphone-vision.md》与 UX 模拟稿。

---

## 1. 背景与目标

- Vision 重新定义了 CityPhone 的存在理由：它是展馆的“策展旁白”，非流程控制器。
- UX 模拟明确了目标体验：玩家进入的是有记忆的展馆，CityPhone 解读历史与风险，不再裁决执行。
- 本文档意在将愿景转化为可实施的工程路线，指导插件、后端与内容生产的协同改造。

### 核心交付

1. CityPhone UI/交互改版，实现“说明牌”式体验。
2. Backend 叙事数据层重构，使得 CityPhone 可以生成语义化解释。
3. Scenario 插拔能力：新企划无需 UI/流程改动即可上线。
4. 指标与运维：确保请求量、延迟、内容一致性达到可控标准。

---

## 2. As-Is vs To-Be 差异梳理

| 维度 | 现状 (As-Is) | 目标 (To-Be) |
| --- | --- | --- |
| CityPhone 角色 | 字段校验器、流程控制台 | 城市自我解释的窗口 |
| 主 UI 信息 | 缺失字段、阻塞原因、模板按钮 | 展馆状态、企划档案、历史叙事 |
| 行动提示 | 明确指令（去补齐、去提交） | 语义暗示，解释城市如何理解玩家 |
| 阻塞表现 | 直接拒绝，明确禁止 | 理解延迟，提醒历史风险，世界照常运行 |
| Scenario 接入 | 需定制 UI、命令、配置 | 注册档案数据即可，CityPhone 自动解释 |
| 玩家心理 | “如何通关/填表” | “城市如何看待我” |

---

## 2.1 展馆地基迁移计划（2026-01-12 Freeze）

### 共识

- CityPhone 只承担「收/发/记录/解释」四职，永不判断「可否执行」。
- 风险、资源、模板、计划保留为档案附录，永不进入主叙事、更不携带控制语义。
- Freeze 守护 + CI 契约校验是防回退底线，任何引入流程语感的改动都需被拒绝。
- Archive 模式仅呈现档案来源、载体与时间位置，不再生成新的“理解”或“总结”，相关语汇一律视为越权回退。

### Phase 0 · 基线验证（可重复执行）

- 停用 CityPhone 插件验证世界仍可运行，确保世界主体无依赖。
- 梳理所有消费 CityPhone 状态的接口与插件，锁定影响面。
- 建立 `CITYPHONE_FREEZE_MODE` 或等价守护标志，禁止控制逻辑回流。

### Phase 1 · 后端数据契约净化

- 定义不可回退的 CityPhone 只读档案载荷，`CityPhoneStatePayload` 对外仅保留 `city_interpretation`、`unknowns`（记忆空白语态）、`history_entries`、`narrative.sections` 与 `exhibit_mode`（纯文本 label/description）。
- 从响应中彻底剥离 `appendix.*`、`plan`、`resources`、`location`、`vision`、`phase`、`ready/available/pending/status/blocked` 等控制字段，相关数据仅允许在内部流程保存或转译为叙事文本。
- 更新 unknowns 推导逻辑，统一生成“档案暂缺”“记忆空白”“尚未形成一致记录”等描述性语句，禁止出现“待/需要/补充”等任务化措辞。
- `technology_status` 不再作为 payload 字段或模式推导输入，仅允许作为叙事写作素材写入 `narrative.sections`。
- StoryState/Pipeline 处理撤展时强制切换 `narrative.mode=archive`，确保历史语态存在；任何模式说明仅通过 `exhibit_mode.label` 与 `exhibit_mode.description` 传达。
- 对应 Pytest 套件更新断言，新增“归档叙事”用例并校验黑名单字段缺失。

#### 2026-01-12 地基硬约束快照

- **只读载荷底线**：`CityPhoneStatePayload` 对外输出仅限 `city_interpretation`、记忆语态的 `unknowns`、`history_entries`、`narrative.sections`、`exhibit_mode.label/description`。其他字段一律禁止出现在公开响应中。
- **unknowns 去任务化**：统一以“档案暂缺”“城市记忆空白”类语气呈现，不得出现“列出/补充/待/需要”等指令式词汇。
- **技术状态解耦**：`technology_status` 自此只作为叙事素材使用，不再暴露为顶层字段，也不驱动 `exhibit_mode`、phase 或 readiness 推导；模式说明仅以文本描述呈现，无 source 等控制线索。

#### 2026-01-12 Archive-only Baseline Update

- **裁决逻辑完全退出 CityPhone 路径**：Archive 模式不再渲染或依赖 ACCEPT/REJECT、ready/blocked、plan/resources 等概念，后端若仍产出相关字段需立即在接入层截断。
- **输出改为来源标注**：Archive 响应必须逐条说明文本来源（提交主体/时间/介质），禁止出现“总结”“重点”“解读”类句式；`city_interpretation` 字段仅承载来源说明文本。
- **LLM 仅限作者工具链**：README/策展文本可借助 LLM 辅助撰写，但 CityPhone 在线路径、接口与测试严禁触发 LLM 推理；任何新增能力上线前必须回答“这是展签，还是策展人？”，仅当答案为“展签”方可进入 CityPhone。
- **测试输入统一为档案文本**：Pytest/合约脚本仅使用 README、策展说明、口述整理稿等 narrative-only payload（`narrative` + `scenario_id`），严禁再以逻辑步骤、资源清单或“我要建设”型语句作为 CityPhone 基线测试输入。
- **unknowns 来源限定为历史差异**：测试断言必须验证 unknowns 只描述“记录缺失/叙述差异”，不得因缺字段而生成。
- **LLM 仅可离线辅助**：CI 与在线路径默认 `IDEAL_CITY_AI_DISABLE=1`，所有叙事由策展文本 + 规则化重排生成，避免重新引入裁决语气。
- **UI/前端接入前提**：只有 Archive 测试套件全部通过且不暴露控制语汇时，才允许推进 UI 实装。

### Phase 2 · 插件 UI 重构（CityPhone 展示层）

- `CityPhoneUi` 主面板仅展示展厅状态、最近事件、来源说明与未决问题，删除计划、状态灯、阻塞列表等控件。
- 历史视图聚焦事件时间线，不再渲染 control 文案/按钮。
- 本地化资源清理 `ui.plan.*`、`ui.status.*` 等命令语感键，新增策展语态键值。
- UI 确保即便后台仅提供档案文本仍可展示，默认首屏无交互按钮。
- Feature Flag：仅允许关闭新 UI 视觉，不得恢复旧控制字段；Freeze 模式下强制启用新语态。

### Phase 3 · Forge/Mod 接口对齐（可与 Phase 2 并行）

- 确认世界侧写入 CityPhone 的事件无需等待审批；协议说明档记录该事实。
- 校验 Manifestation/Narrative 仓库可记录失败、中断、撤展并以历史语态呈现。
- 可选：追加世界快照或影像记录作为档案扩展。

### Phase 4 · Freeze 守护与回退防线

- 在 CI 中加入 schema 校验，检测任何新增 `ready/plan/blocking` 字段的改动即失败。
- 在文档与代码注释中写明“黑名单语感”，引导审查关注语言回退。
- PR 模板新增检查项：“是否触及 CityPhone 控制逻辑？如是，需提供 Freeze 例外说明”。

### 验收准则

- 每完成一个 Phase，仅以「UX 五问」做验收：关掉 CityPhone 世界可运行、新企划纯档案可展示、失败可入史、无命令语感、玩家是在理解世界。
- 任一问题回答为 No，则禁止进入下一 Phase，必须回滚至当期修复。

---

---

## 3. 工程范围与非目标

- **范围内**
  - 插件 UI/文案重构：`mc_plugin/src/com/driftmc/cityphone/*`
  - Backend CityPhone API：`backend/app/core/ideal_city/pipeline.py`, `cityphone_state.py`, `story_state_manager.py`
  - 档案数据生成：`backend/data/ideal_city/*` 与 `protocol` 目录
  - CI/CD 配置、灰度发布策略

- **明确不做**
  - Forge/CrystalTech Mod 逻辑调整
  - 新企划具体内容产出
  - 核心权限、玩家账户体系的大改

---

## 4. 体系结构调整

### 4.1 数据模型层

- **新建 `ExhibitNarrative` 数据结构**
  - 字段：`scenario_id`, `timeframe`, `archive_state`, `unresolved_risks`, `historic_notes`, `city_interpretation`
  - 底层来源：`scenario_manifest.json`, `story_state` 时间线、`technology_status`、`research_hint`
- **CityPhone 状态 API** (`GET /cityphone/state`)
  - 输出从字段校验列表转为叙事数据：`mode`, `last_event`, `narrative_sections`。
  - 保留原有数据（completeness、blocking）但降级为附录字段。
- **记录 API** (`POST /cityphone/action`)
  - 仅接受 narrative 文本与场景标识，返回 `city_interpretation`、`unknowns`、`history_entries` 的增量视图，不再暴露或推导 verdict/plan 信息。
  - 将作者提交的档案文本以 `narrative_event` 形式入库，供历史叙述迭代使用。

### 4.2 插件层（Paper）

- UI 组件拆分：
  - `CityPhoneNarrativePanel`：渲染档案文本与模式标签。
  - `CityPhoneAppendixPanel`：折叠形式展示“阻塞/覆盖率”等附录。
- 命令 `/cityphone`
  - 首屏改为展馆状态 + 最近企划摘要。
  - `Apply Template` 替换为 `查看历史回应`（仅做档案展示）。
- 客户端刷新策略
  - 首次打开、人工刷新时请求 `/state`。
  - 行动提交后仅刷新叙事部分，避免重复提示“缺字段”。

### 4.3 档案内容生成

- 新建内容管线脚本 `scripts/generate_exhibit_narrative.py`：
  - 汇聚 `protocol` 下 scenario manifest + 市政叙事 Markdown。
  - 输出标准化 JSON，供 Backend 读取。
- 建立 `docs/narrative-playbook.md` 指导策展组撰写档案模板。

### 4.4 运维与指标

- 监控项：
  - `/cityphone/state` 请求量/耗时
  - Narratives 缺失率（fallback 次数）
  - 玩家提案 `narrative_event` 存档频率

---

## 5. 迭代路线图

| Iteration | 目标 | 主要任务 | 验收 | 预计工期 |
| --- | --- | --- | --- | --- |
| 0 · 基线治理 | 接口契约冻结、技术债清理 | 1) 整理现有 API 输出；2) 编写回归脚本；3) 初始化指标采集；4) Vision/UX 文档入库并建立 README 链接 | Postman 合同测试通过；CI 自动化出报告 | 1 周 |
| 1 · 叙事数据层 | 建立档案数据结构与内容管线 | 1) 设计 `ExhibitNarrative`；2) 实现数据聚合 & JSON 输出；3) 新建 `generate_exhibit_narrative.py`；4) 后端 API 返回叙事字段（旧结构保留） | `GET /state` 返回叙事段；旧 UI 未崩溃 | 1.5 周 |
| 2 · 插件 UI 改造 | UI 改为“说明牌”体验 | 1) `CityPhoneNarrativePanel` 实现；2) 命令入口文案更新；3) `Apply` 按钮改为档案模式；4) EN/zh 文案资源迁移 | UX 走查 + 玩家内测，无阻断操作 | 2 周 |
| 3 · 档案记录层 | `POST /action` 仅做文本归档并回传来源说明 | 1) 重新定义提案入库为纯 narrative 记录；2) 响应体仅输出来源说明/记忆空白；3) 阻塞提示转化为历史差异说明；4) StoryState 管线剥离 verdict/plan 依赖 | 提交任意档案文本不会触发“补字段”，只收到来源说明 | 1.5 周 |
| 4 · 展馆模式切换 | 实现看展 vs 布展动态切换 | 1) 添加展馆状态机；2) 结合 `technology_status` 控制 Forge/Plugin 切换；3) 回写 CityPhone 状态文案 | 可以切换 Plugin-only & Plugin+Mod，UI 自动适配 | 2 周 |
| 5 · 内容与指标固化 | Not Needed for Current Phase | 迭代暂停，待未来运营需求明确后再评估 | N/A | N/A |

**总计：~9 周，5 个迭代。**

> 注：Iteration 5 已在 2026-01-11 被标记为 “Not Needed for Current Phase”，后续如有运营化目标再重新规划。

---

## 6. 交互改造要点

1. **首页信息架构**
   - 展馆状态标签（Archive / Production）。
   - 最近企划标题 + 时间。
   - 叙事正文（Markdown 渲染 -> 纯文本分段）。
2. **附录区**
   - 原“阻塞原因”“覆盖率”等以折叠形式放在底部。
   - 强调“这是城市的盲区/风险提示”。
3. **提案反馈**
  - 返回 `city_interpretation` + `unknowns`，UI 用“来源说明卡片”展示。
   - 玩家可进入“查看历史回应”查看城市对不同提案的理解演化。

---

## 7. 内容生产与版本控制

- 内容路径：`docs/narratives/<scenario_id>/*.md`
- 管线脚本将 Markdown 转为 JSON 储存于 `backend/data/ideal_city/exhibits/`。
- Scenario 元数据表：`scenario_registry.yaml`
  - 字段：`scenario_id`, `title`, `timeframe`, `status`, `risks`, `notes`。
- PR 流程强制执行 Markdown lint & JSON schema 校验。

---

## 8. 监控与测试策略

- **自动化**
  - Backend：Pytest 套件以 narrative-only payload 覆盖 `cityphone_state`、`action`，默认 `IDEAL_CITY_AI_DISABLE=1` 确保无在线裁决依赖。
  - Plugin：使用 MockBukkit/Headless Inventory 测试 UI 不崩溃。
- **可观测性**
  - Prometheus exporter 暴露 `cityphone_requests_total`、`narrative_missing_total`。
  - 日志：玩家提案写入 `logs/cityphone_events.jsonl`。
- **验收标准**
  - 内测玩家明确信息由“解释”而非“命令”构成。
  - 企划注册仅需新增档案与 Scenario 配置。

---

## 9. 风险与缓解

| 风险 | 影响 | 缓解策略 |
| --- | --- | --- |
| 认知边界被误解（CityPhone 被当作剧情/代理引擎） | 协作者向 UI 注入决策逻辑，角色退化为检验器 | 在 Vision、落地方案与代码注释中强调“解释器”定位，PR 审查禁止 imperative 行为 |
| 档案内容缺失 | CityPhone 无内容可展示 | 引入 fallback 文案 + CI 检查 narrative completeness |
| 插件 UI 文案长度不一 | 版面溢出，影响体验 | 设计多段布局 + 字体自适应；写作模板约束字数 |
| 阻塞逻辑放松后玩家误解 | 以为系统 bug | 在世界内加入 Passive world feedback（机器闪烁等），CityPhone 解释原因 |
| 新数据结构破坏兼容 | 老版客户端崩溃 | 提供版本检测，保持旧字段至少2个版本 |

---

## 10. CityPhone Invariants

以下规则在任何迭代中都不得被破坏，用于防止 CityPhone 重新滑向控制台：

1. CityPhone 永不阻断世界交互，也不锁定玩家行动。
2. CityPhone 永不发出指令式语言或操作提示。
3. CityPhone 永不会成为唯一的进程推进路径。
4. CityPhone 的解释必须可由既有档案或记录推导，而非即时生成结论。
5. CityPhone 的 UI 设计保持企划无关性，不为单一 Scenario 定制布局。

---

## 11. 与其他系统的关系边界

- Scenario 定义情境与约束，但不决定 CityPhone 呈现方式。
- Narrative agents 负责生成叙事数据，决策仍由城市世界逻辑把控。
- Manifestation Intent 仍是执行层产物，不引入 CityPhone UI。
- CityPhone 仅消费、解释与叙述数据本身，从不做裁决或流程安排。

---

## 12. 可接受的失败模式

- 叙事缺失 → 展示档案占位说明，明确档案尚未整理。
- 解读存在歧义 → 同时给出多个视角，让玩家看到城市的不确定。
- 世界状态未变 → CityPhone 解释“停滞”原因，而非提示错误。

---

## 13. 迭代配额与资源评估

- 预计需要 **5 个迭代（约 9 周）** 完成核心改造，建议迭代长度 1~2 周。
- 团队配置：
  - 插件工程师 ×1
  - Backend 工程师 ×1
  - 内容/策展编辑 ×1（穿插登场）
  - QA ×0.5（跨项目共享）
- 每迭代建议保留 **4,000 次 CityPhone API 请求配额**（与愿景文档保持一致），全周期约 **20,000 次**，含双倍安全余量。
- 内容制作：每个新 Scenario 档案预估 1~2 人日，由策展编辑负责。

---

## 14. 请求配额配置任务

为保证迭代执行期间配额充足，请在开始前完成以下动作：

1. **创建配额记录**：在运维配置库或监控系统中新增 "CityPhone Iteration Quota" 条目，默认总配额 20,000 次。
2. **按迭代划分预算**：将配额拆分为 5×4,000 次，对应迭代 0~4/5（视迭代拆分调整），并记录预留的安全冗余。
3. **设置告警阈值**：在监控平台为 `/cityphone/state` 与 `/cityphone/action` 请求量配置 70% / 90% 两级告警（每迭代 2,800 / 3,600 次）。
4. **建立配额消耗看板**：在项目管理工具中建立“配额使用”任务，每次迭代结束由负责人填报本迭代消耗量与剩余额度。
5. **灰度期间加倍监控**：部署或灰度测试时，记录额外使用量并提前从下一迭代预算中预留 10% 作为支持。

上述任务完成后，将执行结果附到迭代 0 的验收记录中，确保所有成员明确剩余配额。

---

## 15. 跟进动作

1. 在 `README.md` 或 `docs/index.md` 引用《cityphone-vision.md》与本落地方案。
2. 建立 `narratives/` 目录与模板，安排 Iteration 0 启动会议。
3. 为迭代创建 Jira/Linear 史诗："CityPhone Curatorial Rebuild"，按本文分解子任务。
4. 每完成一个迭代阶段，须在本文件“进度记录”表格追加一行，注明时间（UTC+8）、阶段名称与事件摘要，确保历史可追溯。

---

## 16. 进度记录

| 时间 (UTC+8) | 阶段 | 事件摘要 |
| --- | --- | --- |
| 2026-01-11 22:45 | Iteration 0 (基线治理) | 冻结 CityPhone API 契约快照；编写 `scripts/verify_cityphone_contract.py` 回归脚本；接入基础指标采集（state/action 请求与错误计数）；在 README 建立 CityPhone 文档索引。 |
| 2026-01-11 23:30 | Iteration 1 (叙事数据层) | 落地 `ExhibitNarrative` 数据结构与仓库；新增 `/cityphone/state` 叙事载荷 `narrative` 并保持旧面板兼容；编写 `scripts/generate_exhibit_narrative.py`，以 `docs/narratives/default/*.md` 生成 `backend/data/ideal_city/exhibits/default.json`；刷新 API 契约与 README 索引。 |
| 2026-01-12 00:20 | Iteration 2 (插件 UI 改造) | 重构 CityPhone UI 主面板为叙事优先视图并完善历史面板；引入 `messages_zh/en.yml` 本地化资源与 `CityPhoneLocalization` 装载器；替换命令、管理器、UI、快照中的硬编码文案；`DriftPlugin` 启动阶段初始化本地化以保障 UI 依赖。 |
| 2026-01-12 01:20 | Iteration 3 (档案记录层) | `/cityphone/action` 退化为纯文本归档接口，仅返回 `city_interpretation`、`unknowns`、`history_entries` 的增量；StoryState 输出改写为“理解延迟”语态并剥离 verdict/plan 字段；插件展示来源说明卡片而不再渲染阻塞提示；契约快照校验控制语汇未回流。 |
| 2026-01-12 02:20 | Iteration 4 (展馆模式切换) | 引入 `ExhibitModeResolver` 基于 `technology-status`、建造计划与执行记录判定看展/布展；`/cityphone/state` / `action` 载荷返回 `exhibit_mode`；插件按模式本地化标签、渲染说明并在模式切换时提示玩家。 |
| 2026-01-12 02:45 | Iteration 5 (Deferred) | 鉴于当前策展终端愿景已实现且暂不进入运营化阶段，将 Iteration 5 标记为 “Not Needed for Current Phase”，后续依据实际运营需求再恢复规划。 |
| 2026-01-12 11:30 | 调研 · CityPhone 功能评估 | 梳理 Drift Backend / Paper 插件 / CrystalTech Mod 对 CityPhone 的实现现状；确认 state/action 契约与 UI 交互仍遵循策展语态；现有界面结构与评估要点见下方树状图。 |

> **CityPhone UI 树状图（2026-01-12 11:30）**

```
CityPhone 主界面
|- 展馆状态卡（slot 10, Lodestone）
|  |- 展签标题 / 时间框架
|  |- 展馆模式标签 + 描述文
|  `- 最近事件提示
|- 档案来源一览（slot 12, Written Book）
|  `- 城市解读文本列表（最多 4 行预览）
|- 展签摘要卡（slot 13, Paper）
|  |- 叙事标题与首段预览
|  `- “左键展开展签全文”提示
|- 城市记忆空白（slot 16, Spyglass）
|  `- 未解问题与记忆空白预览
|- 历史回应摘要（slot 22, Bookshelf）
|  `- 历史档案摘录 + 查看提示
`- 动作按钮
  |- 查看历史回应（slot 18, MAIN → HISTORY）
  |- 返回档案终端（slot 22, HISTORY → MAIN）
  `- 折叠展签全文（slot 49, NARRATIVE → MAIN）

CityPhone 历史视图
|- 展签段落列表（slots 10-23, Written Book）
`- 叙事索引 / 溢出提示（slot 24, Paper）

CityPhone 展签全文视图
|- 展签抬头信息（slot 4, Filled Map）
`- 展签段落网格（最多 28 槽位, Written Book）
```

**评估要点（Backend ↔ Plugin ↔ Mod）**
- Backend `CityPhoneStatePayload` 现仅输出 `city_interpretation`、`unknowns`、`history_entries`、`narrative.sections` 与 `exhibit_mode`，并通过 `ExhibitNarrativeRepository`、`ExhibitModeResolver` 组合档案与执行痕迹，契约测试 `scripts/verify_cityphone_contract.py` 已覆盖黑名单字段。
- Paper 插件使用 `CityPhoneManager` + `CityPhoneUi` 重新组织为叙事优先的 Inventory 界面，可在主界面、历史面板、展签全文三视图间切换，并在动作回调中推送“解释/记忆空白/延迟”语态提示。
- CrystalTech Forge Mod 仍保留旧版 `CityPhoneScreen`（stage/constraints 风格），需要后续排程与策展语态对齐，避免玩家在不同入口看到冲突体验。
- 现存 `CityPhoneSnapshot` 继续兼容 legacy `appendix` 字段但界面未使用；建议保持合约回归并逐步清理冗余解析逻辑，防止旧字段误回流。

---

## 17. 现状（2026-01-12 Snapshot）

### 17.1 关卡定义与进入
- 剧情关卡存放于 `backend/data/flagship_levels/*.json`，由 `backend/app/core/story/story_loader.py` 解析为 `Level` 实例（字段含 `bootstrap_patch/world_patch`、`scene`、`rules`、`tasks` 等），文件名或 `id` 即关卡 ID。
- 玩家通过 `StoryEngine.load_level_for_player`（`backend/app/core/story/story_engine.py`）进入关卡：函数将关卡绑定到 `players[player_id]` 状态，合并 scene/stage/world_patch，并强制写入安全传送 `mc.teleport`；系统提示在首次推进时由 `_inject_level_prompt_if_needed` 注入关卡原文与 NPC 摘要。
- Ideal City 侧的 Scenario 由 `ScenarioRepository`（`backend/app/core/ideal_city/scenario_repository.py`）按需加载 `data/ideal_city/scenarios/<scenario_id>.json`，当前仓库仅存在 `default.json`；CityPhone 与 StoryState 以玩家 ID + scenario ID 为键持久化在 `data/ideal_city/story_state/`（`story_state_repository.py`）。

### 17.2 内容链路（一次提交）
1. 玩家在世界内发言/移动经 `/world/apply`（`backend/app/api/world_api.py`）传入，`WorldEngine.apply` 更新坐标。
2. 若含文本，`story_engine.advance` 读取当前 `Level` 与消息历史，调用 `deepseek_decide` 产出剧情节点与 `world_patch`，期间 `quest_runtime` 可触发 `npc_engine.apply_rule_trigger` 注入 NPC 对话或命令（`backend/app/core/quest/runtime.py` → `backend/app/core/npc/npc_behavior_engine.py`）。
3. CityPhone `submit_narrative` 通过 `IdealCityPipeline.handle_cityphone_action`（`backend/app/core/ideal_city/pipeline.py`）构建 `DeviceSpecSubmission` 并执行 `submit`：加载 `ScenarioContext`、标准化 `DeviceSpec`、交由 `StoryStateManager.process` 合并 `StoryState`（引用 `StoryStateAgent`），随后 `IdealCityAdjudicator.evaluate`、`GuidanceAgent.generate`、若准备就绪则 `BuildPlanAgent.generate` 并排入 `BuildScheduler`。
4. 最终 `IdealCityPipeline` 根据裁决与计划生成 `ExecutionNotice`、`GuidanceItem`、可选 `BuildPlan`/`WorldNarration`/`ManifestationIntent`，存入 `IdealCityRepository` 和 `protocol/city-intents`，`cityphone_state` 使用 `StoryState`、`ExhibitNarrativeRepository`、`ExhibitModeResolver` 组装响应。

### 17.3 剧情 Agent 运行
- `deepseek_decide`（`story_engine.py`）驱动关卡现场叙事，输入包含玩家动作、最近节点、`Level` 与会话消息；系统提示由 `build_level_prompt` 输出的关卡原文和 NPC 摘要组成。
- `StoryStateAgent`（`backend/app/core/ideal_city/story_state_agent.py`）在 `StoryStateManager.process` 中被调用，系统提示 `_STORY_STATE_SYSTEM_PROMPT` + 阶段提示 `_STAGE_PROMPTS`，输入 JSON 含玩家叙述、标准化 spec、Scenario 题面、既有 `StoryState`、阶段 `determine_phase` 与会话记忆；输出 `StoryStatePatch` 补足各槽位。
- `GuidanceAgent`、`BuildPlanAgent`、`WorldNarratorAgent` 各自使用固定系统提示，将裁决、Scenario、StoryState 作为输入生成指导、建造计划与广播（源码位于 `backend/app/core/ideal_city/guidance_agent.py`、`build_plan_agent.py`、`world_narrator.py`）。
- 当前实现中未发现“仅限某关卡生效”的额外信息层：所有 agent 均依赖 Scenario JSON 与玩家提交数据，无额外关卡专属 prompt。

### 17.4 NPC 行为与剧情勾连
- `StoryEngine.load_level_for_player` 在检测到 `world_patch.mc.spawn.behaviors` 时调用 `npc_engine.register_npc`（`npc_behavior_engine.py`）登记行为、AI 提示。
- 关卡定义可在 `rules.listeners` 中提供 `RuleListener`（`backend/app/core/story/level_schema.py`）；`quest_runtime.register_rule_listener` 将其转发给 `npc_engine.register_rule_binding`，按 `rule_ref` 映射元数据。
- 当 `quest_runtime` 接收到规则事件时，调用 `npc_engine.apply_rule_trigger` 检索匹配条目，返回预置对话脚本、世界补丁、指令或行为更新；该流程完全依赖规则元数据，无 LLM 推理，也不会读取 `StoryState`/CityPhone。
- NPC 对话 API `backend/app/api/npc_api.py` 暴露 `handle_player_interaction`，通过行为定义中的关键字返回固定响应；NPC 能力范围仅取决于注册时的 `level_id` 和 `spawn` 数据，不感知 CityPhone 情境或 Scenario。

---

## 18. 企划连接层落地计划（当前焦点）

- **当前状态** CityPhone 已完成角色转型与契约冻结，UI/后端处于“展签终端”正确语态；当前阻塞在于剧情 agent 尚未获取“所处企划”定位信息。
- **阶段目标** 在 StoryEngine → `deepseek_decide` 的 system prompt 中注入结构化“当前企划槽位”，确保剧情 agent 在关卡内运行时能够读取展览 ID/名称/范围（如“紫水晶”），仅提供定位，不做内容润色。
- **工程范围**
  - Story 层：扩展 `Level` 与 Scenario 绑定以携带 `current_exhibit` 元数据，在 `StoryEngine.load_level_for_player` 建立玩家 ↔ 企划关联，并写入玩家状态。
  - Prompt 层：在 `build_level_prompt`（或等效函数）加入只读 `current_exhibit` 区块，字段限定 `id`、`title`、`scope`，保持说明语态。
  - 数据源：企划信息统一来自 `ScenarioRepository`/`scenario_manifest`，与 CityPhone 档案共用 registry，便于后续展签链路复用。
- **约束条件**
  - `current_exhibit` 仅作为场景定位信息进入系统提示或上下文，不提供叙事指令或语气引导。
  - 企划绑定在关卡载入阶段完成，与 CityPhone 展签逻辑解耦；CityPhone 行为不依赖该字段存在。
  - 企划 registry 视为慢变量，仅允许通过版本管理更新，运行期不做动态改写或自我学习。
- **明确禁止** 不改写紫水晶剧情文本、不调整 NPC 台词或行为、不引入策展语气或总结、不以“像不像紫水晶”为验收标准。
- **完成判定** 玩家在紫水晶关卡内行动时，`deepseek_decide` 的系统提示中可见 `current_exhibit = { id: "amethyst", title: "紫水晶", scope: "..." }`（示例），且该信息可被 CityPhone/档案链路读取；即便剧情仍旧，也视为阶段完成。
- **后续顺序** 连接层验证通过后再推进：① 贯通关卡 → 档案 → CityPhone 展签；② 真实布展 + 游玩验证；③ 紫水晶企划内容深化。在此之前不得提前改动关卡内容或叙事风格。

---

## 19. 展品实例层最小可行实现（Amethyst 企划优先）

### 19.1 背景与目标
- 紫水晶企划会在剧情推进过程中生成展品（例如世界补丁、结构、记录稿件），目前只在 StoryState/CityPhone 中“记得发生过”。
- 为保证再次进入关卡时展品仍可见，需要引入独立的展品实例层，对展品进行持久化、回放与展示管理。
- CityPhone 维持“说明牌”角色，只读取实例元数据，不负责存储或渲染展品本体。

### 19.2 范围与非目标
- **范围内**：后端展品实例仓库、关卡加载时的实例拉取与回放、CityPhone 展品引用接口、Paper 插件 HUD 侧的实例呈现钩子。
- **非目标**：改变剧情文本、重写 ManifestationIntent、实现完整的 Forge/CrystalTech 还原器、引入新的建造 AI 流程。

### 19.3 数据模型与存储
- 新建 `backend/app/core/story/exhibit_instance_repository.py`，定义 `ExhibitInstance` 数据结构：
  - `instance_id`（UUID）、`scenario_id`、`exhibit_id`、`level_id`、`created_at`、`created_by`。
  - `snapshot_type`（`world_patch` / `structure` / `narrative` / `item_frame` 等枚举）。
  - `payload`：依据类型存储具体数据，例如世界补丁 `mc` 指令数组、结构方块序列、文本稿件路径引用。
  - `manifestation_ref`：可选地指向现有 `protocol/city-intents` 条目，用于追溯来源。
- 存储路径：`backend/data/ideal_city/exhibit_instances/<scenario_id>/<instance_id>.json`，每个 JSON 为单实例，新增 `index.json` 汇总 metadata 便于枚举。
- 提供 `ExhibitInstanceRepository` API：`save_instance(...)`、`list_instances(scenario_id, exhibit_id)`、`get_instances_for_level(level_id)`。

### 19.4 实例生成流程（写入）
- 在 `StoryStateManager.process` 中监测紫水晶企划（`scenario_id=CrystalTech`）的 `world_patch` 或 `manifestation` 输出，当满足以下条件时落地为实例：
  1. `world_patch.mc` 包含 `fill/setblock/clone` 等结构性更改；或
  2. `BuildPlanAgent` 产生 `structure_blueprint`；或
  3. 手动调用新的 `POST /exhibit/instance` 后端接口（供运维补录）。
- 新增 `ExhibitInstanceBuilder`：负责从 StoryState 事件组装 `ExhibitInstance`，包括提取地理坐标、展示说明、引用的 CityPhone 叙事片段等。
- 写入成功后返回 `instance_id`，并将其追加到玩家当前 StoryState 的 `exhibit_instances` 列表，供 CityPhone/剧情引用。

### 19.5 关卡加载回放（读取）
- 在 `StoryEngine.load_level_for_player` 末尾增加 `_apply_exhibit_instances(player_id, level)`：
  - 通过 `ExhibitInstanceRepository.get_instances_for_level(level.level_id)` 获取所有持久化实例。
  - 根据 `snapshot_type` 分派执行器：
    1. `world_patch` → 使用现有 `world_patch.apply` 流程重放结构。
    2. `structure` → 交给 `StructureSpawner`（新建）逐方块放置。
    3. `narrative` → 将文本注入关卡提示或 NPC 对话缓存。
    4. 其他类型留作 `TODO`，记录日志但不中断加载。
  - 添加幂等控制：记录 `per_player_instance_cache`，避免同一实例在一次会话中重复注入。
- 若回放失败，写入 `logs/exhibit_instance_errors.log`，以便运维排查。

### 19.6 CityPhone 引用与 UI 配合
- CityPhone 状态载荷新增 `exhibits.instances`（只读列表），字段包含 `instance_id`、`title`、`created_at`、`description`、`snapshot_type`，数据来源于 Repository。
- CityPhone UI 新增“已布展展品”折叠卡片（`slot 24` 预留），仅列出实例元数据及“前往现场查看”提示，不做渲染。
- 保持 CityPhone 自身无回放能力，所有实体呈现依赖关卡加载/世界补丁。
- Backend API `GET /exhibit/instances/{scenario_id}` 供策展工具查看实例列表。

### 19.7 任务拆分与验收
1. **Repository & Schema**：实现数据结构、文件落地与基础读写单元测试。
2. **Builder Hooks**：在 StoryState 管线中调用 Builder 生成实例，覆盖紫水晶关键节点；Pytest 验证写入文件内容。
3. **Level Loader Integration**：扩展 StoryEngine 加载流程，编写集成测试确保实例回放幂等。
4. **CityPhone 接入**：更新状态载荷、UI 渲染、契约回归，确认 CityPhone 仅读取元数据。
5. **运维工具**：CLI 脚本 `scripts/list_exhibit_instances.py` 输出实例索引，方便手动验证。

验收标准：
- 在紫水晶关卡中触发一次展品生成后，退出重进世界仍能看到已布展结构或插入物；日志未出现实例回放错误。
- `GET /exhibit/instances/CrystalTech` 返回包含新实例的元数据；CityPhone 展示对应条目。
- CityPhone 响应与 UI 未产生控制语气，保持“只读说明”。
