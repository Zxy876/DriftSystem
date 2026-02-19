# REFACTOR_OPTIONS.md
## DriftSystem 数学化改造路径（Refactoring Options for Mathification）

> **Research Task**: 提出 3 套改造路径（从最保守到最彻底）

---

## 改造路径总览

| 方案 | 侵入程度 | 工作量 | 风险等级 | 数学严谨能力训练点 |
|------|---------|--------|----------|-------------------|
| **方案 1: 最小侵入** | 低 | 2-4 周 | 低 | 基础约束验证（3-5 个） |
| **方案 2: MathKernel 集成** | 中 | 6-8 周 | 中 | 全面数学验证（10-15 个） |
| **方案 3: 事件溯源 Proof 系统** | 高 | 12-16 周 | 高 | 完整证明生态（20+ 个） |

---

## 方案 1: 最小侵入（Minimal Intrusion）

### 1.1 核心理念
**在现有验证前插入 GateLayer，不改变核心逻辑**

```
原有流程:
  Input → Validation → Execution → Output

改造后:
  Input → MathGate (新增) → Validation → Execution → Output
```

### 1.2 改造范围

#### 影响的文件（10 个文件）
```
backend/app/core/world/command_safety.py         # 添加体积/坐标约束
backend/app/core/creation/validation.py          # 添加结构完整性检查
backend/app/core/world/patch_executor.py         # 添加不变量验证
backend/app/core/ideal_city/pipeline.py          # 添加公式验证
backend/app/core/quest/runtime.py                # 添加序列匹配
backend/app/core/world/patch_transaction.py      # 扩展日志支持 proof 字段
backend/app/api/intent_api.py                    # 添加 proof 返回字段
backend/app/api/ideal_city_api.py                # 添加 proof 返回字段
backend/app/api/quest_api.py                     # 添加 proof 返回字段
backend/requirements.txt                         # 添加 sympy 依赖
```

#### 新增的抽象（3 个类）
```python
# backend/app/core/math/gate_layer.py (新建)
class MathGate:
    """数学门控基类"""
    def check(self, input_data: Dict) -> GateResult:
        pass

class VolumeConstraintGate(MathGate):
    """体积约束门控"""
    def check(self, commands: List[str]) -> GateResult:
        # 验证 fill 指令体积 ≤ MAX_VOLUME
        pass

class CoordinateBoundsGate(MathGate):
    """坐标边界门控"""
    def check(self, coordinates: Dict) -> GateResult:
        # 验证坐标在世界边界内
        pass
```

---

### 1.3 具体改造步骤（10 步）

#### Step 1: 添加数学门控基类
**文件**: `backend/app/core/math/gate_layer.py` (新建)

```python
from typing import Dict, List
from dataclasses import dataclass

@dataclass
class GateResult:
    """门控验证结果"""
    passed: bool
    verdict: str  # "PASSED" | "FAILED"
    proof: Dict   # 证明数据
    message: str  # 说明信息

class MathGate:
    """数学门控基类"""
    
    def check(self, input_data: Dict) -> GateResult:
        """验证输入数据"""
        raise NotImplementedError
    
    def generate_proof(self, input_data: Dict) -> Dict:
        """生成证明"""
        raise NotImplementedError
```

#### Step 2: 实现体积约束门控
**文件**: `backend/app/core/math/gate_layer.py`

```python
import re

class VolumeConstraintGate(MathGate):
    """体积约束门控"""
    
    MAX_VOLUME = 1000
    
    def check(self, commands: List[str]) -> GateResult:
        for cmd in commands:
            if cmd.startswith("fill"):
                volume = self._calculate_volume(cmd)
                
                if volume > self.MAX_VOLUME:
                    return GateResult(
                        passed=False,
                        verdict="FAILED",
                        proof=self.generate_proof({"command": cmd, "volume": volume}),
                        message=f"Volume constraint violated: {volume} > {self.MAX_VOLUME}"
                    )
        
        return GateResult(
            passed=True,
            verdict="PASSED",
            proof={},
            message="All commands pass volume constraint"
        )
    
    def _calculate_volume(self, cmd: str) -> int:
        """计算 fill 指令的体积"""
        # 示例: fill ~-2 ~ ~-2 ~2 ~4 ~2 stone
        # 提取坐标
        pattern = r"fill\s+(~?-?\d+)\s+(~?-?\d+)\s+(~?-?\d+)\s+(~?-?\d+)\s+(~?-?\d+)\s+(~?-?\d+)"
        match = re.search(pattern, cmd)
        
        if match:
            x1, y1, z1, x2, y2, z2 = map(int, [g.replace("~", "0") for g in match.groups()])
            volume = abs(x2 - x1 + 1) * abs(y2 - y1 + 1) * abs(z2 - z1 + 1)
            return volume
        
        return 0
    
    def generate_proof(self, data: Dict) -> Dict:
        """生成证明"""
        return {
            "type": "volume_constraint",
            "constraint": f"volume <= {self.MAX_VOLUME}",
            "formula": "V = (x2-x1+1) * (y2-y1+1) * (z2-z1+1)",
            "actual": data["volume"],
            "limit": self.MAX_VOLUME,
            "verdict": "FAILED"
        }
```

