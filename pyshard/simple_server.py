"""Simple HTTP server for PyShard-P9 interactive UI (no external deps required)."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from urllib.parse import urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict

from pyshard.agent import Agent, AgentConfig, InMemoryMemory, OpenAIAdapter, Role, ToolRegistry, tool
from pyshard.analyzer import CodeAnalyzer, GuideBreakdown
from pyshard.filestore.metadata import ShardStore
from pyshard.ingestion.clone_engine import ingest_repos
from pyshard.synthesizer import Synthesizer

SANDBOX_DIR = Path(".pyshard_sandbox")
FILESTORE_DIR = Path(".pyshard_filestore")
OUTPUT_DIR = Path(".pyshard_output")
SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
FILESTORE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

_store = ShardStore(root=str(FILESTORE_DIR))
_analyzer: CodeAnalyzer | None = None
_synthesizer: Synthesizer | None = None


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


class PyShardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, status: int, data: Any):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/health":
            self._send_json(200, {"status": "ok", "timestamp": "2026-08-24T00:50:53Z"})
            return
        if self.path.startswith("/api/shards"):
            qs = urlparse(self.path).query
            params = dict(p.split("=") for p in qs.split("&") if "=" in p) if qs else {}
            shards = _store.query(category=params.get("category"), source_repo=params.get("repo"))
            self._send_json(200, {
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
            })
            return
        self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        body = self._read_body()

        if self.path == "/api/ingest":
            import asyncio
            repo_urls = body.get("repo_urls", [])
            shallow = body.get("shallow", True)
            try:
                results = asyncio.run(ingest_repos(repo_urls, str(SANDBOX_DIR), shallow=shallow))
                self._send_json(200, {
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
                })
            except Exception as e:
                self._send_json(500, {"detail": str(e)})
            return

        if self.path == "/api/shard":
            try:
                from pyshard.analysis.ast_sharder import shard_directory
                repo_dirs = [d for d in SANDBOX_DIR.iterdir() if d.is_dir() and (d / ".git").exists()]
                if not repo_dirs:
                    self._send_json(400, {"detail": "No git repos found in sandbox"})
                    return
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
                self._send_json(200, {"status": "ok", "total_shards": total, "stats": _store.stats()})
            except Exception as e:
                self._send_json(500, {"detail": str(e)})
            return

        if self.path == "/api/analyze":
            try:
                analyzer = _get_analyzer()
                if body.get("repo_url"):
                    guide = analyzer.analyze_repo(body["repo_url"], body.get("instructions"))
                elif body.get("code"):
                    guide = analyzer.analyze_code(body["code"], body.get("language", "Python"), body.get("instructions"))
                else:
                    self._send_json(400, {"detail": "Provide repo_url or code"})
                    return
                self._send_json(200, _guide_to_dict(guide))
            except Exception as e:
                self._send_json(500, {"detail": str(e)})
            return

        if self.path == "/api/synthesize":
            try:
                synthesizer = _get_synthesizer()
                all_shards = _store.list_shards()
                selected = [s for s in all_shards if s["shard_id"] in body.get("shard_ids", [])]
                if not selected:
                    self._send_json(400, {"detail": "No valid shards selected"})
                    return
                output_path = OUTPUT_DIR / (body.get("project_name", "synthesized_project") or "synthesized_project")
                plan = synthesizer.full_synthesis(body.get("description", ""), selected, str(output_path))
                self._send_json(200, {
                    "status": "ok",
                    "project_name": body.get("project_name"),
                    "output_path": str(output_path),
                    "summary": plan.summary,
                    "gaps": [{"type": g.gap_type, "description": g.description, "severity": g.severity} for g in plan.gaps],
                    "files": plan.generated_files,
                })
            except Exception as e:
                self._send_json(500, {"detail": str(e)})
            return

        if self.path == "/api/chat":
            try:
                analyzer = _get_analyzer()
                answer = analyzer.ai_tutor(body.get("repo_name", ""), body.get("query", ""), body.get("context"))
                self._send_json(200, {"answer": answer})
            except Exception as e:
                self._send_json(500, {"detail": str(e)})
            return

        if self.path == "/api/generate-template":
            try:
                analyzer = _get_analyzer()
                template = analyzer.generate_template(body.get("project_type", "app"), body.get("language", "Python"), body.get("features", []))
                self._send_json(200, {
                    "title": template.title,
                    "fileName": template.fileName,
                    "code": template.code,
                    "explanation": template.explanation,
                    "runInstructions": template.runInstructions,
                })
            except Exception as e:
                self._send_json(500, {"detail": str(e)})
            return

        self._send_json(404, {"error": "Not found"})


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


if __name__ == "__main__":
    import threading
    import webbrowser

    port = 8000
    server = HTTPServer(("0.0.0.0", port), PyShardHandler)
    print(f"PyShard-P9 server running on http://0.0.0.0:{port}")
    print(f"Frontend: open pyshard/web/ in browser (run 'npm run dev' from pyshard/web/)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()
