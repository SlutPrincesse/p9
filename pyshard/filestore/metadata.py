"""Shard filestore and metadata schema for PyShard-P9."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ShardStore:
    root: str

    def __post_init__(self):
        Path(self.root).mkdir(parents=True, exist_ok=True)
        Path(os.path.join(self.root, "shards", "functions")).mkdir(parents=True, exist_ok=True)
        Path(os.path.join(self.root, "shards", "classes")).mkdir(parents=True, exist_ok=True)
        Path(os.path.join(self.root, "shards", "modules")).mkdir(parents=True, exist_ok=True)

    def _shard_path(self, shard_type: str, shard_id: str) -> str:
        mapping = {"function": "functions", "class": "classes", "module": "modules"}
        dir_name = mapping.get(shard_type, shard_type)
        return os.path.join(self.root, "shards", dir_name, f"{shard_id}.json")

    def store_shard(self, shard: Dict[str, Any], code: str) -> str:
        shard_type = shard["shard_type"]
        shard_id = shard["shard_id"]
        shard_path = self._shard_path(shard_type, shard_id)

        payload = {
            "metadata": shard,
            "code": code,
        }

        with open(shard_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        return shard_path

    def load_shard(self, shard_type: str, shard_id: str) -> Optional[Dict[str, Any]]:
        shard_path = self._shard_path(shard_type, shard_id)
        if not os.path.exists(shard_path):
            return None
        with open(shard_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_shards(self, shard_type: Optional[str] = None) -> List[Dict[str, Any]]:
        base = os.path.join(self.root, "shards")
        results = []

        types = [shard_type] if shard_type else ["functions", "classes", "modules"]
        for stype in types:
            shard_dir = os.path.join(base, stype)
            if not os.path.isdir(shard_dir):
                continue
            for fname in os.listdir(shard_dir):
                if fname.endswith(".json"):
                    fpath = os.path.join(shard_dir, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            results.append(data["metadata"])
                    except Exception:
                        continue
        return results

    def query(self, category: Optional[str] = None, source_repo: Optional[str] = None) -> List[Dict[str, Any]]:
        shards = self.list_shards()
        filtered = []
        for s in shards:
            if category and s.get("category") != category:
                continue
            if source_repo and s.get("source_repo") != source_repo:
                continue
            filtered.append(s)
        return filtered

    def stats(self) -> Dict[str, Any]:
        all_shards = self.list_shards()
        by_type: Dict[str, int] = {}
        by_category: Dict[str, int] = {}
        by_repo: Dict[str, int] = {}

        for s in all_shards:
            stype = s.get("shard_type", "unknown")
            cat = s.get("category", "unknown")
            repo = s.get("source_repo", "unknown")
            by_type[stype] = by_type.get(stype, 0) + 1
            by_category[cat] = by_category.get(cat, 0) + 1
            by_repo[repo] = by_repo.get(repo, 0) + 1

        return {
            "total_shards": len(all_shards),
            "by_type": by_type,
            "by_category": by_category,
            "by_repo": by_repo,
        }