#### Step 3: 在 CommandSafety 中插入门控
**文件**: `backend/app/core/world/command_safety.py`

```python
# 在文件开头添加导入
from app.core.math.gate_layer import VolumeConstraintGate

def analyze_commands(commands: Iterable[str]) -> CommandSafetyReport:
    """分析指令安全性（添加数学门控）"""
    errors = []
    warnings = []
    
    # 原有逻辑
    for cmd in commands:
        if any(token in cmd for token in BLACKLIST_TOKENS):
            errors.append(f"Blacklist token found: {token}")
        
        if any(cmd.startswith(bc) for bc in BLACKLIST_COMMANDS):
            errors.append(f"Blacklist command: {cmd}")
    
    # 插入数学门控（新增）
    volume_gate = VolumeConstraintGate()
    gate_result = volume_gate.check(commands)
    
    if not gate_result.passed:
        errors.append(gate_result.message)
    
    # 返回结果（扩展支持 proof 字段）
    report = CommandSafetyReport(errors=errors, warnings=warnings)
    
    if not gate_result.passed:
        report.math_proof = gate_result.proof  # 新增字段
    
    return report
```

#### Step 4-10: 类似步骤应用到其他 Surface
- Step 4: 在 `validation.py` 中添加 `StructureCompleteGate`
- Step 5: 在 `patch_executor.py` 中添加 `InvariantGate`
- Step 6: 在 `pipeline.py` 中添加 `FormulaValidationGate`
- Step 7: 在 `runtime.py` 中添加 `SequenceMatchGate`
- Step 8: 扩展 `patch_transaction.py` 支持 `proof` 字段
- Step 9: 更新 API 返回 `proof` 字段
- Step 10: 添加测试用例

---

### 1.4 风险评估

#### 技术风险
| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| **性能下降** | 中 | 低 | 门控计算简单，影响 <10ms |
| **兼容性问题** | 低 | 低 | 门控失败不影响原有流程 |
| **测试覆盖不足** | 中 | 中 | 为每个门控添加单元测试 |

#### 业务风险
| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| **玩家不理解** | 高 | 中 | 提供清晰的错误信息 |
| **误报率高** | 中 | 中 | 调整阈值，允许误差范围 |

---

### 1.5 回滚方式

#### 回滚策略
```python
# 添加特性开关（Feature Flag）
ENABLE_MATH_GATES = os.getenv("ENABLE_MATH_GATES", "false").lower() == "true"

def analyze_commands(commands: Iterable[str]) -> CommandSafetyReport:
    errors = []
    warnings = []
    
    # 原有逻辑
    # ...
    
    # 数学门控（可开关）
    if ENABLE_MATH_GATES:
        volume_gate = VolumeConstraintGate()
        gate_result = volume_gate.check(commands)
        
        if not gate_result.passed:
            errors.append(gate_result.message)
    
    return CommandSafetyReport(errors=errors, warnings=warnings)
```

#### 回滚步骤
1. 设置环境变量 `ENABLE_MATH_GATES=false`
2. 重启后端服务
3. 验证原有功能正常
4. （可选）移除新增代码

---

### 1.6 能训练的数学严谨能力点（5 个）

| 能力点 | 描述 | 训练方式 |
|--------|------|----------|
| **1. 体积计算** | 计算三维空间体积 | 玩家输入 fill 指令，系统验证体积公式 |
| **2. 坐标约束** | 理解坐标系统与边界 | 玩家移动时验证坐标在合法范围内 |
| **3. 资源守恒** | 理解守恒定律 | 合成物品时验证输入 = 输出 |
| **4. 不变量证明** | 理解不变量概念 | 世界变更时验证不变量保持 |
| **5. 公式推导** | 简单公式推导 | 玩家提交推导步骤，系统验证正确性 |

---

### 1.7 总结

