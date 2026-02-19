# CONTRACT_SURFACE.md
## DriftSystem 数学门控插入面（Mathematical Gate Insertion Points）

> **Research Task**: 找出所有可以插入"数学门控（Mathematical Gate）"的接口面（Surface）

---

## 1. Contract Surface 定义

**Contract Surface** 是系统中可以插入验证逻辑的接口面，具有以下特征：
1. **输入/输出清晰**: 有明确的数据结构
2. **决策点**: 存在 True/False 判定
3. **可插入**: 不破坏现有逻辑的前提下添加验证
4. **可审计**: 验证结果可记录

---

## 2. Surface 分类

### 分类标准
| 类型 | 特征 | 适合的数学门控 |
|------|------|----------------|
| **Type A: Command Validation** | 指令执行前的安全检查 | 证明指令不破坏不变量 |
| **Type B: Adjudication** | 裁决决策点 | 证明方案满足数学约束 |
| **Type C: Quest Matching** | 事件匹配与完成判定 | 证明事件序列合法性 |
| **Type D: Resource Allocation** | 资源分配与消耗 | 证明资源守恒 |
| **Type E: State Transition** | 状态迁移门控 | 证明状态转换合法 |

---

## 3. Surface 清单（Contract Surface Inventory）

### Surface 1: Command Safety Analyzer
**文件位置**: `backend/app/core/world/command_safety.py`

**函数签名**:
```python
def analyze_commands(commands: Iterable[str]) -> CommandSafetyReport
```

**输入结构**:
```python
commands: List[str]  # Minecraft 指令列表
# Example: ["setblock ~ ~ ~ stone", "fill ~-2 ~ ~-2 ~2 ~4 ~2 red_bricks"]
```

**输出结构**:
```python
class CommandSafetyReport:
    errors: List[str]      # 阻断性错误（blacklist tokens, illegal commands）
    warnings: List[str]    # 非阻断性警告（unlisted prefix, unexpected characters）
```

**判定发生的位置**:
```python
# Line 59-99 in command_safety.py
if any(token in cmd for token in BLACKLIST_TOKENS):
    errors.append(f"Blacklist token found: {token}")
    
if any(cmd.startswith(bc) for bc in BLACKLIST_COMMANDS):
    errors.append(f"Blacklist command: {cmd}")
```

**是否可插入数学验证**: ✅ **是**

**验证类型**:
- **不变量证明**: 证明指令不会破坏世界边界 (x, y, z 坐标在合法范围内)
- **资源守恒**: 证明 fill 指令的体积不超过阈值
- **时间复杂度**: 证明指令执行时间 ≤ T_max

**插入点示例**:
```python
def analyze_commands_with_math_proof(commands: Iterable[str]) -> CommandSafetyReport:
    report = analyze_commands(commands)  # 原有逻辑
    
    # 插入数学验证
    for cmd in commands:
        if cmd.startswith("fill"):
            volume = calculate_fill_volume(cmd)
            if volume > MAX_VOLUME:
                report.errors.append(f"Volume constraint violated: {volume} > {MAX_VOLUME}")
                report.math_proof = {
                    "constraint": "volume <= MAX_VOLUME",
                    "actual": volume,
                    "limit": MAX_VOLUME,
                    "verdict": "FAILED"
                }
    
    return report
```

---

### Surface 2: Patch Template Validator
**文件位置**: `backend/app/core/creation/validation.py`

**函数签名**:
```python
def validate_patch_template(template: Dict) -> PatchTemplateValidationResult
```

**输入结构**:
```python
template: Dict = {
    "template_id": str,
    "status": str,  # "draft" | "resolved"
    "steps": List[{
        "step_id": str,
        "step_type": str,  # "block_placement" | "entity_spawn" | "mod_function"
        "commands": List[str],
        "placeholders": Dict
    }]
}
```

**输出结构**:
```python
class PatchTemplateValidationResult:
    execution_tier: str  # "safe_auto" | "needs_confirm" | "blocked"
    errors: List[str]
    warnings: List[str]
    missing_fields: List[str]
```

**判定发生的位置**:
```python
# Line 75-123 in validation.py
if errors:
    execution_tier = "blocked"
elif has_placeholders or missing_fields or warnings:
    execution_tier = "needs_confirm"
else:
    execution_tier = "safe_auto"
```

**是否可插入数学验证**: ✅ **是**

**验证类型**:
- **结构完整性**: 证明模板 DAG 无环 (无循环依赖)
- **资源可达性**: 证明所需资源在玩家可达范围内
- **前置条件**: 证明 preconditions → postconditions

