# MATHIFICATION_PLAN.md
## DriftSystem 数学化方案（Mathification Plan）

> **Research Task**: 定义"知识 = Weapon，关卡 = Monster，Gate = Proof of Use"的统一抽象模型

---

## 1. 统一抽象模型（Unified Abstraction Model）

### 1.1 核心隐喻（Core Metaphors）

```
知识（Knowledge） = 武器（Weapon）
    ↓ 装备后获得能力
关卡（Level） = 怪物（Monster）
    ↓ 需要武器才能击败
门控（Gate） = 使用证明（Proof of Use）
    ↓ 必须证明正确使用武器
奖励（Reward） = 新武器解锁（Unlock New Weapon）
    ↓ 循环强化
```

### 1.2 数学映射关系（Math Mapping）

| Minecraft 概念 | 数学概念 | 验证方式 | 可见行为 |
|----------------|----------|----------|----------|
| **物品（Item）** | 定理/公式 | 证明正确性 | 获得物品 = 学会定理 |
| **合成（Crafting）** | 公式推导 | 证明推导链 | 合成配方 = 推导步骤 |
| **建造（Building）** | 算法应用 | 证明算法正确 | 建筑出现 = 算法成功 |
| **采矿（Mining）** | 迭代计算 | 证明收敛 | 挖到矿物 = 算法收敛 |
| **战斗（Combat）** | 优化问题 | 证明最优解 | 击败怪物 = 找到最优解 |
| **探索（Exploration）** | 搜索算法 | 证明遍历完整 | 发现新区域 = 搜索成功 |
| **交易（Trading）** | 资源守恒 | 证明等价交换 | NPC 交易 = 守恒验证 |
| **附魔（Enchanting）** | 概率计算 | 证明期望值 | 附魔成功 = 概率符合 |

---

## 2. 数学化案例（Mathification Cases）

### 案例 A: 梯度下降 → 梯度挖掘（Gradient Mining）

#### 2.1 玩家可见行为（Player-Visible Behavior）
```
玩家进入"紫水晶矿洞"关卡
    ↓
NPC 桃子: "这个矿洞的能量场不均匀，你需要用梯度探测仪找到能量最高点"
    ↓
玩家获得物品: [梯度探测仪]（Gradient Detector）
    ↓
右键使用探测仪 → 显示当前位置的"能量梯度向量"（粒子箭头）
    ↓
玩家按照梯度方向移动（上坡）
    ↓
每移动 10 步，系统验证: 新位置能量 > 旧位置能量
    ↓
如果违反（走错方向）→ 警告: "能量下降！梯度方向错误"
    ↓
玩家到达"能量极大值点"（梯度 = 0）
    ↓
紫水晶矿石自动生成 → 玩家采集
    ↓
任务完成，获得奖励: [紫水晶] + [优化大师勋章]
```

#### 2.2 数学判定公式（Math Judgment Formula）
**能量函数**:
```
E(x, y, z) = 100 - (x - 50)² - (y - 70)² - (z - 100)²
```

**梯度向量**:
```
∇E = (∂E/∂x, ∂E/∂y, ∂E/∂z)
    = (-2(x - 50), -2(y - 70), -2(z - 100))
```

**收敛条件**:
```
||∇E|| < ε  (ε = 0.1)
```

**验证公式** (每步移动):
```
IF E(new_position) > E(old_position):
    verdict = "CORRECT_DIRECTION"
    粒子效果 = GREEN (绿色向上箭头)
ELSE:
    verdict = "WRONG_DIRECTION"
    粒子效果 = RED (红色向下箭头)
    警告音效 = VILLAGER_NO
```

#### 2.3 计算发生在哪一层（Computation Layer）
- **Layer 1 (Plugin)**: 监听玩家移动事件 (`PlayerMoveEvent`)
- **Layer 2 (Backend API)**: `POST /quest/gradient-check`
- **Layer 3 (Quest Runtime)**: `GradientMiningTask.verify_step(old_pos, new_pos)`
- **Layer 4 (Math Kernel)**: `calculate_gradient(position)`, `evaluate_energy(position)`