**优点**:
- ✅ 侵入性最小，风险可控
- ✅ 可快速实现（2-4 周）
- ✅ 可逐步回滚
- ✅ 不影响现有功能

**缺点**:
- ❌ 数学能力训练有限（仅 5 个能力点）
- ❌ 无法记录完整证明链
- ❌ 门控之间相互独立，无协同

**适用场景**:
- 快速验证数学化可行性
- 团队对数学化不确定，需要小规模试点
- 预算/时间有限

---

## 方案 2: MathKernel 集成（MathKernel Integration）

### 2.1 核心理念
**建立统一数学验证内核，所有验证调用 MathKernel**

```
原有流程:
  Input → Validation → Execution → Output

改造后:
  Input → Validation → MathKernel.verify() → Execution → Output
                            ↓
                    Proof Generation & Storage
```

### 2.2 改造范围

#### 影响的文件（25 个文件）
```
# 新增 MathKernel 模块 (15 个文件)
backend/app/core/math/__init__.py
backend/app/core/math/math_kernel.py             # 核心内核
backend/app/core/math/calculus/differentiation.py
backend/app/core/math/calculus/optimization.py
backend/app/core/math/calculus/gradient_descent.py
backend/app/core/math/linear_algebra/matrix.py
backend/app/core/math/graph_theory/graph.py
backend/app/core/math/graph_theory/mst.py
backend/app/core/math/graph_theory/shortest_path.py
backend/app/core/math/probability/distribution.py
backend/app/core/math/probability/hypothesis_test.py
backend/app/core/math/statistics/descriptive.py
backend/app/core/math/combinatorics/permutation.py
backend/app/core/math/discrete_math/boolean_algebra.py
backend/app/core/math/proof_generator.py         # 证明生成器

# 修改现有文件 (10 个文件)
backend/app/core/world/command_safety.py
backend/app/core/creation/validation.py
backend/app/core/world/patch_executor.py
backend/app/core/ideal_city/pipeline.py
backend/app/core/quest/runtime.py
backend/app/core/world/patch_transaction.py
backend/app/api/intent_api.py
backend/app/api/ideal_city_api.py
backend/app/api/quest_api.py
backend/app/main.py                               # 注册 MathKernel
```

#### 新增的抽象（10 个类）
```python
# MathKernel 核心
class MathKernel:
    """统一数学验证内核"""
    
class ProofGenerator:
    """证明生成器"""
    
class ProofValidator:
    """证明验证器"""

# 各数学领域模块
class CalculusModule:
    """微积分模块"""
    
class LinearAlgebraModule:
    """线性代数模块"""
    
class GraphTheoryModule:
    """图论模块"""
    
class ProbabilityModule:
    """概率论模块"""
    
class StatisticsModule:
    """统计学模块"""
    
class CombinatoricsModule:
    """组合数学模块"""
    
class DiscreteMathModule:
    """离散数学模块"""
```

---

### 2.3 具体改造步骤（20 步）

#### Step 1-5: 建立 MathKernel 架构
**Step 1**: 创建 `backend/app/core/math/__init__.py`
```python
from .math_kernel import MathKernel

__all__ = ["MathKernel"]
```

**Step 2**: 实现 `MathKernel` 核心类
```python
# backend/app/core/math/math_kernel.py

from typing import Dict, Any, List
from .calculus.optimization import GradientDescent
from .graph_theory.mst import MinimumSpanningTree
from .probability.hypothesis_test import HypothesisTest
from .proof_generator import ProofGenerator

class MathKernel:
    """统一数学验证内核"""
    
    def __init__(self):
        self.calculus = CalculusModule()
        self.linear_algebra = LinearAlgebraModule()
        self.graph_theory = GraphTheoryModule()
        self.probability = ProbabilityModule()
        self.statistics = StatisticsModule()
        self.combinatorics = CombinatoricsModule()
        self.discrete_math = DiscreteMathModule()
        self.proof_generator = ProofGenerator()
    
    def verify(self, proof_type: str, data: Dict) -> Dict:
        """统一验证接口"""
        if proof_type == "gradient_descent":
            return self.calculus.verify_gradient_descent(data)
        elif proof_type == "minimum_spanning_tree":
            return self.graph_theory.verify_mst(data)
        elif proof_type == "hypothesis_test":
            return self.probability.verify_hypothesis_test(data)
        else:
            raise ValueError(f"Unknown proof type: {proof_type}")
    
    def generate_proof(self, proof_type: str, data: Dict) -> Dict:
        """生成证明"""
        return self.proof_generator.generate(proof_type, data)
```