**插入点示例**:
```python
def validate_with_preconditions(template: Dict) -> PatchTemplateValidationResult:
    result = validate_patch_template(template)
    
    # 插入数学验证
    if "preconditions" in template:
        for condition in template["preconditions"]:
            if not evaluate_logical_formula(condition, current_state):
                result.execution_tier = "blocked"
                result.errors.append(f"Precondition failed: {condition}")
                result.math_proof = {
                    "type": "precondition_check",
                    "formula": condition,
                    "verdict": "FAILED"
                }
    
    return result
```

---

### Surface 3: Patch Executor (Dry-Run)
**文件位置**: `backend/app/core/world/patch_executor.py`

**函数签名**:
```python
def dry_run(self, plan: CreationPlan) -> PatchExecutionResult
```

**输入结构**:
```python
class CreationPlan:
    plan_id: str
    player_id: str
    intent: str
    patches: List[CreationPatchTemplate]
    metadata: Dict
```

**输出结构**:
```python
class PatchExecutionResult:
    executed: List[Template]          # 通过验证的模板
    skipped: List[SkipRecord]         # 跳过的模板 + 原因
    errors: List[str]                 # 错误列表
    warnings: List[str]               # 警告列表
    transactions: List[TransactionEntry]  # 审计日志
```

**判定发生的位置**:
```python
# Line 120-183 in patch_executor.py
for template in plan.patches:
    validation_result = validate_patch_template(template)
    
    if validation_result.execution_tier == "safe_auto":
        executed.append(template)
        transactions.append({
            "status": "validated",
            "commands": template.commands
        })
    else:
        skipped.append({
            "template_id": template.id,
            "reason": validation_result.execution_tier
        })
```

**是否可插入数学验证**: ✅ **是**

**验证类型**:
- **模拟执行**: 证明指令序列在虚拟世界中可成功执行
- **副作用分析**: 证明指令不影响其他玩家的建筑
- **原子性**: 证明执行是原子的（要么全部成功，要么全部回滚）

**插入点示例**:
```python
def dry_run_with_simulation(self, plan: CreationPlan) -> PatchExecutionResult:
    result = self.dry_run(plan)  # 原有逻辑
    
    # 插入数学验证
    virtual_world = VirtualWorldState(current_world)
    
    for template in result.executed:
        try:
            virtual_world.simulate(template.commands)
            
            # 验证不变量
            if not virtual_world.check_invariants():
                result.executed.remove(template)
                result.skipped.append({
                    "template_id": template.id,
                    "reason": "invariant_violated",
                    "math_proof": {
                        "type": "invariant_check",
                        "violated_invariant": virtual_world.get_violated_invariant(),
                        "verdict": "FAILED"
                    }
                })
        except SimulationError as e:
            # 模拟失败
            pass
    
    return result
```

---

### Surface 4: Ideal City Adjudicator
**文件位置**: `backend/app/core/ideal_city/pipeline.py`

**函数签名**:
```python
def evaluate(self, spec: DeviceSpec, scenario: ScenarioContext, submission_hints) -> Tuple[AdjudicationRecord, List[str]]
```

**输入结构**:
```python
class DeviceSpec:
    spec_id: str
    player_ref: str
    submission_text: str
    is_draft: bool
    world_constraints: str       # 必需
    logic_outline: List[str]     # 必需
    risk_register: str           # 必需
    success_criteria: str        # 可选
    resource_ledger: str         # 可选
```

**输出结构**:
```python
class AdjudicationRecord:
    ruling_id: str
    verdict: VerdictEnum  # ACCEPT | REJECT | PARTIAL | REVIEW_REQUIRED
    reasoning: List[str]
    conditions: List[str]
    memory_hooks: List[str]
```

**判定发生的位置**:
```python
# Line 379-455 in pipeline.py
def _rule_based_decision(spec: DeviceSpec) -> AdjudicationRecord:
    if spec.is_draft:
        verdict = VerdictEnum.REVIEW_REQUIRED
    elif missing_sections:
        verdict = VerdictEnum.REJECT
    else:
        verdict = VerdictEnum.ACCEPT
```

**是否可插入数学验证**: ✅ **是**

**验证类型**:
- **定理证明**: 要求玩家提交数学证明作为 `logic_outline`
- **公式验证**: 解析并验证 `world_constraints` 中的数学公式
- **一致性检查**: 证明 `logic_outline` 与 `risk_register` 无矛盾