**代码位置**:
```python
# backend/app/core/math/gradient_descent.py (新建)
def calculate_gradient(position: Dict[str, float]) -> Dict[str, float]:
    x, y, z = position["x"], position["y"], position["z"]
    return {
        "dx": -2 * (x - 50),
        "dy": -2 * (y - 70),
        "dz": -2 * (z - 100)
    }

def evaluate_energy(position: Dict[str, float]) -> float:
    x, y, z = position["x"], position["y"], position["z"]
    return 100 - (x - 50)**2 - (y - 70)**2 - (z - 100)**2

def verify_gradient_step(old_pos, new_pos) -> bool:
    return evaluate_energy(new_pos) > evaluate_energy(old_pos)
```

#### 2.4 如何记录 Proof（Proof Logging）
**Proof Payload**:
```json
{
    "proof_id": "proof-gradient-12345",
    "type": "gradient_descent_verification",
    "player_id": "player-5678",
    "task_id": "gradient_mining_amethyst",
    "timestamp": "2026-01-09T12:34:56Z",
    "old_position": {"x": 45, "y": 65, "z": 95},
    "new_position": {"x": 47, "y": 67, "z": 98},
    "gradient": {"dx": 10, "dy": 10, "dz": 10},
    "energy_old": 75.0,
    "energy_new": 82.0,
    "delta_energy": 7.0,
    "verdict": "CORRECT_DIRECTION",
    "step_count": 5,
    "remaining_steps": 15
}
```

**日志文件**: `backend/data/proofs/gradient_mining/{player_id}/{task_id}.jsonl`

#### 2.5 如何发放奖励/解锁能力（Reward Granting）
**条件**:
```python
if abs(gradient["dx"]) < 0.1 and abs(gradient["dy"]) < 0.1 and abs(gradient["dz"]) < 0.1:
    # 梯度接近 0，到达极值点
    task_completed = True
```

**奖励指令**:
```
setblock {x} {y} {z} amethyst_block
give @p amethyst_shard 10
title @p title {"text":"梯度收敛！","color":"gold"}
title @p subtitle {"text":"紫水晶生成完成","color":"light_purple"}
playsound minecraft:block.amethyst_block.place master @p ~ ~ ~ 1 1
particle minecraft:end_rod {x} {y} {z} 2 2 2 0.1 100
```

**能力解锁**:
```json
{
    "ability_id": "optimization_master",
    "ability_name": "优化大师",
    "description": "解锁梯度下降能力，可在其他关卡中使用",
    "unlocked_items": ["gradient_detector", "optimization_toolkit"],
    "unlocked_recipes": ["energy_crystal_crafting"],
    "memory_flag": "has_gradient_descent_ability"
}
```

---

### 案例 B: 图论 → 交通网络解锁（Graph Theory → Transport Network）

#### 2.1 玩家可见行为
```
玩家进入"昆明湖交通规划"关卡
    ↓
NPC 规划师: "我们需要建立 5 个村庄之间的最短路径网络"
    ↓
玩家获得物品: [路网规划图]（Network Planner）
    ↓
打开规划图 → 显示 5 个村庄节点 + 可能的道路连接（边）
    ↓
玩家需要选择道路建造顺序，使得:
    1. 所有村庄连通（生成树）
    2. 总道路长度最小（最小生成树）
    ↓
玩家提交方案 → 系统验证 Kruskal 算法
    ↓
IF 正确:
    道路自动生成（石砖路径）
    解锁快速旅行能力
ELSE:
    NPC: "这个方案不是最优的，请重新规划"
    显示反例: "如果选择边 (A, C) 而不是 (A, B)，总长度会更短"
```

#### 2.2 数学判定公式
**图定义**:
```
G = (V, E, w)
V = {A, B, C, D, E}  # 5 个村庄
E = {(A,B), (A,C), (B,C), (B,D), (C,D), (C,E), (D,E)}  # 可能的道路
w: E → ℝ⁺  # 道路长度权重
```

**最小生成树（MST）**:
```
Kruskal 算法:
1. 按权重排序所有边: E_sorted = sort(E, key=w)
2. 初始化森林: F = {{v} | v ∈ V}
3. FOR each edge (u, v) in E_sorted:
      IF find(u) ≠ find(v):  # u 和 v 不在同一棵树
         union(u, v)
         MST.add((u, v))
4. RETURN MST
```