**Step 3**: 实现微积分模块
```python
# backend/app/core/math/calculus/optimization.py

import math
from typing import Dict, List, Callable

class GradientDescent:
    """梯度下降算法"""
    
    def __init__(self, energy_function: Callable, gradient_function: Callable):
        self.energy_function = energy_function
        self.gradient_function = gradient_function
    
    def verify_step(self, old_pos: Dict, new_pos: Dict) -> Dict:
        """验证单步移动是否沿梯度方向"""
        energy_old = self.energy_function(old_pos)
        energy_new = self.energy_function(new_pos)
        gradient = self.gradient_function(old_pos)
        
        # 验证能量上升（梯度上升）
        if energy_new > energy_old:
            verdict = "CORRECT_DIRECTION"
        else:
            verdict = "WRONG_DIRECTION"
        
        return {
            "verdict": verdict,
            "energy_old": energy_old,
            "energy_new": energy_new,
            "delta_energy": energy_new - energy_old,
            "gradient": gradient,
            "gradient_magnitude": self._magnitude(gradient)
        }
    
    def check_convergence(self, gradient: Dict, epsilon: float = 0.1) -> bool:
        """检查是否收敛"""
        magnitude = self._magnitude(gradient)
        return magnitude < epsilon
    
    def _magnitude(self, vector: Dict) -> float:
        """计算向量模长"""
        return math.sqrt(sum(v**2 for v in vector.values()))

class CalculusModule:
    """微积分模块"""
    
    def verify_gradient_descent(self, data: Dict) -> Dict:
        """验证梯度下降"""
        # 定义能量函数
        def energy(pos):
            x, y, z = pos["x"], pos["y"], pos["z"]
            return 100 - (x - 50)**2 - (y - 70)**2 - (z - 100)**2
        
        # 定义梯度函数
        def gradient(pos):
            x, y, z = pos["x"], pos["y"], pos["z"]
            return {
                "dx": -2 * (x - 50),
                "dy": -2 * (y - 70),
                "dz": -2 * (z - 100)
            }
        
        gd = GradientDescent(energy, gradient)
        return gd.verify_step(data["old_position"], data["new_position"])
```

**Step 4**: 实现图论模块
```python
# backend/app/core/math/graph_theory/mst.py

from typing import List, Tuple, Dict
import heapq

class Graph:
    """图数据结构"""
    
    def __init__(self, vertices: List[str], edges: List[Dict]):
        self.vertices = vertices
        self.edges = edges
        self.adj_list = self._build_adj_list()
    
    def _build_adj_list(self) -> Dict:
        adj = {v: [] for v in self.vertices}
        for edge in self.edges:
            u, v, w = edge["u"], edge["v"], edge["weight"]
            adj[u].append((v, w))
            adj[v].append((u, w))
        return adj

class MinimumSpanningTree:
    """最小生成树算法"""
    
    def kruskal(self, graph: Graph) -> List[Dict]:
        """Kruskal 算法"""
        # 并查集
        parent = {v: v for v in graph.vertices}
        
        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]
        
        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py
                return True
            return False
        
        # 按权重排序
        sorted_edges = sorted(graph.edges, key=lambda e: e["weight"])
        
        mst = []
        for edge in sorted_edges:
            u, v = edge["u"], edge["v"]
            if union(u, v):
                mst.append(edge)
        
        return mst
    
    def verify_mst(self, solution: List[Dict], graph: Graph) -> Dict:
        """验证是否为最小生成树"""
        optimal_mst = self.kruskal(graph)
        
        solution_weight = sum(e["weight"] for e in solution)
        optimal_weight = sum(e["weight"] for e in optimal_mst)
        
        if solution_weight == optimal_weight:
            verdict = "CORRECT"
        else:
            verdict = "INCORRECT"
        
        return {
            "verdict": verdict,
            "solution_weight": solution_weight,
            "optimal_weight": optimal_weight,
            "solution": solution,
            "optimal_solution": optimal_mst
        }

class GraphTheoryModule:
    """图论模块"""
    
    def verify_mst(self, data: Dict) -> Dict:
        """验证最小生成树"""
        graph = Graph(data["vertices"], data["edges"])
        mst = MinimumSpanningTree()
        return mst.verify_mst(data["solution"], graph)
```

