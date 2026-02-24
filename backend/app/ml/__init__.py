"""
【v1.18 语义层模块】

模块用途：
- 本文件用于：暴露语义层通用协议，实现 SemanticProposalService 与外部 ML 组件的解耦

工程边界：
- 仅参与【语义理解 / 候选提议】
- ❌ 不具备执行权限
- ❌ 不得写入世界
- ❌ 不得修改 execution_tier

版本说明：
- 引入于 DriftSystem v1.18
- 属于“理解层”，不属于“执行层”
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence


@dataclass(frozen=True)
class SemanticCandidate:
    """
    【为什么存在】
    - 在语义层与 CreationWorkflow 之间传递候选信息
    - 确保每个候选都带有治理所需的来源、置信度与追溯字段

    【它具体做什么】
    - 封装 resource_id、confidence、token、sources、origin、reason
    - 供 SemanticProposalService 统一转换为确定性候选
    - 支持语义索引、ML 模型等多种来源

    【它明确不做什么】
    - 不直接决定执行
    - 不验证 ResourceCatalog 权限
    - 不处理世界写入
    """

    resource_id: str
    confidence: float
    token: Optional[str]
    origin: str
    sources: Sequence[str]
    reason: Optional[str] = None


class SemanticResolver(Protocol):
    """
    【为什么存在】
    - 定义语义候选生成接口，允许替换不同 ML 后端
    - 将语义层与具体模型实现解耦，方便回退与审计

    【它具体做什么】
    - 根据玩家输入与物料 token 返回语义候选列表
    - 提供 model_version 字段供日志与治理使用
    - 由 SemanticProposalService 按需调用

    【它明确不做什么】
    - 不执行命令
    - 不进行世界写入
    - 不直接访问 ResourceCatalog
    """

    model_version: str

    def propose(
        self,
        material_tokens: Sequence[str],
        message: Optional[str],
        *,
        limit: int = 3,
    ) -> Sequence[SemanticCandidate]:
        """
        【为什么存在】
        - 为语义层提供统一的候选生成接口
        - 允许在不同模型之间切换而不影响治理逻辑

        【它具体做什么】
        - 输入：物料 token 列表与玩家原始指令
        - 输出：限定数量的 SemanticCandidate 序列
        - 结果供 SemanticProposalService 进一步治理

        【它明确不做什么】
        - 不执行命令
        - 不写入世界
        - 不更改 execution_tier
        """


__all__ = ["SemanticCandidate", "SemanticResolver"]