**验证公式**:
```python
def verify_mst(player_solution: List[Tuple], graph: Graph) -> bool:
    # 1. 检查连通性
    if not is_connected(player_solution, graph.vertices):
        return False
    
    # 2. 检查无环
    if has_cycle(player_solution):
        return False
    
    # 3. 检查边数 = 顶点数 - 1
    if len(player_solution) != len(graph.vertices) - 1:
        return False
    
    # 4. 检查总权重最小
    player_weight = sum(graph.weight(e) for e in player_solution)
    optimal_weight = kruskal_mst_weight(graph)
    
    if player_weight == optimal_weight:
        return True
    else:
        # 提供反例
        counterexample = find_counterexample(player_solution, graph)
        return False
```

#### 2.3 计算发生在哪一层
- **Layer 1 (Plugin)**: CityPhone UI 收集玩家选择的边
- **Layer 2 (Backend API)**: `POST /quest/graph-verify`
- **Layer 3 (Math Kernel)**: `GraphAlgorithms.verify_mst()`
- **Layer 4 (Visualization)**: 在 Minecraft 世界中渲染道路

#### 2.4 Proof 记录
```json
{
    "proof_id": "proof-mst-12345",
    "type": "minimum_spanning_tree",
    "player_id": "player-5678",
    "task_id": "kunming_lake_transport",
    "timestamp": "2026-01-09T12:34:56Z",
    "graph": {
        "vertices": ["A", "B", "C", "D", "E"],
        "edges": [
            {"u": "A", "v": "B", "weight": 10},
            {"u": "A", "v": "C", "weight": 15},
            {"u": "B", "v": "C", "weight": 8},
            {"u": "B", "v": "D", "weight": 12},
            {"u": "C", "v": "D", "weight": 20},
            {"u": "C", "v": "E", "weight": 18},
            {"u": "D", "v": "E", "weight": 9}
        ]
    },
    "player_solution": [
        {"u": "B", "v": "C", "weight": 8},
        {"u": "D", "v": "E", "weight": 9},
        {"u": "A", "v": "B", "weight": 10},
        {"u": "B", "v": "D", "weight": 12}
    ],
    "player_total_weight": 39,
    "optimal_solution": [
        {"u": "B", "v": "C", "weight": 8},
        {"u": "D", "v": "E", "weight": 9},
        {"u": "A", "v": "B", "weight": 10},
        {"u": "B", "v": "D", "weight": 12}
    ],
    "optimal_total_weight": 39,
    "verdict": "CORRECT",
    "algorithm_used": "kruskal",
    "steps": [
        "排序边: [(B,C,8), (D,E,9), (A,B,10), (B,D,12), (A,C,15), (C,E,18), (C,D,20)]",
        "选择 (B,C,8): 无环，加入 MST",
        "选择 (D,E,9): 无环，加入 MST",
        "选择 (A,B,10): 无环，加入 MST",
        "选择 (B,D,12): 无环，加入 MST",
        "MST 完成，总权重 = 39"
    ]
}
```

#### 2.5 奖励发放
**道路生成指令**:
```
# 对每条边 (u, v) 生成石砖路径
fill {x_u} {y_u} {z_u} {x_v} {y_v} {z_v} stone_bricks
```

**能力解锁**:
```json
{
    "ability_id": "fast_travel",
    "ability_name": "快速旅行",
    "description": "在已连通的村庄间传送",
    "unlocked_commands": ["/tp @s {village_name}"],
    "memory_flag": "has_fast_travel_ability"
}
```

---

### 案例 C: 概率统计 → 掉落验证系统（Probability → Loot Verification）

#### 2.1 玩家可见行为
```
玩家进入"紫水晶采样实验"关卡
    ↓
NPC 统计学家: "紫水晶矿石的掉落概率应该是 10%，但我们需要验证"
    ↓
玩家获得任务: "破坏 100 个矿石，记录紫水晶掉落次数"
    ↓
玩家开始采矿 → 系统记录每次掉落结果
    ↓
破坏 100 个矿石后，系统计算:
    observed_drops = 12
    expected_drops = 10
    ↓
系统验证假设检验:
    H0: p = 0.1 (掉落概率为 10%)
    H1: p ≠ 0.1 (掉落概率不为 10%)
    ↓
IF p-value > 0.05:
    verdict = "接受 H0，掉落概率符合预期"
    NPC: "很好！数据证实了理论预测"
    奖励: [统计学大师勋章]
ELSE:
    verdict = "拒绝 H0，掉落概率异常"
    NPC: "奇怪，掉落概率似乎不对，需要重新校准"
    任务失败，需要重做
```

