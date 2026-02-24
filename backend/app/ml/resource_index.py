"""
【v1.18 语义层模块】

模块用途：
- 本文件用于：加载并查询语义索引，为语义候选提供确定性的数据基线

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

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class ResourceIndexEntry:
    """
    【为什么存在】
    - 保存语义索引条目的元信息与向量
    - 让语义候选可以追溯到资源、别名与标签

    【它具体做什么】
    - 持有 resource_id、display_name、aliases、tags 与 embedding
    - 提供给 ResourceIndex 进行相似度检索
    - 被 SemanticResolver 转化为 SemanticCandidate

    【它明确不做什么】
    - 不直接写世界
    - 不裁决执行权限
    - 不处理 Feature Flag
    """

    resource_id: str
    display_name: str
    aliases: Tuple[str, ...]
    tags: Tuple[str, ...]
    embedding: Tuple[float, ...]


class ResourceIndex:
    """
    【为什么存在】
    - 作为语义索引的确定性载体，提供 Top-K 检索能力
    - 让语义候选来源工程化、可回滚

    【它具体做什么】
    - 从 JSON 文件加载索引条目
    - 对外提供基于向量的相似度检索接口
    - 暴露 model_version / generated_at 供治理追溯

    【它明确不做什么】
    - 不执行命令
    - 不更新 ResourceCatalog
    - 不直接访问 ML 服务
    """

    def __init__(
        self,
        *,
        model_name: str,
        model_version: str,
        generated_at: str,
        entries: Sequence[ResourceIndexEntry],
    ) -> None:
        self.model_name = model_name
        self.model_version = model_version
        self.generated_at = generated_at

        prepared: List[Tuple[ResourceIndexEntry, Tuple[float, ...], float]] = []
        for entry in entries:
            vector = tuple(float(value) for value in entry.embedding)
            if not vector:
                continue
            norm = math.sqrt(sum(component * component for component in vector))
            if norm == 0.0:
                continue
            prepared.append((entry, vector, norm))
        self._entries = prepared

    @classmethod
    def load(cls, path: Path) -> "ResourceIndex":
        """
        【为什么存在】
        - 从磁盘加载语义索引，供运行时直接使用

        【它具体做什么】
        - 读取 JSON 文件
        - 解析元数据与 embedding 向量
        - 返回 ResourceIndex 实例

        【它明确不做什么】
        - 不生成索引内容
        - 不写回磁盘
        - 不自动刷新资源快照
        """

        payload = cls._read_payload(path)
        meta = {key: str(payload.get(key) or "") for key in ("model_name", "model_version", "generated_at")}
        raw_entries = payload.get("entries") if isinstance(payload, dict) else None
        entries: List[ResourceIndexEntry] = []
        if isinstance(raw_entries, Sequence):
            for item in raw_entries:
                if not isinstance(item, dict):
                    continue
                resource_id = str(item.get("resource_id") or "").strip()
                display_name = str(item.get("display_name") or "").strip()
                embedding = tuple(float(value) for value in item.get("embedding") or [])
                if not resource_id or not display_name or not embedding:
                    continue
                aliases = tuple(str(alias) for alias in item.get("aliases") or [] if isinstance(alias, str))
                tags = tuple(str(tag) for tag in item.get("tags") or [] if isinstance(tag, str))
                entries.append(
                    ResourceIndexEntry(
                        resource_id=resource_id,
                        display_name=display_name,
                        aliases=aliases,
                        tags=tags,
                        embedding=embedding,
                    )
                )
        return cls(
            model_name=meta.get("model_name", "semantic_index"),
            model_version=meta.get("model_version", "unknown"),
            generated_at=meta.get("generated_at", ""),
            entries=entries,
        )

    def search(
        self,
        vector: Sequence[float],
        *,
        limit: int = 5,
        min_score: float = 0.35,
    ) -> List[Tuple[ResourceIndexEntry, float]]:
        """
        【为什么存在】
        - 对外提供基于语义向量的 Top-K 检索

        【它具体做什么】
        - 计算查询向量与索引条目的余弦相似度
        - 过滤掉低于阈值的结果
        - 按相似度降序返回指定数量的条目

        【它明确不做什么】
        - 不修改底层索引
        - 不写入任何日志
        - 不进行执行裁决
        """

        query = tuple(float(component) for component in vector)
        if not query:
            return []
        query_norm = math.sqrt(sum(component * component for component in query))
        if query_norm == 0.0:
            return []

        ranked: List[Tuple[ResourceIndexEntry, float]] = []
        for entry, entry_vector, entry_norm in self._entries:
            score = self._cosine_similarity(query, query_norm, entry_vector, entry_norm)
            if score < min_score:
                continue
            ranked.append((entry, score))

        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[: max(limit, 0)]

    @staticmethod
    def _cosine_similarity(
        query: Tuple[float, ...],
        query_norm: float,
        entry_vector: Tuple[float, ...],
        entry_norm: float,
    ) -> float:
        limit = min(len(query), len(entry_vector))
        if limit == 0:
            return 0.0
        dot = sum(query[idx] * entry_vector[idx] for idx in range(limit))
        if query_norm == 0.0 or entry_norm == 0.0:
            return 0.0
        return dot / (query_norm * entry_norm)

    @staticmethod
    def _read_payload(path: Path) -> Dict[str, object]:
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}
        except OSError:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}


__all__ = ["ResourceIndex", "ResourceIndexEntry"]
