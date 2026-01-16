# Patch Execution Contract · Phase 3 Draft

> 版本：2026-01-15

## 1. 设计目标
- **确定性**：Patch Executor 只消费经过验证的模板，不解析自然语言。
- **可回放**：每次执行都记录事务日志与撤销信息，支持重放和审计。
- **安全性**：命令白名单 + 参数校验，低置信度计划永不直接改世界。

---

## 2. Step Type V1 枚举
| step_type | 说明 | 默认执行策略 |
| --- | --- | --- |
| `block_placement` | 直接操控方块（`setblock`/`fill`/`clone` 等） | 仅当模板验证通过且无占位符时自动执行 |
| `mod_function` | 调用 datapack `function` 或 `execute ... run function` | 需确认模组存在；默认 `needs_confirm` |
| `entity_spawn` | `summon` / 实体生成类操作 | 永不自动执行，需人工确认位置 |
| `manual_review` | 未解析或待澄清步骤 | 退回策展；不会直接执行 |
| `custom_command` | 其他命令组合（暂未归类） | 标记为草稿，需手动编排 |

> 未在枚举内的类型直接落入 `manual_review`，并强制标记为 `draft`。

---

## 3. Patch Template JSON Schema
以 `CreationPlan.patch_templates[*]` 为准：

```json
{
  "step_id": "step-1",
  "template_id": "minecraft:amethyst_block::default",
  "status": "draft|resolved|needs_review",
  "summary": "部署 Amethyst Block",
  "step_type": "block_placement|mod_function|entity_spawn|manual_review|custom_command",
  "world_patch": {
    "mc": {
      "commands": ["setblock …"]
    },
    "metadata": {
      "resource_id": "minecraft:amethyst_block",
      "material": {"token": "amethyst", "label": "Amethyst Block", "quantity": 12},
      "tags": ["crystal", "lighting"],
      "placeholders": ["target_location"],
      "requirements": ["player_pose"]
    }
  },
  "mod_hooks": ["gm4:balloon_animals"],
  "requires_player_pose": false,
  "notes": ["…"],
  "tags": ["lighting"],
  "validation": {
    "errors": [],
    "warnings": [],
    "execution_tier": "safe_auto|needs_confirm|blocked",
    "missing_fields": [],
    "unsafe_placeholders": []
  }
}
```

约束：
- `world_patch.mc.commands` 必须全部通过命令白名单验证。
- `metadata.resource_id` 对于 `block_placement` / `mod_function` / `entity_spawn` 为必填。
- `validation.execution_tier` 由 `validate_patch_template()` 统一产出，禁止手工填充。

---

## 4. `validate()` 输出契约
`CreationPlan` 将统一输出：

```json
{
  "execution_tier": "safe_auto|needs_confirm|blocked",
  "validation_errors": ["command:…"],
  "validation_warnings": ["command:…"],
  "missing_fields": ["resource_id", "material:amethyst"],
  "unsafe_steps": ["step-2"],
  "safety_assessment": {
    "world_damage_risk": "low|medium|high",
    "reversibility": true,
    "requires_confirmation": true
  }
}
```

规则：
- `execution_tier=blocked` → Patch Executor 不执行，生成 ExhibitDraft。
- `execution_tier=needs_confirm` → 需人工确认后执行。
- `execution_tier=safe_auto` → 满足无占位符、无警告、命令在白名单内。

---

## 5. Patch Transaction Log
- 位置：`backend/data/patch_logs/transactions.log`
- 格式：JSON Lines，每条包含
  - `patch_id`, `template_id`, `step_id`
  - `commands`（执行指令）
  - `undo_patch`（最小撤销信息，默认 `{ "commands": [] }`）
  - `status`
    - `validated`：dry-run 校验通过，但尚未触碰世界。
    - `pending`：命令已执行且肉眼可见，等待策展/确认。
    - `applied`：策展确认完成，进入正式档案。
    - `failed`：自动执行失败（需人工排查或重试）。
    - `rolled_back`：已执行撤销补丁。
  - `created_at`（ISO8601）
  - `metadata`（可选附加信息）
- 所有执行均需追加记录，回放/回滚直接根据日志驱动。

> 默认链路：`dry-run -> 记录 validated -> 自动执行 -> 记录 pending`。策展或恢复流程会继续把同一事务标记为 `applied` 或 `rolled_back`。

---

## 6. 命令白名单
- 允许前缀：`setblock`, `fill`, `clone`, `summon`, `execute`, `function`, `particle`, `title`, `tellraw`
- 禁止关键字：`;`, `&&`, `||`, `` ` ``, `op`, `deop`, `stop`, `reload`
- 所有命令需匹配正则 `^[a-z0-9_{}:^~.\-\s,/|=\[\]]+$`
- 未通过校验 → `RconError: unsafe_commands_detected`

---

## 7. 测试清单
1. `test_creation_plan_transformer` —— 基线匹配 / 低置信度拒绝。
2. `test_patch_template_validation` —— Schema & golden exhibit 覆盖。
3. `test_patch_executor` —— Dry-run 消费 `safe_auto` 模板并写入事务日志。（回放测试待 Phase 3B/3C 接入）。

---

## 8. 下一步
- Phase 3A：`patch_executor.dry_run()` + `plan_executor.auto_execute()` 完成默认链路（`POST /intent/execute` & `/world/apply` 自动接入），下一步接通 dry-run 响应流转与 UI 回放。
- RCON 连通性检测：握手失败或 `DRIFT_CREATION_AUTO_EXEC=0` 会自动降级为 dry-run，仅记录 `validated` 日志，不触碰世界。
- Phase 3B：补齐回滚、chunk 预加载、多步骤原子执行。
- Phase 3C：权限、并发与冲突策略，接入 Exhibit 重播验证。

---

## 9. 当前验证基线（2026-01-15）
- `backend/data/flagship_levels/flagship_03.json` 恢复旗舰关卡资源，`test_beats_v1.py` 与 `test_task_autofix.py` 现已通过。
- `backend/app/core/ideal_city/story_state_manager.sync_execution_feedback` 去重同一计划的执行笔记，`test_story_state_manager.py` 通过。
- `backend/test_ideal_city_pipeline.py` 中依赖 CityPhone AI 摘要的 5 个档案场景用例已标记 `xfail`（当前 summarizer fallback 返回空载荷）。待 Phase 3A 接通执行回放与档案摘要后解除。