#### 2.2 数学判定公式
**假设检验**:
```
H0: p = 0.1 (null hypothesis)
H1: p ≠ 0.1 (alternative hypothesis)

Test Statistic:
z = (p̂ - p0) / sqrt(p0 * (1 - p0) / n)
where:
  p̂ = observed_drops / total_trials  # 样本比例
  p0 = 0.1  # 理论概率
  n = 100   # 样本大小

Critical Region (α = 0.05, two-tailed):
  |z| > 1.96  → Reject H0
  |z| ≤ 1.96  → Accept H0

p-value = 2 * P(Z > |z|)  # 双尾检验
```

**验证公式**:
```python
def verify_drop_probability(observed_drops: int, total_trials: int, expected_prob: float) -> Dict:
    p_hat = observed_drops / total_trials
    p0 = expected_prob
    n = total_trials
    
    # 计算 z-score
    z = (p_hat - p0) / math.sqrt(p0 * (1 - p0) / n)
    
    # 计算 p-value (双尾)
    from scipy.stats import norm
    p_value = 2 * (1 - norm.cdf(abs(z)))
    
    # 判定
    if p_value > 0.05:
        verdict = "ACCEPT_H0"
        message = f"掉落概率符合预期 (p={p_hat:.2%}, p-value={p_value:.4f})"
    else:
        verdict = "REJECT_H0"
        message = f"掉落概率异常 (p={p_hat:.2%}, p-value={p_value:.4f})"
    
    return {
        "verdict": verdict,
        "message": message,
        "z_score": z,
        "p_value": p_value,
        "observed_prob": p_hat,
        "expected_prob": p0
    }
```

#### 2.3 计算发生在哪一层
- **Layer 1 (Plugin)**: `BlockBreakListener` 记录掉落事件
- **Layer 2 (Backend API)**: `POST /quest/loot-verify`
- **Layer 3 (Math Kernel)**: `StatisticsEngine.hypothesis_test()`

#### 2.4 Proof 记录
```json
{
    "proof_id": "proof-loot-12345",
    "type": "probability_hypothesis_test",
    "player_id": "player-5678",
    "task_id": "amethyst_sampling",
    "timestamp": "2026-01-09T12:34:56Z",
    "hypothesis": {
        "H0": "p = 0.1",
        "H1": "p ≠ 0.1",
        "test_type": "two-tailed",
        "significance_level": 0.05
    },
    "data": {
        "total_trials": 100,
        "observed_drops": 12,
        "expected_drops": 10
    },
    "statistics": {
        "p_hat": 0.12,
        "p0": 0.1,
        "z_score": 0.667,
        "p_value": 0.505,
        "critical_value": 1.96
    },
    "verdict": "ACCEPT_H0",
    "conclusion": "掉落概率符合预期 (p=12.00%, p-value=0.5050)",
    "confidence_interval": [0.056, 0.184]
}
```

#### 2.5 奖励发放
**条件**:
```python
if result["verdict"] == "ACCEPT_H0":
    task_completed = True
```

**奖励指令**:
```
give @p diamond 5
title @p title {"text":"假设检验通过！","color":"gold"}
title @p subtitle {"text":"掉落概率符合预期","color":"aqua"}
xp add @p 100 levels
playsound minecraft:ui.toast.challenge_complete master @p ~ ~ ~ 1 1
```

**能力解锁**:
```json
{
    "ability_id": "statistics_master",
    "ability_name": "统计学大师",
    "description": "解锁概率验证能力",
    "unlocked_items": ["probability_calculator"],
    "memory_flag": "has_statistics_ability"
}
```

---

## 3. 数学能力训练矩阵（Math Skills Training Matrix）

