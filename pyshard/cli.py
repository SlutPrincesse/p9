"""PyShard-P9 CLI entry point."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from pyshard.agent import Agent, AgentConfig, InMemoryMemory, OpenAIAdapter, Role, ToolRegistry, tool
from pyshard.analysis.ast_sharder import shard_directory
from pyshard.filestore.metadata import ShardStore
from pyshard.ingestion.clone_engine import ingest_repos


def cmd_agent_demo(args: argparse.Namespace) -> None:
    """Run a quick agent demo using the integrated tiny-agent framework."""
    print("[agent] Starting PyShard-P9 agent demo...")

    @tool()
    def add(a: float, b: float) -> float:
        """Add two numbers."""
        return a + b

    @tool()
    def multiply(a: float, b: float) -> float:
        """Multiply two numbers."""
        return a * b

    @tool()
    def power(base: float, exponent: float) -> float:
        """Raise base to the power of exponent."""
        return base ** exponent

    tools = ToolRegistry()
    tools.register(add._tiny_agent_tool)
    tools.register(multiply._tiny_agent_tool)
    tools.register(power._tiny_agent_tool)

    agent = Agent(
        llm=OpenAIAdapter(api_key=args.api_key or "demo"),
        tools=tools,
        memory=InMemoryMemory(),
        config=AgentConfig(
            system_prompt="You are a calculator agent. Use tools to solve math problems.",
            enable_planning=False,
            max_iterations=5,
        ),
        name="CalculatorAgent",
    )

    queries = [
        "What is 15 + 27?",
        "What is 3 * 4?",
        "What is 2 to the power of 10?",
    ]

    for q in queries:
        print(f"\n  Q: {q}")
        try:
            result = agent.run(q)
            print(f"  A: {result}")
        except Exception as e:
            print(f"  Error: {e}")


def cmd_ingest(args: argparse.Namespace) -> None:
    repos = args.repos
    sandbox = args.sandbox
    store = args.store

    print(f"[ingest] Cloning {len(repos)} repos into {sandbox}...")
    results = asyncio.run(ingest_repos(repos, sandbox, shallow=not args.full))

    for r in results:
        if r.status == "cloned":
            print(f"  [ok] {r.repo_url} -> {r.local_path} ({r.python_file_count} .py files)")
        else:
            print(f"  [fail] {r.repo_url}: {r.error}", file=sys.stderr)


def cmd_shard(args: argparse.Namespace) -> None:
    sandbox = args.sandbox
    store_root = args.store

    store = ShardStore(root=store_root)

    repo_dirs = [d for d in Path(sandbox).iterdir() if d.is_dir() and (d / ".git").exists()]
    if not repo_dirs:
        print(f"No git repos found in {sandbox}", file=sys.stderr)
        sys.exit(1)

    total = 0
    for repo_dir in repo_dirs:
        repo_name = repo_dir.name
        shards = shard_directory(str(repo_dir), source_repo=repo_name)
        for shard in shards:
            code = Path(shard.source_file).read_text(encoding="utf-8").splitlines()
            start = shard.lineno - 1
            end = shard.end_lineno
            snippet = "\n".join(code[start:end])
            store.store_shard(
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
        print(f"  [shard] {repo_name}: {len(shards)} shards extracted")

    print(f"[done] Total shards stored: {total}")
    stats = store.stats()
    print(json.dumps(stats, indent=2))


def cmd_list(args: argparse.Namespace) -> None:
    store = ShardStore(root=args.store)
    shards = store.query(category=args.category, source_repo=args.repo)

    for s in shards:
        print(f"{s['shard_id']} | {s['shard_type']:8} | {s['name']:30} | {s['category']:15} | {s['source_repo']}")


def cmd_stats(args: argparse.Namespace) -> None:
    store = ShardStore(root=args.store)
    stats = store.stats()
    print(json.dumps(stats, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="pyshard", description="PyShard-P9: Agent framework + AST sharding")
    subparsers = parser.add_subparsers(dest="command")

    p_agent = subparsers.add_parser("agent", help="Run integrated agent demo")
    p_agent.add_argument("--api-key", help="OpenAI API key (optional for demo)")
    p_agent.add_argument("--sandbox", default=".pyshard/sandbox")
    p_agent.add_argument("--store", default=".pyshard/filestore")

    p_ingest = subparsers.add_parser("ingest", help="Clone repos into sandbox")
    p_ingest.add_argument("repos", nargs="+", help="GitHub repo URLs")
    p_ingest.add_argument("--sandbox", default=".pyshard/sandbox", help="Sandbox directory")
    p_ingest.add_argument("--store", default=".pyshard/filestore", help="Filestore root")
    p_ingest.add_argument("--full", action="store_true", help="Full clone (not shallow)")

    p_shard = subparsers.add_parser("shard", help="AST-shard Python files in sandbox")
    p_shard.add_argument("--sandbox", default=".pyshard/sandbox", help="Sandbox directory")
    p_shard.add_argument("--store", default=".pyshard/filestore", help="Filestore root")

    p_list = subparsers.add_parser("list", help="List stored shards")
    p_list.add_argument("--store", default=".pyshard/filestore", help="Filestore root")
    p_list.add_argument("--category", help="Filter by category")
    p_list.add_argument("--repo", help="Filter by source repo")

    p_stats = subparsers.add_parser("stats", help="Show filestore statistics")
    p_stats.add_argument("--store", default=".pyshard/filestore", help="Filestore root")

    args = parser.parse_args()
    if args.command == "agent":
        cmd_agent_demo(args)
    elif args.command == "ingest":
        cmd_ingest(args)
    elif args.command == "shard":
        cmd_shard(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "stats":
        cmd_stats(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
