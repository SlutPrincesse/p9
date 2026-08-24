"""PyShard-P9 FastAPI backend with interactive shard synthesis pipeline."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from pyshard.agent import Agent, AgentConfig, InMemoryMemory, OpenAIAdapter, Role, ToolRegistry, tool
from pyshard.analyzer import CodeAnalyzer, GuideBreakdown
from pyshard.filestore.metadata import ShardStore
from pyshard.ingestion.clone_engine import ingest_repos
from pyshard.synthesizer import Synthesizer

app = FastAPI(title="PyShard-P9", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────── Request/Response Models ───────────────────────────

class IngestRequest(BaseModel):
    repo_urls: List[str]
    shallow: bool = True

class AnalyzeRequest(BaseModel):
    repo_url: Optional[str] = None
    code: Optional[str] = None
    language: str = "Python"
    instructions: Optional[str] = None

class SynthesizeRequest(BaseModel):
    shard_ids: List[str]
    description: str
    project_name: str = "synthesized_project"

class ChatRequest(BaseModel):
    repo_name: str
    query: str
    context: Optional[str] = None

class TemplateRequest(BaseModel):
    project_type: str
    language: str
    features: List[str]

# ─────────────────────────── State ───────────────────────────

SANDBOX_DIR = Path(".pyshard_sandbox")
FILESTORE_DIR = Path(".pyshard_filestore")
OUTPUT_DIR = Path(".pyshard_output")
SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
FILESTORE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

_store = ShardStore(root=str(FILESTORE_DIR))
_analyzer: Optional[CodeAnalyzer] = None
_synthesizer: Optional[Synthesizer] = None


def _get_analyzer() -> CodeAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = CodeAnalyzer()
    return _analyzer


def _get_synthesizer() -> Synthesizer:
    global _synthesizer
    if _synthesizer is None:
        _synthesizer = Synthesizer()
    return _synthesizer


# ─────────────────────────── Endpoints ───────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": "2026-08-24T00:50:53Z"}


@app.post("/api/ingest")
async def ingest_repos_endpoint(req: IngestRequest):
    try:
        import asyncio
        results = await ingest_repos(req.repo_urls, str(SANDBOX_DIR), shallow=req.shallow)
        return {
            "status": "ok",
            "results": [
                {
                    "repo_url": r.repo_url,
                    "status": r.status,
                    "file_count": r.file_count,
                    "python_file_count": r.python_file_count,
                    "error": r.error,
                }
                for r in results
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/shard")
async def shard_endpoint():
    try:
        from pyshard.analysis.ast_sharder import shard_directory

        repo_dirs = [d for d in SANDBOX_DIR.iterdir() if d.is_dir() and (d / ".git").exists()]
        if not repo_dirs:
            raise HTTPException(status_code=400, detail="No git repos found in sandbox. Run /api/ingest first.")

        total = 0
        for repo_dir in repo_dirs:
            repo_name = repo_dir.name
            shards = shard_directory(str(repo_dir), source_repo=repo_name)
            for shard in shards:
                path = Path(shard.source_file)
                if not path.exists():
                    continue
                code = path.read_text(encoding="utf-8").splitlines()
                start = shard.lineno - 1
                end = shard.end_lineno
                snippet = "\n".join(code[start:end])
                _store.store_shard(
                    shard={
                        "shard_id": shard.shard_id,
                        "source_repo": shard.source_repo,
                        "source_file": shard.source_file,
                        "category": shard.category,
                        "shard_type": shard.shard_type,
                        "name": shard.name,
                        "lineno": shard.lineno,
                        "end_lineno": shard.end_lineno,
                        "cyclomatic_complexity": shard.cyclomatic_complexity,
                        "import_dependencies": shard.import_dependencies,
                        "description": shard.description,
                        "code_hash": shard.code_hash,
                    },
                    code=snippet,
                )
                total += 1

        return {"status": "ok", "total_shards": total, "stats": _store.stats()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/shards")
async def list_shards(category: Optional[str] = None, source_repo: Optional[str] = None):
    shards = _store.query(category=category, source_repo=source_repo)
    return {
        "shards": [
            {
                "shard_id": s["shard_id"],
                "name": s["name"],
                "shard_type": s["shard_type"],
                "category": s["category"],
                "source_repo": s["source_repo"],
                "cyclomatic_complexity": s["cyclomatic_complexity"],
                "import_dependencies": s["import_dependencies"],
                "description": s["description"],
            }
            for s in shards
        ]
    }


@app.post("/api/analyze")
async def analyze_endpoint(req: AnalyzeRequest):
    try:
        analyzer = _get_analyzer()
        if req.repo_url:
            guide = analyzer.analyze_repo(req.repo_url, req.instructions)
        elif req.code:
            guide = analyzer.analyze_code(req.code, req.language, req.instructions)
        else:
            raise HTTPException(status_code=400, detail="Provide repo_url or code")
        return _guide_to_dict(guide)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/synthesize")
async def synthesize_endpoint(req: SynthesizeRequest):
    try:
        synthesizer = _get_synthesizer()
        all_shards = _store.list_shards()
        selected = [s for s in all_shards if s["shard_id"] in req.shard_ids]
        if not selected:
            raise HTTPException(status_code=400, detail="No valid shards selected")

        output_path = OUTPUT_DIR / req.project_name
        plan = synthesizer.full_synthesis(req.description, selected, str(output_path))

        return {
            "status": "ok",
            "project_name": req.project_name,
            "output_path": str(output_path),
            "summary": plan.summary,
            "gaps": [
                {
                    "type": g.gap_type,
                    "description": g.description,
                    "severity": g.severity,
                }
                for g in plan.gaps
            ],
            "files": plan.generated_files,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    try:
        analyzer = _get_analyzer()
        answer = analyzer.ai_tutor(req.repo_name, req.query, req.context)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate-template")
async def generate_template_endpoint(req: TemplateRequest):
    try:
        analyzer = _get_analyzer()
        template = analyzer.generate_template(req.project_type, req.language, req.features)
        return {
            "title": template.title,
            "fileName": template.fileName,
            "code": template.code,
            "explanation": template.explanation,
            "runInstructions": template.runInstructions,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/output/{project_name}/{file_path:path}")
async def serve_output_file(project_name: str, file_path: str):
    target = OUTPUT_DIR / project_name / file_path
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(target))


def _guide_to_dict(g: GuideBreakdown) -> Dict[str, Any]:
    return {
        "repoName": g.repoName,
        "repoUrl": g.repoUrl,
        "tagline": g.tagline,
        "language": g.language,
        "category": g.category,
        "difficulty": g.difficulty,
        "summary": g.summary,
        "architectureOverview": g.architectureOverview,
        "keyConcepts": [
            {"title": c.title, "explanation": c.explanation, "codeSnippet": c.codeSnippet, "analogy": c.analogy}
            for c in g.keyConcepts
        ],
        "fileStructure": [
            {"path": f.path, "description": f.description, "importance": f.importance}
            for f in g.fileStructure
        ],
        "executionSteps": [
            {"stepNumber": s.stepNumber, "title": s.title, "description": s.description, "codeExample": s.codeExample}
            for s in g.executionSteps
        ],
        "starterTemplate": {
            "title": g.starterTemplate.title,
            "fileName": g.starterTemplate.fileName,
            "code": g.starterTemplate.code,
            "explanation": g.starterTemplate.explanation,
            "runInstructions": g.starterTemplate.runInstructions,
        } if g.starterTemplate else None,
        "quiz": [
            {
                "id": q.id,
                "question": q.question,
                "options": q.options,
                "answerIndex": q.answerIndex,
                "explanation": q.explanation,
            }
            for q in g.quiz
        ],
        "commonPitfalls": [
            {"pitfall": p.pitfall, "solution": p.solution} for p in g.commonPitfalls
        ],
    }