| 数学领域 | Minecraft 机制 | 验证方式 | 训练能力 |
|----------|----------------|----------|----------|
| **微积分（Calculus）** | 梯度挖掘 | 证明收敛 | 导数、极值、优化 |
| **线性代数（Linear Algebra）** | 坐标变换 | 证明矩阵正确 | 矩阵乘法、特征值、向量空间 |
| **图论（Graph Theory）** | 交通网络 | 证明最短路径 | 最小生成树、Dijkstra、BFS/DFS |
| **概率论（Probability）** | 掉落验证 | 证明概率分布 | 期望、方差、假设检验 |
| **数理统计（Statistics）** | 采样实验 | 证明置信区间 | 假设检验、回归分析、方差分析 |
| **数论（Number Theory）** | 密码解锁 | 证明质数性 | 质数、同余、RSA 加密 |
| **组合数学（Combinatorics）** | 合成配方 | 证明组合数 | 排列、组合、生成函数 |
| **离散数学（Discrete Math）** | 逻辑门电路 | 证明逻辑等价 | 布尔代数、谓词逻辑、集合论 |

---

## 4. 统一数学内核设计（Unified Math Kernel Design）

### 4.1 MathKernel 架构
```
MathKernel/
├── calculus/
│   ├── differentiation.py       # 导数计算
│   ├── integration.py            # 积分计算
│   ├── optimization.py           # 优化算法 (梯度下降、牛顿法)
│   └── gradient_descent.py       # 梯度下降任务
├── linear_algebra/
│   ├── matrix.py                 # 矩阵运算
│   ├── vector.py                 # 向量运算
│   ├── eigenvalue.py             # 特征值计算
│   └── coordinate_transform.py   # 坐标变换
├── graph_theory/
│   ├── graph.py                  # 图数据结构
│   ├── mst.py                    # 最小生成树 (Kruskal, Prim)
│   ├── shortest_path.py          # 最短路径 (Dijkstra, Floyd)
│   └── network_flow.py           # 网络流
├── probability/
│   ├── distribution.py           # 概率分布
│   ├── sampling.py               # 采样方法
│   ├── hypothesis_test.py        # 假设检验
│   └── loot_verification.py      # 掉落验证
├── statistics/
│   ├── descriptive.py            # 描述统计
│   ├── inference.py              # 统计推断
│   ├── regression.py             # 回归分析
│   └── anova.py                  # 方差分析
├── number_theory/
│   ├── prime.py                  # 质数相关
│   ├── gcd_lcm.py                # 最大公约数、最小公倍数
│   ├── modular_arithmetic.py     # 模运算
│   └── cryptography.py           # 密码学
├── combinatorics/
│   ├── permutation.py            # 排列
│   ├── combination.py            # 组合
│   ├── generating_function.py    # 生成函数
│   └── crafting_recipes.py       # 合成配方验证
└── discrete_math/
    ├── boolean_algebra.py        # 布尔代数
    ├── predicate_logic.py        # 谓词逻辑
    ├── set_theory.py             # 集合论
    └── logic_gates.py            # 逻辑门验证
```

### 4.2 MathKernel API 示例
```python
# backend/app/core/math/math_kernel.py

from typing import Dict, Any
from .calculus import optimization
from .graph_theory import mst
from .probability import hypothesis_test

class MathKernel:
    """统一数学验证内核"""
    
    def verify_gradient_descent(self, trajectory: List[Dict]) -> Dict:
        """验证梯度下降轨迹"""
        return optimization.verify_gradient_trajectory(trajectory)
    
    def verify_minimum_spanning_tree(self, solution: List[Tuple], graph: Graph) -> Dict:
        """验证最小生成树"""
        return mst.verify_mst(solution, graph)
    
    def verify_probability_distribution(self, observed: List, expected_dist: str) -> Dict:
        """验证概率分布"""
        return hypothesis_test.verify_distribution(observed, expected_dist)
    
    def generate_proof(self, proof_type: str, data: Dict) -> Dict:
        """生成数学证明"""
        if proof_type == "gradient_descent":
            return self._generate_gradient_proof(data)
        elif proof_type == "mst":
            return self._generate_mst_proof(data)
        elif proof_type == "hypothesis_test":
            return self._generate_hypothesis_proof(data)
        else:
            raise ValueError(f"Unknown proof type: {proof_type}")
```