**插入点示例**:
```python
def evaluate_with_math_proof(self, spec: DeviceSpec) -> AdjudicationRecord:
    record = self.evaluate(spec, scenario, hints)  # 原有逻辑
    
    # 插入数学验证
    if record.verdict == VerdictEnum.ACCEPT:
        # 要求提交数学证明
        if "math_proof" not in spec.metadata:
            record.verdict = VerdictEnum.REVIEW_REQUIRED
            record.conditions.append("需要提交数学证明：证明方案满足世界约束")
            return record
        
        # 验证数学证明
        proof = spec.metadata["math_proof"]
        if not verify_proof(proof, spec.world_constraints):
            record.verdict = VerdictEnum.REJECT
            record.reasoning.append("数学证明验证失败")
            record.math_proof_log = {
                "type": "theorem_verification",
                "proof": proof,
                "constraints": spec.world_constraints,
                "verdict": "INVALID"
            }
    
    return record
```

---

### Surface 5: Quest Event Matcher
**文件位置**: `backend/app/core/quest/runtime.py`

**函数签名**:
```python
def _match_event(self, event: Dict, milestone: Milestone) -> Tuple[bool, Optional[Milestone], Optional[str]]
```

**输入结构**:
```python
event: Dict = {
    "type": str,        # "block_break" | "entity_kill" | "item_collect"
    "target": str,      # "stone" | "zombie" | "diamond"
    "count": int,       # 1
    "location": Dict,   # {"x": 100, "y": 70, "z": 200}
    "timestamp": str
}

milestone: Milestone = {
    "id": str,
    "type": str,
    "target": str,
    "count": int,
    "alternates": List[str],
    "status": str  # "pending" | "completed"
}
```

**输出结构**:
```python
(matched: bool, milestone: Optional[Milestone], token: Optional[str])
```

**判定发生的位置**:
```python
# Line 168-232 in runtime.py
def _match_event(self, event, milestone):
    if event["type"] != milestone["type"]:
        return (False, None, None)
    
    if event["target"] == milestone["target"]:
        return (True, milestone, event_token)
    
    if event["target"] in milestone.get("alternates", []):
        return (True, milestone, event_token)
    
    return (False, None, None)
```

**是否可插入数学验证**: ✅ **是**

**验证类型**:
- **序列验证**: 证明事件序列符合预期模式 (正则表达式 / 自动机)
- **概率检验**: 证明掉落物品的概率符合预期分布
- **时间约束**: 证明事件在时间窗口内完成 (t_start ≤ t_event ≤ t_end)

**插入点示例**:
```python
def _match_event_with_sequence_check(self, event: Dict, milestone: Milestone) -> Tuple[bool, Optional[Milestone], Optional[str]]:
    matched, milestone, token = self._match_event(event, milestone)  # 原有逻辑
    
    if matched:
        # 插入序列验证
        event_history = self.get_event_history(milestone.task_id)
        expected_pattern = milestone.get("expected_pattern")
        
        if expected_pattern:
            if not matches_pattern(event_history + [event], expected_pattern):
                return (False, None, None)  # 序列不匹配，拒绝
                # 记录证明
                self.log_proof({
                    "type": "sequence_verification",
                    "pattern": expected_pattern,
                    "actual_sequence": event_history + [event],
                    "verdict": "FAILED"
                })
    
    return (matched, milestone, token)
```

---

### Surface 6: Memory Condition Gate
**文件位置**: `backend/app/core/story/level_schema.py`

**函数签名**:
```python
def is_satisfied(self, flags: Iterable[str]) -> bool
```

**输入结构**:
```python
class MemoryCondition:
    require_all: Optional[List[str]]  # AND 条件
    require_any: Optional[List[str]]  # OR 条件

flags: Set[str]  # 当前玩家的记忆标记集合
# Example: {"level_1_completed", "tutorial_done", "has_diamond_sword"}
```

**输出结构**:
```python
bool  # True (门控开启) | False (门控关闭)
```

**判定发生的位置**:
```python
# Line 125-131 in level_schema.py
def is_satisfied(self, flags: Iterable[str]) -> bool:
    universe = {flag for flag in flags}
    
    if self.require_all and not all(flag in universe for flag in self.require_all):
        return False  # AND 条件不满足
    
    if self.require_any:
        return any(flag in universe for flag in self.require_any)  # OR 条件
    
    return True  # 无条件或条件满足
```

**是否可插入数学验证**: ✅ **是**

**验证类型**:
- **集合逻辑**: 证明 flags 满足布尔逻辑公式
- **路径验证**: 证明玩家经历的关卡路径合法
- **依赖检查**: 证明前置关卡已完成 (拓扑排序)