**Step 5**: 实现证明生成器
```python
# backend/app/core/math/proof_generator.py

from typing import Dict
import uuid
from datetime import datetime

class ProofGenerator:
    """证明生成器"""
    
    def generate(self, proof_type: str, data: Dict) -> Dict:
        """生成证明"""
        proof_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        if proof_type == "gradient_descent":
            return self._generate_gradient_proof(proof_id, timestamp, data)
        elif proof_type == "minimum_spanning_tree":
            return self._generate_mst_proof(proof_id, timestamp, data)
        else:
            raise ValueError(f"Unknown proof type: {proof_type}")
    
    def _generate_gradient_proof(self, proof_id: str, timestamp: str, data: Dict) -> Dict:
        """生成梯度下降证明"""
        return {
            "proof_id": proof_id,
            "type": "gradient_descent_verification",
            "timestamp": timestamp,
            "old_position": data["old_position"],
            "new_position": data["new_position"],
            "energy_old": data["energy_old"],
            "energy_new": data["energy_new"],
            "delta_energy": data["delta_energy"],
            "gradient": data["gradient"],
            "verdict": data["verdict"]
        }
    
    def _generate_mst_proof(self, proof_id: str, timestamp: str, data: Dict) -> Dict:
        """生成最小生成树证明"""
        return {
            "proof_id": proof_id,
            "type": "minimum_spanning_tree",
            "timestamp": timestamp,
            "graph": data["graph"],
            "solution": data["solution"],
            "solution_weight": data["solution_weight"],
            "optimal_weight": data["optimal_weight"],
            "verdict": data["verdict"]
        }
```

#### Step 6-20: 集成 MathKernel 到各个 Surface
- Step 6-10: 修改 5 个核心 Surface 调用 MathKernel
- Step 11-15: 扩展 API 返回 proof 字段
- Step 16-18: 添加 Proof 存储与查询 API
- Step 19: 添加单元测试
- Step 20: 添加集成测试

---

### 2.4 风险评估

#### 技术风险
| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| **架构复杂度上升** | 高 | 中 | 清晰的模块划分 + 文档 |
| **性能下降** | 中 | 中 | 缓存常用计算结果 |
| **依赖库问题** | 低 | 高 | 使用稳定版本（SymPy 1.12） |
| **数学错误** | 中 | 高 | 充分的单元测试 |

#### 业务风险
| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| **学习曲线陡峭** | 高 | 高 | 提供教程 + 示例关卡 |
| **玩家抵触** | 中 | 中 | 可选模式（休闲/挑战） |
| **验证过严** | 中 | 中 | 调整容差参数 |

---

### 2.5 回滚方式

#### 回滚策略
```python
# 使用适配器模式（Adapter Pattern）
class MathKernelAdapter:
    """MathKernel 适配器"""
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        if enabled:
            self.kernel = MathKernel()
        else:
            self.kernel = None
    
    def verify(self, proof_type: str, data: Dict) -> Dict:
        if self.enabled and self.kernel:
            return self.kernel.verify(proof_type, data)
        else:
            # 回退到默认通过
            return {"verdict": "PASSED", "message": "MathKernel disabled"}

# 在 main.py 中配置
MATH_KERNEL_ENABLED = os.getenv("MATH_KERNEL_ENABLED", "true").lower() == "true"
math_kernel = MathKernelAdapter(enabled=MATH_KERNEL_ENABLED)
```

#### 回滚步骤
1. 设置环境变量 `MATH_KERNEL_ENABLED=false`
2. 重启后端服务
3. 验证原有功能正常
4. 如需彻底移除，删除 `app/core/math/` 目录

---

### 2.6 能训练的数学严谨能力点（15 个）

| 领域 | 能力点 | 描述 |
|------|--------|------|
| **微积分** | 1. 导数计算 | 计算函数导数 |
| | 2. 梯度下降 | 使用梯度找极值 |
| | 3. 收敛判定 | 判断是否收敛 |
| **线性代数** | 4. 矩阵乘法 | 计算矩阵乘积 |
| | 5. 向量运算 | 向量加减、点积 |
| **图论** | 6. 最小生成树 | Kruskal/Prim 算法 |
| | 7. 最短路径 | Dijkstra 算法 |
| | 8. 连通性检查 | 图的连通性 |
| **概率论** | 9. 概率计算 | 计算事件概率 |
| | 10. 期望值 | 计算期望 |
| **统计学** | 11. 假设检验 | 执行 t-test |
| | 12. 置信区间 | 计算置信区间 |
| **组合数学** | 13. 排列组合 | 计算 P(n,r) 和 C(n,r) |
| **离散数学** | 14. 布尔逻辑 | 逻辑公式求值 |
| | 15. 集合运算 | 并集、交集、补集 |

---

### 2.7 总结

