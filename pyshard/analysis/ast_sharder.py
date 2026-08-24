"""Python AST/CST sharding layer for extracting SRP-compliant code fragments."""

from __future__ import annotations

import ast
import hashlib
import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ShardMetadata:
    shard_id: str
    source_repo: str
    source_file: str
    category: str
    shard_type: str
    name: str
    lineno: int
    end_lineno: int
    cyclomatic_complexity: int
    import_dependencies: List[str]
    description: str
    code_hash: str


def _compute_cyclomatic_complexity(node: ast.AST) -> int:
    complexity = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor,
                              ast.ExceptHandler, ast.With, ast.AsyncWith)):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
        elif isinstance(child, (ast.IfExp,)):
            complexity += 1
    return complexity


def _infer_category(file_path: str, code: str) -> str:
    path_str = str(file_path).lower()
    code_lower = code.lower()

    if any(k in path_str for k in ["agent", "llm", "model", "openai", "anthropic", "ollama"]):
        return "ai_agent"
    if any(k in path_str for k in ["tool", "registry", "function"]):
        return "tooling"
    if any(k in path_str for k in ["memory", "store", "cache"]):
        return "data_processing"
    if any(k in path_str for k in ["http", "api", "request", "adapter"]):
        return "api_routing"
    if any(k in path_str for k in ["test", "spec"]):
        return "testing"
    if any(k in path_str for k in ["cli", "main", "app"]):
        return "cli"
    if any(k in code_lower for k in ["async def", "await ", "asyncio"]):
        return "asyncio"
    if any(k in code_lower for k in ["class ", "def "]):
        return "utility"
    return "misc"


def _extract_imports(node: ast.AST, source_file: str) -> List[str]:
    imports = []
    for child in ast.walk(node):
        if isinstance(child, ast.Import):
            for alias in child.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(child, ast.ImportFrom):
            if child.module:
                imports.append(child.module.split(".")[0])
    return sorted(set(imports))


def _generate_description(name: str, code: str, shard_type: str) -> str:
    docstring = ""
    try:
        tree = ast.parse(code)
        if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
            docstring = tree.body[0].value.value.strip()
    except Exception:
        pass

    if docstring:
        return docstring.split("\n")[0][:200]

    if shard_type == "function":
        return f"Function '{name}' performing a discrete computational task."
    if shard_type == "class":
        return f"Class '{name}' encapsulating related state and behavior."
    return f"Module-level code segment '{name}'."


def _shard_id(source_file: str, name: str, lineno: int) -> str:
    raw = f"{source_file}:{name}:{lineno}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def shard_file(file_path: str, source_repo: str) -> List[ShardMetadata]:
    path = Path(file_path)
    if not path.suffix == ".py":
        return []

    try:
        source = path.read_text(encoding="utf-8")
    except Exception:
        return []

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    shards: List[ShardMetadata] = []
    rel_path = str(path)

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            start = node.lineno
            end = node.end_lineno or start
            code_lines = source.splitlines()[start - 1:end]
            code = "\n".join(code_lines)

            complexity = _compute_cyclomatic_complexity(node)
            imports = _extract_imports(node, rel_path)
            category = _infer_category(rel_path, code)
            shard_id = _shard_id(rel_path, node.name, start)
            code_hash = hashlib.sha256(code.encode()).hexdigest()[:16]
            description = _generate_description(node.name, code, "function")

            shards.append(ShardMetadata(
                shard_id=shard_id,
                source_repo=source_repo,
                source_file=rel_path,
                category=category,
                shard_type="function",
                name=node.name,
                lineno=start,
                end_lineno=end,
                cyclomatic_complexity=complexity,
                import_dependencies=imports,
                description=description,
                code_hash=code_hash,
            ))

        elif isinstance(node, ast.ClassDef):
            start = node.lineno
            end = node.end_lineno or start
            code_lines = source.splitlines()[start - 1:end]
            code = "\n".join(code_lines)

            complexity = _compute_cyclomatic_complexity(node)
            imports = _extract_imports(node, rel_path)
            category = _infer_category(rel_path, code)
            shard_id = _shard_id(rel_path, node.name, start)
            code_hash = hashlib.sha256(code.encode()).hexdigest()[:16]
            description = _generate_description(node.name, code, "class")

            shards.append(ShardMetadata(
                shard_id=shard_id,
                source_repo=source_repo,
                source_file=rel_path,
                category=category,
                shard_type="class",
                name=node.name,
                lineno=start,
                end_lineno=end,
                cyclomatic_complexity=complexity,
                import_dependencies=imports,
                description=description,
                code_hash=code_hash,
            ))

    return shards


def shard_directory(directory: str, source_repo: str) -> List[ShardMetadata]:
    all_shards: List[ShardMetadata] = []
    for py_file in Path(directory).rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        shards = shard_file(str(py_file), source_repo)
        all_shards.extend(shards)
    return all_shards


def shard_to_dict(shard: ShardMetadata) -> Dict[str, Any]:
    return asdict(shard)