**插入点示例**:
```python
def is_satisfied_with_math_formula(self, flags: Iterable[str], formula: str = None) -> bool:
    satisfied = self.is_satisfied(flags)  # 原有逻辑
    
    if formula:
        # 插入数学公式验证
        # formula example: "(A ∧ B) ∨ (C ∧ ¬D)"
        result = evaluate_boolean_formula(formula, flags)
        
        if not result:
            self.log_proof({
                "type": "boolean_formula_check",
                "formula": formula,
                "flags": list(flags),
                "verdict": "FAILED"
            })
            return False
    
    return satisfied
```

---

### Surface 7: Resource Allocation (Build Executor)
**文件位置**: `backend/app/core/ideal_city/build_executor.py`

**函数签名**:
```python
def execute(self, plan: BuildPlan) -> ExecutionResult
```

**输入结构**:
```python
class BuildPlan:
    plan_id: str
    player_id: str
    patches: List[PatchTemplate]
    resource_requirements: Dict[str, int]  # {"stone": 100, "wood": 50}
```

**输出结构**:
```python
class ExecutionResult:
    success: bool
    executed_patches: List[str]
    failed_patches: List[str]
    resource_consumed: Dict[str, int]
```

**判定发生的位置**:
```python
# Line 85-120 in build_executor.py (推测位置)
def execute(self, plan: BuildPlan):
    # 检查资源是否足够
    if not has_sufficient_resources(plan.player_id, plan.resource_requirements):
        return ExecutionResult(success=False, reason="insufficient_resources")
    
    # 执行补丁
    for patch in plan.patches:
        execute_patch(patch)
    
    # 扣除资源
    deduct_resources(plan.player_id, plan.resource_requirements)
```

**是否可插入数学验证**: ✅ **是**

**验证类型**:
- **资源守恒**: 证明 资源消耗 = 资源需求
- **库存不变量**: 证明玩家库存不会变为负数
- **交易公平性**: 证明交易满足等价交换原则

**插入点示例**:
```python
def execute_with_conservation_proof(self, plan: BuildPlan) -> ExecutionResult:
    # 记录初始资源
    initial_inventory = get_player_inventory(plan.player_id)
    
    result = self.execute(plan)  # 原有逻辑
    
    # 验证资源守恒
    final_inventory = get_player_inventory(plan.player_id)
    expected_inventory = {
        k: initial_inventory.get(k, 0) - plan.resource_requirements.get(k, 0)
        for k in set(initial_inventory) | set(plan.resource_requirements)
    }
    
    if final_inventory != expected_inventory:
        result.success = False
        result.math_proof = {
            "type": "resource_conservation",
            "initial": initial_inventory,
            "expected": expected_inventory,
            "actual": final_inventory,
            "verdict": "VIOLATED"
        }
    
    return result
```

---

### Surface 8: Transaction Log Writer
**文件位置**: `backend/app/core/world/patch_transaction.py`

**函数签名**:
```python
def record(self, patch_id, template_id, step_id, commands, status, metadata)
```

**输入结构**:
```python
patch_id: str
template_id: str
step_id: str
commands: List[str]
status: str  # "pending" | "validated" | "applied" | "rolled_back"
metadata: Dict
```

**输出结构**:
```python
None  # Append-only log, no return value
```

**判定发生的位置**:
```python
# 写入 JSON 日志文件
entry = {
    "patch_id": patch_id,
    "template_id": template_id,
    "step_id": step_id,
    "commands": commands,
    "status": status,
    "created_at": datetime.now().isoformat(),
    "metadata": metadata
}
log_file.write(json.dumps(entry) + "\n")
```

**是否可插入数学验证**: ✅ **是**

**验证类型**:
- **因果链**: 证明每个状态变更有明确的前置事件
- **可重放性**: 证明日志可以重建世界状态
- **完整性**: 证明日志无缺失 (sequence number 连续)

**插入点示例**:
```python
def record_with_proof(self, patch_id, template_id, step_id, commands, status, metadata, proof: Dict = None):
    # 插入证明字段
    if proof:
        metadata["math_proof"] = proof
    
    self.record(patch_id, template_id, step_id, commands, status, metadata)  # 原有逻辑
    
    # 验证日志完整性
    if not self.verify_log_integrity():
        raise LogIntegrityError("Log sequence number gap detected")
```

---

## 4. Surface 优先级排序（Prioritized Surface List）

