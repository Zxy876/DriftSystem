"""
【v1.18 语义层模块】

模块用途：
- 本文件用于：封装语义层调用的文本向量化流程

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
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable, List, Sequence

try:  # OpenAI SDK is optional; fallback mode must remain functional.
    from openai import OpenAI, OpenAIError
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None

    class OpenAIError(Exception):
        """Fallback error type when OpenAI SDK is unavailable."""


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmbeddingRequest:
    """
    【为什么存在】
    - 表达语义向量化所需的输入上下文
    - 提供统一的 text / locale / tags 封装，方便上游传参

    【它具体做什么】
    - 持有原始文本及可选标签
    - 将请求传递给 EmbeddingModel 进行编码
    - 结果将被语义索引用于 Top-K 检索

    【它明确不做什么】
    - 不触发任何执行逻辑
    - 不尝试自行推断资源
    - 不产生世界写入
    """

    text: str
    locale: str = "zh_cn"
    tags: Sequence[str] = ()


class EmbeddingModel:
    """
    【为什么存在】
    - 为语义候选层提供统一的向量生成接口
    - 支持调用外部嵌入服务或回退到确定性哈希向量

    【它具体做什么】
    - 根据配置选择 HTTP 服务或内建算法生成向量
    - 返回长度固定的 embedding，供 ResourceIndex 存储与检索
    - 所有生成的 embedding 都会配合置信度校准使用

    【它明确不做什么】
    - 不直接决定资源命中
    - 不更改任何执行权限
    - 不与 WorldExecutor 产生交互
    """

    _FALLBACK_DIMENSION = 128

    def __init__(self, *, endpoint: str | None = None, timeout: float = 3.0) -> None:
        self._endpoint = endpoint or os.getenv("SEMANTIC_EMBEDDING_ENDPOINT")
        self._timeout = timeout
        raw_mode = (self._endpoint or "").strip().lower()
        self._mode = "http" if self._endpoint else "fallback"
        self._client = None
        self._openai_model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        if raw_mode == "openai":
            if OpenAI is None:
                logger.warning("semantic_embedding_openai_sdk_missing")
                self._mode = "fallback"
                self._endpoint = None
            else:
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    logger.warning("semantic_embedding_openai_missing_key")
                    self._mode = "fallback"
                    self._endpoint = None
                else:
                    raw_timeout = os.getenv("OPENAI_TIMEOUT", "30")
                    try:
                        openai_timeout = float(raw_timeout)
                    except ValueError:
                        logger.warning("semantic_embedding_openai_invalid_timeout value=%s", raw_timeout)
                        openai_timeout = 30.0
                    self._client = OpenAI(api_key=api_key, timeout=openai_timeout)
                    self._mode = "openai"
                    self._endpoint = None
        elif not self._endpoint:
            self._mode = "fallback"

    def embed(self, request: EmbeddingRequest) -> List[float]:
        """
        【为什么存在】
        - 将单条语义请求转换为数值向量
        - 供语义索引用于相似度检索

        【它具体做什么】
        - 如果配置了外部服务，则发起 HTTP POST 获取向量
        - 如调用失败，则回退到确定性的哈希向量
        - 返回长度固定的浮点列表

        【它明确不做什么】
        - 不缓存索引
        - 不更新任何资源元数据
        - 不触发执行或澄清流程
        """

        payload = {
            "text": request.text,
            "locale": request.locale,
            "tags": list(request.tags),
        }
        if self._mode == "openai" and self._client:
            embeddings = self._embed_openai_batch([request])
            if embeddings and embeddings[0]:
                return embeddings[0]
        if self._endpoint and self._mode != "openai":
            try:
                response = self._post_json(self._endpoint, payload)
                vector = response.get("embedding") if isinstance(response, dict) else None
                if isinstance(vector, Sequence):
                    floats = [float(value) for value in vector]
                    if floats:
                        return floats
                logger.warning("semantic_embedding_empty_response endpoint=%s", self._endpoint)
            except Exception:  # pragma: no cover - 网络回退路径
                logger.exception("semantic_embedding_remote_failed endpoint=%s", self._endpoint)
        return self._fallback_embed(payload)

    def embed_batch(self, requests: Iterable[EmbeddingRequest]) -> List[List[float]]:
        """
        【为什么存在】
        - 提供批量编码接口，减少外部服务往返
        - 与构建索引脚本配合使用

        【它具体做什么】
        - 对每个请求调用 embed，收集结果
        - 在批量调用失败时同样回退到哈希向量
        - 保证返回列表等长

        【它明确不做什么】
        - 不改变批次顺序
        - 不抛弃失败的请求
        - 不执行任何治理判断
        """

        batched = list(requests)
        if self._mode == "openai" and self._client:
            vectors = self._embed_openai_batch(batched)
            if vectors and all(vector for vector in vectors):
                return vectors
        return [self.embed(item) for item in batched]

    def _embed_openai_batch(self, requests: Sequence[EmbeddingRequest]) -> List[List[float]]:
        if not requests:
            return []
        if not self._client:
            return []
        inputs = [item.text for item in requests]
        try:
            response = self._client.embeddings.create(model=self._openai_model, input=inputs)
        except OpenAIError:
            logger.exception("semantic_embedding_openai_failed model=%s", self._openai_model)
            return [self._fallback_embed({"text": req.text, "locale": req.locale, "tags": list(req.tags)}) for req in requests]
        data = getattr(response, "data", None)
        if not isinstance(data, Sequence) or len(data) != len(inputs):
            logger.warning("semantic_embedding_openai_invalid_response model=%s", self._openai_model)
            return [self._fallback_embed({"text": req.text, "locale": req.locale, "tags": list(req.tags)}) for req in requests]
        embeddings: List[List[float]] = []
        for idx, item in enumerate(data):
            embedding = getattr(item, "embedding", None)
            if not isinstance(embedding, Sequence):
                logger.warning("semantic_embedding_openai_missing_vector index=%d", idx)
                embeddings.append(self._fallback_embed({"text": requests[idx].text, "locale": requests[idx].locale, "tags": list(requests[idx].tags)}))
                continue
            floats = [float(value) for value in embedding]
            embeddings.append(floats)
        return embeddings

    def _fallback_embed(self, payload: dict) -> List[float]:
        text = str(payload.get("text") or "")
        locale = str(payload.get("locale") or "")
        tags = ",".join(sorted(str(tag) for tag in payload.get("tags") or []))
        seed = "|".join([text.strip().lower(), locale.lower(), tags])
        digest = sha256(seed.encode("utf-8")).digest()
        values = []
        for idx in range(self._FALLBACK_DIMENSION):
            chunk = digest[idx % len(digest)]
            values.append((chunk / 255.0) * 2.0 - 1.0)
        return values

    @staticmethod
    def _post_json(endpoint: str, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=float(os.getenv("SEMANTIC_EMBEDDING_TIMEOUT", "3"))) as response:
            raw = response.read().decode("utf-8")
            if not raw:
                return {}
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                logger.error("semantic_embedding_invalid_json")
                return {}
            return parsed if isinstance(parsed, dict) else {}


__all__ = ["EmbeddingModel", "EmbeddingRequest"]
