# Drift System 聊天输入链路落地计划（Engineering v1.0）

> 本文基于《Drift System · CityPhone & 自然语言造物 愿景文档（Vision v1.0）》制定，目标是把“聊天输入 → 资源理解 → world_patch → ExhibitInstance”整条链路在工程层面跑通。内容覆盖范围、交付物、验证方式与阶段性目标，确保团队对齐执行路径。

---

## 1. 范围与约束
- **范围**：聊天输入链路（聊天输入 → 资源理解 → world_patch → ExhibitInstance → 持久化 → 展示）。
- **不做**：CityPhone UI 重构、裁决文本优化、模板套用系统、高级策展逻辑。
- **前提**：即便关闭 CityPhone，玩家仍可通过聊天完成创造；CityPhone 仅承担只读档案能力。

---

## 2. 目标定义
### 2.1 核心目标
- 玩家在聊天中提交创造意图，系统输出确定性的 world_patch，并持久化为 ExhibitInstance，保证多次进入服务器后仍然存在。

### 2.2 成功判据
1. 玩家无需打开 CityPhone，仅使用聊天与游戏操作即可完成一次创造行为。
2. 系统识别创造行为并落地 world_patch，生成可追踪的 ExhibitInstance。
3. Exhibit 在下次进入服务器或切换关卡后仍然可见、可回顾。
4. CityPhone（若打开）仅作为只读档案查看渠道。

---

## 3. 系统链路分层
```
Chat Input → Intent Recognition → Resource-Behavior Transformer → Patch & Exhibit Engine → Persistence & Replay
```

| 层级 | 说明 | 关键负责人 | 关键交付物 |
| --- | --- | --- | --- |
| Chat Input Handler | 解析玩家输入，产出初步意图数据结构 | Backend 输入链路小组 | `chat_intent_payload` schema 更新、日志样例 |
| Intent Recognition | 判断是否为创造行为，提取核心参数 | NLP/规则小组 | 创造意图分类模型/规则、判定日志 |
| Resource-Behavior Transformer | 将自然语言意图映射为结构化创造指令，绑定资源上下文 | Transformer 小组 | `resource_behavior_transformer` 服务、API 合约、单测 |
| Patch & Exhibit Engine | 根据指令生成 world_patch，并实例化 Exhibit | World Patch 小组 | world_patch 模板、ExhibitInstance schema、执行器更新 |
| Persistence & Replay | 保存 Exhibit、在世界中重建与展示 | Persistence 小组 | 数据落盘策略、重播用例、回归测试脚本 |

---

## 4. 执行计划

### 4.1 阶段拆解
| 阶段 | 目标 | 预计耗时 | 里程碑 |
| --- | --- | --- | --- |
| Phase 0 现状梳理 | 梳理现有链路、数据结构、痛点 | 3 天 | 完成链路审计报告（包含日志截图、接口示意） |
| Phase 1 意图检测 | 搭建创造行为分类器 & 规约 | 7 天 | 产出创造意图识别准确率 ≥90%的验证报告 |
| Phase 2 Transformer | 实现资源—行为 Transformer 原型 | 10 天 | Transformer 服务上线灰度、通过单服压测 |
| Phase 3 Patch & Exhibit | 生成确定性 world_patch + Exhibit 持久化 | 10 天 | 在测试服完成 5 个 Exhibit 用例并全部成功复现 |
| Phase 4 回归验证 | 多人服、重启服、跨关卡验证 | 7 天 | 验证报告，覆盖 3 名玩家、2 次重启、1 次关卡切换 |

在 Phase 2 完成后，必须先完成 1 个真实玩家自由创造用例（玩法验收点），即便流程仍然粗糙也要先跑通，再进入 Phase 3。

> 时间基于连续工期估算，可根据实际资源调整；Phase 间可滚动迭代但需保证前驱能力可用。

### 4.2 关键任务包

#### 4.2.1 Chat Input & Intent Recognition
- 整理当前聊天输入数据结构与触发链路（含 `backend/chat_server`、`intent_pipeline`）。
- 定义“创造行为”判定规则（关键词、结构化槽位、上下文依赖）。
- 建立标注集：收集 ≥100 条历史聊天记录，标注是否为创造行为及关键参数。
- 实现判定模块：
  - 首选规则+轻量模型混合策略，保留 `debug` 日志输出。
  - 暴露 API：`POST /intent/recognize`，输出 `is_creation`, `creation_slots`。
- 编写单元测试 & 集成测试：覆盖“非创造”“模糊描述”“组合动作”。

#### 4.2.2 Resource-Behavior Transformer
- 读取世界资源：
  - 接入 `mods`, `world_state`, `resource_registry`，生成资源候选列表。
  - 提供缓存策略，确保实时性与性能平衡。
- Transformer 逻辑：
  - 输入：创造意图结构体 + 当前世界资源快照。
  - 输出：结构化创造指令（`creation_plan`）。
  - 定义数据协议（JSON Schema），包含：目标结构、使用资源、空间位置、约束条件。
  - 约束：Transformer 不追求高覆盖率或自然语言完备性，本阶段仅支持组合与调用世界中已存在的资源。