| 优先级 | Surface | 原因 | 数学能力训练点 |
|--------|---------|------|----------------|
| **P0** | Ideal City Adjudicator | 最直接的"证明提交"入口 | 定理证明、公式推导、逻辑推理 |
| **P1** | Patch Executor (Dry-Run) | 可模拟执行 + 验证不变量 | 不变量证明、副作用分析、模拟执行 |
| **P2** | Command Safety Analyzer | 最早的验证点 | 边界检查、资源约束、复杂度分析 |
| **P3** | Quest Event Matcher | 可验证序列合法性 | 序列匹配、概率验证、时间约束 |
| **P4** | Memory Condition Gate | 可嵌入逻辑公式 | 布尔逻辑、集合论、路径验证 |
| **P5** | Resource Allocation | 可验证守恒定律 | 资源守恒、库存管理、等价交换 |
| **P6** | Patch Template Validator | 可验证结构完整性 | DAG 检查、前置条件、后置条件 |
| **P7** | Transaction Log Writer | 可记录证明轨迹 | 因果链、可重放性、完整性验证 |

---

## 5. 每个 Surface 的详细规格（Detailed Surface Specifications）

### 规格模板
对每个 Surface，提供以下信息：

| 字段 | 说明 |
|------|------|
| **Surface ID** | 唯一标识符 |
| **Path** | 文件路径 + 行号 |
| **Function** | 函数签名 |
| **Input Schema** | 输入数据结构 |
| **Output Schema** | 输出数据结构 |
| **Validation Moment** | 判定发生的具体位置 |
| **Math Gate Type** | 可插入的数学门控类型 |
| **Proof Format** | 证明数据格式 |
| **Example** | 具体示例 |

---

### Surface 1 详细规格

**Surface ID**: `SURF-001-COMMAND-SAFETY`

**Path**: `backend/app/core/world/command_safety.py:59-99`

**Function**:
```python
def analyze_commands(commands: Iterable[str]) -> CommandSafetyReport
```

**Input Schema**:
```python
{
    "commands": [
        "setblock ~ ~ ~ stone",
        "fill ~-2 ~ ~-2 ~2 ~4 ~2 red_bricks"
    ]
}
```

**Output Schema**:
```python
{
    "errors": [
        "Blacklist token found: ;",
        "Blacklist command: op"
    ],
    "warnings": [
        "Unlisted prefix: custom_command"
    ],
    "math_proof": {  # 新增字段
        "type": "volume_constraint",
        "constraint": "volume <= 1000",
        "actual": 125,
        "verdict": "PASSED"
    }
}
```

**Validation Moment**:
```python
# Line 78-85
for cmd in commands:
    if any(token in cmd for token in BLACKLIST_TOKENS):
        errors.append(f"Blacklist token found: {token}")
        
    # 插入点: 这里可以添加数学验证
    # if not verify_volume_constraint(cmd):
    #     errors.append(f"Volume constraint violated")
```

**Math Gate Type**:
1. **Volume Constraint**: `fill` 指令的体积 ≤ MAX_VOLUME
2. **Coordinate Bounds**: 坐标在世界边界内 (-30M ≤ x, z ≤ 30M, 0 ≤ y ≤ 319)
3. **Time Complexity**: 指令执行时间 ≤ T_max

**Proof Format**:
```json
{
    "type": "volume_constraint",
    "constraint": "volume <= MAX_VOLUME",
    "formula": "V = (x2-x1+1) * (y2-y1+1) * (z2-z1+1)",
    "substitution": {
        "x1": -2, "x2": 2,
        "y1": 0, "y2": 4,
        "z1": -2, "z2": 2
    },
    "evaluation": "V = 5 * 5 * 5 = 125",
    "result": 125,
    "limit": 1000,
    "verdict": "PASSED"
}
```

**Example**:
```python
# 玩家输入: "建造一个 10x10x10 的石头立方体"
commands = ["fill ~0 ~ ~0 ~10 ~10 ~10 stone"]

# 数学验证
volume = 11 * 11 * 11 = 1331
if volume > MAX_VOLUME (1000):
    verdict = "FAILED"
    error = "体积超限: 1331 > 1000"
```

---

### Surface 2 详细规格

**Surface ID**: `SURF-002-ADJUDICATION`

**Path**: `backend/app/core/ideal_city/pipeline.py:379-455`

**Function**:
```python
def evaluate(self, spec: DeviceSpec, scenario: ScenarioContext, submission_hints) -> Tuple[AdjudicationRecord, List[str]]
```

