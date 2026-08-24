"""PyShard-P9 synthesis engine: gap analysis, plan generation, and project scaffolding."""

from __future__ import annotations

import ast
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from pyshard.agent.adapters import OpenAIAdapter
from pyshard.filestore.metadata import ShardStore

__all__ = [
    "SynthesisError",
    "SynthesisGap",
    "SynthesisPlan",
    "Synthesizer",
]


class SynthesisError(Exception):
    """Raised when synthesis fails."""
    pass


@dataclass
class SynthesisGap:
    gap_type: str
    description: str
    severity: str
    suggested_shard_ids: List[str] = field(default_factory=list)


@dataclass
class SynthesisPlan:
    goal: str
    selected_shard_ids: List[str]
    gaps: List[SynthesisGap]
    generated_files: List[Dict[str, str]]
    summary: str


class Synthesizer:
    """Analyzes selected shards against a description, fills gaps, and generates a project."""

    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://integrate.api.nvidia.com/v1"):
        key = api_key or os.environ.get("NVIDIA_API_KEY", "")
        if not key:
            raise SynthesisError("NVIDIA_API_KEY is required")
        self.client = OpenAIAdapter(api_key=key, base_url=base_url, model="nemotron-3.5-lightning-30b-a3b")

    def analyze_gaps(self, description: str, shards: List[Dict[str, Any]]) -> List[SynthesisGap]:
        """Analyze selected shards vs description to find architectural gaps."""
        shard_summary = [
            {
                "id": s.get("shard_id"),
                "name": s.get("name"),
                "type": s.get("shard_type"),
                "category": s.get("category"),
                "complexity": s.get("cyclomatic_complexity"),
                "imports": s.get("import_dependencies", []),
            }
            for s in shards
        ]

        prompt = f"""
You are a senior software architect. Given an app description and a list of available code shards, identify gaps in the architecture.

App Description:
{description}

Available Shards:
{json.dumps(shard_summary, indent=2)}

Identify missing components, import contradictions, type mismatches, or structural gaps.
Return JSON array:
[
  {{
    "gap_type": "missing_component|import_conflict|type_mismatch|structural_gap",
    "description": "string",
    "severity": "high|medium|low",
    "suggested_shard_ids": ["string"]
  }}
]
"""
        try:
            result = self.client._request("chat/completions", {
                "model": self.client.model,
                "messages": [
                    {"role": "system", "content": "You are an expert software architect. Output strictly JSON."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "top_p": 0.95,
                "max_tokens": 4096,
            })
            content = result["choices"][0]["message"]["content"].strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            gaps_data = json.loads(content)
            return [SynthesisGap(**g) for g in gaps_data]
        except Exception as e:
            raise SynthesisError(f"Gap analysis failed: {e}")

    def generate_plan(self, description: str, shards: List[Dict[str, Any]], gaps: List[SynthesisGap]) -> SynthesisPlan:
        """Generate a synthesis plan with file structure and implementation steps."""
        shard_summary = [
            {
                "id": s.get("shard_id"),
                "name": s.get("name"),
                "type": s.get("shard_type"),
                "category": s.get("category"),
            }
            for s in shards
        ]

        prompt = f"""
You are a senior software architect. Create a synthesis plan for building a new app.

App Description:
{description}

Selected Shards:
{json.dumps(shard_summary, indent=2)}

Identified Gaps:
{json.dumps([{"type": g.gap_type, "description": g.description, "severity": g.severity} for g in gaps], indent=2)}

Generate a synthesis plan including:
1. Project name and structure
2. List of files to create with their purposes
3. How shards map to files
4. Dependencies and imports
5. Step-by-step implementation order

Return JSON:
{{
  "project_name": "string",
  "summary": "string",
  "generated_files": [
    {{
      "path": "string",
      "purpose": "string",
      "source_shard_ids": ["string"],
      "content": "string (full file content)"
    }}
  ]
}}
"""
        try:
            result = self.client._request("chat/completions", {
                "model": self.client.model,
                "messages": [
                    {"role": "system", "content": "You are an expert software architect. Output strictly JSON."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.4,
                "top_p": 0.95,
                "max_tokens": 16384,
            })
            content = result["choices"][0]["message"]["content"].strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            plan_data = json.loads(content)

            return SynthesisPlan(
                goal=description,
                selected_shard_ids=[s.get("shard_id") for s in shards],
                gaps=gaps,
                generated_files=plan_data.get("generated_files", []),
                summary=plan_data.get("summary", ""),
            )
        except Exception as e:
            raise SynthesisError(f"Plan generation failed: {e}")

    def write_project(self, plan: SynthesisPlan, output_dir: str) -> str:
        """Write the synthesized project to disk."""
        base = Path(output_dir)
        base.mkdir(parents=True, exist_ok=True)

        for file_info in plan.generated_files:
            file_path = base / file_info["path"]
            file_path.parent.mkdir(parents=True, exist_ok=True)
            content = file_info.get("content", "")
            file_path.write_text(content, encoding="utf-8")

        return str(base)

    def full_synthesis(self, description: str, shards: List[Dict[str, Any]], output_dir: str) -> SynthesisPlan:
        """Run full synthesis pipeline: gap analysis → plan → write project."""
        gaps = self.analyze_gaps(description, shards)
        plan = self.generate_plan(description, shards, gaps)
        self.write_project(plan, output_dir)
        return plan