**优点**:
- ✅ 数学能力训练全面（15 个能力点）
- ✅ 统一验证接口，易于扩展
- ✅ 可生成完整证明
- ✅ 模块化设计，易于维护

**缺点**:
- ❌ 工作量较大（6-8 周）
- ❌ 架构复杂度上升
- ❌ 需要数学专业知识

**适用场景**:
- 团队已验证数学化可行，准备全面推广
- 有足够的开发资源
- 希望建立长期可扩展的数学验证系统

---

## 方案 3: 事件溯源 Proof 系统（Event Sourcing Proof System）

### 3.1 核心理念
**WorldPatch + ProofLog 可回放，建立完整证明生态**

```
原有流程:
  Event → State Mutation → Persist State

改造后:
  Event → Proof Generation → ProofLog (append-only)
                    ↓
            WorldPatch + ProofPayload
                    ↓
            State Mutation (可回放)
```

### 3.2 改造范围

#### 影响的文件（40+ 个文件）
```
# 新增 ProofLog 系统 (20 个文件)
backend/app/core/proof/__init__.py
backend/app/core/proof/proof_log.py               # 证明日志
backend/app/core/proof/proof_validator.py         # 证明验证器
backend/app/core/proof/proof_replayer.py          # 证明回放器
backend/app/core/proof/proof_visualizer.py        # 证明可视化
backend/app/core/proof/proof_chain.py             # 证明链
backend/app/core/proof/event_sourcing.py          # 事件溯源
backend/app/core/proof/world_snapshot.py          # 世界快照
backend/app/core/proof/state_reconstructor.py    # 状态重建器
backend/app/api/proof_api.py                      # Proof API
backend/app/schemas/proof_schema.py               # Proof Schema
... (更多)

# 重构现有系统 (20+ 个文件)
backend/app/core/world/patch_executor.py          # 重构为事件溯源
backend/app/core/world/patch_transaction.py       # 扩展为 ProofLog
backend/app/core/ideal_city/pipeline.py           # 集成 ProofLog
backend/app/core/quest/runtime.py                 # 集成 ProofLog
... (更多)
```

#### 新增的抽象（15 个类）
```python
# ProofLog 核心
class ProofLog:
    """证明日志（Append-Only）"""
    
class ProofValidator:
    """证明验证器"""
    
class ProofReplayer:
    """证明回放器"""
    
class ProofVisualizer:
    """证明可视化"""
    
class ProofChain:
    """证明链（因果关系图）"""

# 事件溯源
class EventSourcing:
    """事件溯源系统"""
    
class WorldSnapshot:
    """世界快照"""
    
class StateReconstructor:
    """状态重建器"""

# WorldPatch 重构
class WorldPatchV2:
    """WorldPatch 2.0（带 Proof）"""
    
class PatchValidator:
    """Patch 验证器"""

# 其他
class ProofChainAnalyzer:
    """证明链分析器"""
    
class CausalGraphBuilder:
    """因果图构建器"""
    
class TimelineVisualizer:
    """时间线可视化"""
    
class ProofAuditor:
    """证明审计器"""
    
class IntegrityChecker:
    """完整性检查器"""
```

---

### 3.3 具体改造步骤（30+ 步）

#### Step 1-10: 建立 ProofLog 系统

**Step 1**: 实现 ProofLog 核心类
```python
# backend/app/core/proof/proof_log.py

import json
from typing import Dict, List
from pathlib import Path
from datetime import datetime
import hashlib

class ProofLog:
    """证明日志（Append-Only）"""
    
    def __init__(self, log_dir: str = "backend/data/proofs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def append(self, proof: Dict):
        """追加证明到日志"""
        # 生成证明签名（防篡改）
        proof["signature"] = self._sign(proof)
        proof["timestamp"] = datetime.now().isoformat()
        
        # 写入日志文件（按日期分片）
        log_file = self.log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        
        with log_file.open("a") as f:
            f.write(json.dumps(proof) + "\n")
    
    def get_proofs(self, from_time: str = None, to_time: str = None) -> List[Dict]:
        """获取证明列表"""
        proofs = []
        
        for log_file in sorted(self.log_dir.glob("*.jsonl")):
            with log_file.open("r") as f:
                for line in f:
                    proof = json.loads(line)
                    
                    if from_time and proof["timestamp"] < from_time:
                        continue
                    if to_time and proof["timestamp"] > to_time:
                        continue
                    
                    proofs.append(proof)
        
        return proofs
    
    def verify_integrity(self) -> bool:
        """验证日志完整性"""
        for log_file in self.log_dir.glob("*.jsonl"):
            with log_file.open("r") as f:
                for line in f:
                    proof = json.loads(line)
                    
                    # 验证签名
                    signature = proof.pop("signature")
                    expected_signature = self._sign(proof)
                    
                    if signature != expected_signature:
                        return False
        
        return True
    
    def _sign(self, proof: Dict) -> str:
        """生成证明签名"""
        proof_str = json.dumps(proof, sort_keys=True)
        return hashlib.sha256(proof_str.encode()).hexdigest()
```