**Input Schema**:
```python
{
    "spec_id": "uuid-1234",
    "player_ref": "player-5678",
    "submission_text": "提案：建造紫水晶能量塔",
    "is_draft": false,
    "world_constraints": "塔高不超过 Y=100，占地面积 ≤ 20x20",
    "logic_outline": [
        "使用导数优化能量传输效率",
        "梯度下降法找最优塔高",
        "证明: dE/dh = 0 时，h = 85 为最优解"
    ],
    "risk_register": "高度过高可能影响天气系统",
    "math_proof": {  # 新增字段
        "theorem": "能量效率优化定理",
        "proof_steps": [
            "定义能量函数 E(h) = h * (100 - h) / 100",
            "求导: dE/dh = (100 - 2h) / 100",
            "令 dE/dh = 0，得 h = 50",
            "二阶导数 d²E/dh² = -2/100 < 0，确认为极大值",
            "结论: h = 50 时能量效率最高"
        ]
    }
}
```

**Output Schema**:
```python
{
    "ruling_id": "ruling-uuid",
    "verdict": "ACCEPT",  # ACCEPT | REJECT | REVIEW_REQUIRED
    "reasoning": [
        "档案馆确认提案包含必要结构",
        "数学证明验证通过: 能量效率优化定理"
    ],
    "conditions": [],
    "memory_hooks": ["ideal_city_accept"],
    "math_proof_log": {  # 新增字段
        "type": "theorem_verification",
        "theorem": "能量效率优化定理",
        "verification_method": "symbolic_differentiation",
        "verdict": "VALID"
    }
}
```

**Validation Moment**:
```python
# Line 420-430
if spec.is_draft:
    verdict = VerdictEnum.REVIEW_REQUIRED
elif missing_sections:
    verdict = VerdictEnum.REJECT
else:
    verdict = VerdictEnum.ACCEPT
    
    # 插入点: 验证数学证明
    # if "math_proof" in spec.metadata:
    #     if not verify_theorem(spec.metadata["math_proof"]):
    #         verdict = VerdictEnum.REJECT
```

**Math Gate Type**:
1. **Theorem Proof**: 要求提交定理证明
2. **Formula Validation**: 验证公式正确性
3. **Constraint Satisfaction**: 证明方案满足约束

**Proof Format**:
```json
{
    "type": "theorem_verification",
    "theorem": "能量效率优化定理",
    "proof_steps": [
        "step1: 定义能量函数",
        "step2: 求导",
        "step3: 令导数为零",
        "step4: 验证二阶导数",
        "step5: 结论"
    ],
    "verification_method": "symbolic_differentiation",
    "tools_used": ["SymPy", "Wolfram Alpha"],
    "verdict": "VALID"
}
```

**Example**:
```python
# 玩家提交: "建造紫水晶能量塔，高度 h = 50"
spec = {
    "logic_outline": ["使用导数优化能量传输效率"],
    "math_proof": {
        "theorem": "能量效率优化定理",
        "proof_steps": [...]
    }
}

# 系统验证
verified = verify_calculus_proof(spec.math_proof)
if verified:
    verdict = "ACCEPT"
    reasoning.append("数学证明验证通过")
else:
    verdict = "REJECT"
    reasoning.append("数学证明验证失败: 导数计算错误")
```

---

### Surface 3 详细规格

**Surface ID**: `SURF-003-QUEST-MATCHER`

**Path**: `backend/app/core/quest/runtime.py:168-232`

**Function**:
```python
def _match_event(self, event: Dict, milestone: Milestone) -> Tuple[bool, Optional[Milestone], Optional[str]]
```

**Input Schema**:
```python
{
    "event": {
        "type": "block_break",
        "target": "stone",
        "count": 10,
        "location": {"x": 100, "y": 70, "z": 200},
        "timestamp": "2026-01-09T12:34:56Z"
    },
    "milestone": {
        "id": "milestone_1",
        "type": "block_break",
        "target": "stone",
        "count": 100,
        "alternates": ["granite", "diorite"],
        "status": "pending",
        "expected_pattern": "STONE{100}",  # 新增字段
        "time_window": {"start": "2026-01-09T12:00:00Z", "end": "2026-01-09T13:00:00Z"}
    }
}
```

**Output Schema**:
```python
{
    "matched": true,
    "milestone": {...},
    "token": "event-token-uuid",
    "math_proof": {  # 新增字段
        "type": "sequence_verification",
        "pattern": "STONE{100}",
        "actual_sequence": ["STONE", "STONE", ...],
        "count": 10,
        "remaining": 90,
        "verdict": "IN_PROGRESS"
    }
}
```

**Validation Moment**:
```python
# Line 205-220
if event["type"] != milestone["type"]:
    return (False, None, None)

if event["target"] == milestone["target"]:
    # 插入点: 验证序列模式
    # if not matches_expected_pattern(event, milestone["expected_pattern"]):
    #     return (False, None, None)
    return (True, milestone, event_token)
```

