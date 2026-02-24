#!/usr/bin/env python3
"""
【v1.18 语义层模块】

模块用途：
- 本文件用于：从 ResourceCatalog 构建语义索引并写入 semantic_index.json

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

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

from app.core.creation.resource_snapshot import ResourceCatalog
from app.ml.embedding_model import EmbeddingModel, EmbeddingRequest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = BACKEND_ROOT / "data" / "transformer" / "semantic_index.json"
DEFAULT_MODEL_NAME = "semantic_index"


def _iter_resources(catalog: ResourceCatalog) -> Iterable[dict]:
    """
    【为什么存在】
    - 将 ResourceCatalog 中的资源转化为语义索引所需的结构

    【它具体做什么】
    - 调用 catalog.load_snapshot 获取最新资源
    - 产出包含 resource_id / display_name / aliases / tags 的字典
    - 供索引构建流程迭代使用

    【它明确不做什么】
    - 不写入世界
    - 不做语义裁决
    - 不修改 ResourceCatalog
    """

    snapshot = catalog.load_snapshot()
    for record in snapshot.resources:
        yield {
            "resource_id": record.resource_id,
            "display_name": record.label,
            "aliases": list(record.aliases),
            "tags": list(record.tags),
        }


def _embed_text(model: EmbeddingModel, text: str) -> List[float]:
    """
    【为什么存在】
    - 为索引构建提供统一的文本向量化接口

    【它具体做什么】
    - 构造 EmbeddingRequest
    - 调用 EmbeddingModel.embed 返回向量
    - 供索引条目序列化

    【它明确不做什么】
    - 不改变模型配置
    - 不进行执行判断
    - 不写入日志
    """

    request = EmbeddingRequest(text=text)
    return model.embed(request)


def _compose_entry(model: EmbeddingModel, resource: dict) -> dict:
    """
    【为什么存在】
    - 将单个资源转化为语义索引条目

    【它具体做什么】
    - 拼接 display_name 与 aliases 形成嵌入输入
    - 生成 embedding 并填充条目字段
    - 返回可直接写入 JSON 的字典

    【它明确不做什么】
    - 不修改资源原始数据
    - 不做执行裁决
    - 不处理 Feature Flag
    """

    parts = [resource["display_name"], *resource.get("aliases", [])]
    payload = "\n".join(part for part in parts if part)
    embedding = _embed_text(model, payload)
    return {
        "resource_id": resource["resource_id"],
        "display_name": resource["display_name"],
        "aliases": resource.get("aliases", []),
        "tags": resource.get("tags", []),
        "embedding": embedding,
    }


def build_index(output: Path, *, model_name: str = DEFAULT_MODEL_NAME) -> None:
    """
    【为什么存在】
    - 离线构建语义索引，提供可回滚的语义候选数据

    【它具体做什么】
    - 加载 ResourceCatalog
    - 对每个资源生成嵌入向量
    - 写入 semantic_index.json，记录版本与时间戳

    【它明确不做什么】
    - 不执行世界改动
    - 不绕过 Feature Flag
    - 不直接修改 ResourceCatalog
    """

    catalog = ResourceCatalog()
    embedding_model = EmbeddingModel()
    resources = list(_iter_resources(catalog))
    entries = [_compose_entry(embedding_model, resource) for resource in resources]
    payload = {
        "model_name": model_name,
        "model_version": f"{model_name}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entry_count": len(entries),
        "entries": entries,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build semantic index for v1.18 semantic layer")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="索引输出路径")
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME, help="模型名称，用于版本号前缀")
    args = parser.parse_args()

    build_index(args.output, model_name=args.model_name)


if __name__ == "__main__":  # pragma: no cover - CLI 入口
    main()