**Step 2**: 实现 ProofReplayer
```python
# backend/app/core/proof/proof_replayer.py

from typing import List, Dict
from .proof_log import ProofLog
from app.core.world.world_snapshot import WorldSnapshot

class ProofReplayer:
    """证明回放器"""
    
    def __init__(self, proof_log: ProofLog):
        self.proof_log = proof_log
    
    def replay(self, from_time: str, to_time: str) -> WorldSnapshot:
        """回放证明，重建世界状态"""
        proofs = self.proof_log.get_proofs(from_time, to_time)
        
        # 初始化世界快照
        snapshot = WorldSnapshot()
        
        for proof in proofs:
            # 根据证明类型回放
            if proof["type"] == "world_patch":
                self._replay_world_patch(snapshot, proof)
            elif proof["type"] == "quest_event":
                self._replay_quest_event(snapshot, proof)
            # ... 更多类型
        
        return snapshot
    
    def _replay_world_patch(self, snapshot: WorldSnapshot, proof: Dict):
        """回放世界补丁"""
        for command in proof["commands"]:
            snapshot.apply_command(command)
    
    def _replay_quest_event(self, snapshot: WorldSnapshot, proof: Dict):
        """回放任务事件"""
        snapshot.record_quest_event(proof["event"])
```

**Step 3**: 实现 ProofChain
```python
# backend/app/core/proof/proof_chain.py

from typing import List, Dict
import networkx as nx

class ProofChain:
    """证明链（因果关系图）"""
    
    def __init__(self):
        self.graph = nx.DiGraph()
    
    def add_proof(self, proof: Dict):
        """添加证明到链"""
        proof_id = proof["proof_id"]
        self.graph.add_node(proof_id, **proof)
        
        # 添加因果关系边
        if "depends_on" in proof:
            for parent_id in proof["depends_on"]:
                self.graph.add_edge(parent_id, proof_id)
    
    def get_causal_chain(self, proof_id: str) -> List[Dict]:
        """获取因果链"""
        # 查找所有前驱节点
        ancestors = nx.ancestors(self.graph, proof_id)
        
        # 拓扑排序
        subgraph = self.graph.subgraph(ancestors | {proof_id})
        sorted_nodes = list(nx.topological_sort(subgraph))
        
        return [self.graph.nodes[node] for node in sorted_nodes]
    
    def visualize(self, proof_id: str = None) -> str:
        """生成 Mermaid 可视化"""
        if proof_id:
            nodes = self.get_causal_chain(proof_id)
        else:
            nodes = list(self.graph.nodes(data=True))
        
        mermaid = "graph TD\n"
        for i, (node_id, data) in enumerate(nodes):
            label = f"{data['type']}\\n{data['timestamp']}"
            mermaid += f"  {node_id}[\"{label}\"]\n"
        
        for u, v in self.graph.edges():
            if proof_id is None or (u in [n[0] for n in nodes] and v in [n[0] for n in nodes]):
                mermaid += f"  {u} --> {v}\n"
        
        return mermaid
```

#### Step 4-10: 实现事件溯源系统
- Step 4: WorldSnapshot 实现
- Step 5: StateReconstructor 实现
- Step 6: EventSourcing 系统
- Step 7: WorldPatchV2 重构
- Step 8: PatchValidator 实现
- Step 9: ProofVisualizer 实现
- Step 10: 集成测试

#### Step 11-30: 重构现有系统
- Step 11-15: 重构 PatchExecutor 为事件溯源
- Step 16-20: 重构 IdealCityPipeline 集成 ProofLog
- Step 21-25: 重构 QuestRuntime 集成 ProofLog
- Step 26-28: 添加 Proof API
- Step 29: 添加 Proof UI (CityPhone)
- Step 30: 完整集成测试

---

### 3.4 风险评估

#### 技术风险
| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| **架构重构风险** | 高 | 高 | 渐进式重构，保留旧系统 |
| **性能问题** | 高 | 中 | 异步写入 + 索引优化 |
| **存储空间** | 中 | 中 | 日志压缩 + 定期归档 |
| **回放不一致** | 中 | 高 | 充分的回放测试 |