**Math Gate Type**:
1. **Sequence Pattern**: 验证事件序列符合正则表达式
2. **Probability Check**: 验证掉落物品概率符合预期
3. **Time Constraint**: 验证事件在时间窗口内

**Proof Format**:
```json
{
    "type": "sequence_verification",
    "pattern": "STONE{100}",
    "regex": "^(STONE|GRANITE|DIORITE){100}$",
    "actual_sequence": ["STONE", "STONE", "GRANITE", ...],
    "count": 10,
    "remaining": 90,
    "time_elapsed": "00:12:34",
    "time_remaining": "00:47:26",
    "verdict": "IN_PROGRESS"
}
```

**Example**:
```python
# 任务: 收集 100 个石头（或花岗岩、闪长岩）
milestone = {
    "type": "block_break",
    "target": "stone",
    "count": 100,
    "alternates": ["granite", "diorite"],
    "expected_pattern": "(STONE|GRANITE|DIORITE){100}"
}

# 玩家破坏方块
event = {"type": "block_break", "target": "stone", "count": 10}

# 验证序列
matched = matches_pattern(event_history + [event], milestone["expected_pattern"])
if matched:
    verdict = "IN_PROGRESS"
else:
    verdict = "PATTERN_MISMATCH"
```

---

## 6. 数学门控类型分类（Math Gate Types）

### 6.1 类型 A: 约束验证（Constraint Verification）
**定义**: 证明某个值/属性满足数学约束

**公式模板**:
```
∀x ∈ Domain, P(x) → Q(x)
where P(x) = precondition, Q(x) = constraint
```

**应用场景**:
- 体积约束: `volume ≤ MAX_VOLUME`
- 坐标约束: `MIN_X ≤ x ≤ MAX_X`
- 时间约束: `t_start ≤ t ≤ t_end`

**示例**:
```python
def verify_volume_constraint(cmd: str) -> bool:
    volume = calculate_volume(cmd)
    return volume <= MAX_VOLUME
```

---

### 6.2 类型 B: 不变量证明（Invariant Proof）
**定义**: 证明某个性质在操作前后保持不变

**公式模板**:
```
Invariant(S) ∧ Action(S, S') → Invariant(S')
where S = state before, S' = state after
```

**应用场景**:
- 资源守恒: `total_resources_before == total_resources_after`
- 世界边界: `world_bounds_before == world_bounds_after`
- 玩家权限: `player_permissions_before ⊆ player_permissions_after`

**示例**:
```python
def verify_resource_conservation(initial, final, consumed):
    expected = {k: initial[k] - consumed.get(k, 0) for k in initial}
    return final == expected
```

---

### 6.3 类型 C: 定理证明（Theorem Proof）
**定义**: 要求玩家提交数学定理的证明

**公式模板**:
```
Theorem: ∀x, P(x) → Q(x)
Proof:
  1. Assume P(x)
  2. ...intermediate steps...
  3. Therefore Q(x)
  QED
```

**应用场景**:
- 微积分: 优化问题（梯度下降）
- 线性代数: 矩阵分解
- 概率论: 期望值计算

**示例**:
```python
def verify_calculus_proof(proof: Dict) -> bool:
    # 验证导数计算
    function = parse_function(proof["function"])
    derivative = differentiate(function)
    critical_points = solve(derivative == 0)
    return proof["critical_points"] == critical_points
```

---

### 6.4 类型 D: 序列匹配（Sequence Matching）
**定义**: 证明事件序列符合预期模式

**公式模板**:
```
Sequence s matches Pattern p
if ∃ mapping f: s → p, s.t. ∀i, f(s[i]) ∈ p[i]
```

**应用场景**:
- Quest 验证: 事件序列匹配
- 故事分支: 玩家选择路径验证
- NPC 对话: 对话树验证

**示例**:
```python
def matches_pattern(sequence: List[str], pattern: str) -> bool:
    import re
    sequence_str = "".join(sequence)
    return bool(re.fullmatch(pattern, sequence_str))
```

---

### 6.5 类型 E: 概率验证（Probability Verification）
**定义**: 证明随机事件的概率符合预期分布

**公式模板**:
```
P(Event) = expected_probability ± tolerance
```

**应用场景**:
- 掉落验证: 物品掉落概率
- 采样验证: 地形生成随机性
- 公平性: 玩家抽奖公平性

**示例**:
```python
def verify_drop_probability(drops: List[str], expected_prob: float, tolerance: float = 0.05) -> bool:
    observed_prob = drops.count("diamond") / len(drops)
    return abs(observed_prob - expected_prob) < tolerance
```

---

## 7. Proof Payload 标准格式（Standard Proof Format）