- 错误处理：输出失败原因，提供回退策略（提示玩家资源不足或需要澄清）。
- 测试：
  - 单元：资源匹配、位置校验、冲突检测。
  - 集成：与 Patch Engine 联调，覆盖常见创造场景。

> **Phase 2 Rolling Update · 2026-01-15**  
> - 引入 `ResourceSnapshotBuilder`：扫描 `mods/` 与 `resourcepack/` 生成动态快照，落盘至 `backend/data/transformer/resource_catalog.json`，并保留 `resource_catalog.seed.json` 作为人工种子。  
> - `CreationPlan` 新增 `steps` 草案，自动携带命令模板/资源标识，未匹配材料标记 `needs_review`。  
> - `/intent/plan` 与 Ideal City 管线同步返回步骤信息，为 Phase 3 world_patch 映射提供输入。
> - `CreationPlan.patch_templates` 输出 `world_patch` 草稿（包含 `mc.commands`、模组依赖、占位符提示），支持规则侧快速套用或人工补完。

#### 4.2.3 Patch & Exhibit Engine
- world_patch 生成：
  - 基于 `creation_plan` 构建确定性 patch（指定方块、坐标、元数据）。
  - 保证 patch 可逆（支持审查/回滚）。
- ExhibitInstance 管理：
  - 定义 Exhibit 元数据（来源、时间、意图摘要、patch id）。
  - 建立持久化存储（DB/文件）与索引策略。
  - 提供查询接口供 CityPhone 调用（只读）。
- 执行器更新：
  - 与 `WorldPatchExecutor` 对接，确保执行成功即写入 ExhibitInstance。
  - 失败时回滚 patch，记录异常。

#### 4.2.4 Persistence & Replay
- 数据落盘：
  - 将 ExhibitInstance 与 patch 结果持久化至服务端存储（优先使用现有 `backend/persistence`）。
  - 建立一致性校验：重载时校验 patch 是否已应用，如未应用则补齐。
- 重播验证：
  - 自动化脚本 `scripts/replay_exhibit.sh`，在测试环境重启服务器后验证 Exhibit 仍在。
  - 设计测试用例：多人同时创造、冲突资源、跨关卡持久化。

---

## 5. 工程交付物清单
- 文档：
  - Phase 0 链路审计报告
  - Transformer API 合约 & Schema 文档
  - Exhibit 数据字典与存储方案
  - 验证报告（多人服/重启/跨关卡）
- 代码：
  - Intent Recognition 模块 + 测试
  - Resource-Behavior Transformer 服务代码 + 测试
  - Patch 引擎增强与 ExhibitInstance 持久化实现
  - Automation scripts（replay、回归测试）
- 运维：
  - 配置更新（服务注册、环境变量）
  - 监控指标：创造成功率、Transformer 错误率、重播失败率

---

## 6. 风险与缓解
- **创造意图识别不准确**：
  - 缓解：规则兜底、手动标注扩充数据集、实时日志复盘。
- **Transformer 资源上下文不完整**：
  - 缓解：定期同步世界资源快照、增加缓存失效策略。
- **world_patch 执行失败**：
  - 缓解：执行前验证资源可用性、执行后校验、失败回滚。
- **持久化不一致**：
  - 缓解：双写校验、重播脚本、引入版本号与事务日志。

---

## 7. 验证策略
- 自动化测试：CI 中增加 `test_creation_pipeline`，涵盖 Intent → Patch → Exhibit。
- 手动验收：
  - 角色：3 名内部玩家，使用不同创造场景（建筑、装置、命名物品）。
  - 场景：单服连续两次登录、多服切换、服务重启后验证 Exhibit 仍在。
- 日志监控：
  - 关键日志路径：`backend/logs/creation_pipeline/*.log`。
  - 指标阈值：Transformer 错误率 <5%，Exhibit 重播成功率 100%。

---

## 8. 对 CityPhone 的具体约束落实
- CityPhone 在本阶段仅支持只读：
  - 更新数据来源，读取 ExhibitInstance 存量。
  - 不新增操作入口，不阻断聊天链路。
- 若 CityPhone 弹窗中包含操作按钮，应在本阶段禁用或提示“请通过聊天完成创造”。

---

## 9. 项目管理与协作
- 项目负责人：技术负责人（任命待定）。
- 周例会：每周一次，汇报阶段进展、阻塞问题、指标数据。
- Issue 跟踪：GitHub 项目看板新增 “chat-input-chain” 列，所有任务需挂 Issue。
- 代码合并：所有核心模块需双人 Code Review，并附带测试结果截图/日志。

---

## 10. 收官条件
当以下条件全部满足，视为本阶段完成：
1. Phase 0-4 的里程碑文档与代码均合入主干。
2. 自动化测试稳定通过，监控指标达标。
3. 验收玩家任务全部成功，验证报告归档。
4. CityPhone 确认为只读档案工具，不影响创造链路。

---

*本文档版本：2026-01-14；维护者：Drift System 工程团队。*