---

## 5. 渐进式数学化路线图（Progressive Mathification Roadmap）

### Phase 1: 基础验证（Basic Verification）
**目标**: 插入简单数学验证，无需玩家主动证明

**案例**:
- 体积约束: `fill` 指令体积 ≤ 1000
- 坐标边界: 坐标在世界边界内
- 资源守恒: 合成前后物品数量守恒

**工作量**: 1-2 周

---

### Phase 2: 被动证明记录（Passive Proof Logging）
**目标**: 记录玩家行为轨迹，系统自动生成证明

**案例**:
- 梯度挖掘: 记录移动轨迹，验证是否沿梯度方向
- 路径规划: 记录玩家选择的边，验证是否为最小生成树
- 掉落统计: 记录掉落事件，验证概率分布

**工作量**: 2-4 周

---

### Phase 3: 主动证明提交（Active Proof Submission）
**目标**: 要求玩家提交数学证明作为任务条件

**案例**:
- Ideal City Adjudication: 提交定理证明
- CityPhone 叙述: 提交算法分析
- Quest 完成: 提交概率计算

**工作量**: 4-8 周

---

### Phase 4: 交互式证明助手（Interactive Proof Assistant）
**目标**: 提供工具辅助玩家构造证明

**案例**:
- SymPy 集成: 符号计算验证
- Wolfram Alpha API: 公式求解
- 证明树可视化: 显示推导步骤

**工作量**: 8-12 周

---

## 6. 数学化实现策略（Implementation Strategy）

### 6.1 最小侵入方案（Minimal Intrusion）
**原则**: 在现有验证点插入数学检查，不改变核心逻辑

**步骤**:
1. 选择 1 个高优先级 Surface (推荐: Command Safety)
2. 添加数学验证函数 (例如: `verify_volume_constraint`)
3. 在验证点调用数学函数
4. 记录 Proof Payload 到 Transaction Log
5. 测试 + 迭代

**示例代码**:
```python
# backend/app/core/world/command_safety.py

def analyze_commands_with_math(commands: Iterable[str]) -> CommandSafetyReport:
    report = analyze_commands(commands)  # 原有逻辑
    
    # 插入数学验证
    for cmd in commands:
        if cmd.startswith("fill"):
            volume = calculate_fill_volume(cmd)
            if volume > MAX_VOLUME:
                report.errors.append(f"Volume constraint violated: {volume} > {MAX_VOLUME}")
                report.math_proof = {
                    "type": "volume_constraint",
                    "constraint": "volume <= MAX_VOLUME",
                    "actual": volume,
                    "limit": MAX_VOLUME,
                    "verdict": "FAILED"
                }
    
    return report
```

---

### 6.2 MathKernel 集成方案（MathKernel Integration）
**原则**: 建立统一数学验证内核，所有验证调用 MathKernel

**步骤**:
1. 创建 `backend/app/core/math/` 目录
2. 实现 `MathKernel` 类
3. 在各个 Surface 调用 `MathKernel.verify_*()`
4. 统一 Proof 格式
5. 建立 Proof 审计系统

**示例代码**:
```python
# backend/app/core/world/patch_executor.py

from app.core.math.math_kernel import MathKernel

class PatchExecutor:
    def __init__(self):
        self.math_kernel = MathKernel()
    
    def dry_run_with_math(self, plan: CreationPlan) -> PatchExecutionResult:
        result = self.dry_run(plan)  # 原有逻辑
        
        # 数学验证
        for template in result.executed:
            math_result = self.math_kernel.verify_patch_invariants(template)
            
            if not math_result["verdict"] == "PASSED":
                result.executed.remove(template)
                result.skipped.append({
                    "template_id": template.id,
                    "reason": "math_verification_failed",
                    "proof": math_result["proof"]
                })
        
        return result
```

---

### 6.3 事件溯源 Proof 系统（Event Sourcing Proof System）
**原则**: 所有世界变更都有可溯源的数学证明

**步骤**:
1. 扩展 Transaction Log 支持 Proof Payload
2. 实现 Proof 回放功能
3. 建立 Proof 验证器（可重新验证历史证明）
4. 可视化 Proof 链（显示因果关系）

