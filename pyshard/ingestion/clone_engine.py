"""Multi-repo ingestion engine using asynchronous Git worker pool."""

from __future__ import annotations

import asyncio
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class RepoIngestionResult:
    repo_url: str
    local_path: str
    status: str
    file_count: int = 0
    python_file_count: int = 0
    error: Optional[str] = None


async def _clone_repo(repo_url: str, target_dir: str, shallow: bool = True) -> RepoIngestionResult:
    target_path = Path(target_dir)

    if target_path.exists():
        shutil.rmtree(target_path)

    target_path.mkdir(parents=True, exist_ok=True)

    cmd = ["git", "clone", "--depth=1" if shallow else "", repo_url, str(target_path)]
    cmd = [c for c in cmd if c]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        return RepoIngestionResult(
            repo_url=repo_url,
            local_path=str(target_path),
            status="failed",
            error=stderr.decode().strip(),
        )

    py_files = list(target_path.rglob("*.py"))
    all_files = [f for f in target_path.rglob("*") if f.is_file()]

    return RepoIngestionResult(
        repo_url=repo_url,
        local_path=str(target_path),
        status="cloned",
        file_count=len(all_files),
        python_file_count=len(py_files),
    )


async def ingest_repos(repo_urls: List[str], sandbox_dir: str, shallow: bool = True) -> List[RepoIngestionResult]:
    Path(sandbox_dir).mkdir(parents=True, exist_ok=True)

    tasks = []
    for idx, url in enumerate(repo_urls):
        target = os.path.join(sandbox_dir, f"repo_{idx}")
        tasks.append(_clone_repo(url, target, shallow=shallow))

    return await asyncio.gather(*tasks)
