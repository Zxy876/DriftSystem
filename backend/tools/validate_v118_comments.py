#!/usr/bin/env python3
"""Validate v1.18 semantic-layer comment contracts."""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple

ROOT = Path(__file__).resolve().parents[1]

MODULE_KEYWORDS = (
    "【v1.18 语义层模块】",
    "模块用途：",
    "工程边界：",
    "❌ 不具备执行权限",
    "❌ 不得写入世界",
    "❌ 不得修改 execution_tier",
    "版本说明：",
    "引入于 DriftSystem v1.18",
    "属于“理解层”，不属于“执行层”",
)

SECTION_KEYWORDS = (
    "【为什么存在】",
    "【它具体做什么】",
    "【它明确不做什么】",
)

ML_ROLE_BLOCK = (
    "# 【ML 角色声明】",
    "# ML_ROLE: 仅用于语义提议（proposal_only）",
    "# EXECUTION_AUTHORITY: 无",
    "# GOVERNANCE_OWNER: CreationWorkflow",
)


@dataclass(frozen=True)
class MethodSpec:
    class_name: str
    method_name: str
    required_keywords: Tuple[str, ...] = SECTION_KEYWORDS


@dataclass(frozen=True)
class ClassSpec:
    class_name: str
    required_keywords: Tuple[str, ...] = SECTION_KEYWORDS


@dataclass(frozen=True)
class ModuleSpec:
    path: Path
    module_keywords: Tuple[str, ...] = MODULE_KEYWORDS
    classes: Tuple[ClassSpec, ...] = ()
    methods: Tuple[MethodSpec, ...] = ()
    require_ml_role_block: bool = False


SPEC = (
    ModuleSpec(
        path=Path("app/ml/embedding_model.py"),
        classes=(
            ClassSpec("EmbeddingRequest"),
            ClassSpec("EmbeddingModel"),
        ),
        methods=(
            MethodSpec("EmbeddingModel", "embed"),
            MethodSpec("EmbeddingModel", "embed_batch"),
        ),
    ),
    ModuleSpec(
        path=Path("app/ml/__init__.py"),
        classes=(
            ClassSpec("SemanticCandidate"),
            ClassSpec("SemanticResolver"),
        ),
        methods=(
            MethodSpec("SemanticResolver", "propose"),
        ),
    ),
    ModuleSpec(
        path=Path("app/ml/resource_index.py"),
        classes=(
            ClassSpec("ResourceIndexEntry"),
            ClassSpec("ResourceIndex"),
        ),
        methods=(
            MethodSpec("ResourceIndex", "load"),
            MethodSpec("ResourceIndex", "search"),
        ),
    ),
    ModuleSpec(
        path=Path("app/ml/semantic_resolver.py"),
        classes=(ClassSpec("IndexedSemanticResolver"),),
        methods=(
            MethodSpec("IndexedSemanticResolver", "propose"),
        ),
    ),
    ModuleSpec(
        path=Path("app/services/semantic_proposal.py"),
        classes=(ClassSpec("SemanticProposalService"),),
        methods=(MethodSpec("SemanticProposalService", "collect_candidates"),),
        require_ml_role_block=True,
    ),
)


def _load_module_tree(spec: ModuleSpec) -> ast.Module:
    target = ROOT / spec.path
    if not target.exists():
        raise FileNotFoundError(f"v1.18 target missing: {spec.path}")
    source = target.read_text(encoding="utf-8")
    return ast.parse(source, filename=str(target))


def _ensure_keywords(name: str, text: str | None, keywords: Iterable[str], errors: list[str]) -> None:
    if not text:
        errors.append(f"{name}: missing required docstring")
        return
    missing = [keyword for keyword in keywords if keyword not in text]
    if missing:
        joined = ", ".join(missing)
        errors.append(f"{name}: docstring missing keywords: {joined}")


def _lookup_class(tree: ast.Module, class_name: str) -> ast.ClassDef | None:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    return None


def _lookup_method(cls: ast.ClassDef, method_name: str) -> ast.FunctionDef | None:
    for node in cls.body:
        if isinstance(node, ast.FunctionDef) and node.name == method_name:
            return node
    return None


def validate() -> list[str]:
    errors: list[str] = []

    for spec in SPEC:
        tree = _load_module_tree(spec)
        module_doc = ast.get_docstring(tree)
        _ensure_keywords(f"module {spec.path}", module_doc, spec.module_keywords, errors)

        cls_cache: dict[str, ast.ClassDef] = {}

        for class_spec in spec.classes:
            cls = cls_cache.setdefault(class_spec.class_name, _lookup_class(tree, class_spec.class_name))
            if cls is None:
                errors.append(f"{spec.path}: missing class {class_spec.class_name}")
                continue
            _ensure_keywords(
                f"class {spec.path}:{class_spec.class_name}",
                ast.get_docstring(cls),
                class_spec.required_keywords,
                errors,
            )

        for method_spec in spec.methods:
            cls = cls_cache.setdefault(method_spec.class_name, _lookup_class(tree, method_spec.class_name))
            if cls is None:
                errors.append(f"{spec.path}: missing class {method_spec.class_name}")
                continue
            method = _lookup_method(cls, method_spec.method_name)
            if method is None:
                errors.append(
                    f"{spec.path}: missing method {method_spec.class_name}.{method_spec.method_name}"
                )
                continue
            if method_spec.method_name.startswith("_"):
                # private helpers不强制，但若声明则仍需检查
                doc = ast.get_docstring(method)
            else:
                doc = ast.get_docstring(method)
            _ensure_keywords(
                f"method {spec.path}:{method_spec.class_name}.{method_spec.method_name}",
                doc,
                method_spec.required_keywords,
                errors,
            )

        if spec.require_ml_role_block:
            source = (ROOT / spec.path).read_text(encoding="utf-8")
            for line in ML_ROLE_BLOCK:
                if line not in source:
                    errors.append(f"{spec.path}: missing ML role block line: {line}")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        sys.stderr.write("v1.18 comment validation failed:\n")
        for item in errors:
            sys.stderr.write(f"  - {item}\n")
        return 1
    print("v1.18 comment validation passed")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    sys.exit(main())