### 7.1 通用 Proof Schema
```json
{
    "proof_id": "uuid",
    "type": "constraint_verification | invariant_proof | theorem_proof | sequence_matching | probability_verification",
    "player_id": "player-uuid",
    "timestamp": "2026-01-09T12:34:56Z",
    "context": {
        "surface_id": "SURF-001",
        "function": "analyze_commands",
        "input": {...}
    },
    "claim": "体积 ≤ 1000",
    "proof_steps": [
        "step1: 计算体积 V = (x2-x1+1) * (y2-y1+1) * (z2-z1+1)",
        "step2: 代入数值 V = 5 * 5 * 5 = 125",
        "step3: 验证 125 ≤ 1000 ✓"
    ],
    "verdict": "PASSED | FAILED",
    "verification_method": "symbolic | numerical | simulation",
    "tools_used": ["SymPy", "NumPy"],
    "metadata": {...}
}
```

---

### 7.2 示例: 体积约束证明
```json
{
    "proof_id": "proof-12345",
    "type": "constraint_verification",
    "player_id": "player-5678",
    "timestamp": "2026-01-09T12:34:56Z",
    "context": {
        "surface_id": "SURF-001-COMMAND-SAFETY",
        "function": "analyze_commands",
        "input": {
            "commands": ["fill ~-2 ~ ~-2 ~2 ~4 ~2 stone"]
        }
    },
    "claim": "fill 指令体积 ≤ 1000",
    "formula": "V = (x2-x1+1) * (y2-y1+1) * (z2-z1+1)",
    "substitution": {
        "x1": -2, "x2": 2,
        "y1": 0, "y2": 4,
        "z1": -2, "z2": 2
    },
    "proof_steps": [
        "step1: V = (2-(-2)+1) * (4-0+1) * (2-(-2)+1)",
        "step2: V = 5 * 5 * 5",
        "step3: V = 125",
        "step4: 125 ≤ 1000 ✓"
    ],
    "result": 125,
    "limit": 1000,
    "verdict": "PASSED",
    "verification_method": "symbolic",
    "tools_used": ["SymPy"]
}
```

---

### 7.3 示例: 微积分定理证明
```json
{
    "proof_id": "proof-67890",
    "type": "theorem_proof",
    "player_id": "player-5678",
    "timestamp": "2026-01-09T12:34:56Z",
    "context": {
        "surface_id": "SURF-002-ADJUDICATION",
        "function": "evaluate",
        "input": {
            "spec_id": "spec-1234",
            "logic_outline": ["优化能量传输效率"]
        }
    },
    "theorem": "能量效率优化定理",
    "claim": "h = 50 时能量效率最高",
    "proof_steps": [
        "step1: 定义能量函数 E(h) = h * (100 - h) / 100",
        "step2: 求导 dE/dh = (100 - 2h) / 100",
        "step3: 令 dE/dh = 0，得 100 - 2h = 0，h = 50",
        "step4: 二阶导数 d²E/dh² = -2/100 < 0",
        "step5: 二阶导数为负，确认 h = 50 为极大值",
        "step6: 结论: h = 50 时能量效率最高 ✓"
    ],
    "verdict": "VALID",
    "verification_method": "symbolic_differentiation",
    "tools_used": ["SymPy", "Wolfram Alpha"],
    "intermediate_results": {
        "critical_point": 50,
        "second_derivative": -0.02,
        "max_energy": 25
    }
}
```

---

## 8. 总结与建议

### 8.1 关键发现
- 发现 **8 个核心 Contract Surface**，全部可插入数学门控
- 识别 **5 种数学门控类型**: 约束验证、不变量证明、定理证明、序列匹配、概率验证
- 定义 **标准 Proof Payload 格式**，可审计、可重放

### 8.2 优先级建议
1. **P0**: Ideal City Adjudicator（最直接的证明提交入口）
2. **P1**: Patch Executor（可模拟执行 + 验证不变量）
3. **P2**: Command Safety（最早的验证点，易插入）

### 8.3 数学严谨能力训练
通过插入数学门控，玩家可以训练：
- **微积分**: 优化问题（梯度下降、极值计算）
- **线性代数**: 矩阵运算（坐标变换、向量空间）
- **离散数学**: 序列匹配（正则表达式、自动机）
- **概率论**: 概率验证（期望值、方差、假设检验）
- **逻辑学**: 布尔逻辑（集合论、谓词逻辑）

### 8.4 下一步行动
1. 选择 1-2 个高优先级 Surface 实现原型
2. 定义标准 Proof Verification Library
3. 创建数学公式解析器（支持 LaTeX、SymPy）
4. 建立 Proof 审计日志系统
