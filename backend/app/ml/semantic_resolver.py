"""
【v1.18 语义层模块】

模块用途：
- 本文件用于：基于语义索引生成候选，供 SemanticProposalService 注入治理流程

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
from typing import Dict, List, Optional, Sequence

from app.ml import SemanticCandidate, SemanticResolver
from app.ml.embedding_model import EmbeddingModel, EmbeddingRequest
from app.ml.resource_index import ResourceIndex, ResourceIndexEntry


@dataclass(frozen=True)
class _CandidateAccumulator:
    """
    【为什么存在】
    - 聚合同一资源在多个 token 查询下的相似度
    - 确保最终候选的置信度与来源信息一致

    【它具体做什么】
    - 记录最高相似度、来源 token、数据来源
    - 暴露给 IndexedSemanticResolver 用于构造 SemanticCandidate
    - 避免重复地向上游返回同一资源

    【它明确不做什么】
    - 不负责执行裁决
    - 不做 Feature Flag 判定
    - 不写入任何日志
    """

    confidence: float
    token: str
    sources: Sequence[str]
    reason: Optional[str] = None


class IndexedSemanticResolver(SemanticResolver):
    """
    【为什么存在】
    - 将语义索引与嵌入模型组合，输出治理所需的候选
    - 作为 SemanticResolver 协议的标准实现

    【它具体做什么】
    - 对每个 token / 消息生成嵌入
    - 查询 ResourceIndex，提取 Top-K 结果
    - 转换为带来源、置信度、token 的 SemanticCandidate

    【它明确不做什么】
    - 不执行命令
    - 不写入世界
    - 不决定 execution_tier
    """

    def __init__(
        self,
        *,
        index: ResourceIndex,
        embedding_model: EmbeddingModel,
        min_confidence: float = 0.35,
        per_query_limit: int = 5,
        origin_label: Optional[str] = None,
    ) -> None:
        self._index = index
        self._embedding_model = embedding_model
        self._min_confidence = min_confidence
        self._per_query_limit = per_query_limit
        self._origin_label = origin_label or index.model_version or "semantic_index"

    @property
    def model_version(self) -> str:
        return self._origin_label

    def propose(
        self,
        material_tokens: Sequence[str],
        message: Optional[str],
        *,
        limit: int = 3,
    ) -> Sequence[SemanticCandidate]:
        """
        【为什么存在】
        - 面向 SemanticProposalService 返回语义候选

        【它具体做什么】
        - 对 material_tokens 与 message 逐个查询索引
        - 聚合资源的最高置信度，并记录来源 token
        - 根据置信度排序后返回限定数量的候选

        【它明确不做什么】
        - 不直接执行
        - 不绕过 ResourceCatalog
        - 不处理澄清流程
        """

        queries = [token for token in material_tokens if isinstance(token, str) and token.strip()]
        if message and isinstance(message, str) and message.strip():
            queries.append(message)
        if not queries:
            return []

        aggregated: Dict[str, _CandidateAccumulator] = {}
        for token in queries:
            vector = self._embed_text(token)
            if not vector:
                continue
            for entry, score in self._index.search(vector, limit=self._per_query_limit, min_score=self._min_confidence):
                if score < self._min_confidence:
                    continue
                previous = aggregated.get(entry.resource_id)
                if previous is None or score > previous.confidence:
                    aggregated[entry.resource_id] = _CandidateAccumulator(
                        confidence=score,
                        token=token,
                        sources=["semantic_index"],
                        reason=None,
                    )

        if not aggregated:
            return []

        ordered = sorted(aggregated.items(), key=lambda item: item[1].confidence, reverse=True)
        limited = ordered[: max(limit, 0)]
        candidates: List[SemanticCandidate] = []
        for resource_id, accumulator in limited:
            candidates.append(
                SemanticCandidate(
                    resource_id=resource_id,
                    confidence=float(accumulator.confidence),
                    token=accumulator.token,
                    origin=self._origin_label,
                    sources=tuple(accumulator.sources),
                    reason=accumulator.reason,
                )
            )
        return candidates

    def _embed_text(self, text: str) -> Sequence[float]:
        """
        【为什么存在】
        - 为查询 token 生成语义向量
        - 统一封装 EmbeddingModel 的调用路径

        【它具体做什么】
        - 构造 EmbeddingRequest
        - 调用 embedding_model.embed 获取向量
        - 返回用于索引检索的浮点序列

        【它明确不做什么】
        - 不修改索引文件
        - 不记录日志
        - 不执行任何治理判断
        """

        request = EmbeddingRequest(text=text.strip())
        try:
            return self._embedding_model.embed(request)
        except Exception:
            return []


__all__ = ["IndexedSemanticResolver"]