#### 业务风险
| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| **学习曲线过陡** | 高 | 高 | 分阶段发布功能 |
| **玩家困惑** | 高 | 中 | 详细的教程与引导 |
| **过度复杂** | 中 | 高 | 简化 UI，隐藏技术细节 |

---

### 3.5 回滚方式

#### 回滚策略
```python
# 使用双写模式（Dual Write）
class DualWriteProofLog:
    """双写模式：同时写入新旧系统"""
    
    def __init__(self, use_new_system: bool = True):
        self.use_new_system = use_new_system
        self.new_log = ProofLog() if use_new_system else None
        self.old_log = PatchTransactionLog()
    
    def record(self, proof: Dict):
        # 始终写入旧系统（保证兼容性）
        self.old_log.record(
            proof["patch_id"],
            proof["template_id"],
            proof["step_id"],
            proof["commands"],
            proof["status"]
        )
        
        # 可选写入新系统
        if self.use_new_system and self.new_log:
            self.new_log.append(proof)
```

#### 回滚步骤
1. 设置环境变量 `USE_PROOF_LOG=false`
2. 系统退回到旧的 PatchTransactionLog
3. ProofLog 数据保留，可后续迁移回来

---

### 3.6 能训练的数学严谨能力点（20+ 个）

除了方案 2 的 15 个能力点，额外增加：

| 领域 | 能力点 | 描述 |
|------|--------|------|
| **逻辑学** | 16. 因果推理 | 理解证明链的因果关系 |
| | 17. 逻辑一致性 | 验证证明链无矛盾 |
| **形式化方法** | 18. 状态机 | 理解状态转换 |
| | 19. 不变量维护 | 证明不变量在所有状态保持 |
| **计算理论** | 20. 可重放性 | 理解确定性计算 |
| | 21. 时间复杂度分析 | 分析回放的复杂度 |
| **密码学** | 22. 哈希校验 | 理解数字签名 |
| | 23. 完整性验证 | 验证数据未被篡改 |

---

### 3.7 总结

**优点**:
- ✅ 完整的证明生态（20+ 能力点）
- ✅ 可回放，可审计
- ✅ 证明链可视化
- ✅ 支持复杂的数学验证

**缺点**:
- ❌ 工作量巨大（12-16 周）
- ❌ 架构重构风险高
- ❌ 需要深厚的数学 + 工程经验
- ❌ 性能 + 存储压力

**适用场景**:
- 长期项目，希望建立学术级的验证系统
- 有充足的开发资源（3+ 工程师）
- 目标是发表论文或建立教学平台

---

## 总结与建议

### 方案对比总表

| 维度 | 方案 1 | 方案 2 | 方案 3 |
|------|--------|--------|--------|
| **工作量** | 2-4 周 | 6-8 周 | 12-16 周 |
| **风险等级** | 低 | 中 | 高 |
| **数学能力点** | 5 个 | 15 个 | 20+ 个 |
| **可回滚性** | 高 | 中 | 低 |
| **长期可扩展性** | 低 | 高 | 极高 |
| **适合团队规模** | 1-2 人 | 2-3 人 | 3+ 人 |

### 推荐路径

**阶段 1 (1-2 个月)**: 实施方案 1
- 快速验证数学化可行性
- 收集玩家反馈
- 建立基础设施

**阶段 2 (3-4 个月)**: 迁移到方案 2
- 在方案 1 基础上建立 MathKernel
- 逐步替换门控为统一接口
- 完善证明生成

**阶段 3 (6-12 个月)**: 演进到方案 3
- 重构为事件溯源架构
- 建立完整证明生态
- 发布学术成果

### 最终答案

> **核心问题**: "如果在系统里教授微积分，那么导数到底存在于哪一层？"

**方案 1 的答案**: 导数存在于 `MathGate.check()` 中，作为独立的验证步骤

**方案 2 的答案**: 导数存在于 `MathKernel.calculus.differentiation` 模块中，统一管理

**方案 3 的答案**: 导数贯穿整个系统：
- **定义层**: Level JSON 定义能量函数
- **计算层**: MathKernel 计算导数
- **验证层**: ProofValidator 验证导数正确性
- **可见层**: Minecraft 粒子显示导数向量
- **存储层**: ProofLog 记录导数计算轨迹
- **审计层**: ProofChain 展示导数应用的因果链

这就是数学知识"嵌入"Minecraft 的完整实现。
