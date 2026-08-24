"""CodeBreaker-style Python code analyzer using NVIDIA Nemotron API.

Converts the TypeScript CodeBreaker logic into pure Python, integrating
with PyShard-P9's AST sharding pipeline to produce educational code guides
and architectural breakdowns.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pyshard.agent.adapters import OpenAIAdapter

__all__ = [
    "AnalyzerError",
    "CodeAnalyzer",
    "GuideBreakdown",
    "KeyConcept",
    "FileStructureItem",
    "ExecutionStep",
    "StarterTemplate",
    "QuizQuestion",
    "CommonPitfall",
]


class AnalyzerError(Exception):
    """Raised when code analysis fails."""
    pass


@dataclass
class KeyConcept:
    title: str
    explanation: str
    codeSnippet: Optional[str] = None
    analogy: str = ""


@dataclass
class FileStructureItem:
    path: str
    description: str
    importance: str = "medium"


@dataclass
class ExecutionStep:
    stepNumber: int
    title: str
    description: str
    codeExample: Optional[str] = None


@dataclass
class StarterTemplate:
    title: str
    fileName: str
    code: str
    explanation: str
    runInstructions: str


@dataclass
class QuizQuestion:
    id: str
    question: str
    options: List[str]
    answerIndex: int
    explanation: str


@dataclass
class CommonPitfall:
    pitfall: str
    solution: str


@dataclass
class GuideBreakdown:
    repoName: str
    repoUrl: Optional[str] = None
    tagline: str = ""
    language: str = "Python"
    category: str = "Utility"
    difficulty: str = "Beginner"
    summary: str = ""
    architectureOverview: str = ""
    keyConcepts: List[KeyConcept] = field(default_factory=list)
    fileStructure: List[FileStructureItem] = field(default_factory=list)
    executionSteps: List[ExecutionStep] = field(default_factory=list)
    starterTemplate: Optional[StarterTemplate] = None
    quiz: List[QuizQuestion] = field(default_factory=list)
    commonPitfalls: List[CommonPitfall] = field(default_factory=list)


class CodeAnalyzer:
    """Pure-Python code analyzer using NVIDIA Nemotron API.

    Mirrors CodeBreaker's Gemini-based analysis pipeline but uses
    NVIDIA's Nemotron model via OpenAI-compatible endpoint.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://integrate.api.nvidia.com/v1"):
        key = api_key or os.environ.get("NVIDIA_API_KEY", "")
        if not key:
            raise AnalyzerError("NVIDIA_API_KEY is required")
        self.client = OpenAIAdapter(api_key=key, base_url=base_url, model="nemotron-3.5-lightning-30b-a3b")

    def _call_model(self, prompt: str, system_instruction: str, response_schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt},
        ]

        payload: Dict[str, Any] = {
            "model": self.client.model,
            "messages": messages,
            "temperature": 0.7,
            "top_p": 0.95,
            "max_tokens": 16384,
        }

        if response_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "guide_breakdown",
                    "schema": response_schema,
                },
            }

        try:
            result = self.client._request("chat/completions", payload)
            content = result["choices"][0]["message"]["content"]
            if not content:
                raise AnalyzerError("Empty response from model")
            text = content.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise AnalyzerError(f"Failed to parse model response as JSON: {e}")
        except Exception as e:
            raise AnalyzerError(f"Model call failed: {e}")

    def analyze_repo(self, repo_url: str, user_instructions: Optional[str] = None) -> GuideBreakdown:
        """Analyze a GitHub repository and produce a CodeBreaker-style guide breakdown.

        Uses AST sharding metadata to ground the analysis in actual code structure.
        """
        from pyshard.ingestion.clone_engine import _clone_repo
        from pyshard.analysis.ast_sharder import shard_directory
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_clone_repo(repo_url, "/tmp/pyshard_analyzer_repo", shallow=True))
        finally:
            loop.close()

        if result.status != "cloned":
            raise AnalyzerError(f"Failed to clone repo: {result.error}")

        shards = shard_directory(result.local_path, repo_url)

        shard_summary = []
        for s in shards[:50]:
            shard_summary.append({
                "name": s.name,
                "type": s.shard_type,
                "category": s.category,
                "complexity": s.cyclomatic_complexity,
                "description": s.description,
                "imports": s.import_dependencies[:5],
            })

        prompt = f"""
You are CodeBreaker, an expert open-source code educator.
Target Subject: Repository URL: {repo_url}
{user_instructions or ''}

Analyze this project/code and generate a comprehensive, highly educational beginner-friendly guide breakdown JSON.
Ensure explanations use simple analogies, step-by-step logic, key file structures, practical starter templates, and interactive quiz questions.

Extracted shard metadata for grounding:
{json.dumps(shard_summary, indent=2)}

Produce output matching this exact schema:
{{
  "repoName": "string",
  "repoUrl": "string",
  "tagline": "string",
  "language": "string",
  "category": "string",
  "difficulty": "string",
  "summary": "string",
  "architectureOverview": "string",
  "keyConcepts": [{{"title": "string", "explanation": "string", "codeSnippet": "string?", "analogy": "string"}}],
  "fileStructure": [{{"path": "string", "description": "string", "importance": "high|medium|low"}}],
  "executionSteps": [{{"stepNumber": 1, "title": "string", "description": "string", "codeExample": "string?"}}],
  "starterTemplate": {{"title": "string", "fileName": "string", "code": "string", "explanation": "string", "runInstructions": "string"}},
  "quiz": [{{"id": "string", "question": "string", "options": ["string"], "answerIndex": 0, "explanation": "string"}}],
  "commonPitfalls": [{{"pitfall": "string", "solution": "string"}}]
}}
"""
        schema = {
            "type": "object",
            "properties": {
                "repoName": {"type": "string"},
                "repoUrl": {"type": "string"},
                "tagline": {"type": "string"},
                "language": {"type": "string"},
                "category": {"type": "string"},
                "difficulty": {"type": "string"},
                "summary": {"type": "string"},
                "architectureOverview": {"type": "string"},
                "keyConcepts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "explanation": {"type": "string"},
                            "codeSnippet": {"type": "string"},
                            "analogy": {"type": "string"},
                        },
                        "required": ["title", "explanation", "analogy"],
                    },
                },
                "fileStructure": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "description": {"type": "string"},
                            "importance": {"type": "string"},
                        },
                        "required": ["path", "description", "importance"],
                    },
                },
                "executionSteps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "stepNumber": {"type": "integer"},
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "codeExample": {"type": "string"},
                        },
                        "required": ["stepNumber", "title", "description"],
                    },
                },
                "starterTemplate": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "fileName": {"type": "string"},
                        "code": {"type": "string"},
                        "explanation": {"type": "string"},
                        "runInstructions": {"type": "string"},
                    },
                    "required": ["title", "fileName", "code", "explanation", "runInstructions"],
                },
                "quiz": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "question": {"type": "string"},
                            "options": {"type": "array", "items": {"type": "string"}},
                            "answerIndex": {"type": "integer"},
                            "explanation": {"type": "string"},
                        },
                        "required": ["id", "question", "options", "answerIndex", "explanation"],
                    },
                },
                "commonPitfalls": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "pitfall": {"type": "string"},
                            "solution": {"type": "string"},
                        },
                        "required": ["pitfall", "solution"],
                    },
                },
            },
            "required": [
                "repoName", "tagline", "language", "category", "difficulty",
                "summary", "architectureOverview", "keyConcepts", "fileStructure",
                "executionSteps", "starterTemplate", "quiz", "commonPitfalls",
            ],
        }

        data = self._call_model(prompt, "You are CodeBreaker, an elite software architecture tutor. Output strictly JSON matching the required guide breakdown schema without markdown codeblocks.", response_schema=schema)

        return GuideBreakdown(
            repoName=data.get("repoName", repo_url),
            repoUrl=data.get("repoUrl", repo_url),
            tagline=data.get("tagline", ""),
            language=data.get("language", "Python"),
            category=data.get("category", "Utility"),
            difficulty=data.get("difficulty", "Beginner"),
            summary=data.get("summary", ""),
            architectureOverview=data.get("architectureOverview", ""),
            keyConcepts=[KeyConcept(**c) for c in data.get("keyConcepts", [])],
            fileStructure=[FileStructureItem(**f) for f in data.get("fileStructure", [])],
            executionSteps=[ExecutionStep(**e) for e in data.get("executionSteps", [])],
            starterTemplate=StarterTemplate(**data["starterTemplate"]) if data.get("starterTemplate") else None,
            quiz=[QuizQuestion(**q) for q in data.get("quiz", [])],
            commonPitfalls=[CommonPitfall(**p) for p in data.get("commonPitfalls", [])],
        )

    def analyze_code(self, code: str, language: str = "Python", user_instructions: Optional[str] = None) -> GuideBreakdown:
        """Analyze a raw code snippet and produce a guide breakdown."""
        prompt = f"""
You are CodeBreaker, an expert open-source code educator.
Target Subject: Provided Code Snippet ({language})
{user_instructions or ''}

Code Content:
```{language}
{code}
```

Analyze this code and generate a comprehensive, highly educational beginner-friendly guide breakdown JSON.
Ensure explanations use simple analogies, step-by-step logic, and practical starter templates.

Produce output matching this exact schema:
{{
  "repoName": "string",
  "tagline": "string",
  "language": "string",
  "category": "string",
  "difficulty": "string",
  "summary": "string",
  "architectureOverview": "string",
  "keyConcepts": [{{"title": "string", "explanation": "string", "codeSnippet": "string?", "analogy": "string"}}],
  "fileStructure": [{{"path": "string", "description": "string", "importance": "high|medium|low"}}],
  "executionSteps": [{{"stepNumber": 1, "title": "string", "description": "string", "codeExample": "string?"}}],
  "starterTemplate": {{"title": "string", "fileName": "string", "code": "string", "explanation": "string", "runInstructions": "string"}},
  "quiz": [{{"id": "string", "question": "string", "options": ["string"], "answerIndex": 0, "explanation": "string"}}],
  "commonPitfalls": [{{"pitfall": "string", "solution": "string"}}]
}}
"""
        schema = {
            "type": "object",
            "properties": {
                "repoName": {"type": "string"},
                "tagline": {"type": "string"},
                "language": {"type": "string"},
                "category": {"type": "string"},
                "difficulty": {"type": "string"},
                "summary": {"type": "string"},
                "architectureOverview": {"type": "string"},
                "keyConcepts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "explanation": {"type": "string"},
                            "codeSnippet": {"type": "string"},
                            "analogy": {"type": "string"},
                        },
                        "required": ["title", "explanation", "analogy"],
                    },
                },
                "fileStructure": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "description": {"type": "string"},
                            "importance": {"type": "string"},
                        },
                        "required": ["path", "description", "importance"],
                    },
                },
                "executionSteps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "stepNumber": {"type": "integer"},
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "codeExample": {"type": "string"},
                        },
                        "required": ["stepNumber", "title", "description"],
                    },
                },
                "starterTemplate": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "fileName": {"type": "string"},
                        "code": {"type": "string"},
                        "explanation": {"type": "string"},
                        "runInstructions": {"type": "string"},
                    },
                    "required": ["title", "fileName", "code", "explanation", "runInstructions"],
                },
                "quiz": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "question": {"type": "string"},
                            "options": {"type": "array", "items": {"type": "string"}},
                            "answerIndex": {"type": "integer"},
                            "explanation": {"type": "string"},
                        },
                        "required": ["id", "question", "options", "answerIndex", "explanation"],
                    },
                },
                "commonPitfalls": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "pitfall": {"type": "string"},
                            "solution": {"type": "string"},
                        },
                        "required": ["pitfall", "solution"],
                    },
                },
            },
            "required": [
                "repoName", "tagline", "language", "category", "difficulty",
                "summary", "architectureOverview", "keyConcepts", "fileStructure",
                "executionSteps", "starterTemplate", "quiz", "commonPitfalls",
            ],
        }

        data = self._call_model(prompt, "You are CodeBreaker, an elite software architecture tutor. Output strictly JSON matching the required guide breakdown schema without markdown codeblocks.", response_schema=schema)

        return GuideBreakdown(
            repoName=data.get("repoName", "Snippet Analysis"),
            tagline=data.get("tagline", ""),
            language=data.get("language", language),
            category=data.get("category", "Utility"),
            difficulty=data.get("difficulty", "Beginner"),
            summary=data.get("summary", ""),
            architectureOverview=data.get("architectureOverview", ""),
            keyConcepts=[KeyConcept(**c) for c in data.get("keyConcepts", [])],
            fileStructure=[FileStructureItem(**f) for f in data.get("fileStructure", [])],
            executionSteps=[ExecutionStep(**e) for e in data.get("executionSteps", [])],
            starterTemplate=StarterTemplate(**data["starterTemplate"]) if data.get("starterTemplate") else None,
            quiz=[QuizQuestion(**q) for q in data.get("quiz", [])],
            commonPitfalls=[CommonPitfall(**p) for p in data.get("commonPitfalls", [])],
        )

    def ai_tutor(self, repo_name: str, query: str, code_context: Optional[str] = None) -> str:
        """Answer a user question about the analyzed codebase."""
        prompt = f"""
You are CodeBreaker's AI Tutor.
Context Project: {repo_name}
{code_context or ''}

User Question: "{query}"

Provide a clear, engaging, friendly, and precise answer. If code is helpful, provide a short, well-commented code snippet.
"""
        result = self.client._request("chat/completions", {
            "model": self.client.model,
            "messages": [
                {"role": "system", "content": "You are an expert, encouraging code teacher. Explain concepts clearly, using formatting like markdown bolding and code blocks when helpful."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "top_p": 0.95,
            "max_tokens": 4096,
        })
        return result["choices"][0]["message"]["content"]

    def generate_template(self, project_type: str, language: str, features: List[str]) -> StarterTemplate:
        """Generate a beginner-friendly starter template."""
        prompt = f"""
Generate a beginner-friendly starter template for a {project_type} project in {language}.
Included key features: {', '.join(features)}.

Provide:
1. Title
2. Main file name (e.g. index.ts, main.py, main.rs)
3. Full clean code boilerplate
4. Detailed explanation of key parts
5. Step-by-step instructions on how to install & run it locally
"""
        schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "fileName": {"type": "string"},
                "code": {"type": "string"},
                "explanation": {"type": "string"},
                "runInstructions": {"type": "string"},
            },
            "required": ["title", "fileName", "code", "explanation", "runInstructions"],
        }

        data = self._call_model(
            prompt,
            "You are a code scaffolding expert. Output strictly JSON matching the required template schema.",
            response_schema=schema,
        )
        return StarterTemplate(
            title=data["title"],
            fileName=data["fileName"],
            code=data["code"],
            explanation=data["explanation"],
            runInstructions=data["runInstructions"],
        )
