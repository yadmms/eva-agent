"""项目管理模块 — 对标OpenCode项目扫描与上下文检索

提供：
1. 项目自动扫描：识别语言、框架、依赖、文件统计
2. 上下文检索：基于grep的简易版相关代码片段检索
3. 支持 Python / JavaScript / TypeScript / Go / Rust 项目自动识别
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

# ═══════════════════════════════════════════
# 语言/框架识别配置
# ═══════════════════════════════════════════

LANGUAGE_SIGNATURES = {
    "Python": {
        "extensions": {".py"},
        "configs": ["requirements.txt", "setup.py", "setup.cfg", "pyproject.toml", "Pipfile", "poetry.lock"],
        "framework_indicators": {
            "FastAPI": ["fastapi", "uvicorn"],
            "Flask": ["flask"],
            "Django": ["django"],
            "PyTorch": ["torch"],
            "TensorFlow": ["tensorflow"],
            "Streamlit": ["streamlit"],
            "Gradio": ["gradio"],
        },
    },
    "JavaScript": {
        "extensions": {".js", ".mjs", ".cjs"},
        "configs": ["package.json", "package-lock.json", "yarn.lock", ".eslintrc.js", ".eslintrc.json"],
        "framework_indicators": {
            "React": ["react", "react-dom"],
            "Vue": ["vue"],
            "Next.js": ["next"],
            "Express": ["express"],
            "Svelte": ["svelte"],
        },
    },
    "TypeScript": {
        "extensions": {".ts", ".tsx", ".mts", ".cts"},
        "configs": ["tsconfig.json", "tsconfig.build.json"],
        "framework_indicators": {
            "React": ["react", "react-dom"],
            "Next.js": ["next"],
            "NestJS": ["@nestjs/core"],
            "Angular": ["@angular/core"],
        },
    },
    "Go": {
        "extensions": {".go"},
        "configs": ["go.mod", "go.sum", "go.work"],
        "framework_indicators": {
            "Gin": ["github.com/gin-gonic/gin"],
            "Echo": ["github.com/labstack/echo"],
            "Fiber": ["github.com/gofiber/fiber"],
        },
    },
    "Rust": {
        "extensions": {".rs"},
        "configs": ["Cargo.toml", "Cargo.lock"],
        "framework_indicators": {
            "Actix": ["actix-web"],
            "Axum": ["axum"],
            "Rocket": ["rocket"],
            "Tauri": ["tauri"],
        },
    },
}

# 额外检测: Shell, Makefile, Docker 等
MISC_SIGNATURES = {
    "Docker": ["Dockerfile", "docker-compose.yml", "docker-compose.yaml", ".dockerignore"],
    "Shell": [".sh"],
    "Make": ["Makefile", "makefile", "GNUmakefile"],
    "Markdown": [".md", ".mdx"],
    "JSON/YAML": [".json", ".yaml", ".yml"],
}

# 忽略目录
IGNORE_DIRS = {
    "__pycache__", ".git", ".svn", ".hg",
    "node_modules", ".venv", "venv", ".env",
    "target", "build", "dist", ".next", ".nuxt",
    ".idea", ".vscode", ".DS_Store",
    "vendor",
}


class ProjectManager:
    """项目管理器 — 扫描、识别、检索项目上下文

    对标 OpenCode 的核心 project 功能：
    - 自动识别项目语言和框架
    - 统计文件/行数
    - 提取依赖信息
    - 基于 grep 的上下文检索
    """

    def __init__(self, root: str = "."):
        self.root = Path(root).resolve()
        self._cache: Optional[dict] = None

    # ─── 扫描 ──────────────────────────────────

    def scan_project(self, path: str = None) -> dict:
        """扫描项目目录，返回结构化摘要

        Args:
            path: 项目路径，默认使用初始化时的 root

        Returns:
            {
                "name": 项目名,
                "path": 绝对路径,
                "languages": [{语言: 文件数}],
                "frameworks": [框架名],
                "files": 总文件数,
                "total_lines": 总行数,
                "dependencies": {语言: {包名: 版本}},
                "directory_tree": 简要目录树,
                "config_files": [配置文件名],
            }
        """
        target = Path(path).resolve() if path else self.root
        if not target.is_dir():
            return {"error": f"路径不存在或不是目录: {target}"}

        # 使用缓存
        if self._cache and self._cache.get("path") == str(target):
            return self._cache

        result = {
            "name": target.name,
            "path": str(target),
            "languages": {},
            "frameworks": [],
            "files": 0,
            "total_lines": 0,
            "dependencies": {},
            "directory_tree": self._tree_snapshot(target),
            "config_files": [],
        }

        file_stats: dict[str, int] = {}      # 语言 -> 文件数
        line_stats: dict[str, int] = {}      # 语言 -> 行数
        found_frameworks: set[str] = set()
        found_configs: list[str] = []
        all_deps: dict[str, dict] = {}

        # 第一遍：收集文件统计
        for fp in target.rglob("*"):
            # 跳过忽略目录
            if any(part in IGNORE_DIRS for part in fp.parts):
                continue
            if not fp.is_file():
                continue

            suffix = fp.suffix.lower()
            rel = str(fp.relative_to(target))

            # 检测配置文件
            if fp.name in self._all_config_names():
                found_configs.append(rel)

            # 识别语言
            lang = self._detect_language_file(suffix, fp.name)
            if lang:
                file_stats[lang] = file_stats.get(lang, 0) + 1
                try:
                    lines = self._count_lines(fp)
                    line_stats[lang] = line_stats.get(lang, 0) + lines
                except Exception:
                    pass
            else:
                # 归入 "Other"
                file_stats["Other"] = file_stats.get("Other", 0) + 1

        result["languages"] = file_stats
        result["files"] = sum(file_stats.values())
        result["total_lines"] = sum(line_stats.values())
        result["config_files"] = sorted(found_configs)

        # 第二遍：检测框架 + 依赖
        for lang, sig in LANGUAGE_SIGNATURES.items():
            if lang not in file_stats:
                continue
            # 依赖文件解析
            deps = self._parse_dependencies(target, lang, sig)
            if deps:
                all_deps[lang] = deps
                # 从依赖中识别框架
                for fw_name, indicators in sig.get("framework_indicators", {}).items():
                    for ind in indicators:
                        if ind.lower() in {k.lower() for k in deps}:
                            found_frameworks.add(fw_name)

        result["dependencies"] = all_deps
        result["frameworks"] = sorted(found_frameworks)

        self._cache = result
        return result

    def summary(self, path: str = None) -> str:
        """返回人类可读的项目摘要"""
        r = self.scan_project(path)
        if "error" in r:
            return f"❌ {r['error']}"

        lines = [
            f"📁 项目: {r['name']}",
            f"📍 路径: {r['path']}",
            f"📊 文件: {r['files']} 个 | 行数: {r['total_lines']}",
            "",
        ]

        if r["languages"]:
            lines.append("**语言分布:**")
            for lang, count in sorted(r["languages"].items(), key=lambda x: -x[1]):
                lines.append(f"  - {lang}: {count} 文件")
            lines.append("")

        if r["frameworks"]:
            lines.append(f"**框架:** {', '.join(r['frameworks'])}")
            lines.append("")

        if r["dependencies"]:
            lines.append("**依赖:**")
            for lang, deps in r["dependencies"].items():
                lines.append(f"  [{lang}] {len(deps)} 个包")
                # 显示前10个
                for i, (pkg, ver) in enumerate(sorted(deps.items())):
                    if i >= 10:
                        lines.append(f"  ... 还有 {len(deps) - 10} 个")
                        break
                    lines.append(f"    - {pkg} {ver}")
            lines.append("")

        if r["config_files"]:
            lines.append(f"**配置文件:** {', '.join(r['config_files'][:10])}")
            if len(r["config_files"]) > 10:
                lines.append(f"  ... 还有 {len(r['config_files']) - 10} 个")

        return "\n".join(lines)

    # ─── 上下文检索 ──────────────────────────

    def get_context(self, question: str, max_results: int = 10) -> str:
        """基于关键词的上下文检索（简易版grep）

        从问题中提取关键词，在项目文件中搜索匹配行，
        返回相关代码片段。

        Args:
            question: 用户问题/查询
            max_results: 最多返回多少条匹配

        Returns:
            格式化的代码片段文本
        """
        proj = self.scan_project()
        if "error" in proj:
            return f"无法扫描项目: {proj['error']}"

        # 提取关键词：中英文分词简化版
        keywords = self._extract_keywords(question)
        if not keywords:
            return "无法从问题中提取有效关键词"

        results = []
        search_exts = self._searchable_extensions()

        for kw in keywords[:5]:  # 最多用5个关键词
            if len(results) >= max_results * 2:
                break
            try:
                # 用 ripgrep 如果可用，否则用 grep
                matches = self._grep(kw, self.root, search_exts, limit=5)
                for m in matches:
                    if len(results) >= max_results * 2:
                        break
                    # 去重
                    key = f"{m['file']}:{m['line']}"
                    if key not in {f"{r['file']}:{r['line']}" for r in results}:
                        results.append(m)
            except Exception:
                continue

        if not results:
            return f"在项目中未找到与 '{question[:80]}' 相关的代码"

        # 格式化输出
        lines = [f"🔍 搜索 '{question[:80]}' — 找到 {len(results)} 条匹配:\n"]
        for i, m in enumerate(results[:max_results]):
            lines.append(f"### [{i+1}] {m['file']}:{m['line']}")
            lines.append("```")
            lines.append(m["content"].rstrip())
            lines.append("```\n")

        return "\n".join(lines)

    def search_files(self, pattern: str, file_pattern: str = "*.py") -> str:
        """在项目中搜索匹配模式的文件内容

        Args:
            pattern: 搜索正则/关键词
            file_pattern: 文件名glob，如 *.py, *.rs

        Returns:
            格式化的搜索结果
        """
        matches = self._grep(pattern, self.root, {file_pattern.lstrip('*.')}, limit=20)
        if not matches:
            return f"未找到匹配 '{pattern}'"

        lines = [f"🔍 搜索 '{pattern}' — {len(matches)} 条结果:\n"]
        for m in matches[:15]:
            lines.append(f"- **{m['file']}:{m['line']}**")
            lines.append(f"  `{m['content'].strip()[:120]}`")
        if len(matches) > 15:
            lines.append(f"  ... 还有 {len(matches) - 15} 条")
        return "\n".join(lines)

    # ─── 内部方法 ─────────────────────────────

    def _detect_language_file(self, suffix: str, filename: str) -> Optional[str]:
        """根据后缀/文件名检测语言"""
        for lang, sig in LANGUAGE_SIGNATURES.items():
            if suffix in sig["extensions"]:
                return lang
        return None

    def _all_config_names(self) -> set[str]:
        """所有已知配置文件名"""
        names = set()
        for sig in LANGUAGE_SIGNATURES.values():
            names.update(sig["configs"])
        names.update(MISC_SIGNATURES.get("Docker", []))
        return names

    def _count_lines(self, fp: Path) -> int:
        """快速统计文件行数（跳过二进制）"""
        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                return sum(1 for _ in f)
        except Exception:
            return 0

    def _parse_dependencies(self, root: Path, lang: str, sig: dict) -> dict:
        """解析依赖文件"""
        deps = {}

        if lang == "Python":
            deps = self._parse_python_deps(root, sig)
        elif lang in ("JavaScript", "TypeScript"):
            deps = self._parse_node_deps(root)
        elif lang == "Go":
            deps = self._parse_go_deps(root)
        elif lang == "Rust":
            deps = self._parse_rust_deps(root)

        return deps

    def _parse_python_deps(self, root: Path, sig: dict) -> dict:
        """解析 Python 依赖"""
        deps = {}

        # requirements.txt
        req_file = root / "requirements.txt"
        if req_file.exists():
            try:
                for line in req_file.read_text().splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or line.startswith("-"):
                        continue
                    # 处理 package==version, package>=version, 等
                    match = re.match(r'^([a-zA-Z0-9_.-]+)\s*([><=!~]+)\s*([\d.]+)', line)
                    if match:
                        deps[match.group(1)] = match.group(2) + match.group(3)
                    else:
                        # 没有版本号
                        pkg = re.split(r'[><=!~;\s]', line)[0].strip()
                        if pkg:
                            deps[pkg] = "*"
            except Exception:
                pass

        # pyproject.toml (简化解析)
        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text()
                in_deps = False
                for line in content.splitlines():
                    line = line.strip()
                    if line.startswith("[") and "dependencies" in line.lower():
                        in_deps = True
                        continue
                    if in_deps and line.startswith("["):
                        in_deps = False
                        continue
                    if in_deps:
                        match = re.match(r'"([^"]+)"', line)
                        if match:
                            deps[match.group(1)] = "*"
            except Exception:
                pass

        return deps

    def _parse_node_deps(self, root: Path) -> dict:
        """解析 Node.js 依赖"""
        deps = {}
        pkg_json = root / "package.json"
        if pkg_json.exists():
            try:
                data = json.loads(pkg_json.read_text())
                for key in ("dependencies", "devDependencies", "peerDependencies"):
                    if key in data:
                        for pkg, ver in data[key].items():
                            deps[pkg] = ver
            except (json.JSONDecodeError, KeyError):
                pass
        return deps

    def _parse_go_deps(self, root: Path) -> dict:
        """解析 Go 依赖 (go.mod)"""
        deps = {}
        go_mod = root / "go.mod"
        if go_mod.exists():
            try:
                in_require = False
                for line in go_mod.read_text().splitlines():
                    line = line.strip()
                    if line.startswith("require ("):
                        in_require = True
                        continue
                    if in_require:
                        if line == ")":
                            in_require = False
                            continue
                        parts = line.split()
                        if len(parts) >= 2:
                            deps[parts[0]] = parts[1]
                    elif line.startswith("require "):
                        parts = line.split()
                        if len(parts) >= 3:
                            deps[parts[1]] = parts[2]
            except Exception:
                pass
        return deps

    def _parse_rust_deps(self, root: Path) -> dict:
        """解析 Rust 依赖 (Cargo.toml)"""
        deps = {}
        cargo = root / "Cargo.toml"
        if cargo.exists():
            try:
                content = cargo.read_text()
                in_deps = False
                for line in content.splitlines():
                    line = line.strip()
                    if line == "[dependencies]" or line.startswith("[dependencies."):
                        in_deps = True
                        continue
                    if in_deps and line.startswith("[") and line != "[dependencies]":
                        in_deps = False
                        continue
                    if in_deps and "=" in line and not line.startswith("#"):
                        parts = line.split("=", 1)
                        pkg = parts[0].strip().strip('"')
                        ver = parts[1].strip().strip('"')
                        deps[pkg] = ver
            except Exception:
                pass
        return deps

    def _extract_keywords(self, text: str) -> list[str]:
        """从文本中提取搜索关键词"""
        # 提取英文标识符和中文词
        keywords = []

        # 英文标识符: 驼峰/下划线/点分隔
        identifiers = re.findall(r'[a-zA-Z_][a-zA-Z0-9_.]*[a-zA-Z0-9_]', text)
        keywords.extend(identifiers)

        # 中文连续字符
        chinese = re.findall(r'[\u4e00-\u9fff]{2,}', text)
        keywords.extend(chinese)

        # 去重，优先长词
        seen = set()
        unique = []
        for kw in sorted(keywords, key=len, reverse=True):
            kw_lower = kw.lower()
            if kw_lower not in seen and len(kw) >= 2:
                seen.add(kw_lower)
                unique.append(kw)
                if len(unique) >= 10:
                    break

        # 过滤太泛的通用词
        stopwords = {"the", "and", "for", "from", "with", "that", "this", "what",
                     "import", "def", "class", "return", "self", "文件", "代码",
                     "项目", "什么", "如何", "一个", "怎么"}
        return [k for k in unique if k.lower() not in stopwords]

    def _searchable_extensions(self) -> set[str]:
        """可搜索的源文件扩展名"""
        exts = set()
        for sig in LANGUAGE_SIGNATURES.values():
            exts.update(sig["extensions"])
        exts.update({".json", ".yaml", ".yml", ".toml", ".md", ".cfg", ".ini", ".env"})
        return exts

    def _grep(self, pattern: str, root: Path, extensions: set[str],
              limit: int = 20) -> list[dict]:
        """执行 grep 搜索（优先 ripgrep）"""
        results = []

        # 构建文件过滤
        globs = []
        for ext in extensions:
            # extensions like '.py' — strip leading dot for rg -g glob
            clean_ext = ext.lstrip(".")
            globs.extend(["-g", f"*.{clean_ext}"])

        try:
            # 尝试 ripgrep
            cmd = ["rg", "--no-heading", "-n", "--no-messages",
                   "-e", pattern, str(root)] + globs
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=15
            )
            output = proc.stdout.strip()
            if output:
                for line in output.split("\n")[:limit]:
                    parts = line.split(":", 2)
                    if len(parts) >= 3:
                        fpath = parts[0]
                        try:
                            lineno = int(parts[1])
                        except ValueError:
                            continue
                        content = parts[2]
                        results.append({
                            "file": str(Path(fpath).relative_to(root)),
                            "line": lineno,
                            "content": content,
                        })
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # 回退到 grep
        if not results:
            try:
                clean_exts = [e.lstrip(".") for e in extensions]
                # grep: each extension needs its own --include=
                cmd = ["grep", "-rn"]
                for e in clean_exts:
                    cmd.extend(["--include", f"*.{e}"])
                cmd.extend([pattern, str(root)])
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=15
                )
                output = proc.stdout.strip()
                if output:
                    for line in output.split("\n")[:limit]:
                        parts = line.split(":", 2)
                        if len(parts) >= 3:
                            fpath = parts[0]
                            try:
                                lineno = int(parts[1])
                            except ValueError:
                                continue
                            content = parts[2]
                            results.append({
                                "file": str(Path(fpath).relative_to(root)),
                                "line": lineno,
                                "content": content,
                            })
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        return results

    def _tree_snapshot(self, root: Path, max_depth: int = 3) -> list[str]:
        """生成简要目录树（仅目录结构）"""
        lines = []

        def _walk(d: Path, prefix: str = "", depth: int = 0):
            if depth > max_depth:
                return
            entries = sorted(
                [e for e in d.iterdir()
                 if e.name not in IGNORE_DIRS and not e.name.startswith(".")],
                key=lambda x: (not x.is_dir(), x.name.lower()),
            )
            for i, entry in enumerate(entries):
                is_last = i == len(entries) - 1
                connector = "└── " if is_last else "├── "
                if entry.is_dir():
                    lines.append(f"{prefix}{connector}{entry.name}/")
                    ext_prefix = "    " if is_last else "│   "
                    _walk(entry, prefix + ext_prefix, depth + 1)
                elif entry.suffix.lower() in self._searchable_extensions():
                    lines.append(f"{prefix}{connector}{entry.name}")

        _walk(root)
        return lines


# ═══════════════════════════════════════════
# 便捷函数 (供 tool_registry 注册)
# ═══════════════════════════════════════════

_global_manager: Optional[ProjectManager] = None


def get_manager(root: str = None) -> ProjectManager:
    """获取全局 ProjectManager 实例"""
    global _global_manager
    if _global_manager is None or root:
        _global_manager = ProjectManager(root or ".")
    return _global_manager


def scan_project(path: str = ".") -> str:
    """工具函数：扫描项目并返回摘要"""
    pm = ProjectManager(path)
    return pm.summary()


def project_context(question: str, path: str = ".") -> str:
    """工具函数：检索项目上下文"""
    pm = ProjectManager(path)
    return pm.get_context(question)


def search_code(pattern: str, path: str = ".") -> str:
    """工具函数：搜索项目代码"""
    pm = ProjectManager(path)
    return pm.search_files(pattern)


def project_detail(path: str = ".") -> str:
    """工具函数：返回完整项目JSON"""
    pm = ProjectManager(path)
    return json.dumps(pm.scan_project(), ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════
# 自测入口
# ═══════════════════════════════════════════
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    pm = ProjectManager(".")
    result = pm.scan_project(".")
    print(f"项目: {result.get('name', '?')}")
    print(f"文件数: {result.get('files', 0)}")
    print(f"语言: {result.get('languages', {})}")
    print(f"框架: {result.get('frameworks', [])}")
    print(f"依赖: {list(result.get('dependencies', {}).keys())}")
    print()

    # 测试上下文检索
    ctx = pm.get_context("memory module")
    print(ctx[:500])
