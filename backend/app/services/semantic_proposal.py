"""
【v1.18 语义层模块】

模块用途：
- 本文件用于：协调语义索引与 transformer 候选，向 CreationWorkflow 提供可治理的资源列表

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
from typing import Callable, Dict, Iterable, List, Optional, Protocol, Sequence

from app.core.creation.resource_snapshot import ResourceRecord
from app.core.creation.transformer import CreationTransformer
from app.ml import SemanticCandidate, SemanticResolver


class CandidateBuilder(Protocol):
	def __call__(
		self,
		entry: ResourceEntry,
		*,
		source: str,
		confidence: Optional[float] = ...,
		token: Optional[str] = ...,
		reason: Optional[str] = ...,
	) -> Optional[Dict[str, object]]:
		...


TokenIterator = Callable[[Sequence[str], Optional[str]], Iterable[str]]
FeatureGate = Callable[[], bool]


class ResourceEntry(Protocol):
	"""
	【为什么存在】
	- 抽象 ResourceCatalog 返回的资源条目，供类型提示使用

	【它具体做什么】
	- 定义语义层需要访问的最小字段
	- 让 SemanticProposalService 可以在不同实现之间解耦
	- 保持治理逻辑的只读性

	【它明确不做什么】
	- 不执行命令
	- 不绑定具体存储实现
	- 不提供写入接口
	"""

	resource_id: str
	display_name: str
	category: Optional[str]


ResourceResolver = Callable[[str], Optional[ResourceEntry]]


@dataclass(frozen=True)
class _CandidateSlot:
	order: int
	payload: Dict[str, object]


class SemanticProposalService:
	"""
	【为什么存在】
	- 将语义索引、别名解析与 transformer 候选统一输出
	- 确保所有 ML 结果均受 Feature Flag 管控并可回退

	【它具体做什么】
	- 根据 Feature Flag 有条件地调用语义 Resolver 与 transformer
	- 将候选注入 CreationWorkflow 所需结构
	- 记录来源、置信度、token 以便治理层澄清

	【它明确不做什么】
	- 不直接执行命令
	- 不修改 execution_tier
	- 不与 WorldExecutor 交互
	"""

	def __init__(
		self,
		*,
		transformer: CreationTransformer,
		transformer_feature_gate: FeatureGate,
		resource_resolver: ResourceResolver,
		candidate_builder: CandidateBuilder,
		token_iterator: TokenIterator,
		source_label: str = "transformer",
		allowed_categories: Sequence[str] = ("block",),
		semantic_resolver: Optional[SemanticResolver] = None,
		semantic_feature_gate: Optional[FeatureGate] = None,
	) -> None:
		self._transformer = transformer
		self._transformer_gate = transformer_feature_gate
		self._resource_resolver = resource_resolver
		self._candidate_builder = candidate_builder
		self._token_iterator = token_iterator
		self._source_label = source_label
		self._allowed_categories = tuple(allowed_categories)
		self._allowed_categories_normalized = {
			str(category).strip().lower()
			for category in self._allowed_categories
			if isinstance(category, str) and category.strip()
		}
		self._semantic_resolver = semantic_resolver
		self._semantic_gate = semantic_feature_gate

	@property
	def model_version(self) -> str:
		if self._semantic_resolver is not None:
			return str(self._semantic_resolver.model_version)
		generated_at = getattr(self._transformer.catalog, "generated_at", None)
		if not generated_at:
			return "transformer_snapshot"
		return str(generated_at)

	def collect_candidates(
		self,
		material_tokens: Sequence[str],
		message: Optional[str],
		*,
		limit: int = 3,
	) -> List[Dict[str, object]]:
		"""
		【为什么存在】
		- 向 CreationWorkflow 提供语义候选 list

		【它具体做什么】
		- 条件调用语义索引和 transformer
		- 统一构建候选 payload，记录置信度与来源
		- 返回限定数量的候选

		【它明确不做什么】
		- 不触发执行
		- 不突破 ResourceCatalog
		- 不跳过 Clarification
		"""

		if limit <= 0:
			return []

		slots: Dict[str, _CandidateSlot] = {}
		next_index = 0

		if self._should_use_semantic_layer():
			# 【ML 角色声明】
			# ML_ROLE: 仅用于语义提议（proposal_only）
			# EXECUTION_AUTHORITY: 无
			# GOVERNANCE_OWNER: CreationWorkflow
			assert self._semantic_resolver is not None
			semantic_candidates = self._semantic_resolver.propose(material_tokens, message, limit=limit)
			for candidate in semantic_candidates:
				entry = self._resource_resolver(candidate.resource_id)
				if entry is None or not self._is_entry_allowed(entry):
					continue
				payload = self._candidate_builder(
					entry,
					source="semantic_layer",
					confidence=candidate.confidence,
					token=candidate.token,
					reason=candidate.reason,
				)
				if payload is None:
					continue
				payload.setdefault("origin", candidate.origin)
				payload.setdefault("source", [])
				payload["source"] = list({*payload["source"], *candidate.sources, "semantic_layer"})
				payload.setdefault("label", entry.display_name)
				payload.setdefault("token", candidate.token)
				slots[candidate.resource_id] = _CandidateSlot(order=next_index, payload=payload)
				next_index += 1

		if self._should_use_transformer():
			snapshot = self._transformer.catalog.load_snapshot()
			for token in self._token_iterator(material_tokens, message):
				if not isinstance(token, str):
					continue
				normalized = token.strip().lower()
				if not normalized:
					continue
				records = snapshot.find_candidates(normalized, limit=limit)
				for record, score in records:
					if not self._is_category_allowed(record):
						continue
					entry = self._resource_resolver(record.resource_id)
					if entry is None or not self._is_entry_allowed(entry):
						continue
					payload = self._candidate_builder(
						entry,
						source=self._source_label,
						confidence=score,
						token=token,
						reason=None,
					)
					if payload is None:
						continue
					payload.setdefault("origin", self._source_label)
					payload.setdefault("source", [])
					if self._source_label not in payload["source"]:
						payload["source"].append(self._source_label)
					payload.setdefault("label", record.label)
					payload.setdefault("token", token)
					existing = slots.get(record.resource_id)
					if existing is None:
						slots[record.resource_id] = _CandidateSlot(order=next_index, payload=payload)
						next_index += 1
					else:
						merged = existing.payload
						merged_conf = payload.get("confidence")
						if isinstance(merged_conf, (int, float)):
							merged["confidence"] = merged_conf
						merged_sources = list({*merged.get("source", []), *payload.get("source", [])})
						merged["source"] = merged_sources
						merged.setdefault("label", record.label)
						merged.setdefault("token", token)

		ordered = sorted(slots.values(), key=lambda item: item.order)
		return [slot.payload for slot in ordered][:limit]

	def _should_use_transformer(self) -> bool:
		try:
			return bool(self._transformer_gate())
		except Exception:  # pragma: no cover - feature flag guard
			return False

	def _should_use_semantic_layer(self) -> bool:
		if self._semantic_resolver is None:
			return False
		if self._semantic_gate is None:
			return True
		try:
			return bool(self._semantic_gate())
		except Exception:  # pragma: no cover - feature flag guard
			return False

	def _is_category_allowed(self, record: ResourceRecord) -> bool:
		if not self._allowed_categories_normalized:
			return True
		return str(record.category).strip().lower() in self._allowed_categories_normalized

	def _is_entry_allowed(self, entry: ResourceEntry) -> bool:
		if not self._allowed_categories_normalized:
			return True
		category = getattr(entry, "category", None)
		if isinstance(category, str) and category.strip():
			return category.strip().lower() in self._allowed_categories_normalized
		return True


__all__ = ["SemanticProposalService"]