**示例代码**:
```python
# backend/app/core/world/proof_log.py

class ProofLog:
    """事件溯源证明日志"""
    
    def record_proof(self, proof: Dict):
        """记录证明"""
        self.append({
            "proof_id": proof["proof_id"],
            "type": proof["type"],
            "timestamp": proof["timestamp"],
            "payload": proof,
            "signature": self.sign(proof)  # 签名防篡改
        })
    
    def replay_proofs(self, from_time: str, to_time: str):
        """回放证明"""
        proofs = self.get_proofs_in_range(from_time, to_time)
        
        for proof in proofs:
            # 重新验证证明
            if not self.verify_proof(proof):
                raise ProofVerificationError(f"Proof {proof['proof_id']} failed replay")
        
        return proofs
    
    def visualize_proof_chain(self, proof_id: str):
        """可视化证明链"""
        chain = self.get_causal_chain(proof_id)
        
        # 生成 Mermaid 图
        mermaid = "graph TD\n"
        for i, proof in enumerate(chain):
            mermaid += f"  P{i}[{proof['type']}]\n"
            if i > 0:
                mermaid += f"  P{i-1} --> P{i}\n"
        
        return mermaid
```

---

## 7. 评估指标（Evaluation Metrics）

### 7.1 数学严谨能力提升指标
| 指标 | 定义 | 目标值 |
|------|------|--------|
| **Proof Submission Rate** | 玩家提交证明的比例 | ≥ 80% |
| **Proof Validity Rate** | 证明验证通过的比例 | ≥ 70% |
| **Math Concept Coverage** | 覆盖的数学概念数 | ≥ 20 个 |
| **Average Proof Length** | 证明步骤的平均长度 | 5-10 步 |
| **Proof Revision Count** | 玩家修改证明的次数 | 1-3 次 |

### 7.2 玩家体验指标
| 指标 | 定义 | 目标值 |
|------|------|--------|
| **Task Completion Time** | 完成任务的平均时间 | 10-30 分钟 |
| **Frustration Score** | 玩家挫败感评分 (1-5) | ≤ 2.5 |
| **Learning Effectiveness** | 学习效果自评 (1-5) | ≥ 4.0 |
| **Replay Rate** | 玩家重玩关卡的比例 | ≥ 40% |

---

## 8. 总结与建议

### 8.1 核心发现
- **3 个具体数学映射案例**: 梯度下降 → 梯度挖掘，图论 → 交通网络，概率统计 → 掉落验证
- **8 个数学领域可训练**: 微积分、线性代数、图论、概率论、统计学、数论、组合数学、离散数学
- **4 个渐进式阶段**: 基础验证 → 被动证明 → 主动证明 → 交互式证明助手

### 8.2 实施建议
1. **优先实现案例 A（梯度挖掘）**: 最直观，玩家可见性高
2. **建立 MathKernel**: 统一验证接口，便于扩展
3. **设计 Proof UI**: 在 CityPhone 中添加"证明提交"面板
4. **集成 SymPy**: 提供符号计算验证

### 8.3 风险与挑战
- **学习曲线**: 玩家可能不熟悉数学概念，需要引导
- **验证成本**: 数学验证可能增加计算开销，需要优化
- **UI 复杂度**: 证明提交 UI 需要设计良好，避免过于复杂

### 8.4 成功标准
> **核心问题**: "如果在系统里教授微积分，那么导数到底存在于哪一层？"

**答案**:
- **定义层**: Level JSON 中的 `math_gate` 字段定义导数公式
- **验证层**: `MathKernel.calculus.differentiation.py` 计算导数
- **执行层**: `GradientMiningTask.verify_step()` 验证玩家是否沿导数方向移动
- **可见层**: Minecraft 粒子箭头显示导数向量
- **审计层**: Transaction Log 记录每步的导数计算证明

导数不是抽象的后端计算，而是：
1. **玩家可见**: 粒子箭头显示梯度方向
2. **玩家可操作**: 沿箭头移动即是应用导数
3. **可验证**: 每步移动验证 E(new) > E(old)
4. **可审计**: Proof Log 记录完整轨迹
5. **可奖励**: 收敛到极值点获得紫水晶

这就是"数学知识嵌入为 Minecraft 世界中可验证的机制"的完整实现。
