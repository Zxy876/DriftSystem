# Phase 16 – Flagship Arc Memory & Reactive Beats

## Entry Conditions
- PHASE_15_COMPLETE = true in docs/STATE.md.

## Scope
Use the flagship levels to prove that:
- 玩家在不同章节做出的选择，可以被“记住”；
- 记忆会影响后续关卡的 NPC 台词、任务、甚至 StoryGraph 推荐。

目标关卡：
- `flagship_tutorial.json`
- `flagship_03.json`（登山）
- `flagship_08.json`（花园 / 疾病）
- `flagship_12.json`（后期章节）

## Allowed Changes
- backend/app/core/story/level_schema.py
- backend/app/core/story/story_engine.py
- backend/app/core/story/story_graph.py
- backend/app/api/world_api.py (debug/memory endpoint)
- backend/data/flagship_levels/flagship_*.json（仅上述几个）
- docs/MEMORY_SYSTEM.md（新建）
- docs/STATE.md

## Tasks

1. **扩展关卡 schema：记忆读写能力**
   - 在 `level_schema.py` 中新增：
     - `MemoryFlag` / `MemoryMutation` / `MemoryCondition` 等 dataclass
   - 支持在以下位置定义记忆操作：
     - beat：`on_enter` / `on_complete` 时写入记忆
     - task：完成 milestone 时写入记忆
   - JSON 示例（写在 beats 里）：
     ```jsonc
     "beats": [
       {
         "id": "garden_choice_escape",
         "trigger": "rule_event:escape",
         "memory_set": ["xinyue.escape_once"],
         "rule_refs": ["garden_branch_escape"]
       }
     ]
     ```

2. **StoryEngine 增强：根据记忆选择合适的 beat**
   - 在 `story_engine.advance()` 中：
     - 读取当前玩家的 `story_memory`（per-player, per-profile）
     - 在决定下一个 beat 时，优先选满足 `memory_required` 条件的 beats：
       ```jsonc
       {
         "id": "mountain_comfort",
         "trigger": "on_enter",
         "memory_required": ["xinyue.escape_once"],
         "rule_refs": ["summit_comfort"]
       }
       ```
   - 在 beat / task 完成时：
     - 执行 `memory_set` / `memory_clear` 操作并持久化。

3. **StoryGraph：把记忆也记进轨迹**
   - 在 `story_graph.py` 中：
     - 在 trajectory 中附加 `memory_tags` 或 choice-derived flags
     - 推荐算法可以轻微优先推荐：
       - 与当前记忆标签相匹配的章节
       - 或相反，推荐“疗愈/修复”型章节（保留空间）

4. **提供 Memory Debug API**
   - 在 `world_api.py` 中新增：
     - `GET /world/story/{player_id}/memory`：
       - 返回当前玩家的记忆 key 列表：
       ```json
       {
         "player_id": "Steve",
         "flags": ["xinyue.escape_once", "xinyue.reached_summit"]
       }
       ```
   - 用于开发阶段在 mc 里验证记忆逻辑。

5. **升级四个旗舰关卡的 JSON，让记忆真正“可见”**
   - `flagship_tutorial.json`：
     - 在结尾根据玩家是否向向导询问“困难/疾病”，打一个记忆标记：
       - `xinyue.admitted_pain = true/false`
   - `flagship_03.json`（登山）：
     - 如果玩家携带 `xinyue.admitted_pain`：
       - 登山 NPC 台词更加温柔/共情
     - 若没有：
       - 台词偏“训练式”，更强调意志
   - `flagship_08.json`（花园 / 疾病）：
     - 玩家在花园中有一个关键选择：
       - “选择继续逃避” → `xinyue.escape_once`
       - “选择面对”等选项 → `xinyue.face_once`
     - 后续 NPC 和 Cinematic 根据这两种记忆差异化展示。
   - `flagship_12.json`：
     - 读取 `xinyue.escape_once` / `xinyue.face_once`：
       - 为玩家呈现不同的回顾桥段（台词 or 小型 cinematic）

6. **文档更新**
   - 新建 `docs/MEMORY_SYSTEM.md`：
     - 解释记忆 flag 命名规范：`domain.topic.event`
     - 演示 JSON 写法（放一个完整的 flagship_08 例子）
   - 更新 STATE.md：
     - 增加 `PHASE_16_COMPLETE = true`
     - Progress – Done 中写明：
       - “Flagship arc 现在拥有跨关卡记忆系统（xinyue.* flags），影响 NPC 台词、电影片段和推荐逻辑。”

## Output Expectations

- 在测试环境中，至少实现以下验证场景：
  1. 玩家在 `flagship_tutorial` 中 **承认自己的痛苦** → 设置 `xinyue.admitted_pain`  
     再进入 `flagship_03` 时，登山者会说出不同的安慰台词。
  2. 玩家在 `flagship_08` 中选择“逃避” → `xinyue.escape_once`  
     在 `flagship_12` 结尾的 cinematic 中，会出现“还在泥泞中徘徊”的影像 / 文案提示。
- `/world/story/{player}/memory` 能正确返回这些 flags，便于开发者检查。