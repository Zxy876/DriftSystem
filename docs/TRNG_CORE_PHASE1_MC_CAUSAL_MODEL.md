# TRNG Core — Minecraft 因果模型（Phase 1：草案）

目的：把 Minecraft 的原始事件流窗口化、显式化为可结算、可审计、可回放的事务（Transaction），并将变更以 GraphLayer + CommittedState 的形式原子提交与投影回 MC。

目录
- 1. MC 事件 → StoryEvent 映射表（白名单）
- 2. 行为窗口定义（时间 / 空间 / 类型 / 提交条件）
- 3. 布尔谓词与计数变量（Predicates / Counters）
- 4. DomainState 四子域字段草案（topology / actors / regime / economy）
- 5. 示例事务：砍树 → 掉落 → 合成 → 解锁
- 6. 验收准则（如何证明因果链被显式化）

---

**1. MC 事件 → StoryEvent 映射表（白名单）**
- block_break → StoryEvent.block_break
- block_place → StoryEvent.block_place
- entity_damage → StoryEvent.entity_damage
- entity_death → StoryEvent.entity_death
- item_pickup → StoryEvent.item_pickup
- item_craft → StoryEvent.item_craft
- region_enter / region_exit → StoryEvent.region_enter / region_exit
- dialog_input / chat_command → StoryEvent.dialog_input
- player_move (仅用于 region 边界检测) → StoryEvent.player_move
- redstone_update（若影响叙事域）→ StoryEvent.redstone_update

说明：只接入“叙事相关事件白名单”。其他低价值/噪声事件可丢弃或记录速览（sampling）。

---

**2. 行为窗口（Behavior Window）定义**
窗口是构成 Transaction 的事件集合，定义维度：

- Temporal Window（时间）
  - 启动：首次白名单事件发生
  - 结束：静默阈值（silenceCount）或最大超时（例如 1.5s / 3s）或显式 commit 事件

- Spatial Window（空间）
  - 中心：发起事件相关玩家或实体坐标
  - 半径 R：16 / 32 / 64 格（可配置）——只收集该范围内的 topology/actors 变化

- Type Filter（类型）
  - 只包含白名单类型，或仅包含对当前叙事有影响的 subtype

- Commit Conditions（事务完结）
  - 达到阈值（count/weight），或接收到显式结束符，或超时

实现要点：窗口内先 build（写入 tx），不写真相；commit 时执行原子 append 到 GraphLayer 并替换 CommittedState。投影回 Minecraft 的 patch 为可选补偿操作（投影失败不回滚真相，只记账）。

---

**3. 布尔谓词与计数变量（Predicate / Counter）**
3.1 原子布尔谓词（示例）
- broke_tree：窗口内是否破坏过原木
- took_damage：窗口内是否受到伤害
- killed_by_mob：是否被怪物击杀
- entered_zone_A：是否进入区域 A
- crafted_item_X：是否合成 X
- placed_block_type_Y：是否放置 Y
- npc_nearby：半径 R 内是否存在 NPC

3.2 聚合计数 / 强度变量（示例）
- damage_sum：窗口内累计伤害
- blocks_changed_count：被改变的方块数
- mob_count_nearby：怪物数
- silence_count：窗口内无有效输入时的计数
- tension：TRNG 内部节奏变量，可从上述量计算得出

用途：谓词作为分叉点（True/False），计数作为 thresholdCheck 与事件优先级输入。

---

**4. DomainState（四子域）字段草案**
4.1 Topology / World-Slice
- fields: chunk_ids[], block_deltas[] (pos, old, new), lighting_changes
- semantics: 仅记录窗口内的 delta；patch 可用于回放/投影

4.2 Actors（NPC / 玩家 / 生物）
- fields: actor_id, hp, position, inventory_delta, ai_state, dialog_state, aggro_list
- semantics: 窗口内 actor 的状态变更写入 tx；read-only snapshot 用于推理

4.3 Regime（调度 / 冷却 / reentrancy）
- fields: cooldowns[(actor_id, ability) -> expiry_ts], reentrancy_locks[player_id], rate_limits
- semantics: 防重入并限制 apply 频率；作为事务可验证的约束

4.4 Economy（资源 / 约束）
- fields: resource_balances[(player_id, resource) -> amount], inventory_invariants
- semantics: 保持守恒规则（不允许负数），作为可验证因果证据链的一部分

不变量样例：同一 `player_id` 同时只有一个 apply 事务；build 只写 tx；commit 做原子替换；abort 能恢复 snapshot。

---

**5. 示例：砍树 → 掉落 → 合成 → 解锁（Transaction 流程）**
步骤：
1. 玩家触发 `block_break`（原木） → 启动窗口 W
2. Window 收集事件（block_break, item_drop, item_pickup）与域 snapshot（topology slice + nearby actors）
3. Build phase（tx）：
   - 生成 nodes：{node: "tree_cut", predicates: {broke_tree=true, item_pickup=true}, patch: block_delta + item_delta}
   - 更新 InternalState.counters（blocks_changed_count++, damage_sum 可能为0）
4. ThresholdCheck：broke_tree && item_pickup => 触发 "wood_acquired" narrative node
5. Commit：
   - Append nodes 到 GraphLayer（append-only）
   - Replace CommittedState 的对应 slice（atomic swap/merge）
6. Projection：生成 MC patch（实际方块移除、掉落实体消失、合成解锁奖励）并尝试投影回 Minecraft。若投影失败：记录失败、发出补偿事件或人工审查，但不回滚 GraphLayer。

示意：build 只影响 tx，commit 保证原子性，projection 为副作用且可补偿。

---

**6. 验收准则（如何证明因果链被显式化）**
- 可回放：从 GraphLayer 读取一窗口的 nodes 与 patches，按时间和依赖重放，结果应等价于投影（若投影成功时）。
- 不变量检查：验证 reentrancy / cooldown / resource invariants 在所有 commit 前后成立。
- 可审计日志：每次 tx/commit 产出可签名的变更记录（metadata: window_id, player_id, timestamp, predicates, counters）。
- 回溯追踪：给定一个最终状态变更（例如配方解锁），能追踪到产生该变更的节点集合与触发谓词。

---

后续建议工作项（Phase 1 完成后）
- 把上述 predicates/counters 落成 YAML/JSON schema，供运行时与 UI 使用
- 在代码中实现 Window manager（时间/空间/类型过滤 + snapshot capture）
- 实现简单的 Transaction executor：build → thresholdCheck → commit → projection（可选）
- 为常见流程写回放测试（unit/integration）以验证回放等价性

---

版本历史
- v0.1 初稿（Phase 1 草案）
