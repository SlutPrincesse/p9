"""WebToApp compatibility layer for PyShard-P9.

Provides:
- Kotlin/Java basic sharding (regex-based class/function extraction)
- WebToApp module manifest generation
- Registry entry generation
- ApkConfig JSON synthesis
- Module package (.wtamod) generation
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


# ─────────────────────────── Kotlin/Java Sharding ───────────────────────────

@dataclass
class KotlinShard:
    name: str
    shard_type: str  # class, function, property, object
    package: str
    imports: List[str]
    lineno: int
    end_lineno: int
    code: str
    description: str
    category: str = "android"
    source_file: str = ""
    source_repo: str = ""
    cyclomatic_complexity: int = 1


def _detect_package(source: str) -> str:
    m = re.search(r"package\s+([\w.]+)", source)
    return m.group(1) if m else ""


def _detect_imports(source: str) -> List[str]:
    return re.findall(r"import\s+([\w.]+)", source)


def _infer_category(file_path: str, code: str) -> str:
    path_str = str(file_path).lower()
    code_lower = code.lower()

    if any(k in path_str for k in ["extension", "module", "builtin"]):
        return "extension"
    if any(k in path_str for k in ["webview", "shell"]):
        return "webview"
    if any(k in path_str for k in ["config", "model", "data"]):
        return "config"
    if any(k in path_str for k in ["agent", "ai", "llm"]):
        return "agent"
    if any(k in path_str for k in ["network", "proxy", "dns"]):
        return "network"
    if any(k in path_str for k in ["ui", "compose", "activity"]):
        return "ui"
    if any(k in code_lower for k in ["@composable", "androidview", "webview"]):
        return "ui"
    if any(k in code_lower for k in ["class", "fun ", "object "]):
        return "utility"
    return "android"


def shard_kotlin_file(file_path: str, source_repo: str = "web-to-app") -> List[KotlinShard]:
    path = Path(file_path)
    if not path.suffix in (".kt", ".java"):
        return []

    try:
        source = path.read_text(encoding="utf-8")
    except Exception:
        return []

    lines = source.splitlines()
    package = _detect_package(source)
    imports = _detect_imports(source)
    shards: List[KotlinShard] = []

    # Match Kotlin class declarations
    class_pattern = re.compile(
        r"^(public\s+)?(abstract\s+)?(data\s+)?class\s+(\w+)",
        re.MULTILINE
    )
    for m in class_pattern.finditer(source):
        name = m.group(4)
        start = source[:m.start()].count("\n") + 1
        # Find end of class (simplified: next class/object/fun at same or lower indent)
        end = len(lines)
        for i in range(start, len(lines)):
            line = lines[i]
            if line.strip() and not line.startswith(" ") and not line.startswith("\t") and i > start:
                end = i
                break
        code = "\n".join(lines[start - 1:end])
        complexity = 1
        for child_line in code.splitlines():
            if re.search(r"\b(if|while|for|when|catch|try)\b", child_line):
                complexity += 1
        shards.append(KotlinShard(
            name=name,
            shard_type="class",
            package=package,
            imports=imports,
            lineno=start,
            end_lineno=end,
            code=code,
            description=f"Kotlin class '{name}' from {package}",
            category=_infer_category(file_path, code),
            source_file=str(path),
            source_repo=source_repo,
            cyclomatic_complexity=complexity,
        ))

    # Match top-level functions
    func_pattern = re.compile(
        r"^(public\s+)?(suspend\s+)?fun\s+(\w+)\s*\(",
        re.MULTILINE
    )
    for m in func_pattern.finditer(source):
        name = m.group(3)
        start = source[:m.start()].count("\n") + 1
        end = len(lines)
        for i in range(start, len(lines)):
            line = lines[i]
            if line.strip() and not line.startswith(" ") and not line.startswith("\t") and i > start:
                end = i
                break
        code = "\n".join(lines[start - 1:end])
        complexity = 1
        for child_line in code.splitlines():
            if re.search(r"\b(if|while|for|when|catch|try)\b", child_line):
                complexity += 1
        shards.append(KotlinShard(
            name=name,
            shard_type="function",
            package=package,
            imports=imports,
            lineno=start,
            end_lineno=end,
            code=code,
            description=f"Kotlin function '{name}' from {package}",
            category=_infer_category(file_path, code),
            source_file=str(path),
            source_repo=source_repo,
            cyclomatic_complexity=complexity,
        ))

    return shards


def shard_kotlin_directory(directory: str, source_repo: str = "web-to-app") -> List[KotlinShard]:
    all_shards: List[KotlinShard] = []
    for f in Path(directory).rglob("*.kt"):
        all_shards.extend(shard_kotlin_file(str(f), source_repo))
    return all_shards


# ─────────────────────────── WebToApp Module Generation ───────────────────────────

@dataclass
class WebToAppModule:
    id: str
    name: str
    description: str
    version: str = "1.0.0"
    category: str = "OTHER"
    tags: List[str] = field(default_factory=list)
    author_name: str = "PyShard-P9"
    author_url: str = ""
    run_at: str = "DOCUMENT_END"
    permissions: List[str] = field(default_factory=list)
    url_matches: List[Dict[str, Any]] = field(default_factory=lambda: [{"pattern": "*", "isRegex": False, "exclude": False}])
    has_css: bool = False
    main_js: str = ""
    style_css: str = ""
    config_items: List[Dict[str, Any]] = field(default_factory=list)
    changelog: str = "Initial release generated by PyShard-P9."

    def to_module_json(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "version": {
                "code": 1,
                "name": self.version,
                "changelog": self.changelog,
            },
            "name": self.name,
            "description": self.description,
            "icon": "package",
            "category": self.category,
            "tags": self.tags,
            "author": {
                "name": self.author_name,
                "url": self.author_url,
            },
            "runAt": self.run_at,
            "permissions": self.permissions,
            "urlMatches": self.url_matches,
            "hasCss": self.has_css,
            "configItems": self.config_items,
            "sourceType": "CUSTOM",
        }

    def to_registry_entry(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "path": self.id,
            "name": self.name,
            "description": self.description,
            "icon": "auto_awesome",
            "category": self.category,
            "tags": self.tags,
            "version": self.version,
            "minAppVersion": 33,
            "author": {
                "name": self.author_name,
                "url": self.author_url,
            },
            "runAt": self.run_at,
            "permissions": self.permissions,
            "urlMatches": self.url_matches,
            "hasCss": self.has_css,
        }

    def write_module_package(self, output_dir: str) -> str:
        base = Path(output_dir) / self.id
        base.mkdir(parents=True, exist_ok=True)

        with open(base / "module.json", "w", encoding="utf-8") as f:
            json.dump(self.to_module_json(), f, indent=2)

        with open(base / "main.js", "w", encoding="utf-8") as f:
            f.write(self.main_js)

        if self.has_css:
            with open(base / "style.css", "w", encoding="utf-8") as f:
                f.write(self.style_css)

        return str(base)


def generate_wtamod(module: WebToAppModule, output_path: str) -> str:
    """Generate a .wtamod (single-module package) file."""
    package = {
        "schema": 1,
        "module": module.to_module_json(),
        "files": {
            "main.js": module.main_js,
        },
    }
    if module.has_css:
        package["files"]["style.css"] = module.style_css

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path), "w", encoding="utf-8") as f:
        json.dump(package, f, indent=2)
    return str(path)


# ─────────────────────────── ApkConfig Synthesis ───────────────────────────

@dataclass
class ApkConfigSynthesis:
    app_name: str
    package_name: str
    target_url: str = ""
    app_type: str = "WEB"
    version_code: int = 1
    version_name: str = "1.0.0"
    theme_type: str = "AURORA"
    dark_mode: str = "SYSTEM"
    language: str = "ENGLISH"
    engine_type: str = "SYSTEM_WEBVIEW"
    extension_enabled: bool = False
    extension_module_ids: List[str] = field(default_factory=list)
    web_view_config: Dict[str, Any] = field(default_factory=dict)
    media_config: Dict[str, Any] = field(default_factory=dict)
    html_config: Dict[str, Any] = field(default_factory=dict)
    gallery_config: Dict[str, Any] = field(default_factory=dict)
    wordpress_config: Dict[str, Any] = field(default_factory=dict)
    nodejs_config: Dict[str, Any] = field(default_factory=dict)
    php_app_config: Dict[str, Any] = field(default_factory=dict)
    python_app_config: Dict[str, Any] = field(default_factory=dict)
    go_app_config: Dict[str, Any] = field(default_factory=dict)
    multi_web_config: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> Dict[str, Any]:
        return {
            "schemaVersion": 1,
            "appName": self.app_name,
            "packageName": self.package_name,
            "targetUrl": self.target_url,
            "appType": self.app_type,
            "versionCode": self.version_code,
            "versionName": self.version_name,
            "themeType": self.theme_type,
            "darkMode": self.dark_mode,
            "language": self.language,
            "engineType": self.engine_type,
            "htmlUsesFileScheme": False,
            "extensionEnabled": self.extension_enabled,
            "extensionModuleIds": self.extension_module_ids,
            "webViewConfig": self.web_view_config,
            "mediaConfig": self.media_config,
            "htmlConfig": self.html_config,
            "galleryConfig": self.gallery_config,
            "wordpressConfig": self.wordpress_config,
            "nodejsConfig": self.nodejs_config,
            "phpAppConfig": self.php_app_config,
            "pythonAppConfig": self.python_app_config,
            "goAppConfig": self.go_app_config,
            "multiWebConfig": self.multi_web_config,
        }

    def write(self, output_path: str) -> str:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(path), "w", encoding="utf-8") as f:
            json.dump(self.to_json(), f, indent=2)
        return str(path)


# ─────────────────────────── Compatibility Registry ───────────────────────────

class WebToAppCompatibility:
    """High-level API for PyShard-P9 ↔ WebToApp compatibility."""

    @staticmethod
    def shard_repo(directory: str, source_repo: str = "web-to-app") -> List[Dict[str, Any]]:
        shards = shard_kotlin_directory(directory, source_repo)
        return [asdict(s) for s in shards]

    @staticmethod
    def generate_module_from_shard(shard: Dict[str, Any], module_name: Optional[str] = None) -> WebToAppModule:
        name = module_name or shard.get("name", "unnamed")
        module_id = f"wta-pyshard-{name.lower().replace('_', '-')}"
        return WebToAppModule(
            id=module_id,
            name=name,
            description=shard.get("description", f"Generated module from {name}"),
            category="DEVELOPER",
            tags=["pyshard", "generated"],
            main_js=f"// Auto-generated by PyShard-P9 from shard {shard.get('shard_id', '?')}\nconsole.log('Module {name} loaded');",
        )

    @staticmethod
    def generate_registry(modules: List[WebToAppModule]) -> Dict[str, Any]:
        return {
            "schema": 1,
            "updatedAt": "2026-08-24T00:00:00Z",
            "modules": [m.to_registry_entry() for m in modules],
        }

    @staticmethod
    def generate_apk_config(app_name: str, package_name: str, target_url: str = "") -> ApkConfigSynthesis:
        return ApkConfigSynthesis(
            app_name=app_name,
            package_name=package_name,
            target_url=target_url,
        )
